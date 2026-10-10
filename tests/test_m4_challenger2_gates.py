"""
Challenger 2 Empirical Verification Suite for Milestone 4 Gates.
Tests the 4 adversarial missions:
1. Relative path writes, mixed case writes, and symlinks against `_check_frozen`.
2. Direct mutation of `task.status = "COMPLETED"` on `CompanyTask`.
3. Initializing `HierarchicalTaskGraph(max_depth=10)` and depth capping.
4. Quoted command splitting in `TestHarness.run_tests` via `shlex.split`.
"""

import os
import shlex
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.agents.software_company.models import (
    CompanyTask,
    ExecutionBudget,
    VerificationVerdict,
    QAReport,
)
from living_assistant.agents.software_company.profiles import ProfileLoader
from living_assistant.agents.software_company.task_graph import (
    HierarchicalTaskGraph,
    MaxDepthExceededError,
)
from living_assistant.agents.software_company.workflow import (
    FrozenTestViolationError,
    TaskScopedToolFactory,
    TestHarness,
)


# ============================================================================
# MISSION 1: _check_frozen CONFINEMENT & TAMPER RESISTANCE
# ============================================================================

def test_frozen_relative_path_writes_blocked(tmp_path: Path):
    """Attempt writes using various relative path variations against frozen file."""
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    test_file = ws.resolve("tests/sub/test_suite.py")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_original(): pass", encoding="utf-8")

    # Registered with relative path
    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=["tests/sub/test_suite.py"],
    )

    variations = [
        "tests/sub/test_suite.py",
        "./tests/sub/test_suite.py",
        "tests/sub/../sub/test_suite.py",
        "tests/../tests/sub/test_suite.py",
        "tests\\sub\\test_suite.py",
        ".\\tests\\sub\\test_suite.py",
    ]

    for rel_path in variations:
        with pytest.raises(FrozenTestViolationError):
            reg.get("write_file").handler(path=rel_path, content="hacked")

        with pytest.raises(FrozenTestViolationError):
            reg.get("edit_file").handler(path=rel_path, old_str="def test_original", new_str="def test_hacked")

    assert test_file.read_text(encoding="utf-8") == "def test_original(): pass"


def test_frozen_mixed_case_writes_blocked(tmp_path: Path):
    """Attempt writes using mixed case path variations against frozen file."""
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    test_file = ws.resolve("tests/test_cart.py")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("ORIGINAL_CONTENT", encoding="utf-8")

    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=["tests/test_cart.py"],
    )

    case_variations = [
        "Tests/test_cart.py",
        "tests/Test_Cart.py",
        "TESTS/TEST_CART.PY",
        "tests/test_cart.PY",
        "Tests/Test_Cart.Py",
    ]

    for path_var in case_variations:
        with pytest.raises(FrozenTestViolationError):
            reg.get("write_file").handler(path=path_var, content="MALICIOUS_OVERWRITE")

        with pytest.raises(FrozenTestViolationError):
            reg.get("edit_file").handler(path=path_var, old_str="ORIGINAL", new_str="HACKED")

    assert test_file.read_text(encoding="utf-8") == "ORIGINAL_CONTENT"


def test_frozen_symlink_writes_blocked(tmp_path: Path):
    """Attempt writes through symlinks or hardlink aliases pointing to frozen files."""
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    test_file = ws.resolve("tests/test_frozen.py")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("CANONICAL_TEST_FILE", encoding="utf-8")

    link_file = ws.resolve("tests/symlink_alias.py")
    using_hardlink = False
    try:
        link_file.symlink_to(test_file)
    except (OSError, NotImplementedError):
        try:
            import os
            os.link(test_file, link_file)
            using_hardlink = True
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"Links not supported in current environment/filesystem permissions: {exc}")

    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=["tests/test_frozen.py"],
    )

    # Attempting to write to the alias should resolve to canonical test_file and be blocked
    with pytest.raises(FrozenTestViolationError):
        reg.get("write_file").handler(path="tests/symlink_alias.py", content="TAMPERED")

    with pytest.raises(FrozenTestViolationError):
        reg.get("edit_file").handler(path="tests/symlink_alias.py", old_str="CANONICAL", new_str="TAMPERED")

    assert test_file.read_text(encoding="utf-8") == "CANONICAL_TEST_FILE"


def test_frozen_uncreated_file_writes_blocked(tmp_path: Path):
    """Attempt writes when frozen file does not yet exist on disk."""
    ws = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    target = "tests/not_yet_created.py"
    reg = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=ws,
        frozen_test_files=[target],
    )

    with pytest.raises(FrozenTestViolationError):
        reg.get("write_file").handler(path=target, content="PREEMPTIVE_CREATION")


