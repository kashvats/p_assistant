from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest
from fastapi.testclient import TestClient

from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.connector_credentials import CredentialStore
from living_assistant.connectors import ConnectorManager, ConnectorRegistry
from living_assistant.desktop_intelligence import DesktopController
from living_assistant.improvements import ImprovementEngine, ImprovementStore
from living_assistant.security_utils import redact_secrets
from living_assistant.tools.database import build_database_tools
from living_assistant.tools.gittools import build_git_tools
from living_assistant.tools.shell import ProcessRegistry, build_shell_tools
from living_assistant.workspace import Workspace


def _handlers(tools):
    return {tool.name: tool.handler for tool in tools}


def _git(cwd: Path, *args: str):
    p = subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def _manager(tmp_path: Path, interactive: bool = False):
    return ApprovalManager(interactive=interactive, store=ApprovalStore(tmp_path / 'approvals.sqlite3'))


def test_git_rejects_parent_repository_outside_workspace(tmp_path):
    repo = tmp_path / 'repo'; allowed = repo / 'allowed'; allowed.mkdir(parents=True)
    _git(repo, 'init'); _git(repo, 'config', 'user.email', 'test@example.com'); _git(repo, 'config', 'user.name', 'Test')
    (repo / 'outside.txt').write_text('old', encoding='utf-8')
    (allowed / 'inside.txt').write_text('inside', encoding='utf-8')
    _git(repo, 'add', '.'); _git(repo, 'commit', '-m', 'base')
    (repo / 'outside.txt').write_text('SENTINEL_OUTSIDE_SECRET', encoding='utf-8')

    tools = _handlers(build_git_tools(Workspace([allowed]), _manager(tmp_path)))
    result = tools['git_diff']('.')
    assert result['ok'] is False and result.get('blocked') is True
    assert 'SENTINEL_OUTSIDE_SECRET' not in str(result)


