from __future__ import annotations
import datetime as dt

class BriefingEngine:
    def __init__(self, config: dict, state, memory, calendar, projects, processes, approvals, notifier):
        self.config=config.get('briefings',{})
        self.state=state; self.memory=memory; self.calendar=calendar; self.projects=projects
        self.processes=processes; self.approvals=approvals; self.notifier=notifier

    def _day_bounds(self, now: dt.datetime):
        start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        return start,start+dt.timedelta(days=1)

    def build(self,kind: str='morning',now: dt.datetime | None=None) -> dict:
        now=now or self.state.now(); start,end=self._day_bounds(now)
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
        if kind=='evening':
            completed=sum(1 for t in self.memory.list_todos(include_done=True) if t.get('done'))
            lines.append(f'Local todo total completed: {completed}.')
        text='\n'.join(lines)
        return {'kind':kind,'generated_at':now.isoformat(timespec='seconds'),'text':text,'calendar':events,'due':due,'overdue':overdue,'pending_approvals':len(pending),'running_processes':len(running),'broken_processes':len(broken)}

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
