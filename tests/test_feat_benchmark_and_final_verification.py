"""
Multi-Task Evaluation Benchmark & Dual-Track E2E Test Suite (Milestone 6 / Features F13 & F14).
Living Assistant - Software Company Evaluation & Final Verification Engine.

Tests:
- F13: Independent QA Rejection Gate, Feedback Remediation Loops, and Final Verifier Completion Gates.
- F14: Multi-Task Benchmark Scenarios:
  1. Full Brownfield Codebase Onboarding & Graph Alignment.
  2. Non-Destructive Git Baseline & Checkpoint Recovery.
  3. 8-Stage Incident Containment & Remediation Cycle.
  4. Sandboxed Hermes Contractor Tool Execution with Path Confinement.
  5. GitHub Researcher & Tool Operator Pipeline with License Risk Classification.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from living_assistant.agents.software_company.change_manager import GitChangeManager
from living_assistant.agents.software_company.incident_recovery import (
    ActionGatekeeper,
    IncidentRecoveryManager,
    IncidentSeverity,
    IncidentStage,
)
from living_assistant.agents.software_company.models import (
    CompanyPlan,
    CompanyTask,
    CriteriaEvidence,
    ExecutionBudget,
    QAReport,
    RoleProfile,
    TaskNode,
    TaskSpec,
    VerificationVerdict,
)
import living_assistant.agents.software_company.roles as _roles_pkg
if not hasattr(_roles_pkg, "__path__"):
    _roles_pkg.__path__ = [str(Path(_roles_pkg.__file__).parent / "roles")]

from living_assistant.agents.software_company.roles import ALL_ROLES, RoleRegistry
from living_assistant.agents.software_company.roles.verifier import FinalVerifier
from living_assistant.agents.software_company.workflow import (
    QARejectionError,
    QARetryLimitExceededError,
    QARunnerHarness,
    SoftwareCompanyWorkflow,
    VerificationError,
)
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.integrations.hermes_contractor import HermesContractor
from living_assistant.learning.eval_engine import detect_test_manipulation
from living_assistant.system.codebase_onboarding import CodebaseOnboardingEngine
from living_assistant.system.graph_validator import SystemGraphValidator
from living_assistant.tools.base import Tool
from living_assistant.tools.filesystem import build_filesystem_tools
from living_assistant.tools.registry import ToolRegistry


@pytest.fixture
def eval_workspace(tmp_path: Path) -> Workspace:
    ws_dir = tmp_path / "software_company_eval"
    ws_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "eval@example.com"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Eval Runner"], cwd=str(ws_dir), capture_output=True, check=True)

    init_file = ws_dir / "README.md"
    init_file.write_text("# Evaluation Workspace\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial eval commit"], cwd=str(ws_dir), capture_output=True, check=True)

    return Workspace([ws_dir])


# =============================================================================
# Feature F13: Independent QA Rejection Gate & Final Verifier Completion Gate
# =============================================================================


def test_f13_qa_rejection_blocks_completion_and_triggers_feedback(eval_workspace: Workspace):
    """Verifies that when QA rejects a build, the task cannot complete and remediation feedback is generated."""
    workflow = SoftwareCompanyWorkflow(workspace=eval_workspace)

    task, spec = workflow.intake_request(
        task_id="eval_task_01",
        title="Add Token Auth",
        goal="Implement JWT bearer validation",
        requirements=["Validate Authorization header"],
        acceptance_criteria=["Return 401 on missing token"],
        interface_contracts={"auth_header": "Bearer <token>"},
        frozen_test_files=["tests/test_auth.py"],
    )
    workflow.approve_spec(task)

    # QA suite fails on first attempt, passes on second
    attempt = 0

    def mock_qa_suite() -> dict[str, Any]:
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return {
                "total": 1,
                "passed": 0,
                "failed": 1,
                "failures": ["test_auth_missing_token"],
                "output": "AssertionError: expected 401, got 200",
                "feedback": "Token validation was missing in handler.",
            }
        return {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "failures": [],
            "output": "test_auth_missing_token PASSED",
            "feedback": "All assertions verified.",
        }

    def mock_remediation(t: CompanyTask, rep: QAReport) -> None:
        pass

    report = workflow.run_qa_remediation_loop(
        task=task,
        qa_suite_fn=mock_qa_suite,
        developer_remediation_fn=mock_remediation,
    )
    assert report.status == "ACCEPTED"
    assert len(task.qa_reports) == 2
    assert task.qa_reports[0].status == "REJECTED"
    assert task.qa_reports[1].status == "ACCEPTED"


def test_f13_qa_retries_exhaustion_raises_exception(eval_workspace: Workspace):
    """Verifies that exceeding max QA retries (2) halts execution with QARetryLimitExceededError."""
    workflow = SoftwareCompanyWorkflow(workspace=eval_workspace, max_retries=2)

    task, spec = workflow.intake_request(
        task_id="eval_task_02",
        title="Flawed Feature",
        goal="Feature that consistently fails",
        requirements=["Impossible req"],
        acceptance_criteria=["Pass tests"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    def perpetually_failing_qa() -> dict[str, Any]:
        return {
            "exit_code": 1,
            "summary": "Failure",
            "failure_count": 1,
            "failed_tests": ["test_feature"],
            "raw_log": "Fatal error",
            "feedback": "Unfixable defect",
        }

    def noop_remediation(t: CompanyTask, rep: QAReport) -> None:
        pass

    with pytest.raises(QARetryLimitExceededError) as exc_info:
        workflow.run_qa_remediation_loop(
            task=task,
            qa_suite_fn=perpetually_failing_qa,
            developer_remediation_fn=noop_remediation,
        )

    assert "retry limit exceeded" in str(exc_info.value).lower()


def test_f13_qa_retry_exhaustion_triggers_automated_baseline_rollback(eval_workspace: Workspace):
    """Verifies that when QA retries are exhausted, the workspace is automatically rolled back to baseline commit."""
    ws_dir = eval_workspace.roots[0]
    cm = GitChangeManager(workspace=eval_workspace)
    workflow = SoftwareCompanyWorkflow(workspace=eval_workspace, max_retries=2, change_manager=cm)

    task_id = "eval_task_retry_rollback"
    target_file = ws_dir / "payment_gateway.py"
    target_file.write_text("def process_payment(): return True\n", encoding="utf-8")
    subprocess.run(["git", "add", "payment_gateway.py"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Baseline payment gateway"], cwd=str(ws_dir), capture_output=True, check=True)

    cm.establish_baseline(task_id)

    task, spec = workflow.intake_request(
        task_id=task_id,
        title="Unstable Gateway Refactor",
        goal="Refactor payment processing",
        requirements=["Reliable payment"],
        acceptance_criteria=["Pass QA"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    # Mutate the file with defect
    target_file.write_text("def process_payment(): raise RuntimeError('CORRUPTED')\n", encoding="utf-8")
    assert "CORRUPTED" in target_file.read_text(encoding="utf-8")

    def perpetually_failing_qa() -> dict[str, Any]:
        return {
            "exit_code": 1,
            "summary": "Payment failure",
            "failure_count": 1,
            "failed_tests": ["test_process_payment"],
            "raw_log": "Fatal exception in gateway",
            "feedback": "Gateway is throwing runtime errors.",
        }

    with pytest.raises(QARetryLimitExceededError):
        workflow.run_qa_remediation_loop(
            task=task,
            qa_suite_fn=perpetually_failing_qa,
            developer_remediation_fn=lambda t, rep: None,
        )

    # Confirm automated rollback restored payment_gateway.py to baseline content!
    assert "CORRUPTED" not in target_file.read_text(encoding="utf-8")
    assert target_file.read_text(encoding="utf-8") == "def process_payment(): return True\n"


def test_f13_final_verifier_strictly_requires_artifacts_for_all_criteria(eval_workspace: Workspace):
    """Verifies Final Verifier rejects task completion if any acceptance criterion lacks an authentic artifact."""
    workflow = SoftwareCompanyWorkflow(workspace=eval_workspace)

    task, spec = workflow.intake_request(
        task_id="eval_task_03",
        title="Validated Feature",
        goal="Produce verifiable artifacts",
        requirements=["Produce schema and route"],
        acceptance_criteria=["schema_artifact_ready", "route_artifact_ready"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    # Simulate passing QA
    task.qa_reports.append(QAReport(
        report_id="rep_ok",
        task_id=task.id,
        exit_code=0,
        status="ACCEPTED",
        total_tests=2,
        passed=2,
        failed=0,
        summary="Passed",
        raw_log="ok",
        log_hash="hash123",
        generated_by_harness=True,
    ))

    # Register only 1 of the 2 needed artifacts
    task.register_artifact("schema_artifact_ready", {"schema": "UserSchema"})

    # Missing route_artifact_ready must cause VerificationError
    criteria_map = {
        "schema_artifact_ready": "schema_artifact_ready",
        "route_artifact_ready": "non_existent_artifact",
    }
    with pytest.raises(VerificationError) as exc_info:
        workflow.verify_and_complete(task, criteria_map)

    assert "Evidence check failed" in str(exc_info.value)

    # Now register the missing artifact
    task.register_artifact("route_artifact_ready", {"route": "/api/users"})
    criteria_map["route_artifact_ready"] = "route_artifact_ready"

    verdict = workflow.verify_and_complete(task, criteria_map)
    assert verdict.status == "VERIFIED"
    assert task.status == "COMPLETED"


# =============================================================================
# Five Verification Pillars: Dedicated Comprehensive Tests
# =============================================================================


def test_f13_pillar1_acceptance_criteria_satisfaction_full_vs_partial(eval_workspace: Workspace):
    """Pillar 1: 100% of spec criteria mapped to genuine artifacts / log_hashes."""
    verifier = FinalVerifier(workspace=eval_workspace)
    spec = TaskSpec(
        spec_id="spec_p1",
        goal="Implement data caching",
        acceptance_criteria=["cache_lookup_valid", "cache_invalidation_valid"],
        approved_by_user=True,
    )
    task = CompanyTask(id="task_p1", title="Caching Task", description="Cache data", spec=spec)

    # 1. Failing condition: no artifacts registered
    ok, met, unmet = verifier.verify_acceptance_criteria(task)
    assert ok is False
    assert len(unmet) > 0

    # 2. Failing condition: partial artifacts (1 out of 2)
    task.register_artifact("cache_lookup_valid", {"method": "get"})
    ok, met, unmet = verifier.verify_acceptance_criteria(task)
    assert ok is False
    assert len(unmet) == 1
    assert "cache_invalidation_valid" in unmet[0]

    # 3. Passing condition: all artifacts registered
    task.register_artifact("cache_invalidation_valid", {"method": "purge"})
    ok, met, unmet = verifier.verify_acceptance_criteria(task)
    assert ok is True
    assert len(unmet) == 0
    assert len(met) == 2


def test_f13_pillar2_automated_test_execution_and_manipulation_defense(eval_workspace: Workspace):
    """Pillar 2: 0 failures, generated_by_harness=True, valid log_hash, and test manipulation defense."""
    verifier = FinalVerifier(workspace=eval_workspace)
    task = CompanyTask(id="task_p2", title="Test Pillar 2")

    # 1. Clean report passes
    clean_report = QAReport(
        report_id="rep_clean",
        task_id=task.id,
        exit_code=0,
        status="ACCEPTED",
        total_tests=5,
        passed=5,
        failed=0,
        log_hash="hash_clean_12345",
        generated_by_harness=True,
    )
    ok, issues = verifier.verify_test_execution(task, qa_report=clean_report)
    assert ok is True
    assert len(issues) == 0

    # 2. Uncertified / forged report fails
    forged_report = clean_report.model_copy(update={"generated_by_harness": False})
    ok, issues = verifier.verify_test_execution(task, qa_report=forged_report)
    assert ok is False
    assert any("Security Alert" in iss for iss in issues)

    # 3. Failing exit code fails
    failing_report = clean_report.model_copy(update={"exit_code": 1, "failed": 1, "status": "REJECTED"})
    ok, issues = verifier.verify_test_execution(task, qa_report=failing_report)
    assert ok is False
    assert any("exit code 1" in iss for iss in issues)

    # 4. Missing log hash fails
    no_hash_report = clean_report.model_copy(update={"log_hash": ""})
    ok, issues = verifier.verify_test_execution(task, qa_report=no_hash_report)
    assert ok is False
    assert any("log hash" in iss.lower() for iss in issues)

    # 5. Test manipulation detection: skip mark
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff="+ @pytest.mark.skip\n+ def test_broken(): pass",
        test_content="@pytest.mark.skip\ndef test_broken(): pass",
    )
    assert ok is False
    assert any("Test Manipulation Gate Violation" in iss for iss in issues)

    # 6. Test manipulation detection: assertion removal
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff="- assert result == expected\n+ pass",
        test_content="def test_weak(): pass",
    )
    assert ok is False
    assert any("Test Manipulation Gate Violation" in iss for iss in issues)

    # 7. Test manipulation detection: exception swallowing
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff="+ except Exception: pass",
        test_content="try:\n    run()\nexcept Exception: pass",
    )
    assert ok is False
    assert any("broad exception swallowing" in iss.lower() for iss in issues)


def test_f13_pillar3_security_policy_compliance_audit_inspection(eval_workspace: Workspace):
    """Pillar 3: Clean audit log with no permission/traversal violations, no uncontained incidents."""
    verifier = FinalVerifier(workspace=eval_workspace)

    # 1. Clean audit log passes
    task_clean = CompanyTask(id="task_p3_clean", title="Clean Task")
    task_clean.record_audit("backend_dev", "write_file", {"outcome": "SUCCESS"})
    ok, issues = verifier.verify_security_compliance(task_clean)
    assert ok is True
    assert len(issues) == 0

    # 2. Audit log with traversal violation fails
    task_dirty = CompanyTask(id="task_p3_dirty", title="Dirty Task")
    task_dirty.audit_log.append({
        "role": "backend_dev",
        "action": "read_file",
        "outcome": "BLOCKED",
        "error": "WorkspaceViolation: path traversal blocked outside root",
    })
    ok, issues = verifier.verify_security_compliance(task_dirty)
    assert ok is False
    assert any("Security violation detected" in iss for iss in issues)

    # 3. Unresolved incident fails
    mock_inc = MagicMock()
    mock_inc.incident_id = "INC-1001"
    mock_inc.stage = IncidentStage.CONTAINED
    ok, issues = verifier.verify_security_compliance(task_clean, active_incidents=[mock_inc])
    assert ok is False
    assert any("Unresolved incident 'INC-1001'" in iss for iss in issues)

    # 4. Resolved incident passes
    mock_inc.stage = IncidentStage.RESOLVED
    ok, issues = verifier.verify_security_compliance(task_clean, active_incidents=[mock_inc])
    assert ok is True


def test_f13_pillar4_artifact_completeness_and_system_graph_validation(eval_workspace: Workspace):
    """Pillar 4: Target files exist on disk with size > 0 and system graph is valid."""
    ws_dir = eval_workspace.roots[0]
    verifier = FinalVerifier(workspace=eval_workspace)

    # 1. Passing target file
    prod_file = ws_dir / "service.py"
    prod_file.write_text("class Service: pass\n", encoding="utf-8")

    spec = TaskSpec(
        spec_id="spec_p4",
        goal="Create service",
        target_files=["service.py"],
        approved_by_user=True,
    )
    task = CompanyTask(id="task_p4", title="Service Creation", spec=spec)
    ok, issues = verifier.verify_artifact_completeness(task)
    assert ok is True
    assert len(issues) == 0

    # 2. Target file missing on disk
    spec_missing = TaskSpec(
        spec_id="spec_p4_miss",
        goal="Create missing",
        target_files=["non_existent_file.py"],
        approved_by_user=True,
    )
    task_missing = CompanyTask(id="task_p4_miss", title="Missing File Task", spec=spec_missing)
    ok, issues = verifier.verify_artifact_completeness(task_missing)
    assert ok is False
    assert any("Target file missing on disk" in iss for iss in issues)

    # 3. Target file empty (size 0)
    empty_file = ws_dir / "empty.py"
    empty_file.write_text("", encoding="utf-8")
    spec_empty = TaskSpec(
        spec_id="spec_p4_empty",
        goal="Create empty",
        target_files=["empty.py"],
        approved_by_user=True,
    )
    task_empty = CompanyTask(id="task_p4_empty", title="Empty File Task", spec=spec_empty)
    ok, issues = verifier.verify_artifact_completeness(task_empty)
    assert ok is False
    assert any("empty (size 0)" in iss for iss in issues)


def test_f13_pillar5_git_state_hygiene_and_untracked_clutter_detection(eval_workspace: Workspace):
    """Pillar 5: Clean working tree, untracked clutter detection, baseline checkpoints consistent."""
    ws_dir = eval_workspace.roots[0]
    cm = GitChangeManager(workspace=eval_workspace)
    verifier = FinalVerifier(workspace=eval_workspace, change_manager=cm)

    task_id = "task_p5_hygiene"
    cm.establish_baseline(task_id)
    task = CompanyTask(id=task_id, title="Hygiene Task")

    # 1. Clean working tree passes
    ok, sha, issues = verifier.verify_git_state_hygiene(task)
    assert ok is True
    assert len(issues) == 0

    # 2. Untracked clutter file created
    clutter = ws_dir / "stray_debug_dump.log"
    clutter.write_text("DEBUG LOG\n", encoding="utf-8")

    ok, sha, issues = verifier.verify_git_state_hygiene(task)
    assert ok is False
    assert any("Untracked clutter" in iss for iss in issues)

    # Clean up clutter
    clutter.unlink()


# =============================================================================
# Adversarial Security Gating Tests
# =============================================================================


def test_f13_adversarial_non_verifier_cannot_complete_task(eval_workspace: Workspace):
    """Adversarial: Non-verifier roles cannot mark tasks COMPLETED."""
    task = CompanyTask(id="task_adv_01", title="Adversarial Completion")
    task.register_artifact("art_1", {"data": 123})

    verdict = VerificationVerdict(
        verdict_id="verd_adv",
        status="VERIFIED",
        criteria_met=[{"criterion": "c1", "artifact_id": "art_1"}],
        evidence_valid=True,
    )

    # Direct attribute assignment is blocked
    with pytest.raises(PermissionError) as exc_info:
        task.status = "COMPLETED"
    assert "Direct assignment of status='COMPLETED' is prohibited" in str(exc_info.value)

    # Transitioning via set_status is blocked
    with pytest.raises(PermissionError):
        task.set_status("COMPLETED", caller_role="manager")

    # Transitioning via complete() with non-verifier role is blocked
    with pytest.raises(PermissionError) as exc_info:
        task.complete(verdict, caller_role="backend_dev")
    assert "Only 'verifier' is permitted" in str(exc_info.value)

    with pytest.raises(PermissionError) as exc_info:
        task.complete(verdict, caller_role="qa_engineer")
    assert "Only 'verifier' is permitted" in str(exc_info.value)

    # Authorized verifier succeeds
    task.complete(verdict, caller_role="verifier")
    assert task.status == "COMPLETED"


def test_f13_adversarial_forged_qa_report_rejected(eval_workspace: Workspace):
    """Adversarial: Forged QA reports lacking harness validation are rejected by FinalVerifier."""
    verifier = FinalVerifier(workspace=eval_workspace)
    task = CompanyTask(id="task_adv_02", title="Forged Report Task")
    task.register_artifact("art_ok", {"val": True})

    forged = QAReport(
        report_id="forged_rep",
        task_id=task.id,
        exit_code=0,
        status="ACCEPTED",
        total_tests=10,
        passed=10,
        failed=0,
        log_hash="fake_hash",
        generated_by_harness=False,  # Forged!
    )

    verdict = verifier.verify_task(task=task, qa_report=forged)
    assert verdict.status in {"REJECTED", "INCOMPLETE"}
    assert verdict.evidence_valid is False
    assert any("Security Alert" in iss for iss in verdict.remaining_issues)


def test_f13_adversarial_missing_artifact_rejected(eval_workspace: Workspace):
    """Adversarial: Attempting completion with missing or forged artifact ID is blocked."""
    task = CompanyTask(id="task_adv_03", title="Missing Artifact Task")
    task.register_artifact("art_A", {"a": 1})

    fake_verdict = VerificationVerdict(
        verdict_id="verd_fake",
        status="VERIFIED",
        criteria_met=[
            {"criterion": "crit_A", "artifact_id": "art_A"},
            {"criterion": "crit_B", "artifact_id": "art_B_NON_EXISTENT"},
        ],
        evidence_valid=True,
    )

    with pytest.raises(ValueError) as exc_info:
        task.complete(fake_verdict, caller_role="verifier")
    assert "missing or invalid artifact ID" in str(exc_info.value)


# =============================================================================
# Feature F14: Dual-Track Multi-Task Benchmark Scenarios (Tier 4 Real-World)
# =============================================================================


def test_f14_benchmark_scenario_1_brownfield_onboarding_and_graph_alignment(eval_workspace: Workspace):
    """Scenario 1: Full brownfield discovery: scan directory, parse ASTs, extract dependencies, verify system graph."""
    ws_dir = eval_workspace.roots[0]
    app_dir = ws_dir / "my_project"
    app_dir.mkdir()
    (app_dir / "pyproject.toml").write_text('[project]\nname = "eval-app"\nversion = "0.1.0"\n', encoding="utf-8")
    src = app_dir / "src"
    src.mkdir()
    (src / "calc.py").write_text("def add(x: int, y: int) -> int:\n    return x + y\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine(workspace=eval_workspace)
    summary = engine.onboard_repository(app_dir, update_graph=False)
    assert summary.status == "SUCCESS"
    assert summary.project_name == "eval-app"
    assert summary.indexed_symbols >= 1


def test_f14_benchmark_scenario_2_non_destructive_git_baseline_and_rollback(eval_workspace: Workspace):
    """Scenario 2: Pre-task baseline capture -> multi-file modifications -> checkpoint creation -> safe rollback."""
    ws_dir = eval_workspace.roots[0]
    cm = GitChangeManager(workspace=eval_workspace)
    baseline = cm.establish_baseline("bench_task_02")
    assert baseline.is_dirty is False

    target = ws_dir / "critical_core.py"
    target.write_text("CORE_VERSION = 'v1.0.0'\n", encoding="utf-8")
    chk = cm.create_checkpoint("bench_task_02", reason="Pre-refactor core")

    # Contaminate file
    target.write_text("CORE_VERSION = 'BROKEN_SYNTAX(\n", encoding="utf-8")
    assert "BROKEN" in target.read_text(encoding="utf-8")

    # Safe rollback via snapshot archive
    res = cm.rollback_to_checkpoint(chk.checkpoint_id)
    assert res["ok"] is True
    assert target.read_text(encoding="utf-8") == "CORE_VERSION = 'v1.0.0'\n"


def test_f14_benchmark_scenario_3_incident_containment_and_remediation_cycle(eval_workspace: Workspace):
    """Scenario 3: 8-stage incident detection -> diagnosis -> containment -> rollback -> repair -> resolution."""
    ws_dir = eval_workspace.roots[0]
    cm = GitChangeManager(workspace=eval_workspace)
    cm.establish_baseline("bench_task_03")

    f = ws_dir / "db_connector.py"
    f.write_text("def connect(): return True\n", encoding="utf-8")
    chk = cm.create_checkpoint("bench_task_03", reason="Working DB connector")

    # Malicious or broken logic injected
    f.write_text("def connect(): raise ConnectionRefusedError('Database unreachable')\n", encoding="utf-8")

    rec_mgr = IncidentRecoveryManager(workspace=eval_workspace, change_manager=cm)

    # 1. Detect
    inc = rec_mgr.detect_incident("bench_task_03", "ConnectionRefusedError: Database unreachable", severity=IncidentSeverity.HIGH)
    assert inc.stage == IncidentStage.DETECTED

    # 2. Diagnose
    rec_mgr.diagnose_incident(inc.incident_id, "Bad connection string in config.")

    # 3. Contain
    rec_mgr.contain_incident(inc.incident_id, "Temporarily severed external outbound sockets.")

    # 4. Rollback
    rec_mgr.rollback_incident(inc.incident_id, checkpoint_id=chk.checkpoint_id)
    assert f.read_text(encoding="utf-8") == "def connect(): return True\n"

    # 5. Repair
    f.write_text("def connect(): return {'status': 'connected', 'pool': 5}\n", encoding="utf-8")
    rec_mgr.record_repair(inc.incident_id, ["db_connector.py"])

    # 6-8. Verify & Resolve
    inc = rec_mgr.verify_and_resolve(inc.incident_id, tests_passed=True)
    assert inc.stage == IncidentStage.RESOLVED
    assert inc.verification_passed is True


def test_f14_benchmark_scenario_4_sandboxed_hermes_contractor_tool_execution(eval_workspace: Workspace):
    """Scenario 4: Sandboxed Hermes contractor tool execution with path confinement and command gating."""
    ws_dir = eval_workspace.roots[0]
    fs_tools = build_filesystem_tools(eval_workspace)

    mock_run = MagicMock(return_value={"ok": True, "returncode": 0, "stdout": "mocked command output", "stderr": ""})
    run_tool = Tool("run_command", "Run shell", {"type": "object"}, mock_run)

    registry = ToolRegistry(fs_tools + [run_tool])
    with patch.dict("sys.modules", {"run_agent": MagicMock(AIAgent=MagicMock())}):
        contractor = HermesContractor(None, "session_bench_4", tool_registry=registry)

        # 1. Step 1: write_file inside workspace
        res_write = contractor._handle_tool_call("write_file", {"path": "worker_output.txt", "content": "Hermes execution complete."})
        assert (ws_dir / "worker_output.txt").exists()

        # 2. Step 2: read_file inside workspace
        res_read = contractor._handle_tool_call("read_file", {"path": "worker_output.txt"})
        assert "Hermes execution complete." in str(res_read)

        # 3. Step 3: run_command execution through registry
        res_cmd = contractor._handle_tool_call("run_command", {"command": "echo 'ok'"})
        assert res_cmd.get("ok") is True

    # 4. Step 4: Sandbox confinement defense - path traversal outside workspace
    with pytest.raises(WorkspaceViolation):
        eval_workspace.resolve("../../../etc/shadow")


def test_f14_benchmark_scenario_5_github_researcher_and_tool_operator_pipeline(eval_workspace: Workspace):
    """Scenario 5: GitHub researcher & tool operator pipeline with structured license evaluation and multi-step execution."""
    registry = RoleRegistry(ALL_ROLES)

    # 1. GitHub researcher role discovery and profile verification
    gh_profile = registry.get("github_researcher")
    assert gh_profile.name == "github_researcher"
    assert gh_profile.department == "specialist"
    assert "REUSE" in gh_profile.system_prompt
    assert "REJECT" in gh_profile.system_prompt

    # Simulated candidate evaluations
    candidates = [
        {"repo": "owner/permissive-lib", "license": "MIT", "healthy": True, "stars": 1200},
        {"repo": "owner/gpl-tool", "license": "GPL-3.0", "healthy": True, "stars": 5000},
        {"repo": "owner/unmaintained", "license": "Apache-2.0", "healthy": False, "stars": 10},
    ]

    eval_results = []
    for c in candidates:
        if c["license"] in {"MIT", "Apache-2.0", "BSD-3-Clause"} and c["healthy"]:
            category = "REUSE"
        elif c["license"].startswith("GPL") or c["license"].startswith("AGPL"):
            category = "REJECT"
        else:
            category = "INSPECT"
        eval_results.append({"repo": c["repo"], "category": category})

    assert eval_results[0]["category"] == "REUSE"
    assert eval_results[1]["category"] == "REJECT"

    # 2. Tool operator role execution with task-scoped tools
    to_profile = registry.get("tool_operator")
    assert to_profile.name == "tool_operator"
    assert "read_file" in to_profile.allowed_tools
    assert "run_command" in to_profile.allowed_tools

    fs_tools = build_filesystem_tools(eval_workspace)
    available_tools = ToolRegistry(fs_tools)
    scoped_registry = registry.get_scoped_tools("tool_operator", available_tools)
    assert scoped_registry.get("read_file") is not None
    assert scoped_registry.get("write_file") is not None

    # Tool operator writes synthesized research artifact
    research_report = {
        "recommended_candidate": eval_results[0]["repo"],
        "category": "REUSE",
        "license_clean": True,
        "pipeline_status": "APPROVED_FOR_MANAGER",
    }
    ws_dir = eval_workspace.roots[0]
    report_file = ws_dir / "research_report.json"
    report_file.write_text(json.dumps(research_report, indent=2), encoding="utf-8")

    assert report_file.exists()
    assert "APPROVED_FOR_MANAGER" in report_file.read_text(encoding="utf-8")
