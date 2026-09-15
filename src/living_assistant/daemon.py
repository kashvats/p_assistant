from __future__ import annotations
import time
import psutil, httpx
from .memory import MemoryStore
from .tools.security import audit_local
from .tools.shell import ProcessRegistry
from .watchers import WatchRegistry
from .notifications import Notifier
from .routines import RoutineRegistry

class NervousSystem:
    """Low-resource deterministic event loop. It does not keep an LLM loaded."""
    def __init__(self, config: dict, memory: MemoryStore, processes: ProcessRegistry | None = None,
                 watches: WatchRegistry | None = None, notifier: Notifier | None = None,
                 routines: RoutineRegistry | None = None, orchestrator=None, model_manager=None,
                 briefings=None, sessions=None):
        self.config=config; self.cfg=config.get('daemon',{}); self.memory=memory
        self.processes=processes or ProcessRegistry(); self.watches=watches or WatchRegistry()
        self.notifier=notifier or Notifier(); self.routines=routines or RoutineRegistry()
        self.orchestrator=orchestrator; self.model_manager=model_manager; self.briefings=briefings; self.sessions=sessions
        self.last_ports=set(); self.previous_running={}; self.health_failures={}; self.restart_exhausted_notified=set()
        self.last_maintenance=0.0

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
                try: ok=httpx.get(item['health_url'],timeout=2.5,follow_redirects=True).status_code<500
                except Exception: ok=False
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
        events=[]; vm=psutil.virtual_memory(); cpu=psutil.cpu_percent(interval=0.15)
        self.notifier.flush(max_items=int(self.cfg.get('notification_flush_per_tick',5)))
        if vm.percent>=float(self.cfg.get('high_memory_percent',88)): events.append({'kind':'high_memory','percent':vm.percent})
        if cpu>=float(self.cfg.get('high_cpu_percent',92)): events.append({'kind':'high_cpu','percent':cpu})
        if self.cfg.get('alert_on_new_listening_port',True):
            now_ports=self._ports()
            if self.last_ports:
                for port in sorted(now_ports-self.last_ports): events.append({'kind':'new_listening_port','local':port})
            self.last_ports=now_ports
        events.extend(self._process_events()); events.extend(self._todo_events())
        if self.cfg.get('watch_files',True): events.extend(self.watches.poll(max_events_per_watch=int(self.cfg.get('max_watch_events_per_tick',25))))

        if self.briefings is not None:
            events.extend(self.briefings.process_due())

        routine_cfg=self.config.get('routines',{})
        if bool(routine_cfg.get('enabled',True)):
            events.extend(self.routines.process(list(events),self.memory,self.notifier,orchestrator=self.orchestrator,
                                                allow_model_wake=bool(routine_cfg.get('allow_model_wake',False)) and not self.notifier.is_quiet(),model_manager=self.model_manager))

        todo_notified=set()
        for e in events:
            self.memory.add_event(e['kind'],e)
            if e['kind'] in {'project_process_crashed','project_process_restarted','project_restart_exhausted','project_health_failed','todo_due','new_listening_port'}:
                result=self.notifier.send('Living Assistant',self._event_message(e))
                if e['kind']=='todo_due' and result.get('ok'):
                    todo_notified.add(int(e['todo_id']))
        for todo_id in todo_notified: self.memory.mark_todo_notified(todo_id)

        now=time.time()
        if self.sessions is not None and now-self.last_maintenance>=3600:
            pruned=self.sessions.prune()
            if pruned: self.memory.add_event('session_history_pruned',{'count':pruned})
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
        return kind or 'Event'

    def run_forever(self):
        poll=max(5,int(self.cfg.get('poll_seconds',15)))
        print(f'Nervous system active (poll={poll}s). No model is kept loaded. Ctrl+C to stop.')
        while True:
            for e in self.tick(): print('EVENT',e)
            time.sleep(poll)
