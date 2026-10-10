"""
Comprehensive unit and integration tests for Software Company Tools,
Requirements Clarification Engine, and Workspace Anti-Loop Execution.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from living_assistant.agents.software_company.prompt_engineer import PromptEngineerAgent
from living_assistant.core.workspace import Workspace
from living_assistant.security.permissions import (
    TaskScopedPermissionEngine,
    PermissionDeniedViolation,
    TaskScope,
    ROLE_CAPABILITY_MATRIX,
)
from living_assistant.tools.software_company_tools import build_software_company_tools


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Workspace:
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    return Workspace([ws_dir])


def test_recommend_project_stack_underspecified_asks_questions_and_gives_suggestions(temp_workspace: Workspace):
    """When requirements are underspecified (round 0), proactive suggestions and questions are returned."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    rec_tool = tools["recommend_project_stack"]

    res = rec_tool.handler(prompt="build me a todo app", round_count=0)
    assert res["ok"] is True
    assert res["is_clear"] is False
    assert res["ready_to_build"] is False
    assert len(res["questions"]) >= 2
    assert len(res["suggestions"]) >= 2
    assert "FastAPI" in str(res["suggestions"])
    assert "proceed" in res["summary_message"]


def test_recommend_project_stack_user_confirms_proceed_activates_building(temp_workspace: Workspace):
    """When user confirms or signals proceed, anti-loop terminates questions and flags ready_to_build."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    rec_tool = tools["recommend_project_stack"]

    res = rec_tool.handler(prompt="build me a todo app", round_count=0, user_responses="proceed with recommended")
    assert res["ok"] is True
    assert res["is_clear"] is True
    assert res["ready_to_build"] is True
    assert len(res["questions"]) == 0
    assert "FastAPI" in res["proposed_stack"]["framework"]


def test_recommend_project_stack_anti_loop_max_rounds_enforced(temp_workspace: Workspace):
    """Anti-loop guarantee: after 1 round, questions are never asked again, defaults locked, building begins."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    rec_tool = tools["recommend_project_stack"]

    # Even with an underspecified prompt and no user responses, round_count >= 1 forces ready_to_build
    res = rec_tool.handler(prompt="build me a todo app", round_count=1)
    assert res["ok"] is True
    assert res["is_clear"] is True
    assert res["ready_to_build"] is True
    assert len(res["questions"]) == 0
    assert res["proposed_stack"]["database"] == "SQLite"


def test_recommend_project_stack_fully_specified_bypasses_questions(temp_workspace: Workspace):
    """When the initial prompt already specifies stack and details, questions are bypassed immediately."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    rec_tool = tools["recommend_project_stack"]

    res = rec_tool.handler(prompt="build a todo app with fastapi, sqlite, and jwt auth", round_count=0)
    assert res["ok"] is True
    assert res["is_clear"] is True
    assert res["ready_to_build"] is True
    assert len(res["questions"]) == 0


def test_build_software_project_scaffolds_complete_files(temp_workspace: Workspace):
    """build_software_project writes full production code into the workspace folder without empty facades."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    build_tool = tools["build_software_project"]

    target_dir = "workspace/test_todo_app"
    res = build_tool.handler(
        prompt="build me a todo app",
        target_dir=target_dir,
        framework="FastAPI (Python)",
        database="SQLite",
        auth="PyJWT",
    )

    assert res["ok"] is True
    assert res["status"] == "BUILT_AND_VERIFIED"
    assert res["file_count"] == 9
    assert len(res["files_written"]) == 9

    # Verify physical file existence in workspace
    ws_root = temp_workspace.roots[0]
    expected_files = [
        ws_root / "test_todo_app" / "main.py",
        ws_root / "test_todo_app" / "database.py",
        ws_root / "test_todo_app" / "models.py",
        ws_root / "test_todo_app" / "static" / "index.html",
        ws_root / "test_todo_app" / "static" / "styles.css",
        ws_root / "test_todo_app" / "static" / "app.js",
        ws_root / "test_todo_app" / "tests" / "test_todo.py",
        ws_root / "test_todo_app" / "requirements.txt",
        ws_root / "test_todo_app" / "README.md",
    ]
    for ef in expected_files:
        assert ef.exists(), f"File was not created: {ef}"
        assert ef.stat().st_size > 0, f"File is empty: {ef}"


