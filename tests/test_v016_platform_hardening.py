from __future__ import annotations

from pathlib import Path
import os
import platform
import pytest

from living_assistant.platform_hardening import (
    SleepResumeMonitor,
    create_portable_link,
    platform_status,
    probe_link_capability,
)
from living_assistant.watchers import WatchRegistry
from living_assistant.workspace import Workspace


def test_portable_link_prefers_symlink(tmp_path):
    target=tmp_path/'target'; target.mkdir()
    link=tmp_path/'link'
    result=create_portable_link(target,link)
    assert result['ok'] is True
    assert result['method'] in {'symlink','junction'}
    assert link.exists()


def test_file_link_falls_back_to_hardlink(monkeypatch,tmp_path):
    target=tmp_path/'a.txt'; target.write_text('hello',encoding='utf-8')
    link=tmp_path/'b.txt'
    monkeypatch.setattr(os,'symlink',lambda *a,**k: (_ for _ in ()).throw(PermissionError('no symlink privilege')))
    result=create_portable_link(target,link)
    assert result['method']=='hardlink'
    assert link.read_text(encoding='utf-8')=='hello'
    target.write_text('changed',encoding='utf-8')
    assert link.read_text(encoding='utf-8')=='changed'


def test_windows_directory_uses_junction_fallback(monkeypatch,tmp_path):
    import living_assistant.platform_hardening as ph
    target=tmp_path/'target'; target.mkdir()
    link=tmp_path/'link'
    monkeypatch.setattr(os,'symlink',lambda *a,**k: (_ for _ in ()).throw(PermissionError('1314 privilege not held')))
    monkeypatch.setattr(platform,'system',lambda: 'Windows')
    def fake_junction(target_p,link_p):
        link_p.mkdir()
    monkeypatch.setattr(ph,'_create_windows_junction',fake_junction)
    result=create_portable_link(target,link)
    assert result['method']=='junction'
    assert link.is_dir()


def test_copy_fallback_is_never_implicit(monkeypatch,tmp_path):
    target=tmp_path/'a.txt'; target.write_text('x',encoding='utf-8')
    link=tmp_path/'b.txt'
    monkeypatch.setattr(os,'symlink',lambda *a,**k: (_ for _ in ()).throw(PermissionError('no')))
    monkeypatch.setattr(os,'link',lambda *a,**k: (_ for _ in ()).throw(OSError('no hardlink')))
    with pytest.raises(OSError):
        create_portable_link(target,link)
    result=create_portable_link(target,link,allow_copy_fallback=True)
    assert result['method']=='copy'
    assert 'does not preserve link semantics' in result['warning']


def test_sleep_resume_monitor_detects_large_gap():
    m=SleepResumeMonitor(60)
    m.last_wall=100.0; m.last_mono=50.0
    normal=m.observe(110.0,60.0)
    assert normal['resumed'] is False
    resumed=m.observe(250.0,70.0)
    assert resumed['resumed'] is True
    assert resumed['wall_gap_seconds']==140.0


def test_watch_rebaseline_suppresses_resume_churn(tmp_path):
    watched=tmp_path/'watched'; watched.mkdir()
    f=watched/'a.txt'; f.write_text('one',encoding='utf-8')
    reg=WatchRegistry(tmp_path/'watches.json')
    reg.add('x',str(watched))
    assert reg.poll()==[]
    f.write_text('two',encoding='utf-8')
    state=reg.rebaseline()
    assert state['refreshed']==1
    assert reg.poll()==[]


def test_workspace_listing_survives_broken_symlink(tmp_path):
    root=tmp_path/'root'; root.mkdir()
    link=root/'broken'
    try:
        link.symlink_to(root/'missing')
    except (OSError,NotImplementedError):
        pytest.skip('symlinks unavailable on this test host')
    ws=Workspace([root])
    rows=ws.list('.')
    item=next(x for x in rows if x['name']=='broken')
    assert item['is_symlink'] is True
    assert item['size'] is None


def test_link_probe_leaves_no_persistent_artifact(tmp_path):
    before={x.name for x in tmp_path.iterdir()}
    result=probe_link_capability(tmp_path)
    after={x.name for x in tmp_path.iterdir()}
    assert isinstance(result['supported'],bool)
    assert before==after


def test_platform_status_is_serializable():
    data=platform_status().to_dict()
    assert data['os']
    assert isinstance(data['elevated'],bool)
    assert 'user_service_backend' in data


def test_service_installers_use_current_safe_patterns():
    root=Path(__file__).resolve().parents[1]
    mac=(root/'scripts/install_daemon_macos.sh').read_text(encoding='utf-8')
    linux=(root/'scripts/install_daemon_linux.sh').read_text(encoding='utf-8')
    win=(root/'scripts/install_daemon_windows.ps1').read_text(encoding='utf-8')
    assert 'launchctl bootstrap' in mac and 'plistlib' in mac
    assert 'TimeoutStopSec=20' in linux and 'systemctl --user' in linux
    assert 'RunLevel Limited' in win and 'StartWhenAvailable' in win


