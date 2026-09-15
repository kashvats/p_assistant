import datetime as dt
from living_assistant.routines import RoutineRegistry

class Memory:
    def __init__(self): self.todos=[]
    def add_todo(self,title,due_at=None): self.todos.append(title); return len(self.todos)
class Notifier:
    def __init__(self): self.items=[]
    def send(self,t,m): self.items.append(m); return {'ok':True}

def ts(y,m,d,h,mi): return dt.datetime(y,m,d,h,mi).timestamp()

def test_daily_clock_routine_once_per_day(tmp_path):
    r=RoutineRegistry(tmp_path/'r.json'); n=Notifier(); mem=Memory()
    r.add('morning',{'type':'daily','time':'09:00'},{'type':'notify','message':'go'})
    assert r.process([],mem,n,now=ts(2026,9,15,8,59))==[]
    assert len(r.process([],mem,n,now=ts(2026,9,15,9,1)))==1
    assert r.process([],mem,n,now=ts(2026,9,15,10,0))==[]
    assert len(r.process([],mem,n,now=ts(2026,9,16,9,1)))==1

def test_weekly_clock_routine_days(tmp_path):
    r=RoutineRegistry(tmp_path/'r.json'); n=Notifier(); mem=Memory()
    r.add('weekly',{'type':'weekly','days':['mon','wed'],'time':'18:00'},{'type':'notify','message':'weekly'})
    # 2026-09-15 is Tuesday; 2026-09-16 Wednesday.
    assert r.process([],mem,n,now=ts(2026,9,15,18,10))==[]
    assert len(r.process([],mem,n,now=ts(2026,9,16,18,10)))==1
