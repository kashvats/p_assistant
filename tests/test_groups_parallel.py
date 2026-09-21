from __future__ import annotations
import threading
import time

from living_assistant.groups import ProjectGroupController, ProjectGroupRegistry


class Projects:
    def __init__(self):
        self.items={name:{'name':name,'path':f'/tmp/{name}','start_command':f'python {name}.py'} for name in ('db','api','web')}
    def get(self,name): return self.items.get(name)


class Approval:
    def request(self,*args,**kwargs): return {'allowed':True}


class Processes:
    def __init__(self, fail=None):
        self.fail=fail; self.active=0; self.max_active=0; self.lock=threading.Lock(); self.started=[]
    def start(self,command,path,**kwargs):
        name=kwargs['project']
        with self.lock:
            self.active+=1; self.max_active=max(self.max_active,self.active); self.started.append(name)
        time.sleep(0.04)
        with self.lock: self.active-=1
        return {'ok':name!=self.fail,'id':name}
    def list(self): return []


def test_group_dependency_plan_builds_topological_stages(tmp_path):
    groups=ProjectGroupRegistry(tmp_path/'groups.json')
    groups.add('stack',['db','api','web'],dependencies={'api':['db'],'web':['api']},parallel_start=True)
    ctl=ProjectGroupController(groups,Projects(),Processes(),Approval())
    plan=ctl.plan('stack')
    assert plan['ok'] is True
    assert [[x['project'] for x in stage] for stage in plan['stages']]==[['db'],['api'],['web']]


def test_group_parallel_start_runs_independent_projects_concurrently(tmp_path):
    groups=ProjectGroupRegistry(tmp_path/'groups.json')
    groups.add('stack',['db','api','web'],dependencies={'web':['db','api']},parallel_start=True,max_parallel=2)
    proc=Processes(); ctl=ProjectGroupController(groups,Projects(),proc,Approval())
    result=ctl.start('stack')
    assert result['ok'] is True
    assert proc.max_active==2
    assert proc.started[-1]=='web'


def test_group_dependency_failure_skips_downstream_projects(tmp_path):
    groups=ProjectGroupRegistry(tmp_path/'groups.json')
    groups.add('stack',['db','api','web'],dependencies={'api':['db'],'web':['api']},parallel_start=True)
    proc=Processes(fail='api'); ctl=ProjectGroupController(groups,Projects(),proc,Approval())
    result=ctl.start('stack')
    assert result['ok'] is False
    assert 'web' not in proc.started
    assert any(x.get('project')=='web' and x.get('skipped') for x in result['results'])


def test_group_dependency_cycle_is_rejected_by_plan(tmp_path):
    groups=ProjectGroupRegistry(tmp_path/'groups.json')
    groups.add('stack',['db','api'],dependencies={'db':['api'],'api':['db']})
    ctl=ProjectGroupController(groups,Projects(),Processes(),Approval())
    result=ctl.plan('stack')
    assert result['ok'] is False
    assert 'cycle' in result['error'].lower()

def test_group_health_tracks_expected_running_members(tmp_path):
    groups=ProjectGroupRegistry(tmp_path/'groups.json')
    groups.add('stack',['db','api'])
    class HealthProcesses(Processes):
        def list(self):
            return [
                {'id':'db1','project':'db','desired_state':'running','running':True},
                {'id':'api1','project':'api','desired_state':'running','running':False},
            ]
    ctl=ProjectGroupController(groups,Projects(),HealthProcesses(),Approval())
    assert ctl.health('stack')['monitored'] is False
    groups.set_desired_state('stack','running')
    status=ctl.health('stack')
    assert status['monitored'] is True and status['healthy'] is False
    assert {p['project']:p['running'] for p in status['projects']}=={'db':True,'api':False}
