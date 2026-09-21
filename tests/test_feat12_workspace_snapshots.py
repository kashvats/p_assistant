from __future__ import annotations

from pathlib import Path
import sys

from living_assistant.core.workspace import Workspace
from living_assistant.system.workspace_snapshots import WorkspaceSnapshotManager
from living_assistant.tools.filesystem import build_filesystem_tools
from living_assistant.tools.projects import ProjectRegistry, build_project_tools
from living_assistant.tools.shell import ProcessRegistry, build_shell_tools


class AllowApproval:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def request(self, action, reason, kind):
        self.calls.append((action, reason, kind))
        return {'allowed': self.allowed, 'id': 'approval-1'}


def _manager(tmp_path: Path):
    root = tmp_path / 'project'
    root.mkdir()
    ws = Workspace([root])
    mgr = WorkspaceSnapshotManager(
        ws,
        root=tmp_path / 'snapshots',
        db_path=tmp_path / 'assistant.sqlite3',
        retention_per_root=10,
    )
    return root, ws, mgr


def test_snapshot_restore_recovers_source_and_preserves_generated_directories(tmp_path):
    root, _ws, mgr = _manager(tmp_path)
    (root / 'src').mkdir()
    (root / 'src' / 'app.py').write_text('VERSION = 1\n', encoding='utf-8')
    (root / 'node_modules').mkdir()
    (root / 'node_modules' / 'cache.txt').write_text('cache-before', encoding='utf-8')

    snap = mgr.create(root, 'before AI change')
    (root / 'src' / 'app.py').write_text('VERSION = 2\n', encoding='utf-8')
    (root / 'src' / 'new.py').write_text('new = True\n', encoding='utf-8')
    (root / 'node_modules' / 'cache.txt').write_text('cache-after', encoding='utf-8')

    restored = mgr.restore(snap['snapshot_id'])
    assert restored['ok'] is True
    assert restored['pre_restore_snapshot_id'] != snap['snapshot_id']
    assert (root / 'src' / 'app.py').read_text() == 'VERSION = 1\n'
    assert not (root / 'src' / 'new.py').exists()
    assert (root / 'node_modules' / 'cache.txt').read_text() == 'cache-after'


def test_snapshot_metadata_never_exposes_archive_contents_or_credentials(tmp_path):
    root, _ws, mgr = _manager(tmp_path)
    secret = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
    (root / '.env').write_text(f'TOKEN={secret}\n', encoding='utf-8')
    snap = mgr.create(root, 'credential-bearing project recovery')

    listed = mgr.list(root)
    assert listed and listed[0]['snapshot_id'] == snap['snapshot_id']
    rendered = repr(listed)
    assert secret not in rendered
    assert 'archive_path' not in rendered

    (root / '.env').write_text('TOKEN=changed\n', encoding='utf-8')
    mgr.restore(snap['snapshot_id'])
    assert secret in (root / '.env').read_text(encoding='utf-8')


def test_ai_write_file_snapshots_immediately_before_mutation(tmp_path):
    root, ws, mgr = _manager(tmp_path)
    target = root / 'settings.py'
    target.write_text('VALUE = 1\n', encoding='utf-8')
    tools = {tool.name: tool for tool in build_filesystem_tools(ws, snapshot_manager=mgr)}

    result = tools['write_file'].handler('settings.py', 'VALUE = 2\n')
    assert result['ok'] is True
    assert result['snapshot_id']
    assert target.read_text() == 'VALUE = 2\n'

    mgr.restore(result['snapshot_id'])
    assert target.read_text() == 'VALUE = 1\n'


def test_ai_shell_command_snapshots_before_possible_workspace_mutation(tmp_path):
    root, ws, mgr = _manager(tmp_path)
    target = root / 'state.txt'
    target.write_text('before', encoding='utf-8')
    registry = ProcessRegistry(tmp_path / 'processes.json')
    tools = {tool.name: tool for tool in build_shell_tools(
        ws,
        AllowApproval(True),
        {'policy': {'require_execute_approval': False, 'command_timeout_seconds': 10}},
        registry,
        snapshot_manager=mgr,
    )}
    command = f'''{sys.executable} -c "from pathlib import Path; Path('state.txt').write_text('after')"'''
    result = tools['run_command'].handler(command, '.', 10)

    assert result['ok'] is True
    assert result['snapshot_id']
    assert target.read_text() == 'after'
    mgr.restore(result['snapshot_id'])
    assert target.read_text() == 'before'


