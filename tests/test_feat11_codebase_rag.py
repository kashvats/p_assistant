from __future__ import annotations

from pathlib import Path

from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.system.codebase_index import CodebaseIndex
from living_assistant.tools.projects import ProjectRegistry, build_project_tools


def _build_index(tmp_path: Path):
    root = tmp_path / 'project'
    root.mkdir()
    ws = Workspace([root])
    index = CodebaseIndex(ws, path=tmp_path / 'index.sqlite3', dimensions=512)
    return root, ws, index


def test_section_aware_python_index_and_semantic_identifier_retrieval(tmp_path):
    root, _ws, index = _build_index(tmp_path)
    (root / 'auth.py').write_text(
        '''class AuthenticationService:\n'
        '    def authenticate_user(self, username, password):\n'
        '        """Validate credentials and establish a login session."""\n'
        '        return bool(username and password)\n\n'
        'def calculate_invoice_total(items):\n'
        '    return sum(items)\n'''.replace("'\n        '", ''),
        encoding='utf-8',
    )

    result = index.index_project('.')
    assert result['ok'] is True
    assert result['files_indexed'] == 1
    assert result['chunks_indexed'] >= 2

    found = index.search('how does user authentication and login work?', '.')
    assert found['ok'] is True
    assert found['results']
    top = found['results'][0]
    assert top['path'] == 'auth.py'
    assert top['section'] == 'class AuthenticationService'
    assert 'authenticate_user' in top['content']
    assert top['trust'] == 'untrusted_project_content'


def test_markdown_heading_chunking_is_preserved(tmp_path):
    root, _ws, index = _build_index(tmp_path)
    (root / 'architecture.md').write_text(
        '# Overview\nGeneral notes.\n\n## Payment Retry Flow\nRetries use exponential backoff and idempotency keys.\n',
        encoding='utf-8',
    )
    index.index_project('.')
    found = index.search('payment retry idempotency backoff', '.')
    assert found['results']
    assert found['results'][0]['section'] == 'Payment Retry Flow'


def test_sensitive_generated_binary_and_oversized_files_are_not_persisted(tmp_path):
    root, _ws, index = _build_index(tmp_path)
    live_secret = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
    (root / '.env').write_text(f'API_TOKEN={live_secret}', encoding='utf-8')
    (root / 'normal.py').write_text(
        f'def use_api():\n    token = "{live_secret}"\n    return "safe"\n',
        encoding='utf-8',
    )
    generated = root / 'node_modules'
    generated.mkdir()
    (generated / 'bad.js').write_text('function forbiddenDependencyCode() {}', encoding='utf-8')
    (root / 'binary.txt').write_bytes(b'hello\x00secret')
    (root / 'huge.py').write_text('x = 1\n' * 100_000, encoding='utf-8')

    result = index.index_project('.')
    assert result['ok'] is True

    rows = index.conn.execute('SELECT relative_path,text FROM code_index_chunks').fetchall()
    paths = {row[0] for row in rows}
    stored_text = '\n'.join(row[1] for row in rows)
    assert '.env' not in paths
    assert all(not path.startswith('node_modules/') for path in paths)
    assert 'binary.txt' not in paths
    assert 'huge.py' not in paths
    assert live_secret not in stored_text
    assert '[REDACTED' in stored_text


def test_index_persists_across_process_like_reopen(tmp_path):
    root, ws, index = _build_index(tmp_path)
    (root / 'queue.py').write_text(
        'def retry_failed_jobs():\n    """Requeue failed jobs with exponential delay."""\n    return True\n',
        encoding='utf-8',
    )
    index.index_project('.')
    index.conn.close_all()

    reopened = CodebaseIndex(ws, path=tmp_path / 'index.sqlite3')
    status = reopened.status('.')
    assert status['indexed'] is True
    assert status['chunks_indexed'] >= 1
    result = reopened.search('failed job retry queue delay', '.')
    assert result['results'][0]['path'] == 'queue.py'


def test_project_tools_expose_index_search_and_status_without_duplicate_tool_family(tmp_path):
    root, ws, index = _build_index(tmp_path)
    (root / 'worker.py').write_text('def process_background_job():\n    return "done"\n', encoding='utf-8')
    registry = ProjectRegistry(tmp_path / 'projects.json')
    tools = {tool.name: tool for tool in build_project_tools(ws, registry, index)}

    assert {'project_index_code', 'project_search_code', 'project_index_status'} <= tools.keys()
    before = tools['project_index_status'].handler('.')
    assert before['indexed'] is False
    indexed = tools['project_index_code'].handler('.')
    assert indexed['ok'] is True
    searched = tools['project_search_code'].handler('background worker job', '.', 5)
    assert searched['ok'] is True
    assert searched['results'][0]['path'] == 'worker.py'


def test_code_index_remains_workspace_bounded(tmp_path):
    root, _ws, index = _build_index(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'private.py').write_text('def private(): pass', encoding='utf-8')

    try:
        index.index_project(outside)
    except WorkspaceViolation:
        pass
    else:
        raise AssertionError('outside-workspace indexing must be rejected')
