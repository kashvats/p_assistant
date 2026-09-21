from living_assistant.routines import RoutineRegistry

class Memory:
    def __init__(self): self.todos=[]
    def add_todo(self,title,due_at=None): self.todos.append((title,due_at)); return len(self.todos)
class Notifier:
    def __init__(self): self.items=[]
    def send(self,title,message): self.items.append((title,message)); return True


def test_interval_routine_runs_once_inside_window(tmp_path):
    r=RoutineRegistry(tmp_path/'routines.json'); m=Memory(); n=Notifier()
    r.add('ping',{'type':'interval','seconds':60},{'type':'notify','message':'hello'})
    first=r.process([],m,n,now=1000)
    second=r.process([],m,n,now=1020)
    assert first and first[0]['routine']=='ping'
    assert second == []
    assert n.items[-1][1]=='hello'


def test_event_routine_and_prompt_gate(tmp_path):
    r=RoutineRegistry(tmp_path/'routines.json'); m=Memory(); n=Notifier()
    r.add('crash-note',{'type':'event','kind':'project_process_crashed'},{'type':'todo','title':'Inspect crash'})
    out=r.process([{'kind':'project_process_crashed'}],m,n,now=1000)
    assert out[0]['todo_id']==1
    r.add('prompt',{'type':'interval','seconds':30},{'type':'assistant_prompt','prompt':'summarize'})
    out=r.process([],m,n,allow_model_wake=False,now=2000)
    assert out[0]['skipped'] is True
    assert any('prompt skipped' in message.lower() for _title,message in n.items)
    prompt=[x for x in out if x['routine']=='prompt'][0]
    assert prompt['skipped'] is True
