from living_assistant.workspace import Workspace
from living_assistant.approval import ApprovalStore, ApprovalManager
from living_assistant.improvements import ImprovementStore, ImprovementEngine


def build(tmp_path):
    ws=Workspace([tmp_path/'workspace'])
    approvals=ApprovalStore(tmp_path/'db.sqlite3')
    manager=ApprovalManager(interactive=False,store=approvals)
    store=ImprovementStore(tmp_path/'imp.sqlite3')
    return ws,approvals,ImprovementEngine(ws,manager,store)


def test_proposal_requires_approval_then_applies(tmp_path):
    ws,approvals,engine=build(tmp_path)
    ws.write_text('a.txt','old\n')
    p=engine.propose('a.txt','new\n','Update a','test change',['pytest'])
    assert p['status']=='pending' and '-old' in p['diff'] and '+new' in p['diff']
    first=engine.apply(p['id'])
    assert first['approval_required'] is True
    approvals.resolve(first['approval_id'],True)
    second=engine.apply(p['id'])
    assert second['ok'] is True
    assert ws.read_text('a.txt')=='new\n'


def test_conflict_and_protected_core(tmp_path):
    ws,approvals,engine=build(tmp_path)
    ws.write_text('x.txt','one')
    p=engine.propose('x.txt','two','change','reason')
    ws.write_text('x.txt','changed elsewhere')
    assert engine.apply(p['id'])['conflict'] is True
    # A user project may legitimately have this basename; basename alone is no longer protected.
    ws.write_text('security_policy.py','x')
    p2=engine.propose('security_policy.py','y','user project file','reason')
    assert engine.apply(p2['id'])['approval_required'] is True


def test_rollback_requires_approval_and_restores(tmp_path):
    ws,approvals,engine=build(tmp_path)
    ws.write_text('a.txt','old')
    p=engine.propose('a.txt','new','change','reason')
    first=engine.apply(p['id']); approvals.resolve(first['approval_id'],True); assert engine.apply(p['id'])['ok']
    rb=engine.rollback(p['id']); assert rb['approval_required'] is True
    approvals.resolve(rb['approval_id'],True)
    assert engine.rollback(p['id'])['ok'] is True
    assert ws.read_text('a.txt')=='old'
