from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.system.notifications import Notifier


def test_notifier_plays_approval_sound_only_when_not_quiet(tmp_path, monkeypatch):
    note=Notifier(quiet_provider=lambda:False, queue_path=tmp_path/'q.json')
    monkeypatch.setattr(note,'_send_now',lambda title,message:{'ok':True,'backend':'test'})
    sounds=[]
    monkeypatch.setattr(note,'_play_sound',lambda kind:sounds.append(kind) or {'ok':True,'backend':'test-sound'})
    result=note.send('Approval','Need input',sound='approval')
    assert sounds==['approval']
    assert result['sound']['backend']=='test-sound'

    quiet=Notifier(quiet_provider=lambda:True, queue_path=tmp_path/'qq.json')
    qsounds=[]
    monkeypatch.setattr(quiet,'_play_sound',lambda kind:qsounds.append(kind) or {'ok':True})
    result=quiet.send('Approval','Need input',sound='approval')
    assert result['queued'] is True
    assert qsounds==[]


def test_pending_approval_sounds_once_for_new_gate(tmp_path):
    class Note:
        def __init__(self): self.calls=[]
        def send(self,title,message,**kwargs): self.calls.append((title,message,kwargs)); return {'ok':True}
    note=Note(); store=ApprovalStore(tmp_path/'a.sqlite3')
    manager=ApprovalManager(interactive=False,store=store,notifier=note)
    first=manager.request('delete file','destructive','WRITE')
    second=manager.request('delete file','destructive','WRITE')
    assert first['pending'] is True and second['pending'] is True
    assert len(note.calls)==1
    assert note.calls[0][2]['sound']=='approval'


def test_preapproved_retry_does_not_sound_again(tmp_path):
    class Note:
        def __init__(self): self.calls=[]
        def send(self,title,message,**kwargs): self.calls.append((title,message,kwargs)); return {'ok':True}
    note=Note(); store=ApprovalStore(tmp_path/'a.sqlite3')
    manager=ApprovalManager(interactive=False,store=store,notifier=note)
    pending=manager.request('run','reason','EXECUTE')
    store.resolve(pending['approval_id'],True)
    allowed=manager.request('run','reason','EXECUTE')
    assert allowed['allowed'] is True
    assert len(note.calls)==1


def test_sound_can_be_disabled(tmp_path, monkeypatch):
    note=Notifier(queue_path=tmp_path/'q.json', approval_sound_enabled=False)
    monkeypatch.setattr(note,'_send_now',lambda title,message:{'ok':True})
    result=note.send('Approval','x',sound='approval')
    assert result['sound']['suppressed'] is True
