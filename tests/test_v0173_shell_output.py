from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.tools.shell import ProcessRegistry, build_shell_tools
from living_assistant.workspace import Workspace


def test_run_command_bounds_model_visible_output_without_buffering_capture(tmp_path):
    root = tmp_path / 'ws'; root.mkdir()
    approvals = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path / 'a.sqlite3'))
    registry = ProcessRegistry(tmp_path / 'processes.json')
    tools = {tool.name: tool.handler for tool in build_shell_tools(
        Workspace([root]), approvals,
        {'policy': {'require_execute_approval': False, 'command_timeout_seconds': 5}},
        registry,
    )}

    command = "python -c \"import sys; sys.stdout.write('x'*2000000); sys.stderr.write('y'*50000)\""
    result = tools['run_command'](command, '.', 5)
    assert result['ok'] is True
    assert result['output_truncated'] is True
    assert result['stdout_truncated'] is True and result['stderr_truncated'] is True
    assert len(result['stdout']) <= 20000
    assert len(result['stderr']) <= 20000
