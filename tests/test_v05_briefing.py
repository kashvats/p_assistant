import datetime as dt
from living_assistant.briefing import BriefingEngine
from living_assistant.personal_state import PersonalState
from living_assistant.memory import MemoryStore
from living_assistant.calendar_store import CalendarStore

class EmptyProjects:
    def list(self): return {}
class EmptyProcesses:
    def list(self): return []
class EmptyApprovals:
    def list(self,status='pending',limit=50): return []
class Note:
    def __init__(self): self.items=[]
    def send(self,t,m): self.items.append((t,m)); return {'ok':True}


def test_briefing_build_and_schedule_once(tmp_path):
    state=PersonalState(tmp_path/'state.json')
    mem=MemoryStore(tmp_path/'db.sqlite3')
    cal=CalendarStore(tmp_path/'db.sqlite3')
    cal.add('Standup','2026-09-15T10:00:00')
    mem.add_todo('Ship release','2026-09-15T17:00:00')
    note=Note()
    b=BriefingEngine({'briefings':{'enabled':True,'morning_time':'08:30','evening_time':'20:30','notify':True}},state,mem,cal,EmptyProjects(),EmptyProcesses(),EmptyApprovals(),note)
    now=dt.datetime(2026,9,15,9,0)
    out=b.process_due(now)
    assert len(out)==1 and out[0]['briefing']=='morning' and 'Standup' in out[0]['text']
    assert b.process_due(now)==[]


def test_briefing_build_uses_bounded_same_day_cache(tmp_path):
    state=PersonalState(tmp_path/'state.json')
    mem=MemoryStore(tmp_path/'db.sqlite3')
    cal=CalendarStore(tmp_path/'db.sqlite3')
    note=Note()
    b=BriefingEngine({'briefings':{'enabled':True,'cache_seconds':300}},state,mem,cal,EmptyProjects(),EmptyProcesses(),EmptyApprovals(),note)

    now=dt.datetime(2026,9,15,9,0)
    first=b.build('morning',now)
    mem.add_todo('Added after first build','2026-09-15T17:00:00')

    cached=b.build('morning',now+dt.timedelta(seconds=60))
    assert cached['text']==first['text']
    # Returned objects are copies; caller mutation must not poison the cache.
    cached['text']='mutated by caller'
    assert b.build('morning',now+dt.timedelta(seconds=120))['text']==first['text']

    refreshed=b.build('morning',now+dt.timedelta(seconds=301))
    assert 'Added after first build' in refreshed['text']