# ============================================================================
# MISSION 2: CompanyTask.status MUTATION ATTACKS
# ============================================================================

def test_company_task_direct_status_completed_raises_permission_error():
    """Verify task.status = 'COMPLETED' directly raises PermissionError."""
    task = CompanyTask(id="task_mut", title="Mutation Attack")
    assert task.status == "PENDING"

    # Direct attribute assignment
    with pytest.raises(PermissionError) as exc_info:
        task.status = "COMPLETED"
    assert "Direct assignment of status='COMPLETED' is prohibited" in str(exc_info.value)
    assert task.status == "PENDING"


def test_company_task_set_status_completed_raises_permission_error():
    """Verify task.set_status('COMPLETED') raises PermissionError."""
    task = CompanyTask(id="task_set", title="Set Status Attack")

    with pytest.raises(PermissionError) as exc_info:
        task.set_status("COMPLETED")
    assert "Direct transition to COMPLETED is prohibited" in str(exc_info.value)

    with pytest.raises(PermissionError):
        task.set_status("COMPLETED", caller_role="verifier")

    assert task.status == "PENDING"


def test_company_task_allowed_status_transitions():
    """Verify normal statuses can be set directly or via set_status."""
    task = CompanyTask(id="task_norm", title="Normal Transitions")

    task.status = "PLANNING"
    assert task.status == "PLANNING"

    task.status = "IN_PROGRESS"
    assert task.status == "IN_PROGRESS"

    task.set_status("QA_REVIEW")
    assert task.status == "QA_REVIEW"

    task.set_status("FAILED")
    assert task.status == "FAILED"


def test_company_task_complete_role_and_evidence_enforcement():
    """Verify complete() strictly enforces verifier role and registered artifacts."""
    task = CompanyTask(id="task_comp", title="Completion Verification")
    task.register_artifact("artifact_valid", {"file": "output.py"})

    verdict_valid = VerificationVerdict(
        verdict_id="v_ok",
        status="VERIFIED",
        criteria_met=[{"criterion": "C1", "artifact_id": "artifact_valid"}],
        verified_by="verifier",
    )

    # 1. Non-verifier role rejected
    for unauthorized_role in ["developer", "manager", "qa", "attacker", "architect"]:
        with pytest.raises(PermissionError):
            task.complete(verdict_valid, caller_role=unauthorized_role)
        assert task.status != "COMPLETED"

    # 2. Missing artifact rejected
    verdict_missing_art = VerificationVerdict(
        verdict_id="v_missing",
        status="VERIFIED",
        criteria_met=[{"criterion": "C1", "artifact_id": "nonexistent_artifact"}],
        verified_by="verifier",
    )
    with pytest.raises(ValueError):
        task.complete(verdict_missing_art, caller_role="verifier")
    assert task.status != "COMPLETED"

    # 3. Legitimate verifier succeeds
    task.complete(verdict_valid, caller_role="verifier")
    assert task.status == "COMPLETED"


# ============================================================================
# MISSION 3: HierarchicalTaskGraph MAX_DEPTH ENFORCEMENT
# ============================================================================

def test_hierarchical_task_graph_max_depth_capped_at_3():
    """Verify initializing HierarchicalTaskGraph(max_depth=10) caps max_depth at 3."""
    graph = HierarchicalTaskGraph(max_depth=10)
    assert graph.max_depth == 3
    assert graph.budget.max_depth <= 3

    graph_large = HierarchicalTaskGraph(max_depth=999)
    assert graph_large.max_depth == 3
    assert graph_large.budget.max_depth <= 3


def test_execution_budget_max_depth_validation():
    """Verify ExecutionBudget validates max_depth <= 3 via Pydantic Field(le=3)."""
    with pytest.raises(ValidationError):
        ExecutionBudget(max_depth=10)

    with pytest.raises(ValidationError):
        ExecutionBudget(max_depth=4)

    valid_budget = ExecutionBudget(max_depth=3)
    assert valid_budget.max_depth == 3


def test_hierarchical_task_graph_depth_exhaustion():
    """Verify DAG rejects adding nodes beyond depth 3."""
    graph = HierarchicalTaskGraph(max_depth=3)

    n0 = graph.add_node("r0", "Root", "manager", parent_id=None)
    assert n0.depth == 0

    n1 = graph.add_node("c1", "Level 1", "backend_dev", parent_id="r0")
    assert n1.depth == 1

    n2 = graph.add_node("c2", "Level 2", "backend_dev", parent_id="c1")
    assert n2.depth == 2

    n3 = graph.add_node("c3", "Level 3", "backend_dev", parent_id="c2")
    assert n3.depth == 3

    # Attempt depth 4 -> Must be blocked
    with pytest.raises(MaxDepthExceededError):
        graph.add_node("c4", "Level 4", "backend_dev", parent_id="c3")


