from living_assistant.daemon import NervousSystem
from living_assistant.memory import MemoryStore


class Processes:
    def list(self): return []


class Watches:
    def poll(self, **kwargs): return []
    def rebaseline(self): return {'refreshed':0,'missing':[]}


class Note:
    def flush(self, **kwargs): return {'ok':True}
    def send(self, *args, **kwargs): return {'ok':True}
    def is_quiet(self): return False


class Groups:
    def __init__(self): self.healthy=False
    def health_all(self):
        return [{'ok':True,'group':'stack','monitored':True,'healthy':self.healthy,'projects':[]}]


def test_daemon_emits_group_degraded_once_and_recovery_once(tmp_path):
    groups=Groups()
    ns=NervousSystem(
        {'daemon':{'alert_on_new_listening_port':False,'watch_files':False},'routines':{'enabled':False}},
        MemoryStore(tmp_path/'db.sqlite3'), Processes(), Watches(), Note(), group_controller=groups,
    )
    ns.power_monitor.observe=lambda:{'resumed':False}
    first=ns.tick()
    assert [e['kind'] for e in first].count('project_group_degraded')==1
    second=ns.tick()
    assert not any(e['kind']=='project_group_degraded' for e in second)
    groups.healthy=True
    third=ns.tick()
    assert [e['kind'] for e in third].count('project_group_recovered')==1
    fourth=ns.tick()
    assert not any(e['kind']=='project_group_recovered' for e in fourth)
