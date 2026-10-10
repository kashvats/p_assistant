"""
Unit tests for HermesContractor armored tool integration and Collibri wiring (Milestone 1).
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch
import pytest

from living_assistant.core.workspace import Workspace
from living_assistant.tools.base import Tool
from living_assistant.tools.filesystem import build_filesystem_tools
from living_assistant.tools.registry import ToolRegistry
from living_assistant.integrations.hermes_contractor import (
    HermesContractor,
    _ALLOWED_TOOL_MAPPING,
    _ALLOWED_TOOL_NAMES,
    _la_tool_to_hermes_schema,
    _build_tool_dispatch,
)


# =====================================================================
# 1. TOOL NAME MAPPING & DISPATCH REGISTRATION
# =====================================================================

def test_allowed_tool_mapping_definitions():
    """Verify canonical and legacy tool names in _ALLOWED_TOOL_MAPPING and _ALLOWED_TOOL_NAMES."""
    canonical_tools = [
        "read_file", "write_file", "edit_file", "list_files", "search_files",
        "run_command", "git_commit", "git_diff", "git_status", "browser_snapshot",
    ]
    for name in canonical_tools:
        assert name in _ALLOWED_TOOL_MAPPING, f"Canonical tool {name} must be in _ALLOWED_TOOL_MAPPING"
        assert _ALLOWED_TOOL_MAPPING[name] == name

    # Legacy aliases
    legacy_aliases = {
        "file_read": "read_file",
        "file_write": "write_file",
        "shell_exec": "run_command",
        "playwright_navigate": "browser_snapshot",
        "playwright_extract": "browser_snapshot",
    }
    for alias, expected in legacy_aliases.items():
        assert alias in _ALLOWED_TOOL_MAPPING, f"Legacy alias {alias} must be in _ALLOWED_TOOL_MAPPING"
        assert _ALLOWED_TOOL_MAPPING[alias] == expected

    # _ALLOWED_TOOL_NAMES must contain both canonical and legacy names
    for name in canonical_tools:
        assert name in _ALLOWED_TOOL_NAMES
    for alias in legacy_aliases:
        assert alias in _ALLOWED_TOOL_NAMES


def test_la_tool_to_hermes_schema():
    """Verify _la_tool_to_hermes_schema produces valid OpenAI-compatible function schemas."""
    tool = Tool(
        name="read_file",
        description="Read file content safely.",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        handler=lambda path: "data",
    )
    schema = _la_tool_to_hermes_schema(tool)
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert schema["function"]["description"] == "Read file content safely."
    assert schema["function"]["parameters"]["required"] == ["path"]

    # Tool with empty/None description and parameters
    tool_empty = Tool(name="noop", description="", parameters={}, handler=lambda: None)
    schema_empty = _la_tool_to_hermes_schema(tool_empty)
    assert schema_empty["function"]["name"] == "noop"
    assert schema_empty["function"]["description"] == ""
    assert schema_empty["function"]["parameters"] == {}


def test_contractor_tool_registration_and_dispatch_mapping():
    """Verify canonical and legacy tool names are correctly registered and mapped in _dispatch."""
    read_mock = MagicMock(return_value={"ok": True, "content": "mock text"})
    write_mock = MagicMock(return_value={"ok": True, "bytes": 10})
    shell_mock = MagicMock(return_value={"ok": True, "stdout": "ok"})
    browser_mock = MagicMock(return_value={"ok": True, "html": "<html></html>"})
    git_mock = MagicMock(return_value={"ok": True, "commit": "abc1234"})
    unrelated_mock = MagicMock(return_value={"ok": True})

    tools = [
        Tool("read_file", "Read file", {"type": "object"}, read_mock),
        Tool("write_file", "Write file", {"type": "object"}, write_mock),
        Tool("run_command", "Run shell", {"type": "object"}, shell_mock),
        Tool("browser_snapshot", "Snapshot", {"type": "object"}, browser_mock),
        Tool("git_commit", "Commit", {"type": "object"}, git_mock),
        Tool("disallowed_internal_op", "Internal", {"type": "object"}, unrelated_mock),
    ]
    registry = ToolRegistry(tools)
    contractor = HermesContractor(None, "test_session", tool_registry=registry)

    # 1. Canonical entries must be in _dispatch
    assert "read_file" in contractor._dispatch
    assert "write_file" in contractor._dispatch
    assert "run_command" in contractor._dispatch
    assert "browser_snapshot" in contractor._dispatch
    assert "git_commit" in contractor._dispatch

    # 2. Legacy alias entries must also be in _dispatch and point to the same tool
    assert "file_read" in contractor._dispatch
    assert contractor._dispatch["file_read"] is contractor._dispatch["read_file"]

    assert "file_write" in contractor._dispatch
    assert contractor._dispatch["file_write"] is contractor._dispatch["write_file"]

    assert "shell_exec" in contractor._dispatch
    assert contractor._dispatch["shell_exec"] is contractor._dispatch["run_command"]

    assert "playwright_navigate" in contractor._dispatch
    assert contractor._dispatch["playwright_navigate"] is contractor._dispatch["browser_snapshot"]

    assert "playwright_extract" in contractor._dispatch
    assert contractor._dispatch["playwright_extract"] is contractor._dispatch["browser_snapshot"]

    # 3. Disallowed tools must NOT be in _dispatch
    assert "disallowed_internal_op" not in contractor._dispatch

    # 4. _tool_schemas must contain schemas for all 5 allowed tools
    schema_names = {s["function"]["name"] for s in contractor._tool_schemas}
    assert schema_names == {"read_file", "write_file", "run_command", "browser_snapshot", "git_commit"}


# =====================================================================
# 2. FILE READ/WRITE & PATH RESOLUTION CONFINEMENT
# =====================================================================

def test_workspace_file_read_write_routing(tmp_path):
    """File read/write calls route to real Workspace tool handlers with proper path resolution."""
    ws = Workspace([str(tmp_path)])
    fs_tools = build_filesystem_tools(ws)
    registry = ToolRegistry(fs_tools)
    contractor = HermesContractor(None, "ws_session", tool_registry=registry)

    # Setup test file
    test_file = tmp_path / "greeting.txt"
    test_file.write_text("Hello from Living Assistant!", encoding="utf-8")

    # 1. Read via canonical tool name
    res_canonical = contractor._handle_tool_call("read_file", {"path": "greeting.txt"})
    assert isinstance(res_canonical, dict)
    assert res_canonical.get("content") == "Hello from Living Assistant!"

    # 2. Read via legacy alias tool name
    res_alias = contractor._handle_tool_call("file_read", {"path": "greeting.txt"})
    assert isinstance(res_alias, dict)
    assert res_alias.get("content") == "Hello from Living Assistant!"

    # 3. Read with legacy 'file_path' argument
    res_arg_alias = contractor._handle_tool_call("file_read", {"file_path": "greeting.txt"})
    assert isinstance(res_arg_alias, dict)
    assert res_arg_alias.get("content") == "Hello from Living Assistant!"

    # 4. Write via canonical tool name
    res_write_canonical = contractor._handle_tool_call("write_file", {"path": "out_canonical.txt", "content": "Sample A"})
    assert res_write_canonical.get("ok") is True
    assert (tmp_path / "out_canonical.txt").read_text(encoding="utf-8") == "Sample A"

    # 5. Write via legacy alias tool name
    res_write_alias = contractor._handle_tool_call("file_write", {"path": "out_alias.txt", "content": "Sample B"})
    assert res_write_alias.get("ok") is True
    assert (tmp_path / "out_alias.txt").read_text(encoding="utf-8") == "Sample B"


def test_workspace_path_confinement_boundary(tmp_path):
    """Path traversal outside workspace root is blocked by Workspace confinement."""
    ws = Workspace([str(tmp_path)])
    fs_tools = build_filesystem_tools(ws)
    registry = ToolRegistry(fs_tools)
    contractor = HermesContractor(None, "ws_confinement", tool_registry=registry)

    # Attempt directory traversal with canonical tool
    res_escape_read = contractor._handle_tool_call("read_file", {"path": "../secret.txt"})
    assert res_escape_read.get("ok") is False
    assert any(msg in str(res_escape_read.get("error")) for msg in ["Workspace violation", "outside allowed workspace roots"])

    # Attempt directory traversal with legacy alias
    res_escape_alias = contractor._handle_tool_call("file_read", {"path": "../../outside.txt"})
    assert res_escape_alias.get("ok") is False
    assert any(msg in str(res_escape_alias.get("error")) for msg in ["Workspace violation", "outside allowed workspace roots"])

    # Attempt write traversal
    res_escape_write = contractor._handle_tool_call("file_write", {"path": "../forbidden.txt", "content": "bad"})
    assert res_escape_write.get("ok") is False
    assert any(msg in str(res_escape_write.get("error")) for msg in ["Workspace violation", "outside allowed workspace roots"])


# =====================================================================
# 3. SHELL EXECUTION & APPROVAL REQUIREMENT
# =====================================================================

def test_shell_execution_routing():
    """Shell execution calls route to run_command handler under canonical and legacy alias."""
    mock_run = MagicMock(return_value={"ok": True, "returncode": 0, "stdout": "hello shell", "stderr": ""})
    tool = Tool("run_command", "Run shell", {"type": "object"}, mock_run)
    registry = ToolRegistry([tool])
    contractor = HermesContractor(None, "shell_session", tool_registry=registry)

    # Canonical call
    res_canonical = contractor._handle_tool_call("run_command", {"command": "echo hello"})
    assert res_canonical.get("ok") is True
    assert res_canonical.get("stdout") == "hello shell"
    mock_run.assert_called_with(command="echo hello")

    # Legacy alias call
    res_alias = contractor._handle_tool_call("shell_exec", {"command": "echo hello"})
    assert res_alias.get("ok") is True
    assert res_alias.get("stdout") == "hello shell"

    # Legacy alias argument: cmd -> command
    res_cmd_alias = contractor._handle_tool_call("shell_exec", {"cmd": "ls -la"})
    assert res_cmd_alias.get("ok") is True
    mock_run.assert_called_with(command="ls -la")


def test_shell_execution_approval_required_handling():
    """Check approval_required returns clean structured response PENDING_APPROVAL."""
    mock_run = MagicMock(return_value={
        "ok": False,
        "approval_required": True,
        "approval_id": "appr_12345",
        "risk": "HIGH",
        "explanation": "Destructive rm command",
    })
    tool = Tool("run_command", "Run shell", {"type": "object"}, mock_run)
    registry = ToolRegistry([tool])
    contractor = HermesContractor(None, "approval_session", tool_registry=registry)

    # 1. Canonical call requiring approval
    res_canonical = contractor._handle_tool_call("run_command", {"command": "rm -rf /"})
    assert res_canonical == {
        "ok": False,
        "status": "PENDING_APPROVAL",
        "message": "Action paused for user approval.",
    }

    # 2. Legacy alias call requiring approval
    res_alias = contractor._handle_tool_call("shell_exec", {"command": "drop database"})
    assert res_alias == {
        "ok": False,
        "status": "PENDING_APPROVAL",
        "message": "Action paused for user approval.",
    }

    # 3. Status PENDING_APPROVAL in tool result also returns clean response
    mock_run.return_value = {"ok": False, "status": "PENDING_APPROVAL", "details": "Awaiting admin token"}
    res_status = contractor._handle_tool_call("shell_exec", {"command": "reboot"})
    assert res_status == {
        "ok": False,
        "status": "PENDING_APPROVAL",
        "message": "Action paused for user approval.",
    }


# =====================================================================
# 4. COLLIBRI CONFIGURATION & AIAgent PROPAGATION
# =====================================================================

def test_collibri_init_parameters_and_defaults():
    """Verify Collibri base_url, model_name, and provider defaults and custom options."""
    # 1. Default configuration
    c_default = HermesContractor(None, "default_session")
    assert c_default.base_url == "http://127.0.0.1:8080/v1"
    assert c_default.model_name == "openai/collibri"
    assert c_default.provider == "ollama"

    # 2. Custom Collibri endpoint
    c_custom = HermesContractor(
        model_manager="fake_mm",
        session_id="custom_session",
        tool_registry=None,
        base_url="http://192.168.1.100:8080/v1",
        model_name="openai/collibri-q4",
        provider="openai",
    )
    assert c_custom.base_url == "http://192.168.1.100:8080/v1"
    assert c_custom.model_name == "openai/collibri-q4"
    assert c_custom.provider == "openai"


def test_aiagent_propagation_in_execute_task():
    """Collibri base_url, model, and provider parameters are correctly passed to AIAgent."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.run.return_value = "Task completed successfully"
    mock_agent_cls = MagicMock(return_value=mock_agent_instance)

    contractor = HermesContractor(
        None,
        session_id="task_session",
        tool_registry=None,
        base_url="http://127.0.0.1:8080/v1",
        model_name="openai/collibri",
        provider="openai",
    )
    contractor._AIAgent = mock_agent_cls

    result = contractor.execute_task("Analyze code", "Context data", timeout=5.0)

    assert result["ok"] is True
    assert result["output"] == "Task completed successfully"
    assert result["contractor"] == "hermes_agent"

    # Verify kwargs passed to AIAgent
    mock_agent_cls.assert_called_once()
    called_kwargs = mock_agent_cls.call_args[1]
    assert called_kwargs["provider"] == "openai"
    assert called_kwargs["base_url"] == "http://127.0.0.1:8080/v1"
    assert called_kwargs["model"] == "openai/collibri"
    assert called_kwargs["session_id"] == "task_session"
    assert called_kwargs["quiet_mode"] is True


