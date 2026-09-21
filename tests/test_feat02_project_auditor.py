from __future__ import annotations

import json

import pytest

from living_assistant.system.project_auditor import ProjectAuditor
from living_assistant.tools.projects import ProjectRegistry, build_project_tools
from living_assistant.workspace import Workspace, WorkspaceViolation


def test_project_auditor_reports_dependencies_lint_dead_code_and_security_without_secret_values(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "requirements.txt").write_text("requests\nhttpx>=0.27\n")
    secret = "ghp_123456789012345678901234567890"
    (project / "app.py").write_text(
        "API_TOKEN = '" + secret + "'\n"
        "def unused_helper():\n    return 1\n\n"
        "def main():\n    eval('1 + 1')\n    return 2    \n"
    )
    (project / ".env").write_text("PASSWORD=do-not-read")
    result = ProjectAuditor(Workspace([project])).audit(".")
    assert result["ok"] is True
    assert result["dependencies"]["issue_count"] >= 1
    assert result["lint"]["score"] < 100
    assert any(item["name"] == "unused_helper" for item in result["dead_code"]["candidates"])
    rules = {item["rule"] for item in result["security"]["findings"]}
    assert "hardcoded-credential-assignment" in rules
    assert "dangerous-call:eval" in rules
    rendered = json.dumps(result)
    assert secret not in rendered
    assert "do-not-read" not in rendered


def test_project_auditor_is_workspace_bounded(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    auditor = ProjectAuditor(Workspace([project]))
    with pytest.raises(WorkspaceViolation):
        auditor.audit(str(outside))


def test_project_audit_is_exposed_as_existing_project_tool_family(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    ws = Workspace([project])
    registry = ProjectRegistry(tmp_path / "projects.json")
    tools = {tool.name: tool for tool in build_project_tools(ws, registry)}
    assert "project_audit" in tools
    assert tools["project_audit"].handler(".")["ok"] is True
