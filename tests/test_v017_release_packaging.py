from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import zipfile
import pytest

from living_assistant.release_manager import (
    ReleaseManager, _snapshot_data_tree, _restore_data_tree, ensure_data_schema,
)


def _fake_installed_version(mgr: ReleaseManager, version: str):
    env=mgr.layout.versions/version/'venv'
    organism=env/('Scripts/organism.exe' if os.name=='nt' else 'bin/organism')
    py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    organism.parent.mkdir(parents=True,exist_ok=True)
    organism.write_text('x'); py.write_text('x')
    if os.name!='nt': organism.chmod(0o755); py.chmod(0o755)
    state=mgr.state(); state['installations'][version]={'version':version,'path':str(env.parent)}; mgr._write_state(state)


def _minimal_wheel(path: Path, name='living-assistant', version='0.17.0'):
    dist=f"{name.replace('-','_')}-{version}.dist-info"
    with zipfile.ZipFile(path,'w') as z:
        z.writestr(f'{dist}/METADATA',f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n')
        z.writestr(f'{dist}/WHEEL','Wheel-Version: 1.0\nTag: py3-none-any\n')
    return path


def test_release_status_is_read_only(tmp_path):
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data')
    out=mgr.status()
    assert out['current_version'] is None
    assert out['data_schema']==0
    assert not (tmp_path/'data'/'data_schema.json').exists()


def test_data_schema_migration_is_idempotent(tmp_path):
    data=tmp_path/'data'
    first=ensure_data_schema(data); second=ensure_data_schema(data)
    assert first['applied']==[1]
    assert second['applied']==[]
    assert second['schema']==1


def test_backup_uses_sqlite_snapshot_and_excludes_browser_cache(tmp_path):
    data=tmp_path/'data'; data.mkdir()
    db=data/'assistant.sqlite3'
    c=sqlite3.connect(db); c.execute('create table x(v text)'); c.execute('insert into x values (?)',('ok',)); c.commit(); c.close()
    (data/'personal_state.json').write_text('{"ok":true}')
    bp=data/'browser_profiles'/'x'; bp.mkdir(parents=True); (bp/'cookie').write_text('secret')
    archive=tmp_path/'backup.zip'
    result=_snapshot_data_tree(data,archive)
    assert result['file_count']>=2
    with zipfile.ZipFile(archive) as z:
        names=set(z.namelist())
        assert 'assistant.sqlite3' in names
        assert 'personal_state.json' in names
        assert all(not n.startswith('browser_profiles/') for n in names)
    restored=tmp_path/'restored'; _restore_data_tree(archive,restored)
    c=sqlite3.connect(restored/'assistant.sqlite3'); assert c.execute('select v from x').fetchone()[0]=='ok'; c.close()


def test_foreign_wheel_is_rejected(tmp_path):
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data')
    wheel=_minimal_wheel(tmp_path/'other.whl',name='other-package')
    with pytest.raises(ValueError,match='not the Living Assistant'):
        mgr._inspect_wheel_version(wheel)


def test_checksum_mismatch_rejected_before_install(tmp_path):
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data')
    wheel=_minimal_wheel(tmp_path/'living.whl')
    with pytest.raises(RuntimeError,match='SHA-256'):
        mgr.install_wheel(wheel,with_dependencies=False,expected_sha256='00'*32)
    assert not list(mgr.layout.versions.iterdir())


def test_rollback_swaps_stable_shim(tmp_path,monkeypatch):
    import living_assistant.release_manager as rm
    monkeypatch.setattr(rm,'restart_user_service_if_installed',lambda:{'ok':True,'supported':False})
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data')
    _fake_installed_version(mgr,'0.16.0'); _fake_installed_version(mgr,'0.17.0')
    state=mgr.state(); state['current_version']='0.17.0'; state['previous_version']='0.16.0'; mgr._write_state(state)
    mgr._write_shims('0.17.0')
    result=mgr.rollback()
    assert result['to']=='0.16.0'
    shim=(mgr.layout.bin/('organism.cmd' if os.name=='nt' else 'organism')).read_text()
    assert '0.16.0' in shim
    assert mgr.state()['previous_version']=='0.17.0'


def test_remove_active_version_is_refused(tmp_path):
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data'); _fake_installed_version(mgr,'0.17.0')
    state=mgr.state(); state['current_version']='0.17.0'; mgr._write_state(state)
    with pytest.raises(RuntimeError,match='active version'): mgr.remove_version('0.17.0')


def test_uninstall_purge_requires_confirmation_before_removing_runtime(tmp_path):
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data'); _fake_installed_version(mgr,'0.17.0')
    marker=mgr.layout.versions/'keep.txt'; marker.write_text('keep')
    with pytest.raises(RuntimeError,match='explicit confirmation'):
        mgr.uninstall_runtime(purge_data=True,confirm_purge=False)
    assert marker.exists()


def test_release_scripts_use_versioned_runtime_shims():
    root=Path(__file__).resolve().parents[1]
    linux=(root/'scripts/install_daemon_linux.sh').read_text()
    mac=(root/'scripts/install_daemon_macos.sh').read_text()
    win=(root/'scripts/install_daemon_windows.ps1').read_text()
    assert 'LivingAssistantRuntime/bin/living-assistant-daemon' in linux
    assert 'LivingAssistantRuntime/bin/living-assistant-daemon' in mac
    assert 'LivingAssistant\\Runtime\\bin\\living-assistant-daemon.cmd' in win
    for name in ['install_release_linux.sh','update_release_linux.sh','uninstall_release_linux.sh','install_release_macos.sh','install_release_windows.ps1']:
        assert (root/'scripts'/name).exists()


def test_api_health_reports_v017():
    from fastapi.testclient import TestClient
    from living_assistant.api import app
    r=TestClient(app).get('/health')
    assert r.status_code==200
    assert r.json()['version']=='0.17.0'

def test_release_verify_checks_active_runtime(tmp_path,monkeypatch):
    import living_assistant.release_manager as rm
    mgr=ReleaseManager(tmp_path/'runtime',tmp_path/'data')
    _fake_installed_version(mgr,'0.17.0')
    state=mgr.state(); state['current_version']='0.17.0'; mgr._write_state(state); mgr._write_shims('0.17.0')
    # Avoid executing the fake python file; emulate the installed package self-check.
    class P:
        returncode=0; stdout='0.17.0\n'; stderr=''
    monkeypatch.setattr(rm.subprocess,'run',lambda *a,**k:P())
    out=mgr.verify()
    assert out['ok'] is True
    assert any(x['name']=='stable-shim' and x['ok'] for x in out['checks'])
