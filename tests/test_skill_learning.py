"""
Comprehensive test suite for Persistent Skill Learning and Acquisition System (Section 10).
Verifies Capability Gap Detection, Multi-Source Acquisition, 6-Stage Lifecycle,
Isolated Sandboxed Testing, Security Scope Gating, and Verified Tool Execution.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from living_assistant.core.workspace import Workspace
from living_assistant.skills.learning import (
    CapabilityGapDetector,
    SkillLearningEngine,
    LearnedSkillStatus,
    CapabilityGap,
)
from living_assistant.skills.manager import SkillManager
from living_assistant.skills.manifest import SkillStep, SkillPermissionScope
from living_assistant.skills.store import SkillStore
from living_assistant.skills.tools import build_skill_tools
from living_assistant.tools.registry import ToolRegistry


@pytest.fixture
def temp_env(tmp_path: Path):
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    ws = Workspace([ws_dir])

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "test_assistant.sqlite3"
    store = SkillStore(path=db_path)

    from living_assistant.tools.base import Tool
    registry = ToolRegistry()
    # Register portable mock tools
    registry.register(Tool("files.read", "Read file content", {"type": "object", "properties": {"path": {"type": "string"}}}, lambda path="": "mock content"))
    registry.register(Tool("files.write", "Write file content", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}, lambda path="", content="": True))
    registry.register(Tool("files.list", "List directory files", {"type": "object", "properties": {"path": {"type": "string"}}}, lambda path=".": ["file1.txt"]))
    registry.register(Tool("documents.extract", "Extract data", {"type": "object", "properties": {"path": {"type": "string"}}}, lambda path="": {"key": "val"}))

    manager = SkillManager(
        workspace=ws,
        tool_registry=registry,
        skills_dir=skills_dir,
        store=store,
    )

    engine = SkillLearningEngine(
        store=store,
        tool_registry=registry,
        skills_dir=skills_dir,
    )

    return {
        "workspace": ws,
        "skills_dir": skills_dir,
        "store": store,
        "registry": registry,
        "manager": manager,
        "engine": engine,
    }


def test_capability_gap_detector_identifies_genuine_gaps(temp_env):
    """Detects missing procedural capability when task requires unsupported data format."""
    detector = CapabilityGapDetector()
    tools = {"files.read", "files.write", "files.list"}
    active_skills = []

    # 1. Frontmatter metadata extraction gap
    gap = detector.detect_gap("Parse markdown YAML frontmatter headers into JSON", tools, active_skills)
    assert gap is not None
    assert gap.missing_capability == "markdown_frontmatter_parser"
    assert gap.category in ("missing_procedure", "unsupported_data_format", "missing_tool")
    assert gap.resolution_strategy == "acquire_new_skill"
    assert "documentation" in gap.candidate_sources

    # 2. Parquet conversion gap
    gap_parquet = detector.detect_gap("convert csv to parquet format", tools, active_skills)
    assert gap_parquet is not None
    assert gap_parquet.missing_capability == "tabular_parquet_converter"


def test_capability_gap_detector_does_not_confuse_app_requests(temp_env):
    """Software/coding app requests are handled by Software Company, not reported as skill gaps."""
    detector = CapabilityGapDetector()
    tools = {"files.read", "files.write"}
    active_skills = []

    # Software application requests
    gap_app = detector.detect_gap("build me a notes app with markdown", tools, active_skills)
    assert gap_app is None

    gap_todo = detector.detect_gap("build me a todo app", tools, active_skills)
    assert gap_todo is None


def test_capability_gap_detector_bypasses_when_skill_already_active(temp_env):
    """When an active skill already covers the triggers, no gap is flagged."""
    detector = CapabilityGapDetector()
    tools = {"files.read", "files.write"}
    active_skills = [{"name": "Invoice Organizer", "triggers": ["organize invoices", "sort receipts"]}]

    gap = detector.detect_gap("please organize invoices in workspace", tools, active_skills)
    assert gap is None


def test_skill_learning_engine_full_lifecycle_success(temp_env):
    """Tests complete 6-stage lifecycle from PROPOSED -> LEARNING -> TESTING -> VERIFIED."""
    engine = temp_env["engine"]
    store = temp_env["store"]

    gap = CapabilityGap(
        task_id="gap_frontmatter_test",
        task_description="Parse markdown frontmatter",
        missing_capability="markdown_frontmatter",
        category="unsupported_data_format",
        severity="blocking",
        candidate_sources=["documentation", "repository"],
    )

    # 1. PROPOSE
    prop = engine.propose_skill(gap)
    assert prop["ok"] is True
    assert prop["status"] == LearnedSkillStatus.PROPOSED
    skill_id = prop["skill_id"]

    rec = store.get_lifecycle(skill_id)
    assert rec["state"] == LearnedSkillStatus.PROPOSED

    # 2. LEARN FROM SOURCE -> Advances to TESTING
    steps = [
        SkillStep(
            id="read_file",
            tool="files.read",
            description="Read markdown file content",
            arguments={"path": "{inputs.path}"},
        ),
        SkillStep(
            id="extract_meta",
            tool="documents.extract",
            description="Extract frontmatter key-values",
            arguments={"path": "{inputs.path}"},
        ),
    ]
    pkg = engine.learn_from_source(
        skill_id=skill_id,
        source_type="documentation",
        source_reference="CommonMark Frontmatter Specification",
        workflow_steps=steps,
    )
    assert pkg.manifest.id == skill_id
    rec_learning = store.get_lifecycle(skill_id)
    assert rec_learning["state"] == LearnedSkillStatus.TESTING

    # 3. TEST AND VALIDATE -> Advances to VERIFIED
    test_inputs = [{"path": "./workspace/post.md"}]
    val = engine.test_and_validate(skill_id, test_inputs=test_inputs)
    assert val["ok"] is True
    assert val["status"] == LearnedSkillStatus.VERIFIED
    assert val["tests_passed"] == 1

    rec_verified = store.get_lifecycle(skill_id)
    assert rec_verified["state"] == LearnedSkillStatus.VERIFIED
    assert rec_verified["approval_id"] is not None

    # 4. Discovery in catalog
    learned_list = engine.list_learned_skills(state=LearnedSkillStatus.VERIFIED)
    assert any(s["skill_id"] == skill_id for s in learned_list)


def test_skill_learning_engine_fails_on_unregistered_tool(temp_env):
    """Tests that a proposed procedure using unregistered or invalid tools is marked FAILED."""
    engine = temp_env["engine"]
    store = temp_env["store"]

    gap = CapabilityGap(
        task_id="gap_invalid_tool",
        task_description="Task using missing tool",
        missing_capability="unsupported_tool_op",
        category="missing_tool",
        severity="blocking",
    )
    prop = engine.propose_skill(gap)
    skill_id = prop["skill_id"]

    # Add step using nonexistent tool
    bad_steps = [
        SkillStep(
            id="bad_step",
            tool="nonexistent_external_tool_xyz",
            description="Calls missing tool",
            arguments={},
        )
    ]
    engine.learn_from_source(
        skill_id=skill_id,
        source_type="unverified_source",
        source_reference="None",
        workflow_steps=bad_steps,
    )

    val = engine.test_and_validate(skill_id, test_inputs=[{}])
    assert val["ok"] is False
    assert val["status"] == LearnedSkillStatus.FAILED
    assert "unregistered" in str(val["errors"]).lower()

    rec = store.get_lifecycle(skill_id)
    assert rec["state"] == LearnedSkillStatus.FAILED


def test_skill_learning_engine_gates_high_privilege_permissions(temp_env):
    """A skill requesting destructive or network permissions holds in TESTING awaiting explicit approval."""
    engine = temp_env["engine"]

    gap = CapabilityGap(
        task_id="gap_network_op",
        task_description="Download remote schema",
        missing_capability="remote_schema_fetcher",
        category="missing_procedure",
        severity="blocking",
    )
    prop = engine.propose_skill(gap)
    skill_id = prop["skill_id"]

    steps = [
        SkillStep(
            id="read_local",
            tool="files.read",
            arguments={"path": "schema.json"},
        )
    ]
    high_perms = SkillPermissionScope(filesystem=["."], network=True)

    engine.learn_from_source(
        skill_id=skill_id,
        source_type="documentation",
        source_reference="API Spec",
        workflow_steps=steps,
        permissions=high_perms,
    )

    val = engine.test_and_validate(skill_id, test_inputs=[{"path": "schema.json"}])
    assert val["ok"] is True
    assert val["status"] == LearnedSkillStatus.TESTING
    assert val["requires_approval"] is True


def test_skill_tools_integration_and_verified_execution(temp_env):
    """Tests the orchestrator-facing tools: detect_capability_gap, acquire_and_verify_skill, list_learned_skills."""
    manager = temp_env["manager"]
    tools = {t.name: t for t in build_skill_tools(manager)}

    # 1. detect_capability_gap tool
    detect_tool = tools["detect_capability_gap"]
    det_res = detect_tool.handler(task_description="extract YAML frontmatter header")
    assert det_res["has_gap"] is True
    assert "markdown_frontmatter" in str(det_res["gap"])

    # 2. acquire_and_verify_skill tool
    acquire_tool = tools["acquire_and_verify_skill"]
    acq_res = acquire_tool.handler(
        capability_name="changelog_extractor",
        source_type="repository",
        source_reference="Git Conventional Commits standard",
        steps=[
            {
                "id": "read_log",
                "tool": "files.read",
                "description": "Read commit history",
                "arguments": {"path": "commits.txt"},
            }
        ],
        test_inputs=[{"path": "commits.txt"}],
    )
    assert acq_res["ok"] is True
    assert acq_res["status"] == LearnedSkillStatus.VERIFIED

    # 3. list_learned_skills tool
    list_tool = tools["list_learned_skills"]
    learned_skills = list_tool.handler(status="VERIFIED")
    assert len(learned_skills) >= 1
    assert any("changelog" in s["skill_id"] for s in learned_skills)

    # 4. execute_skill executes the verified skill in dry-run mode
    ws = temp_env["workspace"]
    ws.write_text("commits.txt", "feat: initial commit\nfix: bug fix")
    exec_tool = tools["execute_skill"]
    skill_id = acq_res["skill_id"]
    run_res = exec_tool.handler(skill_id=skill_id, inputs={"path": "commits.txt"}, dry_run=True)
    assert run_res["status"] == "COMPLETED"
    assert run_res["dry_run"] is True
