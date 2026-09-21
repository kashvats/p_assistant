from pathlib import Path
import yaml

from living_assistant.core.config import load_config
from living_assistant.system.config_reload import ConfigReloader
from living_assistant.system.daemon import NervousSystem
from living_assistant.core.memory import MemoryStore


def seeded(tmp_path):
    src=Path('/mnt/data/config_repo/src/living_assistant/default_config.yaml')
    path=tmp_path/'assistant.yaml'
    path.write_text(src.read_text())
    return path


def test_reloader_applies_safe_sections_and_reports_structural_restart(tmp_path):
    path=seeded(tmp_path)
    cfg=load_config(path)
    original_profile_model=cfg['profiles']['lite']['models']['orchestrator']
    applied=[]
    reloader=ConfigReloader(cfg,path,lambda changes:applied.extend(changes))

    edited=yaml.safe_load(path.read_text())
    edited['notifications']['approval_sound']=False
    edited['daemon']['high_cpu_percent']=77
    edited['profiles']['lite']['models']['orchestrator']='changed:latest'
    path.write_text(yaml.safe_dump(edited,sort_keys=False))

    events=reloader.poll()
    assert cfg['notifications']['approval_sound'] is False
    assert cfg['daemon']['high_cpu_percent']==77
    assert cfg['profiles']['lite']['models']['orchestrator']==original_profile_model
    assert 'notifications' in applied and 'daemon.high_cpu_percent' in applied
    restart=next(e for e in events if e['kind']=='config_restart_required')
    assert 'profiles' in restart['settings']
    assert reloader.poll()==[]


def test_invalid_yaml_fails_once_without_mutating_live_config(tmp_path):
    path=seeded(tmp_path)
    cfg=load_config(path); before=cfg['notifications']['approval_sound']
    reloader=ConfigReloader(cfg,path)
    path.write_text('notifications: [broken\n')
    first=reloader.poll()
    assert first and first[0]['kind']=='config_reload_failed'
    assert cfg['notifications']['approval_sound']==before
    assert reloader.poll()==[]


def test_connector_enabled_requires_restart_but_refresh_window_is_live(tmp_path):
    path=seeded(tmp_path); cfg=load_config(path); reloader=ConfigReloader(cfg,path)
    edited=yaml.safe_load(path.read_text())
    edited['connectors']['enabled']=False
    edited['connectors']['refresh_window_seconds']=999
    path.write_text(yaml.safe_dump(edited,sort_keys=False))
    events=reloader.poll()
    assert cfg['connectors']['enabled'] is True
    assert cfg['connectors']['refresh_window_seconds']==999
    restart=next(e for e in events if e['kind']=='config_restart_required')
    assert 'connectors.enabled' in restart['settings']


class Processes:
    def list(self): return []
class Watches:
    def poll(self,**kwargs): return []
    def rebaseline(self): return {'refreshed':0,'missing':[]}
class Note:
    def __init__(self): self.approval_sound_enabled=True; self.sent=[]
    def flush(self,**kwargs): return {'ok':True}
    def send(self,title,message,*args,**kwargs): self.sent.append((title,message)); return {'ok':True}
    def is_quiet(self): return False


def test_daemon_tick_applies_live_notification_config(tmp_path, monkeypatch):
    path=seeded(tmp_path); cfg=load_config(path)
    import living_assistant.system.daemon as daemon_module
    monkeypatch.setattr(daemon_module,'active_config_path',lambda:path)
    note=Note()
    ns=NervousSystem(cfg,MemoryStore(tmp_path/'db.sqlite3'),Processes(),Watches(),note)
    ns.power_monitor.observe=lambda:{'resumed':False}
    # Avoid unrelated port/security behavior.
    ns.config['daemon']['alert_on_new_listening_port']=False
    ns.config['daemon']['watch_files']=False
    ns.config['routines']['enabled']=False
    ns.config['security_guardian']['enabled']=False
    ns.config['security_sensors']['enabled']=False
    ns.config['connectors']['enabled']=False

    edited=yaml.safe_load(path.read_text())
    edited['notifications']['approval_sound']=False
    edited['daemon']['high_cpu_percent']=1000
    path.write_text(yaml.safe_dump(edited,sort_keys=False))
    events=ns.tick()
    assert note.approval_sound_enabled is False
    assert any(e['kind']=='config_reloaded' for e in events)


def test_mobile_and_peer_runtime_objects_receive_reloaded_cfg(tmp_path):
    path=seeded(tmp_path); cfg=load_config(path)
    class Mobile:
        def __init__(self): self.config=cfg; self.cfg=dict(cfg['mobile_bridge'])
    class Peers:
        def __init__(self): self.config=cfg; self.cfg=dict(cfg['peers']); self.stops=0
        def stop(self): self.stops+=1
    mobile=Mobile(); peers=Peers()
    ns=object.__new__(NervousSystem)
    ns.config=cfg; ns.cfg=cfg['daemon']; ns.notifier=None; ns.mobile_bridge=mobile; ns.peers=peers; ns.briefings=None; ns.guardian=None
    edited=yaml.safe_load(path.read_text())
    edited['mobile_bridge']['enabled']=True
    edited['peers']['enabled']=True
    path.write_text(yaml.safe_dump(edited,sort_keys=False))
    reloader=ConfigReloader(cfg,path,ns._on_config_reload)
    # Reloader was created after write, so make one more revision.
    edited['mobile_bridge']['poll_interval_seconds']=9
    edited['peers']['peer_ttl_seconds']=99
    path.write_text(yaml.safe_dump(edited,sort_keys=False))
    events=reloader.poll()
    assert mobile.cfg['enabled'] is True and mobile.cfg['poll_interval_seconds']==9
    assert peers.cfg['enabled'] is True and peers.cfg['peer_ttl_seconds']==99
    assert peers.stops==1
    assert any(e['kind']=='config_reloaded' for e in events)