# =====================================================================
# 5. FALLBACK & ERROR HANDLING
# =====================================================================

def test_hermes_agent_import_error_handling():
    """Verify RuntimeError is raised with actionable guidance if hermes-agent cannot be imported."""
    with patch.dict("sys.modules", {"run_agent": None}):
        with pytest.raises(RuntimeError) as exc_info:
            HermesContractor(None, "err_session")
        assert "hermes-agent is not installed or broken" in str(exc_info.value)
        assert "pip install" in str(exc_info.value)


def test_missing_tools_fallback():
    """When tool_registry is None or empty, contractor runs without crash and blocks calls."""
    contractor = HermesContractor(None, "empty_session", tool_registry=None)
    assert contractor._dispatch == {}
    assert contractor._tool_schemas == []

    # Attempting to call an unavailable tool returns clean error
    res = contractor._handle_tool_call("read_file", {"path": "test.txt"})
    assert res.get("ok") is False
    assert "Tool 'read_file' is not available" in res.get("error", "")

    # Attempting to call an unallowed arbitrary tool
    res_unallowed = contractor._handle_tool_call("system_shutdown", {})
    assert res_unallowed.get("ok") is False
    assert "Tool 'system_shutdown' is not available" in res_unallowed.get("error", "")


def test_handle_tool_call_json_string_and_invalid_arguments():
    """Test JSON string argument parsing and TypeError argument handling."""
    mock_fn = MagicMock(return_value={"ok": True, "received": True})
    tool = Tool("read_file", "Read file", {"type": "object"}, mock_fn)
    registry = ToolRegistry([tool])
    contractor = HermesContractor(None, "json_session", tool_registry=registry)

    # Arguments passed as JSON string
    res_str = contractor._handle_tool_call("read_file", json.dumps({"path": "foo.txt"}))
    assert res_str.get("ok") is True
    mock_fn.assert_called_with(path="foo.txt")

    # Tool handler raises TypeError on invalid signature
    def strict_handler(path: str):
        return {"content": "ok"}

    strict_tool = Tool("write_file", "Write file", {"type": "object"}, strict_handler)
    contractor_strict = HermesContractor(None, "strict_session", tool_registry=ToolRegistry([strict_tool]))
    res_type_error = contractor_strict._handle_tool_call("write_file", {"invalid_param": 123})
    assert res_type_error.get("ok") is False
    assert "Invalid arguments for write_file" in res_type_error.get("error", "")


