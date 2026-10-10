"""
Milestone 6 Adversarial Stress-Testing Suite: Independent QA Rejection Gate, Auto-Rollback & Edge Cases.
Agent: Challenger M6-1 (teamwork_preview_challenger)

Exhaustive empirical testing of:
1. QA Retry Limit Exhaustion & Automated Baseline Rollback on Disk (max_retries=3).
2. Failing Test Suite Detection with Negative or Non-Zero Exit Codes & Zero-Test Edge Cases.
3. Forged and Uncertified QA Report Gating (missing harness flag, empty/whitespace log_hash, test manipulation).
4. Frozen Path Confinement & Edge Cases (whitespace, case sensitivity, relative traversals, symlinks, hardlinks).
5. Verifier Authorization & Artifact Integrity Invariants.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from living_assistant.agents.software_company.change_manager import GitChangeManager
from living_assistant.agents.software_company.models import (
    CompanyPlan,
    CompanyTask,
    CriteriaEvidence,
    ExecutionBudget,
    QAReport,
    RoleProfile,
    TaskSpec,
    VerificationVerdict,
)
from living_assistant.agents.software_company.roles.verifier import FinalVerifier
from living_assistant.agents.software_company.workflow import (
    CompanyWorkflow,
    ForgedQAReportViolation,
    FrozenTestViolationError,
    QARejectionError,
    QARetryLimitExceededError,
    QARunnerHarness,
    SoftwareCompanyWorkflow,
    TestHarness,
    UnauthorizedCompletionViolation,
    VerificationError,
    WorkflowRoleToolFactory,
)
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.security.permissions import (
    Risk,
    TaskScope,
    TaskScopedPermissionEngine,
)


@pytest.fixture
def adversarial_workspace(tmp_path: Path) -> tuple[Workspace, Path]:
    repo_dir = tmp_path / "adversarial_m6_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "challenger_m6_1@example.com"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Challenger M6-1"], cwd=str(repo_dir), capture_output=True, check=True)

    # Initial baseline file
    baseline_file = repo_dir / "service_core.py"
    baseline_file.write_text("def run_core():\n    return 'BASELINE_ACTIVE'\n", encoding="utf-8")
    subprocess.run(["git", "add", "service_core.py"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial baseline core commit"], cwd=str(repo_dir), capture_output=True, check=True)

    return Workspace([repo_dir]), repo_dir


# =============================================================================
# Suite 1: QA Retry Limit Exhaustion & Automated Baseline Rollback on Disk
# =============================================================================


def test_adversarial_qa_retry_exhaustion_rollback_to_clean_baseline(adversarial_workspace: tuple[Workspace, Path]):
    """
    Adversarial Scenario 1:
    A developer repeatedly fails QA until max_retries (3) is exceeded.
    Verify:
    1. QARetryLimitExceededError is strictly raised on the 4th consecutive failure.
    2. All intermediate mutations (corrupted tracked files, untracked clutter files, nested directories)
       are completely rolled back to the clean baseline on disk.
    """
    workspace, repo_dir = adversarial_workspace
    cm = GitChangeManager(workspace=workspace)
    workflow = SoftwareCompanyWorkflow(workspace=workspace, max_retries=3, change_manager=cm)

    task_id = "task_adv_retry_exhaustion"
    core_file = repo_dir / "service_core.py"
    initial_content = core_file.read_text(encoding="utf-8")

    # Baseline established prior to task execution
    cm.establish_baseline(task_id)

    task, spec = workflow.intake_request(
        task_id=task_id,
        title="Payment Engine Refactoring",
        goal="Refactor payment processing without breaking contracts",
        requirements=["Reliable payments"],
        acceptance_criteria=["Pass automated QA test suite"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    # Developer creates dirty changes across multiple cycles
    remediation_calls = 0
    untracked_stray = repo_dir / "untracked_debug_dump.log"
    nested_dir = repo_dir / "temp_patch"
    nested_file = nested_dir / "scratch.py"

    def faulty_developer_remediation(t: CompanyTask, rep: QAReport) -> None:
        nonlocal remediation_calls
        remediation_calls += 1
        # Each remediation attempt mutates the code further and drops clutter
        core_file.write_text(f"def run_core():\n    raise RuntimeError('CORRUPTED_CYCLE_{remediation_calls}')\n", encoding="utf-8")
        untracked_stray.write_text(f"DEBUG DATA CYCLE {remediation_calls}\n", encoding="utf-8")
        nested_dir.mkdir(parents=True, exist_ok=True)
        nested_file.write_text(f"# Patch {remediation_calls}\n", encoding="utf-8")

    def perpetually_failing_qa() -> dict[str, Any]:
        return {
            "exit_code": 1,
            "total": 3,
            "passed": 1,
            "failed": 2,
            "failures": ["test_core_payment", "test_core_refund"],
            "output": "FAILED: test_core_payment\nFAILED: test_core_refund\n2 failed, 1 passed",
            "feedback": "Core payment assertions failed.",
        }

    # Initial defect injection prior to first QA run
    core_file.write_text("def run_core():\n    raise RuntimeError('INITIAL_DEFECT')\n", encoding="utf-8")

    # Run remediation loop: max_retries=3 means 3 retries permitted (4 total attempts)
    with pytest.raises(QARetryLimitExceededError) as exc_info:
        workflow.run_qa_remediation_loop(
            task=task,
            qa_suite_fn=perpetually_failing_qa,
            developer_remediation_fn=faulty_developer_remediation,
        )

    # Verify exception details
    assert "retry limit exceeded" in str(exc_info.value).lower()
    assert task.budget.current_retries == 4
    assert remediation_calls == 3

    # EMPIRICAL DISK STATE VERIFICATION:
    # 1. Tracked file restored to clean baseline content
    restored_content = core_file.read_text(encoding="utf-8")
    assert restored_content == initial_content, f"Expected initial content, got: {restored_content}"
    assert "CORRUPTED" not in restored_content
    assert "INITIAL_DEFECT" not in restored_content

    # 2. Untracked clutter files unlinked and removed
    assert not untracked_stray.exists(), f"Untracked file '{untracked_stray}' was not removed by rollback."
    assert not nested_file.exists(), f"Untracked nested file '{nested_file}' was not removed by rollback."

    # 3. Git status confirms clean working tree
    git_status = cm.get_git_status()
    uncommitted = git_status.get("untracked_files", []) + git_status.get("uncommitted_files", [])
    assert len(uncommitted) == 0 or all("software_company_eval" in str(u) for u in uncommitted), (
        f"Working tree has uncommitted files after rollback: {uncommitted}"
    )


def test_adversarial_qa_retry_boundary_zero_retries(adversarial_workspace: tuple[Workspace, Path]):
    """Boundary test: max_retries=0 immediately triggers rollback on first failure."""
    workspace, repo_dir = adversarial_workspace
    cm = GitChangeManager(workspace=workspace)
    workflow = SoftwareCompanyWorkflow(workspace=workspace, max_retries=0, change_manager=cm)

    task_id = "task_adv_zero_retries"
    core_file = repo_dir / "service_core.py"
    initial_content = core_file.read_text(encoding="utf-8")
    cm.establish_baseline(task_id)

    task, spec = workflow.intake_request(
        task_id=task_id,
        title="Zero Retry Task",
        goal="Task with zero retry tolerance",
        requirements=["Zero fail"],
        acceptance_criteria=["Pass QA"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    core_file.write_text("def run_core(): return 'MUTATED_FAIL'\n", encoding="utf-8")

    with pytest.raises(QARetryLimitExceededError):
        workflow.run_qa_remediation_loop(
            task=task,
            qa_suite_fn=lambda: {"exit_code": 1, "total": 1, "passed": 0, "failed": 1, "failures": ["t1"]},
            developer_remediation_fn=lambda t, r: None,
        )

    # Reverted immediately
    assert core_file.read_text(encoding="utf-8") == initial_content


# =============================================================================
# Suite 2: Negative and Non-Zero Exit Code Gating & Test Parsing
# =============================================================================


@pytest.mark.parametrize("exit_code", [-15, -9, -1, 1, 2, 124, 127, 255])
def test_adversarial_qa_runner_strictly_rejects_non_zero_and_negative_exit_codes(exit_code: int):
    """
    Adversarial Scenario 2a:
    Verifies that any negative exit code (signals: SIGKILL, SIGTERM) or non-zero exit code
    (errors, timeouts, syntax crashes) strictly produces status REJECTED.
    """
    report = QAReport.create_from_runner(
        report_id=f"rep_exit_{abs(exit_code)}",
        command="pytest tests/adversarial_suite.py",
        exit_code=exit_code,
        output_log=f"Process terminated with exit code {exit_code}",
        total_tests=5,
        passed=0,
        failed=5,
        failures=[{"test": "test_crash", "error": f"Signal or exit code {exit_code}"}],
        feedback=f"Terminated with code {exit_code}",
        task_id="task_exit_code_test",
    )

    assert report.status == "REJECTED"
    assert report.exit_code == exit_code

    # Pillar 2 verifier verification
    dummy_ws = Workspace([Path(".")])
    verifier = FinalVerifier(workspace=dummy_ws)
    task = CompanyTask(id="task_exit_code_test", title="Exit Code Test")

    ok, issues = verifier.verify_test_execution(task, qa_report=report)
    assert ok is False
    assert any(f"exit code {exit_code}" in iss for iss in issues)


def test_adversarial_qa_runner_rejects_zero_exit_code_with_failed_tests():
    """
    Adversarial Scenario 2b:
    A malformed test runner exits 0 but reports failed tests > 0.
    Verify that QA status is strictly REJECTED.
    """
    report = QAReport.create_from_runner(
        report_id="rep_zero_exit_with_failures",
        command="pytest",
        exit_code=0,
        output_log="1 failed, 2 passed",
        total_tests=3,
        passed=2,
        failed=1,
        failures=["test_failing_case"],
        task_id="task_inconsistent_results",
    )
    assert report.status == "REJECTED"


def test_adversarial_qa_runner_rejects_zero_total_tests():
    """
    Adversarial Scenario 2c:
    A test runner exits 0 but collected zero tests (e.g. pytest collected 0 items).
    Verify that QA status is strictly REJECTED and cannot pass verification.
    """
    report = QAReport.create_from_runner(
        report_id="rep_zero_tests",
        command="pytest tests/empty_suite.py",
        exit_code=0,
        output_log="collected 0 items\n0 passed in 0.01s",
        total_tests=0,
        passed=0,
        failed=0,
        task_id="task_empty_suite",
    )
    assert report.status == "REJECTED"

    dummy_ws = Workspace([Path(".")])
    verifier = FinalVerifier(workspace=dummy_ws)
    task = CompanyTask(id="task_empty_suite", title="Empty Suite Task")

    ok, issues = verifier.verify_test_execution(task, qa_report=report)
    assert ok is False
    assert any("total=0" in iss for iss in issues)


def test_adversarial_test_harness_negative_exit_code_subprocess(adversarial_workspace: tuple[Workspace, Path]):
    """
    Adversarial Scenario 2d:
    TestHarness execution when subprocess returns negative returncode (e.g. killed by SIGKILL / -9).
    """
    workspace, _ = adversarial_workspace
    harness = TestHarness(workspace=workspace)

    mock_proc = MagicMock()
    mock_proc.returncode = -9
    mock_proc.stdout = ""
    mock_proc.stderr = "Killed: 9"

    with patch("subprocess.run", return_value=mock_proc):
        report = harness.run_tests(task_id="task_sigkill_test", test_command="pytest tests/slow.py")

    assert report.status == "REJECTED"
    assert report.exit_code == -9
    assert report.generated_by_harness is True
    assert report.log_hash is not None and len(report.log_hash) == 64


# =============================================================================
# Suite 3: Forged & Uncertified QA Report Gating
# =============================================================================


def test_adversarial_forged_qa_report_missing_harness_flag():
    """
    Adversarial Scenario 3a:
    Developer crafts a fake QA report with generated_by_harness=False.
    Verify:
    1. workflow.validate_qa_report raises ForgedQAReportViolation.
    2. FinalVerifier flags 'Security Alert' and rejects verification.
    """
    fake_report = QAReport(
        report_id="forged_rep_01",
        task_id="task_forged_01",
        status="ACCEPTED",
        total_tests=10,
        passed=10,
        failed=0,
        exit_code=0,
        log_hash="hash_fake_001",
        generated_by_harness=False,  # Uncertified / forged!
    )

    dummy_ws = Workspace([Path(".")])
    workflow = CompanyWorkflow(workspace=dummy_ws, tool_registry=MagicMock())

    # Direct validation raises ForgedQAReportViolation
    with pytest.raises(ForgedQAReportViolation) as exc_info:
        workflow.validate_qa_report(fake_report)
    assert "generated_by_harness is False" in str(exc_info.value)

    # FinalVerifier also rejects with Security Alert
    verifier = FinalVerifier(workspace=dummy_ws)
    task = CompanyTask(id="task_forged_01", title="Forged Task")
    verdict = verifier.verify_task(task=task, qa_report=fake_report)

    assert verdict.status in {"REJECTED", "INCOMPLETE"}
    assert verdict.evidence_valid is False
    assert any("Security Alert" in iss for iss in verdict.remaining_issues)


@pytest.mark.parametrize("invalid_hash", ["", "   ", "\t\n", None])
def test_adversarial_forged_qa_report_empty_or_whitespace_log_hash(invalid_hash: str | None):
    """
    Adversarial Scenario 3b:
    Developer submits a QA report with an empty, whitespace, or None log_hash.
    Verify:
    1. workflow.validate_qa_report raises ForgedQAReportViolation.
    2. FinalVerifier Pillar 2 rejects test execution.
    """
    dummy_ws = Workspace([Path(".")])
    workflow = CompanyWorkflow(workspace=dummy_ws, tool_registry=MagicMock())

    report = QAReport(
        report_id="rep_invalid_hash",
        task_id="task_hash_test",
        status="ACCEPTED",
        total_tests=5,
        passed=5,
        failed=0,
        exit_code=0,
        log_hash=invalid_hash or "",
        generated_by_harness=True,
    )

    with pytest.raises(ForgedQAReportViolation) as exc_info:
        workflow.validate_qa_report(report)
    assert "missing or invalid log hash" in str(exc_info.value)

    verifier = FinalVerifier(workspace=dummy_ws)
    task = CompanyTask(id="task_hash_test", title="Hash Test")
    ok, issues = verifier.verify_test_execution(task, qa_report=report)
    assert ok is False
    assert any("log hash" in iss.lower() for iss in issues)


@pytest.mark.parametrize(
    "manipulated_diff,manipulated_content,expected_keyword",
    [
        ("+ @pytest.mark.skip\n+ def test_feature(): pass", "@pytest.mark.skip\ndef test(): pass", "skip"),
        ("+ @unittest.skip('temporarily disabled')\n+ def test_f(): pass", "@unittest.skip\ndef test(): pass", "skip"),
        ("- assert result == 42\n+ pass", "def test_f(): pass", "assertion"),
        ("+ except Exception: pass", "try:\n    do_work()\nexcept Exception: pass", "exception"),
        ("+ except: pass", "try:\n    do_work()\nexcept: pass", "exception"),
    ],
)
def test_adversarial_test_manipulation_defense(
    manipulated_diff: str, manipulated_content: str, expected_keyword: str
):
    """
    Adversarial Scenario 3c:
    Developer attempts to pass QA by sneaking in test skips, removing assertions,
    or swallowing broad exceptions.
    Verify that FinalVerifier Pillar 2 detects manipulation and blocks completion.
    """
    dummy_ws = Workspace([Path(".")])
    verifier = FinalVerifier(workspace=dummy_ws)
    task = CompanyTask(id="task_tamper", title="Tamper Test")

    clean_report = QAReport(
        report_id="rep_tamper",
        task_id=task.id,
        exit_code=0,
        status="ACCEPTED",
        total_tests=2,
        passed=2,
        failed=0,
        log_hash="hash_clean",
        generated_by_harness=True,
    )

    ok, issues = verifier.verify_test_execution(
        task=task,
        qa_report=clean_report,
        test_diff=manipulated_diff,
        test_content=manipulated_content,
    )
    assert ok is False
    assert any("Test Manipulation Gate Violation" in iss for iss in issues)
    assert any(expected_keyword in iss.lower() for iss in issues)


# =============================================================================
# Suite 4: Frozen Test Path Protection & Adversarial Edge Cases
# =============================================================================


def test_adversarial_frozen_path_whitespace_edge_cases(adversarial_workspace: tuple[Workspace, Path]):
    """
    Adversarial Scenario 4a:
    Agent attempts to modify a frozen test file using whitespace obfuscation:
    leading/trailing spaces, tab characters, or interior whitespace.
    Verify that FrozenTestViolationError is raised.
    """
    workspace, repo_dir = adversarial_workspace
    frozen_test = repo_dir / "tests" / "test_frozen_api.py"
    frozen_test.parent.mkdir(parents=True, exist_ok=True)
    frozen_test.write_text("def test_api(): assert True\n", encoding="utf-8")

    profile = RoleProfile(
        role_id="backend_dev",
        name="backend_dev",
        description="Backend developer",
        tier="engineering",
        allowed_tools=["write_file", "edit_file", "read_file"],
    )

    registry = WorkflowRoleToolFactory.create_registry(
        profile=profile,
        workspace=workspace,
        frozen_test_files=["tests/test_frozen_api.py"],
    )

    write_tool = registry.get("write_file")
    assert write_tool is not None

    whitespace_variations = [
        " tests/test_frozen_api.py",
        "tests/test_frozen_api.py ",
        "  tests/test_frozen_api.py  ",
        "\ttests/test_frozen_api.py",
        "tests/test_frozen_api.py\n",
    ]

    for variant in whitespace_variations:
        with pytest.raises(FrozenTestViolationError) as exc_info:
            write_tool.handler(path=variant, content="# Overwritten")
        assert "strictly prohibited" in str(exc_info.value).lower()


def test_adversarial_frozen_path_case_sensitivity(adversarial_workspace: tuple[Workspace, Path]):
    """
    Adversarial Scenario 4b:
    Agent attempts to modify a frozen test file by altering casing:
    'TESTS/TEST_FROZEN_API.PY' or 'Tests/Test_Frozen_Api.py'.
    On Windows (case-insensitive NTFS), verify that FrozenTestViolationError is raised.
    """
    workspace, repo_dir = adversarial_workspace
    frozen_test = repo_dir / "tests" / "test_frozen_api.py"
    frozen_test.parent.mkdir(parents=True, exist_ok=True)
    frozen_test.write_text("def test_api(): assert True\n", encoding="utf-8")

    profile = RoleProfile(
        role_id="backend_dev",
        name="backend_dev",
        description="Backend developer",
        tier="engineering",
        allowed_tools=["write_file"],
    )

    registry = WorkflowRoleToolFactory.create_registry(
        profile=profile,
        workspace=workspace,
        frozen_test_files=["tests/test_frozen_api.py"],
    )

    write_tool = registry.get("write_file")
    case_variations = [
        "TESTS/TEST_FROZEN_API.PY",
        "Tests/Test_Frozen_Api.py",
        "tests/TEST_FROZEN_API.py",
    ]

    for variant in case_variations:
        if os.name == "nt":
            with pytest.raises(FrozenTestViolationError) as exc_info:
                write_tool.handler(path=variant, content="# Case Bypass")
            assert "strictly prohibited" in str(exc_info.value).lower()


def test_adversarial_frozen_path_relative_traversal_obfuscation(adversarial_workspace: tuple[Workspace, Path]):
    """
    Adversarial Scenario 4c:
    Agent attempts to modify a frozen test file using redundant relative path segments:
    'tests/../tests/test_frozen_api.py' or './tests/./test_frozen_api.py' or 'tests//test_frozen_api.py'.
    Verify that FrozenTestViolationError is raised.
    """
    workspace, repo_dir = adversarial_workspace
    frozen_test = repo_dir / "tests" / "test_frozen_api.py"
    frozen_test.parent.mkdir(parents=True, exist_ok=True)
    frozen_test.write_text("def test_api(): assert True\n", encoding="utf-8")

    profile = RoleProfile(
        role_id="backend_dev",
        name="backend_dev",
        description="Backend developer",
        tier="engineering",
        allowed_tools=["write_file", "edit_file"],
    )

    registry = WorkflowRoleToolFactory.create_registry(
        profile=profile,
        workspace=workspace,
        frozen_test_files=["tests/test_frozen_api.py"],
    )

    write_tool = registry.get("write_file")
    traversal_variations = [
        "tests/../tests/test_frozen_api.py",
        "./tests/./test_frozen_api.py",
        "tests//test_frozen_api.py",
        "tests/fixtures/../../tests/test_frozen_api.py",
    ]

    for variant in traversal_variations:
        with pytest.raises(FrozenTestViolationError) as exc_info:
            write_tool.handler(path=variant, content="# Traversal Bypass")
        assert "strictly prohibited" in str(exc_info.value).lower()


def test_adversarial_frozen_path_symlink_and_hardlink_detection(adversarial_workspace: tuple[Workspace, Path]):
    """
    Adversarial Scenario 4d:
    Agent creates an alias (symlink or hardlink) in the workspace pointing to the frozen test
    and attempts to write through the alias.
    Verify that inode/device matching or path resolution intercepts and blocks the modification.
    """
    workspace, repo_dir = adversarial_workspace
    frozen_test = repo_dir / "tests" / "test_frozen_core.py"
    frozen_test.parent.mkdir(parents=True, exist_ok=True)
    frozen_test.write_text("def test_core(): assert True\n", encoding="utf-8")

    profile = RoleProfile(
        role_id="backend_dev",
        name="backend_dev",
        description="Backend developer",
        tier="engineering",
        allowed_tools=["write_file"],
    )

    registry = WorkflowRoleToolFactory.create_registry(
        profile=profile,
        workspace=workspace,
        frozen_test_files=["tests/test_frozen_core.py"],
    )
    write_tool = registry.get("write_file")

    # 1. Hardlink test (supported across NTFS without special privileges)
    hardlink_path = repo_dir / "hardlink_to_test.py"
    try:
        os.link(str(frozen_test), str(hardlink_path))
        hardlink_created = True
    except (OSError, NotImplementedError):
        hardlink_created = False

    if hardlink_created:
        with pytest.raises(FrozenTestViolationError) as exc_info:
            write_tool.handler(path="hardlink_to_test.py", content="# Hardlink Write")
        assert "strictly prohibited" in str(exc_info.value).lower()

    # 2. Symlink test (if permitted by OS)
    symlink_path = repo_dir / "symlink_to_test.py"
    try:
        os.symlink(str(frozen_test), str(symlink_path))
        symlink_created = True
    except (OSError, NotImplementedError):
        symlink_created = False

    if symlink_created:
        with pytest.raises(FrozenTestViolationError) as exc_info:
            write_tool.handler(path="symlink_to_test.py", content="# Symlink Write")
        assert "strictly prohibited" in str(exc_info.value).lower()


# =============================================================================
# Suite 5: Verifier Authorization & Artifact Integrity Invariants
# =============================================================================


def test_adversarial_non_verifier_completion_attempts_strictly_blocked():
    """
    Adversarial Scenario 5a:
    Verifies that no role other than 'verifier' can transition a task to COMPLETED,
    neither via direct attribute assignment, set_status, nor complete().
    """
    task = CompanyTask(id="task_adv_auth", title="Auth Invariant Task")
    task.register_artifact("valid_art", {"data": "verified"})

    verdict = VerificationVerdict(
        verdict_id="verd_01",
        status="VERIFIED",
        criteria_met=[{"criterion": "c1", "artifact_id": "valid_art"}],
        evidence_valid=True,
    )

    # 1. Direct assignment blocked
    with pytest.raises(PermissionError) as exc_info:
        task.status = "COMPLETED"
    assert "Direct assignment of status='COMPLETED' is prohibited" in str(exc_info.value)

    # 2. set_status blocked
    for role in ["manager", "backend_dev", "frontend_dev", "qa_engineer", "security_auditor"]:
        with pytest.raises(PermissionError):
            task.set_status("COMPLETED", caller_role=role)

    # 3. complete() with unauthorized caller_role blocked
    for role in ["manager", "backend_dev", "qa_engineer", "devops"]:
        with pytest.raises(PermissionError) as exc_info:
            task.complete(verdict, caller_role=role)
        assert "Only 'verifier' is permitted" in str(exc_info.value)

    # 4. CompanyWorkflow.set_task_completed blocked for unauthorized roles
    workflow = CompanyWorkflow(workspace=Workspace([Path(".")]), tool_registry=MagicMock())
    with pytest.raises(UnauthorizedCompletionViolation) as exc_info:
        workflow.set_task_completed(task_id=task.id, role="manager", verdict=verdict)
    assert "Only 'verifier' role has completion authority" in str(exc_info.value)


def test_adversarial_task_completion_requires_valid_registered_artifacts():
    """
    Adversarial Scenario 5b:
    Verifies that task.complete() strictly rejects verdicts with missing, unverified,
    or fabricated artifact IDs.
    """
    task = CompanyTask(id="task_adv_evidence", title="Evidence Invariant Task")
    task.register_artifact("artifact_genuine", {"code": "clean"})

    # 1. Verdict referencing un-registered artifact ID
    fake_verdict = VerificationVerdict(
        verdict_id="verd_fake_art",
        status="VERIFIED",
        criteria_met=[
            {"criterion": "c1", "artifact_id": "artifact_genuine"},
            {"criterion": "c2", "artifact_id": "artifact_fabricated_ghost"},
        ],
        evidence_valid=True,
    )
    with pytest.raises(ValueError) as exc_info:
        task.complete(fake_verdict, caller_role="verifier")
    assert "missing or invalid artifact ID" in str(exc_info.value)

    # 2. Verdict with evidence_valid=False
    invalid_evidence_verdict = VerificationVerdict(
        verdict_id="verd_invalid_ev",
        status="VERIFIED",
        criteria_met=[{"criterion": "c1", "artifact_id": "artifact_genuine"}],
        evidence_valid=False,
    )
    with pytest.raises(ValueError) as exc_info:
        task.complete(invalid_evidence_verdict, caller_role="verifier")
    assert "evidence is marked invalid" in str(exc_info.value)

    # 3. Verdict with non-verified status
    rejected_verdict = VerificationVerdict(
        verdict_id="verd_rejected",
        status="REJECTED",
        criteria_met=[],
        evidence_valid=False,
    )
    with pytest.raises(ValueError) as exc_info:
        task.complete(rejected_verdict, caller_role="verifier")
    assert "non-verified status" in str(exc_info.value)