def test_windows_bootstrap_does_not_require_activation_script():
    root=Path(__file__).resolve().parents[1]
    text=(root/'scripts/bootstrap.ps1').read_text(encoding='utf-8')
    assert 'Activate.ps1' not in text
    assert 'Scripts\\python.exe' in text


def test_windows_private_createjunction_argument_order(monkeypatch,tmp_path):
    import sys, types
    import living_assistant.platform_hardening as ph
    target=tmp_path/'target'; target.mkdir(); link=tmp_path/'link'
    calls=[]
    fake=types.SimpleNamespace(CreateJunction=lambda src,dst: calls.append((src,dst)))
    monkeypatch.setitem(sys.modules,'_winapi',fake)
    monkeypatch.setattr(platform,'system',lambda: 'Windows')
    ph._create_windows_junction(target,link)
    assert calls==[(str(target.resolve()),str(link))]


def test_api_exposes_platform_status(monkeypatch):
    from fastapi.testclient import TestClient
    import living_assistant.api as api
    class Fake:
        def to_dict(self):
            return {'os':'TestOS','symlink_supported':False}
    monkeypatch.setattr(api,'platform_status',lambda:Fake())
    monkeypatch.setenv('ASSISTANT_API_TOKEN','test-token')
    client=TestClient(api.app,headers={'Authorization':'Bearer test-token'})
    r=client.get('/platform/status')
    assert r.status_code==200
    assert r.json()['os']=='TestOS'


def test_api_health_reports_current_package_version():
    from fastapi.testclient import TestClient
    from living_assistant.api import app
    from living_assistant import __version__
    r=TestClient(app).get('/health')
    assert r.status_code==200
    assert r.json()['version']==__version__


def test_daemon_resume_revalidates_ephemeral_state(tmp_path,monkeypatch):
    import living_assistant.daemon as d
    from living_assistant.memory import MemoryStore

    class Proc:
        def list(self): return []
    class Watch:
        def __init__(self): self.rebased=0
        def rebaseline(self): self.rebased+=1; return {'refreshed':1,'missing':[]}
        def poll(self,**kwargs): return []
    class Notify:
        def flush(self,**kwargs): return []
        def send(self,*a,**k): return {'ok':True}
        def is_quiet(self): return False
    class Routine:
        def process(self,*a,**k): return []
    class Models:
        def __init__(self): self.synced=0
        def sync_running_models(self): self.synced+=1; return []
    watch=Watch(); models=Models()
    ns=d.NervousSystem(
        {'daemon':{'poll_seconds':15,'alert_on_new_listening_port':False,'watch_files':False,'resume_gap_seconds':60},
         'routines':{'enabled':False},'security_guardian':{'enabled':False},'security_sensors':{'enabled':False}},
        MemoryStore(tmp_path/'m.sqlite3'),processes=Proc(),watches=watch,notifier=Notify(),routines=Routine(),model_manager=models,
    )
    ns.power_monitor.observe=lambda:{'resumed':True,'wall_gap_seconds':120.0,'monotonic_gap_seconds':5.0,'suspend_drift_seconds':115.0}
    monkeypatch.setattr(ns,'_ports',lambda:set())
    events=ns.tick()
    resume=next(x for x in events if x['kind']=='system_resume_detected')
    assert resume['watch_rebaseline']['refreshed']==1
    assert watch.rebased==1
    assert models.synced==1



def test_tree_walker_does_not_descend_link_like_directory(monkeypatch,tmp_path):
    import living_assistant.platform_hardening as ph
    root=tmp_path/'root'; root.mkdir()
    normal=root/'normal'; normal.mkdir(); (normal/'ok.txt').write_text('ok')
    boundary=root/'junction'; boundary.mkdir(); (boundary/'secret.txt').write_text('secret')
    original=ph.is_link_like
    monkeypatch.setattr(ph,'is_link_like',lambda p: Path(p).name=='junction' or original(p))
    paths=[x.relative_to(root).as_posix() for x in ph.iter_tree_without_link_traversal(root,True)]
    assert 'junction' in paths
    assert 'junction/secret.txt' not in paths
    assert 'normal/ok.txt' in paths


def test_integrity_snapshot_does_not_follow_directory_symlink(tmp_path):
    from living_assistant.security_guardian import SecurityGuardian
    root=tmp_path/'root'; root.mkdir()
    outside=tmp_path/'outside'; outside.mkdir(); (outside/'secret.txt').write_text('secret')
    link=root/'linked-dir'
    try:
        link.symlink_to(outside,target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip('directory symlink unavailable')
    g=SecurityGuardian({'security_guardian':{}},db_path=tmp_path/'g.sqlite3')
    snap=g._snapshot_path(root,True,[],100,20)
    assert 'linked-dir' in snap['items']
    assert all('secret.txt' not in key for key in snap['items'])