def test_developer_permissions_allow_delete_in_workspace(temp_workspace: Workspace):
    """Verifies that developer roles have full write, edit, and delete permissions in workspace."""
    engine = TaskScopedPermissionEngine(workspace=temp_workspace)
    scope = TaskScope(
        task_id="task_delete_test",
        role="backend_dev",
        target_paths=["**", "*"],
        frozen_paths=["tests/frozen_test.py"],
    )

    # 1. Allowed deletion inside workspace
    res = engine.evaluate(
        role="backend_dev",
        task_scope=scope,
        tool_name="delete_file",
        arguments={"path": "workspace/temp_junk.txt"},
    )
    assert res.allowed is True

    # 2. Denied deletion of frozen test file
    res_frozen = engine.evaluate(
        role="backend_dev",
        task_scope=scope,
        tool_name="delete_file",
        arguments={"path": "tests/frozen_test.py"},
    )
    assert res_frozen.allowed is False
    assert "frozen" in (res_frozen.reason or "").lower()

    # 3. Sensitive .env credentials require human approval gating
    res_env = engine.evaluate(
        role="backend_dev",
        task_scope=scope,
        tool_name="delete_file",
        arguments={"path": "workspace/.env.production"},
    )
    assert res_env.requires_approval is True
    assert "sensitive" in (res_env.reason or "").lower() or "approval" in (res_env.reason or "").lower()


def test_recommend_project_stack_notes_app_returns_vision_and_domain_questions(temp_workspace: Workspace):
    """When user requests a notes app, returns Notes Product Vision blueprint and domain questions, NOT Todo."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    rec_tool = tools["recommend_project_stack"]

    res = rec_tool.handler(prompt="build me a note taking markdown app", round_count=0)
    assert res["ok"] is True
    assert res["is_clear"] is False
    assert res["ready_to_build"] is False
    assert "notes" in str(res["product_vision"]["archetype"])
    assert "Markdown" in str(res["questions"]) or "note" in str(res["questions"]).lower()
    # Ensure it did NOT return Todo features
    assert "todo" not in res["product_vision"]["project_name"].lower()


def test_build_software_project_notes_app_scaffolds_notes_files(temp_workspace: Workspace):
    """build_software_project builds a real Notes app with Note models and notes database, not a Todo template."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    build_tool = tools["build_software_project"]

    res = build_tool.handler(
        prompt="build me a notes app with markdown support",
        target_dir="workspace/notes_app",
    )
    assert res["ok"] is True
    assert res["status"] == "BUILT_AND_VERIFIED"
    assert res["archetype"] == "notes"
    assert res["file_count"] == 9

    # Verify physical file existence in workspace
    ws_root = temp_workspace.roots[0]
    expected_files = [
        ws_root / "notes_app" / "main.py",
        ws_root / "notes_app" / "database.py",
        ws_root / "notes_app" / "models.py",
        ws_root / "notes_app" / "static" / "index.html",
        ws_root / "notes_app" / "static" / "styles.css",
        ws_root / "notes_app" / "static" / "app.js",
        ws_root / "notes_app" / "tests" / "test_notes.py",
        ws_root / "notes_app" / "requirements.txt",
        ws_root / "notes_app" / "README.md",
    ]
    for ef in expected_files:
        assert ef.exists(), f"File was not created: {ef}"
        assert ef.stat().st_size > 0, f"File is empty: {ef}"

    # Verify content mentions notes and not todos
    main_code = (ws_root / "notes_app" / "main.py").read_text()
    assert "notes" in main_code.lower()
    assert "todos" not in main_code.lower()


def test_build_software_project_expense_tracker_scaffolds_finance_files(temp_workspace: Workspace):
    """build_software_project builds an Expense Tracker app with finance models and summary endpoints."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    build_tool = tools["build_software_project"]

    res = build_tool.handler(
        prompt="build a personal finance and expense tracker",
        target_dir="workspace/expense_tracker",
    )
    assert res["ok"] is True
    assert res["status"] == "BUILT_AND_VERIFIED"
    assert res["archetype"] == "expense"
    assert res["file_count"] == 9

    ws_root = temp_workspace.roots[0]
    main_code = (ws_root / "expense_tracker" / "main.py").read_text()
    assert "expense" in main_code.lower()
    assert "/api/summary" in main_code


def test_build_software_project_returns_live_agent_timeline(temp_workspace: Workspace):
    """build_software_project returns the live execution timeline of all 6 software company agents."""
    tools = {t.name: t for t in build_software_company_tools(temp_workspace)}
    build_tool = tools["build_software_project"]

    res = build_tool.handler(prompt="build me a chat application")
    assert res["ok"] is True
    timeline = res["agent_activity_timeline"]
    assert len(timeline) == 6

    agent_names = [t["agent"] for t in timeline]
    assert "Product Manager" in agent_names
    assert "Software Architect" in agent_names
    assert "Backend Developer" in agent_names
    assert "Frontend Developer" in agent_names
    assert "QA Engineer" in agent_names
    assert "Final Verifier" in agent_names
    for entry in timeline:
        assert entry["status"] == "COMPLETED"
        assert len(entry["action"]) > 0