def test_handle_tool_call_handler_exception():
    """Test tool handler raising arbitrary exception returns clean error dict."""
    def broken_handler(**kwargs):
        raise RuntimeError("Disk I/O error occurred")

    broken_tool = Tool("read_file", "Read", {"type": "object"}, broken_handler)
    contractor = HermesContractor(None, "broken_session", tool_registry=ToolRegistry([broken_tool]))
    res = contractor._handle_tool_call("read_file", {"path": "any"})
    assert res.get("ok") is False
    assert "Disk I/O error occurred" in res.get("error", "")


def test_execute_task_agent_run_failure():
    """Test execute_task returns clean error dict when AIAgent.run raises."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.run.side_effect = RuntimeError("Ollama connection refused")
    mock_agent_cls = MagicMock(return_value=mock_agent_instance)

    contractor = HermesContractor(None, "fail_session")
    contractor._AIAgent = mock_agent_cls

    result = contractor.execute_task("Do work", "Context")
    assert result.get("ok") is False
    assert "Ollama connection refused" in result.get("error", "")
    assert result.get("contractor") == "hermes_agent"


def test_execute_task_timeout():
    """Test execute_task returns timeout error when agent exceeds timeout."""
    def hanging_run(prompt):
        time.sleep(1.0)
        return "late"

    mock_agent_instance = MagicMock()
    mock_agent_instance.run.side_effect = hanging_run
    mock_agent_cls = MagicMock(return_value=mock_agent_instance)

    contractor = HermesContractor(None, "timeout_session")
    contractor._AIAgent = mock_agent_cls

    result = contractor.execute_task("Long task", "", timeout=0.1)
    assert result.get("ok") is False
    assert "timed out after 0s" in result.get("error", "")
    assert result.get("contractor") == "hermes_agent"
