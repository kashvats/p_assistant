from __future__ import annotations

from types import SimpleNamespace

from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.core.workspace import Workspace
from living_assistant.security.safe_commands import explain_command
from living_assistant.tools.shell import ProcessRegistry, build_shell_tools


def _handlers(tools):
    return {tool.name: tool.handler for tool in tools}


class _Events:
    def __init__(self, order=None):
        self.rows = []
        self.order = order

    def publish(self, event_type, **data):
        if self.order is not None:
            self.order.append("preview")
        self.rows.append((event_type, data))
        return {"type": event_type, "data": data}


def test_command_explainer_is_deterministic_and_does_not_echo_arguments():
    read = explain_command("git status")
    assert read.risk == "READ"
    assert read.risk_level == "low"
    assert "read-only" in read.summary.lower()

    secret = "super-secret-token"
    npm = explain_command(f"npm install example --token={secret}")
    assert npm.risk == "EXECUTE"
    assert npm.risk_level == "medium"
    assert npm.executable == "npm"
    assert "package" in npm.summary.lower()
    assert secret not in npm.summary
    assert secret not in str(npm.to_dict())

    blocked = explain_command("rm -rf /")
    assert blocked.allowed is False
    assert blocked.risk_level == "blocked"
    assert blocked.risk == "DESTRUCTIVE"


def test_run_command_publishes_preview_before_subprocess_execution(tmp_path, monkeypatch):
    import living_assistant.tools.shell as shell

    root = tmp_path / "workspace"
    root.mkdir()
    order = []
    events = _Events(order)
    approvals = ApprovalManager(
        interactive=False, store=ApprovalStore(tmp_path / "approvals.sqlite3")
    )
    registry = ProcessRegistry(tmp_path / "processes.json")

    def fake_run(*args, **kwargs):
        order.append("execute")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(shell.subprocess, "run", fake_run)
    tools = _handlers(
        build_shell_tools(
            Workspace([root]),
            approvals,
            {"policy": {"require_execute_approval": False}},
            registry,
            event_bus=events,
        )
    )

    result = tools["run_command"]("pwd", ".")
    assert result["ok"] is True
    assert order == ["preview", "execute"]
    assert result["risk"] == "READ"
    assert result["explanation"]["risk_level"] == "low"
    assert events.rows[0][0] == "shell.command_preview"


def test_command_approval_shows_explanation_and_exact_retry_still_consumes(tmp_path, monkeypatch):
    import living_assistant.tools.shell as shell

    root = tmp_path / "workspace"
    root.mkdir()
    store = ApprovalStore(tmp_path / "approvals.sqlite3")
    approvals = ApprovalManager(interactive=False, store=store)
    registry = ProcessRegistry(tmp_path / "processes.json")
    events = _Events()
    tools = _handlers(
        build_shell_tools(
            Workspace([root]),
            approvals,
            {"policy": {"require_execute_approval": True}},
            registry,
            event_bus=events,
        )
    )

    first = tools["run_command"]("echo hello", ".")
    assert first["approval_required"] is True
    assert first["risk"] == "EXECUTE"
    approval = store.list("pending")[0]
    assert "Explanation:" in approval["reason"]
    assert "Risk level: MEDIUM (EXECUTE)" in approval["reason"]
    store.resolve(approval["id"], True)

    monkeypatch.setattr(shell.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    second = tools["run_command"]("echo hello", ".")
    assert second["ok"] is True
    assert second["explanation"]["risk_level"] == "medium"
    assert store.list("approved")[0]["consumed_at"] is not None


def test_blocked_command_is_explained_but_never_executed(tmp_path, monkeypatch):
    import living_assistant.tools.shell as shell

    root = tmp_path / "workspace"
    root.mkdir()
    approvals = ApprovalManager(
        interactive=False, store=ApprovalStore(tmp_path / "approvals.sqlite3")
    )
    events = _Events()
    registry = ProcessRegistry(tmp_path / "processes.json")
    monkeypatch.setattr(
        shell.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not execute")),
    )
    tools = _handlers(
        build_shell_tools(
            Workspace([root]), approvals, {"policy": {}}, registry, event_bus=events
        )
    )

    result = tools["run_command"]("rm -rf /", ".")
    assert result["blocked"] is True
    assert result["explanation"]["risk_level"] == "blocked"
    assert events.rows[0][0] == "shell.command_preview"


def test_start_process_approval_also_contains_command_explanation(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    store = ApprovalStore(tmp_path / "approvals.sqlite3")
    approvals = ApprovalManager(interactive=False, store=store)
    tools = _handlers(
        build_shell_tools(
            Workspace([root]),
            approvals,
            {"policy": {}},
            ProcessRegistry(tmp_path / "processes.json"),
            event_bus=_Events(),
        )
    )

    result = tools["start_process"]("python app.py", ".")
    assert result["approval_required"] is True
    assert result["explanation"]["executable"] == "python"
    approval = store.list("pending")[0]
    assert "Runs Python code" in approval["reason"]
