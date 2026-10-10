"""
Milestone 6 Adversarial Challenge & Stress-Testing Suite: Final Verifier 5 Pillars & Release Gates.
Author: Challenger M6-2 (teamwork_preview_challenger)

This test suite empirically stresses:
1. Pillar 1: Acceptance Criteria Satisfaction (partial vs 100% criteria mapping, missing artifacts, status INCOMPLETE).
2. Pillar 2: Automated Test Execution & Manipulation Defense (skips, deleted asserts, exception catches, evasion blindspots).
3. Pillar 3: Security Policy Compliance (audit log violation detection, IncidentStage.ANALYZING open incidents, nested audit format).
4. Pillar 4: Artifact Completeness (missing files, 0-byte files, system graph validation).
5. Pillar 5: Git State Hygiene (untracked clutter files, baseline commit consistency, target file allowance).
6. Direct Bypass Defense (direct task.status="COMPLETED", caller role permission checks, invalid verdict rejection).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from living_assistant.agents.software_company.change_manager import GitChangeManager
from living_assistant.agents.software_company.incident_recovery import (
    IncidentSeverity,
    IncidentStage,
)
from living_assistant.agents.software_company.models import (
    CompanyTask,
    CriteriaEvidence,
    QAReport,
    TaskSpec,
    VerificationVerdict,
)
from living_assistant.agents.software_company.roles.verifier import FinalVerifier
from living_assistant.core.workspace import Workspace
from living_assistant.learning.eval_engine import detect_test_manipulation


@pytest.fixture
def eval_workspace(tmp_path: Path) -> Workspace:
    ws_dir = tmp_path / "final_verifier_stress_ws"
    ws_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "challenger@example.com"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Challenger M6-2"], cwd=str(ws_dir), capture_output=True, check=True)

    init_file = ws_dir / "README.md"
    init_file.write_text("# Final Verifier Stress Workspace\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(ws_dir), capture_output=True, check=True)

    return Workspace([ws_dir])


# =============================================================================
# 1. PILLAR 1: ACCEPTANCE CRITERIA SATISFACTION (PARTIAL VS 100%)
# =============================================================================


def test_pillar1_partial_criteria_mapping_yields_incomplete_status(eval_workspace: Workspace):
    """
    Stress-test Pillar 1:
    When 5 of 6 criteria are satisfied, verify that:
    - ok is False
    - unmet list contains the missing criterion
    - verify_task yields status='INCOMPLETE' (not 'VERIFIED')
    """
    verifier = FinalVerifier(workspace=eval_workspace)

    criteria_list = [f"criterion_{i}" for i in range(1, 7)]
    spec = TaskSpec(
        spec_id="spec_p1_partial",
        goal="Test partial criteria mapping",
        acceptance_criteria=criteria_list,
        approved_by_user=True,
    )
    task = CompanyTask(id="task_p1_partial", title="Partial Criteria Task", spec=spec)

    # Register only 5 of 6 criteria as artifacts
    criteria_map: Dict[str, str] = {}
    for crit in criteria_list[:5]:
        art_id = f"artifact_{crit}"
        task.register_artifact(art_id, {"content": f"deliverable for {crit}"})
        criteria_map[crit] = art_id

    # 1. verify_acceptance_criteria with criteria_artifact_map
    ok, met, unmet = verifier.verify_acceptance_criteria(task, criteria_artifact_map=criteria_map)
    assert ok is False, "Expected Pillar 1 to fail when only 5 of 6 criteria are mapped"
    assert len(met) == 5
    assert len(unmet) == 1
    assert "criterion_6" in unmet[0]

    # Clean QA report to isolate Pillar 1 behavior
    qa_report = QAReport(
        report_id="rep_clean",
        task_id=task.id,
        exit_code=0,
        status="ACCEPTED",
        total_tests=5,
        passed=5,
        failed=0,
        log_hash="hash_clean_001",
        generated_by_harness=True,
    )

    verdict = verifier.verify_task(
        task=task,
        qa_report=qa_report,
        criteria_artifact_map=criteria_map,
    )

    assert verdict.status == "INCOMPLETE", f"Expected status INCOMPLETE, got {verdict.status}"
    assert verdict.evidence_valid is False
    assert any("criterion_6" in iss for iss in verdict.remaining_issues)


def test_pillar1_full_criteria_satisfaction_passes(eval_workspace: Workspace):
    """Verify that when 6 of 6 criteria are mapped to registered artifacts, Pillar 1 succeeds."""
    verifier = FinalVerifier(workspace=eval_workspace)

    criteria_list = [f"criterion_{i}" for i in range(1, 7)]
    spec = TaskSpec(
        spec_id="spec_p1_full",
        goal="Test full criteria mapping",
        acceptance_criteria=criteria_list,
        approved_by_user=True,
    )
    task = CompanyTask(id="task_p1_full", title="Full Criteria Task", spec=spec)

    criteria_map: Dict[str, str] = {}
    for crit in criteria_list:
        art_id = f"artifact_{crit}"
        task.register_artifact(art_id, {"content": f"deliverable for {crit}"})
        criteria_map[crit] = art_id

    ok, met, unmet = verifier.verify_acceptance_criteria(task, criteria_artifact_map=criteria_map)
    assert ok is True
    assert len(met) == 6
    assert len(unmet) == 0


def test_pillar1_missing_artifact_id_in_map_detected(eval_workspace: Workspace):
    """Pillar 1: Criteria mapping referencing a non-existent artifact ID is flagged."""
    verifier = FinalVerifier(workspace=eval_workspace)

    spec = TaskSpec(
        spec_id="spec_p1_bad_art",
        goal="Test missing artifact",
        acceptance_criteria=["crit_1", "crit_2"],
        approved_by_user=True,
    )
    task = CompanyTask(id="task_p1_bad_art", title="Bad Art Task", spec=spec)
    task.register_artifact("art_1", {"content": "data"})

    criteria_map = {
        "crit_1": "art_1",
        "crit_2": "non_existent_art_id",
    }
    ok, met, unmet = verifier.verify_acceptance_criteria(task, criteria_artifact_map=criteria_map)
    assert ok is False
    assert any("non_existent_art_id" in iss for iss in unmet)


# =============================================================================
# 2. PILLAR 2: AUTOMATED TEST EXECUTION & MANIPULATION DEFENSE
# =============================================================================


def test_pillar2_detects_skip_markers_and_deleted_assertions(eval_workspace: Workspace):
    """
    Stress-test Pillar 2:
    - @pytest.mark.skip injected in test content
    - @unittest.skip injected in test content
    - Deleted assertions in test diff
    - Single-line broad exception catches
    """
    verifier = FinalVerifier(workspace=eval_workspace)
    task = CompanyTask(id="task_p2_manip", title="Pillar 2 Task")

    clean_report = QAReport(
        report_id="rep_clean",
        task_id=task.id,
        exit_code=0,
        status="ACCEPTED",
        total_tests=4,
        passed=4,
        failed=0,
        log_hash="hash_clean_002",
        generated_by_harness=True,
    )

    # 1. @pytest.mark.skip
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff="+ @pytest.mark.skip\n+ def test_auth(): pass",
        test_content="@pytest.mark.skip\ndef test_auth(): pass",
    )
    assert ok is False
    assert any("test was marked as skipped" in iss for iss in issues)

    # 2. @unittest.skip
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff="+ @unittest.skip('temporarily disabled')\n+ def test_login(): pass",
        test_content="@unittest.skip('temporarily disabled')\ndef test_login(): pass",
    )
    assert ok is False
    assert any("test was marked as skipped" in iss for iss in issues)

    # 3. Deleted assertions (3 removed, 0 added)
    diff_deleted_asserts = (
        "- assert response.status_code == 200\n"
        "- assert response.json()['token'] is not None\n"
        "- assert user.is_authenticated is True\n"
        "+ pass\n"
    )
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff=diff_deleted_asserts,
        test_content="def test_login():\n    pass\n",
    )
    assert ok is False
    assert any("assertion(s) were removed" in iss for iss in issues)

    # 4. Single-line broad exception catches
    ok, issues = verifier.verify_test_execution(
        task,
        qa_report=clean_report,
        test_diff="+ except Exception: pass",
        test_content="try:\n    run_test()\nexcept Exception: pass",
    )
    assert ok is False
    assert any("broad exception swallowing" in iss for iss in issues)


def test_pillar2_adversarial_evasion_surfaces_blindspots():
    """
    Adversarial finding in eval_engine.detect_test_manipulation:
    Demonstrates blindspots where malicious test modifications slip past regex checks:
    1. Multiline 'except Exception:\n    pass'
    2. Assertion neutering 'assert True' replacing 'assert result == 100'
    3. Skip marker present only in git diff when test_content is empty
    """
    # Finding 1: Multiline exception catch is NOT detected because check is literal 'except Exception: pass'
    multiline_except = "try:\n    risky_test()\nexcept Exception:\n    pass\n"
    manip_detected, _ = detect_test_manipulation("", multiline_except)
    assert manip_detected is False, "Demonstrates blindspot: multiline broad exception catch is not caught"

    # Finding 2: Neutering assertion by replacing with 'assert True'
    neutered_diff = "- assert user.is_admin is True\n+ assert True"
    manip_detected, _ = detect_test_manipulation(neutered_diff, "def test_admin(): assert True")
    assert manip_detected is False, "Demonstrates blindspot: replacing assert with 'assert True' maintains assert count"

    # Finding 3: Skip in diff without test_content
    diff_with_skip = "+ @pytest.mark.skip\n+ def test_feature(): pass\n"
    manip_detected, _ = detect_test_manipulation(diff_with_skip, "")
    assert manip_detected is False, "Demonstrates blindspot: skip marker in diff alone is ignored without new_content"


# =============================================================================
# 3. PILLAR 3: SECURITY POLICY COMPLIANCE & INCIDENT RESOLUTION
# =============================================================================


def test_pillar3_security_violation_in_audit_log_denies_approval(eval_workspace: Workspace):
    """
    Stress-test Pillar 3:
    Inject simulated security violations into task.audit_log:
    - Path traversal attempt (WorkspaceViolation)
    - Unauthorized tool execution
    Verify that security approval is denied (security_approved=False).
    """
    verifier = FinalVerifier(workspace=eval_workspace)

    # 1. Path traversal violation
    task_traversal = CompanyTask(id="task_p3_traversal", title="Traversal Task")
    task_traversal.audit_log.append({
        "role": "backend_dev",
        "action": "read_file",
        "outcome": "BLOCKED",
        "error": "WorkspaceViolation: path traversal blocked outside workspace root",
    })

    ok, issues = verifier.verify_security_compliance(task_traversal)
    assert ok is False
    assert any("Security violation detected in audit log" in iss for iss in issues)

    verdict = verifier.verify_task(task_traversal)
    assert verdict.security_approved is False
    assert verdict.status in {"REJECTED", "INCOMPLETE"}

    # 2. Unauthorized tool execution
    task_unauth = CompanyTask(id="task_p3_unauth", title="Unauth Tool Task")
    task_unauth.audit_log.append({
        "role": "frontend_dev",
        "action": "run_command",
        "outcome": "DENIED",
        "error": "PermissionError: unauthorized tool 'run_command' prohibited for role frontend_dev",
    })
    ok, issues = verifier.verify_security_compliance(task_unauth)
    assert ok is False
    assert any("unauthorized" in iss.lower() for iss in issues)


def test_pillar3_open_incident_in_analyzing_denies_approval(eval_workspace: Workspace):
    """
    Stress-test Pillar 3:
    Mock an active incident in IncidentStage.ANALYZING (or any non-RESOLVED stage).
    Verify security approval is denied.
    """
    verifier = FinalVerifier(workspace=eval_workspace)
    task = CompanyTask(id="task_p3_inc", title="Open Incident Task")

    mock_incident = MagicMock()
    mock_incident.incident_id = "INC-2026-0042"
    mock_incident.stage = IncidentStage.ANALYZING

    ok, issues = verifier.verify_security_compliance(task, active_incidents=[mock_incident])
    assert ok is False
    assert any("Unresolved incident 'INC-2026-0042' remains in stage" in iss for iss in issues)

    verdict = verifier.verify_task(task, active_incidents=[mock_incident])
    assert verdict.security_approved is False
    assert verdict.status in {"REJECTED", "INCOMPLETE"}

    # When resolved, it passes
    mock_incident.stage = IncidentStage.RESOLVED
    ok_res, issues_res = verifier.verify_security_compliance(task, active_incidents=[mock_incident])
    assert ok_res is True
    assert len(issues_res) == 0


def test_pillar3_adversarial_nested_audit_log_format_gap():
    """
    Adversarial finding in FinalVerifier.verify_security_compliance:
    task.record_audit(role, action, details) stores outcome and error inside 'details'.
    verifier.py inspects entry.get('outcome') and entry.get('error') at the root,
    so violations logged via standard task.record_audit() are not detected.
    """
    verifier = FinalVerifier(workspace=MagicMock(roots=[Path(".")]))
    task = CompanyTask(id="task_gap", title="Gap Test")

    # Logged via standard task.record_audit()
    task.record_audit("backend_dev", "read_file", {
        "outcome": "BLOCKED",
        "error": "WorkspaceViolation: traversal attempt",
    })

    ok, issues = verifier.verify_security_compliance(task)
    # Documents that root-only key lookup creates a blindspot for nested details
    assert ok is True, "Confirms root lookup misses details.outcome"
    assert len(issues) == 0


# =============================================================================
# 4. PILLAR 4: ARTIFACT COMPLETENESS
# =============================================================================


def test_pillar4_missing_or_zero_byte_target_file_rejected(eval_workspace: Workspace):
    """
    Stress-test Pillar 4:
    - Target file missing on disk -> rejected.
    - Target file present but 0 bytes -> rejected.
    - Valid target file with size > 0 -> accepted.
    """
    ws_dir = eval_workspace.roots[0]
    verifier = FinalVerifier(workspace=eval_workspace)

    # 1. Missing target file
    spec_missing = TaskSpec(
        spec_id="spec_p4_miss",
        goal="Produce API",
        target_files=["src/missing_api.py"],
        approved_by_user=True,
    )
    task_missing = CompanyTask(id="task_p4_miss", title="Missing Target Task", spec=spec_missing)
    ok, issues = verifier.verify_artifact_completeness(task_missing)
    assert ok is False
    assert any("Target file missing on disk: 'src/missing_api.py'" in iss for iss in issues)

    # 2. 0-byte target file
    zero_byte_file = ws_dir / "zero_byte.py"
    zero_byte_file.write_text("", encoding="utf-8")
    assert zero_byte_file.stat().st_size == 0

    spec_zero = TaskSpec(
        spec_id="spec_p4_zero",
        goal="Produce empty stub",
        target_files=["zero_byte.py"],
        approved_by_user=True,
    )
    task_zero = CompanyTask(id="task_p4_zero", title="Zero Byte Task", spec=spec_zero)
    ok, issues = verifier.verify_artifact_completeness(task_zero)
    assert ok is False
    assert any("Target file is empty (size 0): 'zero_byte.py'" in iss for iss in issues)

    # 3. Legitimate non-zero target file
    valid_file = ws_dir / "valid_service.py"
    valid_file.write_text("class ValidService:\n    def run(self): return True\n", encoding="utf-8")
    assert valid_file.stat().st_size > 0

    spec_valid = TaskSpec(
        spec_id="spec_p4_valid",
        goal="Produce valid service",
        target_files=["valid_service.py"],
        approved_by_user=True,
    )
    task_valid = CompanyTask(id="task_p4_valid", title="Valid Target Task", spec=spec_valid)
    ok, issues = verifier.verify_artifact_completeness(task_valid)
    assert ok is True
    assert len(issues) == 0


# =============================================================================
# 5. PILLAR 5: GIT STATE HYGIENE & UNTRACKED CLUTTER
# =============================================================================


def test_pillar5_untracked_clutter_flagged_by_git_hygiene(eval_workspace: Workspace):
    """
    Stress-test Pillar 5:
    - Clean workspace -> git hygiene passes.
    - Untracked clutter file introduced -> git hygiene flags violation.
    - Declared target file in untracked state -> tolerated as deliverable.
    """
    ws_dir = eval_workspace.roots[0]
    cm = GitChangeManager(workspace=eval_workspace)
    verifier = FinalVerifier(workspace=eval_workspace, change_manager=cm)

    task_id = "task_p5_clutter"
    cm.establish_baseline(task_id)

    spec = TaskSpec(
        spec_id="spec_p5",
        goal="Implement feature",
        target_files=["expected_output.py"],
        approved_by_user=True,
    )
    task = CompanyTask(id=task_id, title="Clutter Task", spec=spec)

    # 1. Clean workspace
    ok, sha, issues = verifier.verify_git_state_hygiene(task)
    assert ok is True
    assert len(issues) == 0

    # 2. Add untracked clutter file
    clutter = ws_dir / "tmp_debug_trace.log"
    clutter.write_text("CRASH TRACE DUMP\n", encoding="utf-8")

    ok, sha, issues = verifier.verify_git_state_hygiene(task)
    assert ok is False
    assert any("Git hygiene violation: Untracked clutter 'tmp_debug_trace.log'" in iss for iss in issues)

    # 3. Clean clutter, add expected target file
    clutter.unlink()
    expected = ws_dir / "expected_output.py"
    expected.write_text("print('hello')\n", encoding="utf-8")

    ok, sha, issues = verifier.verify_git_state_hygiene(task)
    assert ok is True, "Target file from spec is not flagged as stray clutter"
    assert len(issues) == 0


# =============================================================================
# 6. DIRECT BYPASS DEFENSE: AUTHORIZATION & PERMISSION GATING
# =============================================================================


def test_direct_bypass_attempts_raise_permission_error():
    """
    Stress-test Authorization Gate:
    1. Direct assignment `task.status = 'COMPLETED'` raises PermissionError.
    2. Transition via `task.set_status('COMPLETED')` raises PermissionError.
    3. Direct completion with `caller_role='manager'` raises PermissionError.
    4. Direct completion with `caller_role='backend_dev'` raises PermissionError.
    5. Direct completion with `caller_role='qa_engineer'` raises PermissionError.
    6. Verifier completion with non-verified status or invalid evidence raises ValueError.
    7. Legitimate completion by `caller_role='verifier'` succeeds.
    """
    task = CompanyTask(id="task_bypass_test", title="Bypass Defense Test")
    task.register_artifact("art_req_1", {"status": "ok"})

    valid_verdict = VerificationVerdict(
        verdict_id="verd_test_01",
        task_id=task.id,
        status="VERIFIED",
        criteria_met=[{"criterion": "crit_1", "artifact_id": "art_req_1"}],
        security_approved=True,
        evidence_valid=True,
    )

    # 1. Direct assignment
    with pytest.raises(PermissionError) as exc_info:
        task.status = "COMPLETED"
    assert "Direct assignment of status='COMPLETED' is prohibited" in str(exc_info.value)

    # 2. set_status to COMPLETED
    with pytest.raises(PermissionError) as exc_info:
        task.set_status("COMPLETED", caller_role="manager")
    assert "Direct transition to COMPLETED is prohibited" in str(exc_info.value)

    # 3. Caller role 'manager'
    with pytest.raises(PermissionError) as exc_info:
        task.complete(valid_verdict, caller_role="manager")
    assert "Only 'verifier' is permitted" in str(exc_info.value)

    # 4. Caller role 'backend_dev'
    with pytest.raises(PermissionError) as exc_info:
        task.complete(valid_verdict, caller_role="backend_dev")
    assert "Only 'verifier' is permitted" in str(exc_info.value)

    # 5. Caller role 'qa_engineer'
    with pytest.raises(PermissionError) as exc_info:
        task.complete(valid_verdict, caller_role="qa_engineer")
    assert "Only 'verifier' is permitted" in str(exc_info.value)

    # 6. Verifier with invalid verdict status (e.g. INCOMPLETE)
    incomplete_verdict = valid_verdict.model_copy(update={"status": "INCOMPLETE"})
    with pytest.raises(ValueError) as exc_info:
        task.complete(incomplete_verdict, caller_role="verifier")
    assert "Cannot complete task with non-verified status" in str(exc_info.value)

    # 7. Verifier with evidence_valid=False
    invalid_evidence_verdict = valid_verdict.model_copy(update={"evidence_valid": False})
    with pytest.raises(ValueError) as exc_info:
        task.complete(invalid_evidence_verdict, caller_role="verifier")
    assert "evidence is marked invalid" in str(exc_info.value)

    # 8. Legitimate verifier completion succeeds
    task.complete(valid_verdict, caller_role="verifier")
    assert task.status == "COMPLETED"
    assert task.verdict == valid_verdict