def test_git_sensitive_diff_requires_approval_and_redacts_provider_tokens(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    _git(repo, 'init'); _git(repo, 'config', 'user.email', 'test@example.com'); _git(repo, 'config', 'user.name', 'Test')
    env = repo / '.env'; env.write_text('API_KEY=old\n', encoding='utf-8')
    _git(repo, 'add', '.env'); _git(repo, 'commit', '-m', 'base')
    env.write_text('API_KEY=ghp_abcdefghijklmnopqrstuvwxyz123456\n', encoding='utf-8')

    approvals = _manager(tmp_path)
    tools = _handlers(build_git_tools(Workspace([repo]), approvals))
    first = tools['git_diff']('.')
    assert first.get('approval_required') is True and first.get('sensitive') is True
    assert 'abcdefghijklmnopqrstuvwxyz' not in str(first)
    approvals.store.resolve(first['approval_id'], True)
    second = tools['git_diff']('.')
    assert second['ok'] is True and second.get('sensitive') is True
    assert 'ghp_abcdefghijklmnopqrstuvwxyz123456' not in second['stdout']
    assert 'REDACTED' in second['stdout']


def test_api_auth_fails_closed_and_generated_token_works(tmp_path, monkeypatch):
    import living_assistant.api as api
    import living_assistant.api_auth as api_auth

    monkeypatch.delenv('ASSISTANT_API_TOKEN', raising=False)
    monkeypatch.setattr(api_auth, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(api, 'platform_status', lambda: SimpleNamespace(to_dict=lambda: {'os': 'Test'}))

    client = TestClient(api.app)
    denied = client.get('/platform/status')
    assert denied.status_code == 401
    token = (tmp_path / 'api_token').read_text(encoding='utf-8').strip()
    allowed = client.get('/platform/status', headers={'Authorization': f'Bearer {token}'})
    assert allowed.status_code == 200 and allowed.json()['os'] == 'Test'


@pytest.mark.skipif(os.name == 'nt', reason='POSIX process-group regression test')
def test_shell_timeout_kills_descendants(tmp_path):
    root = tmp_path / 'ws'; root.mkdir()
    approvals = _manager(tmp_path)
    registry = ProcessRegistry(tmp_path / 'processes.json')
    tools = _handlers(build_shell_tools(
        Workspace([root]), approvals,
        {'policy': {'require_execute_approval': False, 'command_timeout_seconds': 1}},
        registry,
    ))
    code = (
        "import subprocess,time,pathlib; "
        "p=subprocess.Popen(['sleep','30']); "
        "pathlib.Path('child.pid').write_text(str(p.pid)); "
        "time.sleep(30)"
    )
    result = tools['run_command'](f'python -c "{code}"', '.', 1)
    assert result.get('timeout') is True and result.get('terminated_process_tree') is True
    pid = int((root / 'child.pid').read_text())
    deadline = time.time() + 3
    alive = True
    while time.time() < deadline:
        try:
            proc = psutil.Process(pid)
            alive = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.Error:
            alive = False
        if not alive:
            break
        time.sleep(0.05)
    assert alive is False


def test_self_improvement_refuses_sensitive_targets(tmp_path):
    root = tmp_path / 'ws'; root.mkdir(); (root / '.env').write_text('TOKEN=secret\n')
    engine = ImprovementEngine(Workspace([root]), _manager(tmp_path), ImprovementStore(tmp_path / 'improvements.sqlite3'))
    result = engine.propose('.env', 'TOKEN=new-secret\n', 'rotate', 'test')
    assert result['ok'] is False and result.get('sensitive') is True
    assert engine.store.list(status=None) == []


def test_connector_settings_reject_secret_values_even_under_benign_keys(tmp_path):
    registry = ConnectorRegistry(tmp_path / 'connectors.json')
    with pytest.raises(ValueError, match='credential|secret'):
        registry.add('gh', 'developer', 'github', ['pr.read'], settings={'note': 'ghp_abcdefghijklmnopqrstuvwxyz123456'})


def test_device_oauth_does_not_return_raw_device_code(tmp_path, monkeypatch):
    registry = ConnectorRegistry(tmp_path / 'connectors.json')
    registry.add('gh', 'developer', 'github', ['pr.read'], settings={'client_id': 'public-client-id'})
    manager = ConnectorManager(registry, _manager(tmp_path), CredentialStore(use_keyring=False))
    monkeypatch.setattr(manager.oauth, 'github_begin_device', lambda c, scopes: {
        'device_code': 'RAW_DEVICE_CODE_SHOULD_STAY_INTERNAL', 'user_code': 'ABCD-EFGH',
        'verification_uri': 'https://github.com/login/device', 'expires_in': 900, 'interval': 5,
    })
    seen = {}
    monkeypatch.setattr(manager.oauth, 'github_poll_device', lambda c, d: seen.setdefault('device', d) or {'ok': True})
    start = manager.authorize('gh')
    assert start['ok'] is True and 'transaction_id' in start
    assert 'RAW_DEVICE_CODE_SHOULD_STAY_INTERNAL' not in str(start)
    finish = manager.finish_device_authorize('gh', start['transaction_id'])
    assert finish
    assert seen['device']['device_code'] == 'RAW_DEVICE_CODE_SHOULD_STAY_INTERNAL'
    again = manager.finish_device_authorize('gh', start['transaction_id'])
    assert again['ok'] is False


def test_desktop_window_titles_are_opt_in_and_approval_gated(tmp_path, monkeypatch):
    root = tmp_path / 'ws'; root.mkdir()
    approvals = _manager(tmp_path)
    controller = DesktopController(Workspace([root]), approvals, {'desktop': {}})
    controller.system = 'linux'
    monkeypatch.setattr(controller, '_linux_windows', lambda: [{'title': 'Secret Customer - Invoice', 'app': 'browser', 'pid': 123}])
    safe = controller.windows()
    assert safe['ok'] is True and 'title' not in safe['windows'][0]
    sensitive = controller.windows(include_titles=True)
    assert sensitive.get('approval_required') is True
    assert 'Secret Customer' not in str(sensitive)


def test_database_alias_policy_blocks_unknown_tables_and_redacts_columns(tmp_path, monkeypatch):
    import living_assistant.tools.database as db
    monkeypatch.setattr(db, '_dsn', lambda alias: 'postgresql://example')
    monkeypatch.setattr(db, '_sql_query', lambda dsn, sql, limit: {
        'columns': ['id', 'email', 'password_hash'],
        'rows': [[1, 'a@example.com', 'hash-secret']], 'truncated': False,
    })
    config = {
        'policy': {'max_db_rows': 20},
        'databases': {'require_alias_policy': True, 'aliases': {
            'prod': {'allowed_tables': ['users'], 'sensitive_columns': ['password_hash']}
        }},
    }
    tools = _handlers(build_database_tools(config, _manager(tmp_path)))
    blocked = tools['db_query']('prod', 'SELECT * FROM payments', 10)
    assert blocked.get('blocked') is True
    ok = tools['db_query']('prod', 'SELECT id,email,password_hash FROM users', 10)
    assert ok['ok'] is True
    assert ok['rows'][0][2].startswith('[REDACTED')


def test_redaction_catches_provider_tokens_without_secret_key_name():
    secret = 'ghp_abcdefghijklmnopqrstuvwxyz123456'
    result = redact_secrets(f'neutral text contains {secret}')
    assert secret not in result and 'REDACTED' in result


def test_browser_dns_pin_reuses_single_validated_resolution(tmp_path, monkeypatch):
    import living_assistant.browser as browser_mod
    root = tmp_path / 'ws'; root.mkdir()
    controller = browser_mod.BrowserController(Workspace([root]), _manager(tmp_path))
    calls = []

    def fake_resolve(url):
        calls.append(url)
        if len(calls) == 1:
            return 'public', None, ('203.0.113.10', '203.0.113.11')
        # A second lookup would model a DNS-rebinding answer.
        return 'private', 'Hostname resolves to a non-public address.', ('127.0.0.1',)

    monkeypatch.setattr(browser_mod, 'resolve_url_target', fake_resolve)
    auth = controller._authorize_url('https://example.com/path', 'Open')
    assert auth['ok'] is True
    args = controller._resolver_args(auth['pinned_hosts'])
    assert calls == ['https://example.com/path']
    assert args == ['--host-resolver-rules=MAP example.com 203.0.113.10']
    assert '127.0.0.1' not in str(args)


def test_strict_browser_route_guard_does_not_reresolve_dns(monkeypatch):
    import living_assistant.browser as browser_mod

    def should_not_resolve(*args, **kwargs):
        raise AssertionError('strict pinned route guard must not perform DNS classification')

    monkeypatch.setattr(browser_mod, 'url_network_scope', should_not_resolve)

    class Context:
        handler = None
        def route(self, pattern, handler):
            self.handler = handler

    class Request:
        def __init__(self, url): self.url = url

    class Route:
        def __init__(self, url): self.request = Request(url); self.action = None
        def continue_(self): self.action = 'continue'; return self.action
        def abort(self): self.action = 'abort'; return self.action

    ctx = Context()
    browser_mod.BrowserController._install_route_guard(ctx, set(), {'example.com'})
    allowed = Route('https://example.com/app.js'); ctx.handler(allowed)
    blocked = Route('https://127.0.0.1/admin'); ctx.handler(blocked)
    assert allowed.action == 'continue'
    assert blocked.action == 'abort'


def test_browser_fixed_public_dependency_rejects_private_dns(tmp_path, monkeypatch):
    import living_assistant.browser as browser_mod
    root = tmp_path / 'ws'; root.mkdir()
    controller = browser_mod.BrowserController(Workspace([root]), _manager(tmp_path))
    monkeypatch.setattr(
        browser_mod,
        'resolve_url_target',
        lambda url: ('private', 'Hostname resolves to a non-public address.', ('10.0.0.7',)),
    )
    result = controller._authorize_extra_host('cdn.example.com', 'Search dependency', allow_private=False)
    assert result['ok'] is False and result.get('blocked') is True
    assert 'private/local' in result['error']
