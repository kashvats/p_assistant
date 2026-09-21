import living_assistant.daemon as daemon_mod
from living_assistant.daemon import NervousSystem
from living_assistant.memory import MemoryStore


class Processes:
    def list(self): return []
class Watches:
    def poll(self, **kwargs): return []
    def rebaseline(self): return {'refreshed':0,'missing':[]}
class Note:
    def __init__(self): self.sent=[]
    def flush(self, **kwargs): return {'ok':True}
    def send(self, title, message): self.sent.append((title,message)); return {'ok':True}
    def is_quiet(self): return False


def test_run_forever_recovers_from_tick_exception_and_records_report(tmp_path, monkeypatch):
    note=Note(); memory=MemoryStore(tmp_path/'db.sqlite3')
    ns=NervousSystem({'daemon':{'poll_seconds':5,'crash_backoff_seconds':1}},memory,Processes(),Watches(),note)
    calls={'tick':0}
    def tick():
        calls['tick'] += 1
        if calls['tick']==1: raise RuntimeError('provider token=super-secret-value failed')
        return []
    ns.tick=tick

    class Event:
        def __init__(self): self.waits=0; self.stopped=False
        def is_set(self): return self.stopped
        def set(self): self.stopped=True
        def wait(self, seconds):
            self.waits += 1
            if self.waits >= 2: self.stopped=True
            return self.stopped
    monkeypatch.setattr(daemon_mod.threading,'Event',Event)
    monkeypatch.setattr(daemon_mod.signal,'signal',lambda *a,**k:None)
    monkeypatch.setattr(daemon_mod.signal,'getsignal',lambda *a,**k:None)
    ns.run_forever()

    assert calls['tick']==2
    events=memory.list_events(limit=20)
    crash=next(e for e in events if e['kind']=='daemon_tick_error')
    text=str(crash)
    assert 'super-secret-value' not in text
    assert note.sent and 'recovered' in note.sent[0][1].lower()


def test_installers_have_process_level_restart_policy():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    linux=(root/'scripts/install_daemon_linux.sh').read_text()
    mac=(root/'scripts/install_daemon_macos.sh').read_text()
    win=(root/'scripts/install_daemon_windows.ps1').read_text()
    assert 'Restart=on-failure' in linux
    assert "'KeepAlive':{'SuccessfulExit':False}" in mac
    assert '-RestartCount 3' in win and '-RestartInterval' in win