# ============================================================================
# MISSION 4: TestHarness QUOTED COMMAND SPLITTING
# ============================================================================

def test_shlex_split_behavior_on_windows_vs_posix():
    """
    Test how shlex.split(test_command, posix=(os.name != 'nt')) behaves
    with quoted arguments.
    """
    posix_flag = (os.name != "nt")

    # Double quotes command
def test_shlex_split_behavior_on_windows_vs_posix():
    """
    Test how shlex.split(test_command, posix=(os.name != 'nt')) behaves
    with quoted arguments.
    """
    posix_flag = (os.name != "nt")

    # Double quotes command: on Windows posix=False retains literal quotes in tokens
    cmd1 = 'python -c "import sys; sys.exit(0)"'
    args1 = shlex.split(cmd1, posix=posix_flag)
    assert args1[0] == "python"
    assert args1[1] == "-c"
    if not posix_flag:
        # On Windows (posix=False), shlex RETAINS the literal quotes:
        assert args1[2] == '"import sys; sys.exit(0)"', f"Expected literal quotes retained, got {args1[2]}"
    else:
        assert args1[2] == "import sys; sys.exit(0)"

    # Pytest filter with single quotes: on Windows posix=False keeps literal quotes in token
    cmd_single = "pytest -k 'test_a or test_b'"
    args_single = shlex.split(cmd_single, posix=posix_flag)
    if not posix_flag:
        # On Windows (posix=False), shlex keeps literal single quotes within the token:
        assert args_single == ['pytest', '-k', "'test_a or test_b'"]
    else:
        assert args_single == ['pytest', '-k', 'test_a or test_b']


def test_test_harness_quoted_executable_fails_to_spawn_on_windows(tmp_path: Path):
    """
    EMPIRICAL BUG REPRODUCTION:
    When test_command has a quoted executable path (e.g. '"path/to/python.exe" ...'),
    shlex.split with posix=False preserves the outer quotes on the executable token.
    subprocess.run(['"path/to/python.exe"', ...]) fails with WinError 2!
    """
    ws = Workspace([tmp_path])
    harness = TestHarness(ws)

    # Quoted executable path
    cmd = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
    report = harness.run_tests(task_id="t_test", test_command=cmd)

    if os.name == "nt":
        # On Windows, this FAILS to spawn because cmd_args[0] includes literal quote characters!
        assert report.exit_code == 1
        assert report.status == "REJECTED"
        assert "Test execution failed to spawn: [WinError 2]" in report.test_output


def test_test_harness_quoted_inline_code_turns_into_no_op_string_literal(tmp_path: Path):
    """
    EMPIRICAL BUG REPRODUCTION:
    When python -c "...code..." is passed, posix=False causes shlex.split to retain
    double quotes: cmd_args[2] == '"import sys; sys.exit(1)"'.
    On Windows, subprocess.list2cmdline escapes it as: -c "\"import sys; sys.exit(1)\"".
    Python receives it as a string literal expression (no-op), so sys.exit(1) NEVER RUNS,
    and Python exits 0! TestHarness erroneously reports ACCEPTED!
    """
    ws = Workspace([tmp_path])
    harness = TestHarness(ws)

    # Command intended to exit 1
    cmd = f'{sys.executable} -c "import sys; sys.exit(1)"'
    report = harness.run_tests(task_id="t_fail", test_command=cmd)

    if os.name == "nt":
        # BUG: It exited 0 because python executed a string literal statement instead of the code!
        assert report.exit_code == 0
        assert report.status == "ACCEPTED"


def test_test_harness_genuine_failure_detected_without_inline_quotes(tmp_path: Path):
    """
    Verify TestHarness detects genuine test failure when not corrupted by inline quotes
    (e.g., executing a command or python script returning non-zero exit code).
    """
    ws = Workspace([tmp_path])
    harness = TestHarness(ws)

    # Write a test script file that exits 1
    fail_script = ws.resolve("fail_script.py")
    fail_script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")

    cmd = f"{sys.executable} fail_script.py"
    report = harness.run_tests(task_id="t_fail_script", test_command=cmd)

    assert isinstance(report, QAReport)
    assert report.exit_code == 1
    assert report.status == "REJECTED"
    assert report.failed >= 1

