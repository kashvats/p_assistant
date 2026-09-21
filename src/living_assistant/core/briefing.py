from __future__ import annotations
import copy
import datetime as dt

class BriefingEngine:
    def __init__(self, config: dict, state, memory, calendar, projects, processes, approvals, notifier, guardian=None, experiences=None):
        self.config=config.get('briefings',{})
        self.state=state; self.memory=memory; self.calendar=calendar; self.projects=projects
        self.processes=processes; self.approvals=approvals; self.notifier=notifier; self.guardian=guardian; self.experiences=experiences
        self._cache: dict[str, tuple[dt.datetime, dict]] = {}

    def _day_bounds(self, now: dt.datetime):
        start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        return start,start+dt.timedelta(days=1)

    def build(self,kind: str='morning',now: dt.datetime | None=None) -> dict:
        now=now or self.state.now()
        cache_seconds=max(0,int(self.config.get('cache_seconds',300)))
        cached=self._cache.get(kind)
        if cached is not None and cache_seconds>0:
            cached_at,cached_item=cached
            age=(now-cached_at).total_seconds()
            if cached_at.date()==now.date() and 0 <= age <= cache_seconds:
                return copy.deepcopy(cached_item)
        start,end=self._day_bounds(now)
        todos=self.memory.list_todos(include_done=False)
        due=[]; overdue=[]
        for t in todos:
            if not t.get('due_at'): continue
            try:
                d=dt.datetime.fromisoformat(t['due_at'])
                if d.tzinfo is None and now.tzinfo: d=d.replace(tzinfo=now.tzinfo)
                if d < start: overdue.append(t)
                elif d < end: due.append(t)
            except Exception: pass
        events=self.calendar.list(start.isoformat(timespec='seconds'),end.isoformat(timespec='seconds'),limit=50)
        running=[p for p in self.processes.list() if p.get('running')]
        expected=[p for p in self.processes.list() if p.get('desired_state')=='running']
        broken=[p for p in expected if not p.get('running')]
        pending=self.approvals.list(status='pending',limit=50)
        recent=self.memory.list_events(limit=30)
        important=[e for e in recent if e.get('kind') in {'project_process_crashed','project_restart_exhausted','project_health_failed','new_listening_port'}][:5]
        security_findings=[]
        if self.guardian is not None:
            try: security_findings=list(self.guardian.findings('open',limit=20))
            except Exception: security_findings=[]
        experience_stats={}
        if self.experiences is not None:
            try: experience_stats=dict(self.experiences.stats() or {})
            except Exception: experience_stats={}
        lines=[]
        heading='Morning briefing' if kind=='morning' else 'Evening briefing'
        lines.append(f'{heading} — {now.strftime("%A, %d %B %Y")}')
        if events:
            lines.append('Calendar: '+ '; '.join(f"{e['start_at'][11:16]} {e['title']}" for e in events[:6]))
        else: lines.append('Calendar: no local events scheduled today.')
        if overdue: lines.append(f'Overdue todos: {len(overdue)} — '+ '; '.join(x['title'] for x in overdue[:4]))
        if due: lines.append(f'Due today: {len(due)} — '+ '; '.join(x['title'] for x in due[:4]))
        if not due and not overdue: lines.append('Todos: nothing dated for today.')
        lines.append(f'Projects: {len(running)} managed processes running' + (f', {len(broken)} expected processes down.' if broken else '.'))
        if pending: lines.append(f'Approvals waiting: {len(pending)}.')
        if important: lines.append('Recent attention: '+ '; '.join(e['kind'] for e in important))
        if security_findings:
            sev={}
            for finding in security_findings:
                level=str(finding.get('severity') or 'unknown').lower(); sev[level]=sev.get(level,0)+1
            severity_text=', '.join(f'{k}={v}' for k,v in sorted(sev.items(), key=lambda x: {'critical':0,'high':1,'medium':2,'low':3}.get(x[0],4)))
            titles='; '.join(str(x.get('title') or x.get('kind') or 'finding')[:120] for x in security_findings[:3])
            lines.append(f'Security: {len(security_findings)} open finding(s)' + (f' ({severity_text})' if severity_text else '') + (f' — {titles}' if titles else ''))
        elif self.guardian is not None:
            lines.append('Security: no open findings.')
        if experience_stats:
            active=int((experience_stats.get('lessons_by_status') or {}).get('active',0) or 0)
            trusted=int(experience_stats.get('trusted_lessons',0) or 0)
            episodes=int(experience_stats.get('episodes',0) or 0)
            lines.append(f'Experience: {trusted} trusted lesson(s), {active} active lesson(s), {episodes} retained episode(s).')
        if kind=='evening':
            completed=sum(1 for t in self.memory.list_todos(include_done=True) if t.get('done'))
            lines.append(f'Local todo total completed: {completed}.')
        text='\n'.join(lines)
        item={'kind':kind,'generated_at':now.isoformat(timespec='seconds'),'text':text,'calendar':events,'due':due,'overdue':overdue,'pending_approvals':len(pending),'running_processes':len(running),'broken_processes':len(broken),'security_open_findings':len(security_findings),'experience_stats':experience_stats}
        self._cache[kind]=(now,copy.deepcopy(item))
        return item

    @staticmethod
    def _time_due(now: dt.datetime, hhmm: str) -> bool:
        try: h,m=[int(x) for x in hhmm.split(':',1)]
        except Exception: return False
        return (now.hour,now.minute)>=(h,m)

    def process_due(self,now: dt.datetime | None=None) -> list[dict]:
        if not bool(self.config.get('enabled',True)): return []
        now=now or self.state.now(); today=str(now.date()); emitted=[]
        morning_time=str(self.config.get('morning_time','08:30'))
        evening_time=str(self.config.get('evening_time','20:30'))
        # If the daemon starts late in the day, emit only the evening briefing rather than
        # sending a stale morning briefing immediately before it.
        candidates=[]
        if self._time_due(now,evening_time): candidates=[('evening',evening_time)]
        elif self._time_due(now,morning_time): candidates=[('morning',morning_time)]
        for kind,_ in candidates:
            if self.state.briefing_last(kind)==today: continue
            item=self.build(kind,now)
            if bool(self.config.get('notify',True)):
                self.notifier.send('Living Assistant',item['text'])
            self.state.mark_briefing(kind,today)
            emitted.append({'kind':'briefing_generated','briefing':kind,'text':item['text']})
        return emitted
