from __future__ import annotations
import time, signal, threading, traceback
import psutil, httpx
from living_assistant.core.memory import MemoryStore
from living_assistant.tools.security import audit_local
from living_assistant.tools.shell import ProcessRegistry
from living_assistant.system.watchers import WatchRegistry
from living_assistant.system.notifications import Notifier
from living_assistant.system.routines import RoutineRegistry
from living_assistant.security.security_utils import is_loopback_http_url
from living_assistant.system.platform_hardening import SleepResumeMonitor
from living_assistant.security.security_utils import redact_secrets
from living_assistant.core.config import active_config_path
from living_assistant.system.config_reload import ConfigReloader

class NervousSystem:
    """Low-resource deterministic event loop. It does not keep an LLM loaded."""
    def __init__(self, config: dict, memory: MemoryStore, processes: ProcessRegistry | None = None,
                 watches: WatchRegistry | None = None, notifier: Notifier | None = None,
                 routines: RoutineRegistry | None = None, orchestrator=None, model_manager=None,
                 briefings=None, sessions=None, guardian=None, security_sensors=None, experiences=None, group_controller=None, connector_manager=None, mobile_bridge=None, peers=None, scheduler=None):
        self.config=config; self.cfg=config.get('daemon',{}); self.memory=memory
        self.processes=processes or ProcessRegistry(); self.watches=watches or WatchRegistry()
        self.notifier=notifier or Notifier(); self.routines=routines or RoutineRegistry()
        self.orchestrator=orchestrator; self.model_manager=model_manager; self.briefings=briefings; self.sessions=sessions; self.guardian=guardian; self.security_sensors=security_sensors; self.experiences=experiences; self.group_controller=group_controller; self.connector_manager=connector_manager; self.mobile_bridge=mobile_bridge; self.peers=peers; self.scheduler=scheduler
        self.last_ports=set(); self.previous_running={}; self.health_failures={}; self.restart_exhausted_notified=set(); self.previous_group_health={}
        self.last_maintenance=0.0; self.last_security_scan=0.0; self.last_security_posture_scan=0.0; self.last_sensor_scan=0.0; self.last_connector_refresh=0.0
        resume_gap=max(float(self.cfg.get('resume_gap_seconds',60)), float(self.cfg.get('poll_seconds',15))*3.0)
        self.power_monitor=SleepResumeMonitor(resume_gap)
        self.config_reloader=ConfigReloader(self.config, active_config_path(), self._on_config_reload)

    def _on_config_reload(self, applied: list[str]) -> None:
        self.cfg=self.config.get('daemon',{})
        if self.notifier is not None and any(x == 'notifications' or x.startswith('notifications.') for x in applied):
            try: self.notifier.approval_sound_enabled=bool(self.config.get('notifications',{}).get('approval_sound',True))
            except Exception: pass
        if self.mobile_bridge is not None and any(x == 'mobile_bridge' or x.startswith('mobile_bridge.') for x in applied):
            try:
                self.mobile_bridge.config=self.config
                self.mobile_bridge.cfg=dict(self.config.get('mobile_bridge',{}) or {})
            except Exception: pass
        if self.peers is not None and any(x == 'peers' or x.startswith('peers.') for x in applied):
            try:
                self.peers.stop()
                self.peers.config=self.config
                self.peers.cfg=dict(self.config.get('peers',{}) or {})
            except Exception: pass
        if self.briefings is not None and any(x == 'briefings' or x.startswith('briefings.') for x in applied):
            try: self.briefings.config=self.config.get('briefings',{})
            except Exception: pass
        if self.guardian is not None and any(x == 'security_guardian' or x.startswith('security_guardian.') for x in applied):
            try:
                self.guardian.config=self.config
                self.guardian.cfg=self.config.get('security_guardian',{})
            except Exception: pass

    def _ports(self):
        audit=audit_local(); return {str(x.get('local')) for x in audit.get('listening_ports',[]) if x.get('local')}

    def _process_events(self):
        events=[]
        for item in self.processes.list():
            key=item['id']; running=bool(item.get('running')); prev=self.previous_running.get(key); self.previous_running[key]=running
            if prev is True and not running and item.get('desired_state')=='running':
                events.append({'kind':'project_process_crashed','process_id':key,'name':item.get('name'),'project':item.get('project')})
            if not running and item.get('desired_state')=='running' and item.get('auto_restart'):
                result=self.processes.restart(key,automatic=True)
                if result.get('ok'):
                    self.previous_running[key]=True; events.append({'kind':'project_process_restarted','process_id':key,'name':item.get('name'),'restart_count':result.get('restart_count')})
                elif 'Maximum automatic restart' in result.get('error','') and key not in self.restart_exhausted_notified:
                    self.restart_exhausted_notified.add(key); events.append({'kind':'project_restart_exhausted','process_id':key,'name':item.get('name'),'error':result.get('error')})
            if running and item.get('health_url'):
                if not is_loopback_http_url(str(item['health_url'])):
                    ok=False
                else:
                    try:
                        with httpx.Client(timeout=2.5, follow_redirects=False, trust_env=False) as client:
                            ok=client.get(item['health_url']).status_code < 500
                    except Exception:
                        ok=False
                if ok: self.health_failures[key]=0
                else:
                    self.health_failures[key]=self.health_failures.get(key,0)+1
                    if self.health_failures[key]==3: events.append({'kind':'project_health_failed','process_id':key,'name':item.get('name'),'health_url':item.get('health_url')})
        return events

    def _todo_events(self):
        events=[]
        for todo in self.memory.due_todos():
            events.append({'kind':'todo_due','todo_id':todo['id'],'title':todo['title'],'due_at':todo['due_at']})
            # Mark as notified after delivery or durable quiet-hours queueing in tick().
        return events

    def tick(self):
        events=[]
        power=self.power_monitor.observe()
        if power.get('resumed'):
            # Resume is a boundary: re-baseline ephemeral state before normal scans
            # so sleep-time changes do not create false port/file/ransomware alerts.
            try:
                self.last_ports=self._ports()
            except Exception:
                self.last_ports=set()
            self.health_failures.clear()
            try:
                watch_state=self.watches.rebaseline()
            except Exception as exc:
                watch_state={'error':str(exc)}
            if self.model_manager is not None:
                try: self.model_manager.sync_running_models()
                except Exception: pass
            if self.scheduler is not None:
                try:
                    recovered = self.scheduler.recover_missed_tasks()
                    if recovered:
                        events.append({'kind':'scheduler_missed_tasks_recovered','recovered':recovered})
                except Exception: pass
            events.append({'kind':'system_resume_detected', **power, 'watch_rebaseline':watch_state})
        try:
            events.extend(self.config_reloader.poll())
        except Exception as exc:
            events.append({'kind':'config_reload_failed','error':redact_secrets(exc,1000)})
        vm=psutil.virtual_memory(); cpu=psutil.cpu_percent(interval=0.15)
        self.notifier.flush(max_items=int(self.cfg.get('notification_flush_per_tick',5)))
        if vm.percent>=float(self.cfg.get('high_memory_percent',88)): events.append({'kind':'high_memory','percent':vm.percent})
        if cpu>=float(self.cfg.get('high_cpu_percent',92)): events.append({'kind':'high_cpu','percent':cpu})
        if self.cfg.get('alert_on_new_listening_port',True):
            now_ports=self._ports()
            if self.last_ports:
                for port in sorted(now_ports-self.last_ports): events.append({'kind':'new_listening_port','local':port})
            self.last_ports=now_ports
        events.extend(self._process_events()); events.extend(self._todo_events())
        if self.group_controller is not None:
            try:
                for status in self.group_controller.health_all():
                    if not status.get('ok') or not status.get('monitored'): continue
                    name=status.get('group'); healthy=bool(status.get('healthy')); previous=self.previous_group_health.get(name)
                    self.previous_group_health[name]=healthy
                    if previous is not False and not healthy:
                        events.append({'kind':'project_group_degraded','group':name,'projects':status.get('projects',[])})
                    elif previous is False and healthy:
                        events.append({'kind':'project_group_recovered','group':name,'projects':status.get('projects',[])})
            except Exception as exc:
                events.append({'kind':'project_group_health_error','error':str(exc)})
        file_events=[]
        if self.cfg.get('watch_files',True):
            file_events=self.watches.poll(max_events_per_watch=int(self.cfg.get('max_watch_events_per_tick',25)))
            events.extend(file_events)
        if self.security_sensors is not None and file_events:
            try:
                burst=self.security_sensors.observe_file_events(file_events)
                if burst.get('score',0)>=60:
                    events.append({'kind':'security_ransomware_like_burst','severity':burst.get('severity','high'),'signals':burst.get('signals',[]),'score':burst.get('score',0)})
            except Exception as exc:
                events.append({'kind':'security_sensor_error','severity':'medium','error':str(exc)})

        if self.briefings is not None:
            events.extend(self.briefings.process_due())

        security_cfg=self.config.get('security_guardian',{})
        now_ts=time.time()
        if self.guardian is not None and bool(security_cfg.get('enabled',True)):
            interval=max(60,int(security_cfg.get('scan_interval_seconds',300)))
            if now_ts-self.last_security_scan>=interval:
                try: events.extend(self.guardian.periodic_scan())
                except Exception as exc: events.append({'kind':'security_guardian_error','error':str(exc)})
                self.last_security_scan=now_ts
            posture_interval=max(300,int(security_cfg.get('posture_interval_seconds',3600)))
            if now_ts-self.last_security_posture_scan>=posture_interval:
                try:
                    posture_scan=self.guardian.posture_scan(record=True)
                    for finding in posture_scan.get('findings',[]):
                        if finding.get('_new'):
                            events.append({'kind':'security_posture_weakened','severity':finding.get('severity','medium'),'finding_id':finding.get('id'),'title':finding.get('title')})
                except Exception as exc: events.append({'kind':'security_guardian_error','error':str(exc)})
                self.last_security_posture_scan=now_ts

        sensor_cfg=self.config.get('security_sensors',{})
        if self.security_sensors is not None and bool(sensor_cfg.get('enabled',True)):
            interval=max(60,int(sensor_cfg.get('scan_interval_seconds',300)))
            if now_ts-self.last_sensor_scan>=interval:
                try: events.extend(self.security_sensors.periodic_scan())
                except Exception as exc: events.append({'kind':'security_sensor_error','severity':'medium','error':str(exc)})
                self.last_sensor_scan=now_ts

        connector_cfg=self.config.get('connectors',{})
        if self.connector_manager is not None and bool(connector_cfg.get('enabled',True)):
            refresh_interval=max(60,int(connector_cfg.get('refresh_interval_seconds',60)))
            if now_ts-self.last_connector_refresh>=refresh_interval:
                try:
                    refresh_results=self.connector_manager.refresh_expiring_oauth_tokens(
                        refresh_window_seconds=int(connector_cfg.get('refresh_window_seconds',300))
                    )
                    for result in refresh_results:
                        if not result.get('ok'):
                            events.append({'kind':'connector_oauth_refresh_failed', **result})
                except Exception as exc:
                    events.append({'kind':'connector_oauth_refresh_failed','error':str(exc)})
                self.last_connector_refresh=now_ts

        if self.mobile_bridge is not None:
            try:
                events.extend(self.mobile_bridge.poll_once())
            except Exception as exc:
                events.append({'kind':'mobile_bridge_error','error':redact_secrets(exc,1000)})

        if self.peers is not None:
            try:
                events.extend(self.peers.poll_events())
            except Exception as exc:
                events.append({'kind':'peer_discovery_error','error':redact_secrets(exc,1000)})

        routine_cfg=self.config.get('routines',{})
        if bool(routine_cfg.get('enabled',True)):
            events.extend(self.routines.process(list(events),self.memory,self.notifier,orchestrator=self.orchestrator,
                                                allow_model_wake=bool(routine_cfg.get('allow_model_wake',False)) and not self.notifier.is_quiet(),model_manager=self.model_manager))

        todo_notified=set()
        for e in events:
            self.memory.add_event(e['kind'],e)
            if e['kind'] in {'project_process_crashed','project_process_restarted','project_restart_exhausted','project_health_failed','project_group_degraded','project_group_recovered','todo_due','new_listening_port','connector_oauth_refresh_failed','mobile_bridge_error','peer_discovery_error','config_reload_failed','config_restart_required','security_baseline_missing','security_new_persistence','security_new_listener','security_integrity_change','security_suspicious_process','security_posture_weakened','security_guardian_error','security_sensor_error','security_correlated_chain','security_new_usb','security_new_browser_extension','security_extension_permissions','security_backup_integrity','security_ransomware_like_burst','security_trusted_binary_changed'}:
                should_notify=True
                if str(e.get('kind','')).startswith('security_'):
                    ranks={'low':1,'medium':2,'high':3,'critical':4}
                    wanted=str(self.config.get('security_guardian',{}).get('notify_min_severity','medium')).lower()
                    severity=str(e.get('severity','medium')).lower()
                    should_notify=ranks.get(severity,2)>=ranks.get(wanted,2)
                result=self.notifier.send('Living Assistant',self._event_message(e)) if should_notify else {'ok':True,'suppressed':True}
                if e['kind']=='todo_due' and result.get('ok'):
                    todo_notified.add(int(e['todo_id']))
        for todo_id in todo_notified: self.memory.mark_todo_notified(todo_id)

        now=time.time()
        if self.sessions is not None and now-self.last_maintenance>=3600:
            pruned=self.sessions.prune()
            if pruned: self.memory.add_event('session_history_pruned',{'count':pruned})
            if self.experiences is not None:
                try:
                    ex=self.experiences.maintenance()
                    if ex.get('episodes_pruned'): self.memory.add_event('experience_episodes_pruned',ex)
                    if ex.get('lessons_demoted') or ex.get('lessons_expired'):
                        self.memory.add_event('experience_confidence_maintenance',ex)
                    # Jev semantic GC: score remaining active lessons for knowledge value.
                    # Replaces brittle timestamp-only logic for stale knowledge retirement.
                    try:
                        from living_assistant.core.typesafe import JevClient
                        jev = JevClient()
                        jev_retired = []
                        for lesson in self.experiences.list(status='active', limit=200):
                            level, conf = jev.score_knowledge_value(lesson)
                            if level == 'Obsolete/Wrong' and conf >= 0.75 and not lesson.get('user_confirmed'):
                                self.experiences.reject(lesson['id'], reason='Jev GC: scored Obsolete/Wrong')
                                jev_retired.append(lesson['id'])
                        if jev_retired:
                            self.memory.add_event('jev_gc_retired', {'count': len(jev_retired), 'ids': jev_retired[:10]})
                    except Exception:
                        pass
                except Exception: pass
            self.last_maintenance=now
        return events

    @staticmethod
    def _event_message(e):
        kind=e.get('kind')
        if kind=='todo_due': return f"Reminder: {e.get('title')}"
        if kind=='new_listening_port': return f"New local listening port: {e.get('local')}"
        if kind=='project_process_crashed': return f"Process crashed: {e.get('name')}"
        if kind=='project_process_restarted': return f"Restarted: {e.get('name')} (attempt {e.get('restart_count')})"
        if kind=='project_restart_exhausted': return f"Auto-restart exhausted for {e.get('name')}"
        if kind=='project_health_failed': return f"Health check failed for {e.get('name')}"
        if kind=='project_group_degraded': return f"Project group degraded: {e.get('group')}"
        if kind=='project_group_recovered': return f"Project group recovered: {e.get('group')}"
        if kind=='connector_oauth_refresh_failed': return f"Connector OAuth refresh failed for {e.get('connector') or 'connector'}: {e.get('error') or 'unknown error'}"
        if kind=='mobile_bridge_error': return f"Mobile bridge error: {e.get('error') or 'unknown error'}"
        if kind=='peer_discovery_error': return f"Peer discovery error: {e.get('error') or 'unknown error'}"
        if kind=='config_reload_failed': return f"Configuration reload failed: {e.get('error') or 'unknown error'}"
        if kind=='config_restart_required': return f"Configuration changed; restart required for: {', '.join(e.get('settings') or [])}"
        if kind=='security_baseline_missing': return f"Security setup needed: initialize the {e.get('baseline')} baseline"
        if kind=='security_new_persistence': return 'Security: new startup/persistence item detected'
        if kind=='security_new_listener':
            x=e.get('listener') or {}; return f"Security: new listener {x.get('ip')}:{x.get('port')} ({x.get('process') or 'unknown process'})"
        if kind=='security_integrity_change': return f"Security: protected files changed in {e.get('baseline') or e.get('path')}"
        if kind=='security_suspicious_process': return f"Security: suspicious process signals for {e.get('name')} (PID {e.get('pid')})"
        if kind=='security_posture_weakened': return f"Security posture: {e.get('title') or 'protection weakened'}"
        if kind=='security_guardian_error': return f"Security guardian error: {e.get('error')}"
        if kind=='security_sensor_error': return f"Security sensor error: {e.get('error')}"
        if kind=='security_correlated_chain': return f"Security: correlated suspicious activity ({', '.join(e.get('signals') or [])})"
        if kind=='security_new_usb': return 'Security: new USB device detected'
        if kind=='security_new_browser_extension': return 'Security: new browser extension detected'
        if kind=='security_extension_permissions': return 'Security: browser extension gained permissions'
        if kind=='security_backup_integrity': return f"Security: backup integrity changed for {e.get('baseline')}"
        if kind=='security_ransomware_like_burst': return 'Security: ransomware-like mass file-change behavior detected'
        if kind=='security_trusted_binary_changed': return f"Security: trusted binary changed: {e.get('path')}"
        if kind=='system_resume_detected': return f"System resumed after ~{e.get('wall_gap_seconds',0)}s; runtime state revalidated"
        return kind or 'Event'

    def run_forever(self):
        poll=max(5,int(self.cfg.get('poll_seconds',15)))
        stop=threading.Event()
        previous={}
        def request_stop(signum=None, frame=None):
            stop.set()
        # SIGTERM matters for systemd/launchd. Signal registration can fail when
        # embedded in a non-main thread, so degrade gracefully there.
        for sig in [getattr(signal,'SIGINT',None), getattr(signal,'SIGTERM',None)]:
            if sig is None: continue
            try:
                previous[sig]=signal.getsignal(sig)
                signal.signal(sig, request_stop)
            except (ValueError, OSError):
                pass
        print(f'Nervous system active (poll={poll}s). No model is kept loaded. Ctrl+C to stop.')
        try:
            while not stop.is_set():
                try:
                    for e in self.tick(): print('EVENT',e)
                except Exception as exc:
                    report=redact_secrets(traceback.format_exc(),4000)
                    payload={'error':redact_secrets(exc,1000),'traceback':report}
                    try: self.memory.add_event('daemon_tick_error',payload)
                    except Exception: pass
                    try: self.notifier.send('Living Assistant',f"Background daemon recovered from an internal error: {payload['error']}")
                    except Exception: pass
                    print('EVENT',{'kind':'daemon_tick_error','error':payload['error']})
                    backoff=max(1,min(int(self.cfg.get('crash_backoff_seconds',5)),60))
                    if stop.wait(backoff): break
                    continue
                poll=max(5,int(self.cfg.get('poll_seconds',15)))
                stop.wait(poll)
        except KeyboardInterrupt:
            stop.set()
        finally:
            try:
                if self.model_manager is not None: self.model_manager.sleep()
            except Exception:
                pass
            try:
                if self.peers is not None: self.peers.stop()
            except Exception:
                pass
            for sig, handler in previous.items():
                try: signal.signal(sig, handler)
                except Exception: pass
