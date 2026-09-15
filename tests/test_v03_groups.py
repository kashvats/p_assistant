from living_assistant.groups import ProjectGroupRegistry, ProjectGroupController
from living_assistant.approval import ApprovalManager, ApprovalStore

class Projects:
    def __init__(self, root): self.root = root
    def get(self, name):
        if name == 'api':
            return {'name':'api','path':str(self.root),'start_command':'python app.py','auto_restart':False,'max_restarts':3,'health_url':None}
        if name == 'web':
            return {'name':'web','path':str(self.root),'start_command':'npm run dev','auto_restart':False,'max_restarts':3,'health_url':None}
        return None

class Processes:
    def list(self): return []
    def stop(self, key): return {'ok':True}


def test_group_plan(tmp_path):
    reg = ProjectGroupRegistry(tmp_path/'groups.json')
    reg.add('stack',['api','web'])
    approvals = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path/'approvals.sqlite3'))
    c = ProjectGroupController(reg, Projects(tmp_path), Processes(), approvals)
    plan = c.plan('stack')
    assert plan['ok']
    assert [x['project'] for x in plan['plan']] == ['api','web']


def test_group_unknown_project(tmp_path):
    reg = ProjectGroupRegistry(tmp_path/'groups.json')
    reg.add('bad',['missing'])
    approvals = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path/'approvals.sqlite3'))
    c = ProjectGroupController(reg, Projects(tmp_path), Processes(), approvals)
    assert not c.plan('bad')['ok']
