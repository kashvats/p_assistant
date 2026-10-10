"""
Adversarial Stress Test Suite for Milestone 3 Software Company Implementation.
Directly probes for bypasses across:
1. Frozen test protection (path traversal, relative/absolute mismatch, case insensitivity, edit_file).
2. Task scope tool access (unallowed tools, custom handlers injection, registry tampering).
3. Unapproved spec gating (decomposition blocking, approve_spec spoofing, CompanyWorkflow bypass).
4. Tree depth limits (chain depth > 3, max_depth configuration capping, reparenting).
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from living_assistant.agents.software_company.models import (
    CompanyTask,
    ExecutionBudget,
    TaskNode,
    TaskSpec,
    VerificationVerdict,
)
from living_assistant.agents.software_company.profiles import ProfileLoader
from living_assistant.agents.software_company.task_graph import (
    HierarchicalTaskGraph,
    MaxDepthExceededError,
    TaskGraphError,
)
from living_assistant.agents.software_company.workflow import (
    FrozenTestViolationError,
    SoftwareCompanyWorkflow,
    SpecNotApprovedError,
    TaskScopedToolFactory,
    CompanyWorkflow,
)
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.tools.registry import ToolRegistry
from living_assistant.tools.base import Tool


# ============================================================================
# 1. FROZEN TEST PROTECTION TESTS
# ============================================================================

def test_frozen_test_exact_relative_match_blocked(tmp_path: Path):
    """Baseline: Identical relative path is blocked."""
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    target = "tests/test_frozen.py"
    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=[target],
    )
    with pytest.raises(FrozenTestViolationError):
        reg.get("write_file").handler(path=target, content="cheat")


def test_frozen_test_bypass_via_dot_dot_traversal(tmp_path: Path):
    """
    CRITICAL VULNERABILITY CHECK:
    Can a developer overwrite a frozen test using 'tests/../tests/test_frozen.py'?
    """
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    frozen_rel = "tests/test_frozen.py"
    actual_file = ws.resolve(frozen_rel)
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    actual_file.write_text("ORIGINAL_SAFE_TEST", encoding="utf-8")

    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=[frozen_rel],
    )

    # Attack: Path traversal resolves to the exact same file within workspace
    traversal_path = "tests/../tests/test_frozen.py"

    bypassed = False
    try:
        reg.get("write_file").handler(path=traversal_path, content="OVERWRITTEN_MALICIOUS")
        bypassed = True
    except FrozenTestViolationError:
        bypassed = False

    # Check file on disk
    disk_content = actual_file.read_text(encoding="utf-8")
    assert not bypassed, f"BYPASS DETECTED! Frozen test was overwritten with: '{disk_content}'"
    assert disk_content == "ORIGINAL_SAFE_TEST"


def test_frozen_test_bypass_absolute_frozen_vs_relative_write(tmp_path: Path):
    """
    CRITICAL VULNERABILITY CHECK:
    If frozen_test_files contains absolute path (e.g. from workspace.resolve()),
    can a developer overwrite it by passing a relative path?
    """
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    actual_file = ws.resolve("tests/test_cart.py")
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    actual_file.write_text("ORIGINAL_TEST_CODE", encoding="utf-8")

    # Registration uses absolute path (as done in test_e2e_implement_cart_vertical_slice)
    frozen_abs = str(actual_file)
    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=[frozen_abs],
    )

    # Developer writes using relative path
    bypassed = False
    try:
        reg.get("write_file").handler(path="tests/test_cart.py", content="MALICIOUS_CHEAT")
        bypassed = True
    except FrozenTestViolationError:
        bypassed = False

    disk_content = actual_file.read_text(encoding="utf-8")
    assert not bypassed, f"BYPASS DETECTED! Relative path bypassed absolute frozen test file. Disk: '{disk_content}'"
    assert disk_content == "ORIGINAL_TEST_CODE"


def test_frozen_test_bypass_relative_frozen_vs_absolute_write(tmp_path: Path):
    """
    CRITICAL VULNERABILITY CHECK:
    If frozen_test_files contains relative path,
    can a developer overwrite it by passing an absolute path?
    """
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    actual_file = ws.resolve("tests/test_cart.py")
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    actual_file.write_text("ORIGINAL_TEST_CODE", encoding="utf-8")

    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=["tests/test_cart.py"],
    )

    # Developer writes using absolute path
    bypassed = False
    try:
        reg.get("write_file").handler(path=str(actual_file), content="MALICIOUS_CHEAT")
        bypassed = True
    except FrozenTestViolationError:
        bypassed = False

    disk_content = actual_file.read_text(encoding="utf-8")
    assert not bypassed, f"BYPASS DETECTED! Absolute path bypassed relative frozen test file. Disk: '{disk_content}'"
    assert disk_content == "ORIGINAL_TEST_CODE"


def test_frozen_test_bypass_case_variation_on_windows(tmp_path: Path):
    """
    CRITICAL VULNERABILITY CHECK:
    On Windows NTFS (case-insensitive), can a developer overwrite frozen test
    by changing case (e.g. 'TESTS/test_frozen.py')?
    """
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    actual_file = ws.resolve("tests/test_frozen.py")
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    actual_file.write_text("ORIGINAL_TEST", encoding="utf-8")

    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=["tests/test_frozen.py"],
    )

    case_attack_path = "Tests/test_frozen.py"
    bypassed = False
    try:
        reg.get("write_file").handler(path=case_attack_path, content="OVERWRITTEN_BY_CASE")
        bypassed = True
    except FrozenTestViolationError:
        bypassed = False

    disk_content = actual_file.read_text(encoding="utf-8")
    assert not bypassed, f"BYPASS DETECTED! Case variation bypassed frozen test file on Windows. Disk: '{disk_content}'"
    assert disk_content == "ORIGINAL_TEST"


def test_frozen_test_edit_file_traversal_bypass(tmp_path: Path):
    """
    CRITICAL VULNERABILITY CHECK:
    Can edit_file tamper with a frozen test via path traversal?
    """
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    actual_file = ws.resolve("tests/test_frozen.py")
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    actual_file.write_text("assert False, 'must fail'", encoding="utf-8")

    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=["tests/test_frozen.py"],
    )

    traversal_path = "tests/../tests/test_frozen.py"
    bypassed = False
    try:
        reg.get("edit_file").handler(path=traversal_path, old_str="assert False", new_str="assert True")
        bypassed = True
    except FrozenTestViolationError:
        bypassed = False

    disk_content = actual_file.read_text(encoding="utf-8")
    assert not bypassed, f"BYPASS DETECTED! edit_file bypassed frozen test file. Disk: '{disk_content}'"
    assert "assert True" not in disk_content


# ============================================================================
# 2. TASK SCOPE / TOOL PERMISSION TESTS
# ============================================================================

def test_task_scope_developer_cannot_invoke_unallowed_tools(tmp_path: Path):
    """Verify backend_dev cannot access verifier or manager tools."""
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    reg = TaskScopedToolFactory.create_registry(profile=profile, workspace=ws)

    # Disallowed tools for backend_dev
    assert reg.get("certify_completion") is None
    assert reg.get("verify_evidence") is None
    assert reg.get("generate_spec") is None
    assert reg.get("decompose_task") is None
    assert reg.get("browser_snapshot") is None


def test_task_scope_custom_handler_injection_blocked(tmp_path: Path):
    """
    Verify passing custom handlers for tools NOT in allowed_tools
    does NOT register them into the registry.
    """
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    injected = {"certify_completion": lambda v: {"certified": True}}
    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        custom_handlers=injected,
    )
    assert reg.get("certify_completion") is None


# ============================================================================
# 3. UNAPPROVED SPEC DECOMPOSITION GATING TESTS
# ============================================================================

def test_unapproved_spec_blocks_decomposition(tmp_path: Path):
    """Verify decompose_task raises SpecNotApprovedError if unapproved."""
    ws = Workspace([tmp_path])
    wf = SoftwareCompanyWorkflow(workspace=ws)
    graph = HierarchicalTaskGraph()

    task, spec = wf.intake_request(
        task_id="t1",
        title="Unapproved Task",
        goal="Build something",
        requirements=["R1"],
        acceptance_criteria=["AC1"],
        interface_contracts={},
        frozen_test_files=[],
    )
    assert not spec.approved_by_user

    with pytest.raises(SpecNotApprovedError):
        wf.decompose_task(task, graph)


def test_spec_none_blocks_decomposition(tmp_path: Path):
    """Verify decompose_task raises SpecNotApprovedError if task.spec is None."""
    ws = Workspace([tmp_path])
    wf = SoftwareCompanyWorkflow(workspace=ws)
    graph = HierarchicalTaskGraph()

    task = CompanyTask(id="t_nospec", title="No Spec")
    task.spec = None

    with pytest.raises(SpecNotApprovedError):
        wf.decompose_task(task, graph)


# ============================================================================
# 4. TREE DEPTH / MAX DEPTH ENFORCEMENT TESTS
# ============================================================================

def test_tree_depth_exceeding_max_depth_blocked():
    """Verify adding nodes at depth > 3 raises MaxDepthExceededError."""
    graph = HierarchicalTaskGraph(max_depth=3)

    n0 = graph.add_node("n0", "Root", "manager", parent_id=None)
    assert n0.depth == 0

    n1 = graph.add_node("n1", "Child 1", "manager", parent_id="n0")
    assert n1.depth == 1

    n2 = graph.add_node("n2", "Child 2", "backend_dev", parent_id="n1")
    assert n2.depth == 2

    n3 = graph.add_node("n3", "Child 3", "backend_dev", parent_id="n2")
    assert n3.depth == 3

    # Attempt depth 4 (> 3)
    with pytest.raises(MaxDepthExceededError):
        graph.add_node("n4", "Child 4", "backend_dev", parent_id="n3")


def test_tree_depth_configured_max_depth_capping():
    """
    Check whether max_depth parameter can be set > 3 without restriction.
    Directive B1 specifies max depth 2 / 3.
    """
    graph = HierarchicalTaskGraph(max_depth=5)
    # Does the graph allow setting max_depth > 3?
    # If it does, depth > 3 can be created when max_depth > 3 is configured.
    assert graph.max_depth <= 3, f"max_depth was configured to {graph.max_depth} exceeding max_depth limit 3"
