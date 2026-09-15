from __future__ import annotations
from living_assistant.orchestrator import Orchestrator
from living_assistant.tools.base import Tool
from living_assistant.experience import ExperienceEngine

class FakeProvider:
    def __init__(self):
        self.i=0; self.systems=[]
    def chat(self,model,messages,tools=None,keep_alive=45,options=None):
        self.systems.append(messages[0]['content'])
        seq=[
            {'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'try_command','arguments':{'mode':'bad'}}}]}},
            {'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'try_command','arguments':{'mode':'good'}}}]}},
            {'message':{'role':'assistant','content':'done','tool_calls':[]}},
        ]
        out=seq[self.i%3]; self.i+=1; return out

class FakeMM:
    def __init__(self): self.provider=FakeProvider(); self.active=None
    def activate(self,model): self.active=model
    def sleep(self): self.active=None

class DummySpecialists:
    def delegate(self,*a,**k): return {'ok':True}


def test_orchestrator_auto_learns_repeated_recovery_and_retrieves_it(tmp_path):
    exp=ExperienceEngine(tmp_path/'e.sqlite3',{'experience':{'auto_promote_repeats':2,'min_inject_confidence':.55}})
    def handler(mode: str):
        return {'ok': mode=='good','error':'bad mode' if mode!='good' else None}
    tool=Tool('try_command','test tool',{'type':'object','properties':{'mode':{'type':'string'}},'required':['mode']},handler)
    mm=FakeMM()
    orch=Orchestrator(mm,'fake',[tool],DummySpecialists(),max_steps=4,experiences=exp)
    assert orch.run('Start my demo app',context='Project path: /tmp/Demo')=='done'
    assert exp.list('active')==[]
    assert orch.run('Start my demo app',context='Project path: /tmp/Demo')=='done'
    active=exp.list('active')
    assert len(active)==1 and active[0]['kind']=='recovery_candidate'
    # Third run should receive the promoted experience in its system prompt before any tool is called.
    assert orch.run('Start my demo app',context='Project path: /tmp/Demo')=='done'
    assert any('[LOCAL EXPERIENCE MEMORY' in x and 'good' in x for x in mm.provider.systems[-3:])