def test_snapshot_failure_blocks_ai_file_mutation(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    ws = Workspace([root])
    target = root / 'large.txt'
    original = 'x' * 1_100_000
    target.write_text(original, encoding='utf-8')
    mgr = WorkspaceSnapshotManager(
        ws,
        root=tmp_path / 'snapshots',
        db_path=tmp_path / 'assistant.sqlite3',
        max_total_bytes=1_000_000,
    )
    tools = {tool.name: tool for tool in build_filesystem_tools(ws, snapshot_manager=mgr)}
    result = tools['write_file'].handler('large.txt', 'replacement')
    assert result['ok'] is False
    assert result['blocked'] is True
    assert target.read_text() == original


def test_project_snapshot_restore_tool_is_approval_gated(tmp_path):
    root, ws, mgr = _manager(tmp_path)
    target = root / 'app.txt'
    target.write_text('old', encoding='utf-8')
    snap = mgr.create(root, 'old state')
    target.write_text('new', encoding='utf-8')
    registry = ProjectRegistry(tmp_path / 'projects.json')

    denied = AllowApproval(False)
    denied_tools = {tool.name: tool for tool in build_project_tools(ws, registry, snapshot_manager=mgr, approval=denied)}
    result = denied_tools['project_snapshot_restore'].handler(snap['snapshot_id'])
    assert result['approval_required'] is True
    assert target.read_text() == 'new'

    allowed = AllowApproval(True)
    allowed_tools = {tool.name: tool for tool in build_project_tools(ws, registry, snapshot_manager=mgr, approval=allowed)}
    result = allowed_tools['project_snapshot_restore'].handler(snap['snapshot_id'])
    assert result['ok'] is True
    assert target.read_text() == 'old'
    assert allowed.calls[0][2] == 'WRITE_WORKSPACE'


def test_deepest_workspace_root_is_snapshotted_for_registered_project(tmp_path):
    workspace_root = tmp_path / 'workspace'
    project_root = workspace_root / 'client-project'
    project_root.mkdir(parents=True)
    ws = Workspace([workspace_root, project_root])
    mgr = WorkspaceSnapshotManager(ws, root=tmp_path / 'snapshots', db_path=tmp_path / 'db.sqlite3')
    assert mgr.project_root_for(project_root / 'src' / 'file.py') == project_root.resolve()


def test_improvement_apply_creates_recoverable_workspace_snapshot(tmp_path):
    from living_assistant.learning.improvements import ImprovementEngine, ImprovementStore

    root, ws, mgr = _manager(tmp_path)
    target = root / 'feature.py'
    target.write_text('def value():\n    return 1\n', encoding='utf-8')
    engine = ImprovementEngine(
        ws,
        AllowApproval(True),
        ImprovementStore(tmp_path / 'improvements.sqlite3'),
        snapshot_manager=mgr,
    )
    proposal = engine.propose(
        'feature.py',
        'def value():\n    return 2\n',
        'update value',
        'test snapshot integration',
    )
    result = engine.apply(proposal['id'])
    assert result['ok'] is True
    assert result['snapshot_id']
    assert 'return 2' in target.read_text()
    mgr.restore(result['snapshot_id'])
    assert 'return 1' in target.read_text()


def test_snapshot_storage_inside_workspace_is_rejected(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    ws = Workspace([root])
    try:
        WorkspaceSnapshotManager(ws, root=root / '.snapshots', db_path=tmp_path / 'db.sqlite3')
    except ValueError as exc:
        assert 'outside approved workspace' in str(exc)
    else:
        raise AssertionError('snapshot archives must not be stored inside the project they protect')


def test_cli_exposes_single_command_restore_path():
    from living_assistant.cli import app

    project_group = next(group.typer_instance for group in app.registered_groups if group.name == 'project')
    commands = {getattr(command, 'name', None) or command.callback.__name__ for command in project_group.registered_commands}
    assert {'snapshot', 'snapshots', 'snapshot-restore'} <= commands
