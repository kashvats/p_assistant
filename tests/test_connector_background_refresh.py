import time

from living_assistant.connectors import ConnectorManager, ConnectorRegistry
from living_assistant.connector_credentials import CredentialStore
from living_assistant.daemon import NervousSystem
from living_assistant.memory import MemoryStore


class Approval:
    def request(self, *args, **kwargs):
        return {'allowed': True}


class Processes:
    def list(self): return []


class Watches:
    def poll(self, **kwargs): return []
    def rebaseline(self): return {'refreshed': 0, 'missing': []}


class Note:
    def __init__(self): self.sent=[]
    def flush(self, **kwargs): return {'ok': True}
    def send(self, title, message): self.sent.append((title, message)); return {'ok': True}
    def is_quiet(self): return False


def test_manager_proactively_refreshes_only_enabled_expiring_google_and_microsoft(tmp_path, monkeypatch):
    registry = ConnectorRegistry(tmp_path / 'connectors.json')
    registry.add('google-expiring', 'mail', 'google', ['mail.read'], env_prefix='GE')
    registry.add('ms-future', 'mail', 'microsoft', ['mail.read'], env_prefix='MF')
    registry.add('google-disabled', 'mail', 'google', ['mail.read'], env_prefix='GD', enabled=False)
    registry.add('github-expiring', 'developer', 'github', ['pr.read'], env_prefix='GH')
    manager = ConnectorManager(registry, Approval(), CredentialStore(use_keyring=False))
    now = time.time()

    bundles = {
        'google-expiring': {'refresh_token': 'r1', 'expires_at': now + 30},
        'ms-future': {'refresh_token': 'r2', 'expires_at': now + 3600},
        'google-disabled': {'refresh_token': 'r3', 'expires_at': now + 30},
        'github-expiring': {'refresh_token': 'r4', 'expires_at': now + 30},
    }
    monkeypatch.setattr(manager.credentials, 'load_bundle', lambda connector: bundles.get(connector['name'], {}))
    refreshed=[]
    monkeypatch.setattr(manager.oauth, 'refresh', lambda connector: refreshed.append(connector['name']) or 'new-token')

    result = manager.refresh_expiring_oauth_tokens(refresh_window_seconds=300)
    assert refreshed == ['google-expiring']
    assert result == [{'connector': 'google-expiring', 'ok': True, 'provider': 'google'}]


def test_daemon_runs_background_refresh_on_interval_and_surfaces_failure(tmp_path):
    class ConnectorManager:
        def __init__(self): self.calls=0
        def refresh_expiring_oauth_tokens(self, **kwargs):
            self.calls += 1
            return [{'connector':'work-mail','ok':False,'error':'refresh failed'}]

    connectors=ConnectorManager(); note=Note()
    ns=NervousSystem(
        {
            'daemon': {'alert_on_new_listening_port': False, 'watch_files': False},
            'routines': {'enabled': False},
            'security_guardian': {'enabled': False},
            'security_sensors': {'enabled': False},
            'connectors': {'enabled': True, 'refresh_interval_seconds': 60, 'refresh_window_seconds': 300},
        },
        MemoryStore(tmp_path/'db.sqlite3'), Processes(), Watches(), note, connector_manager=connectors,
    )
    ns.power_monitor.observe=lambda:{'resumed':False}
    first=ns.tick()
    assert connectors.calls == 1
    event=next(e for e in first if e['kind']=='connector_oauth_refresh_failed')
    assert event['connector']=='work-mail'
    assert note.sent and 'work-mail' in note.sent[-1][1]

    ns.tick()
    assert connectors.calls == 1
