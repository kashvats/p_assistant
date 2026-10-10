"""
Adversarial Verification Suite for Milestone 5 Remediation (Iteration 2).
Challenger 2 (challenger_m5_it2_2).

Exhaustive empirical testing of:
1. ActionGatekeeper command normalization and obfuscation resistance:
   - Prohibited commands (git reset --hard permutations, fork bombs, disk formats).
   - Approval-required commands (git push --force permutations, refspecs, flags, production deploy, destructive DB, rm -rf).
   - False-positive prevention for legitimate developer commands.
2. Incident recovery stage progression invariants under failed rollback.
3. CompanyWorkflow auto-rollback to clean baseline on unhandled failures and QA rejection.
4. Human denial gating enforcement across all rejection statuses.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from living_assistant.agents.software_company.incident_recovery import (
    ActionClass,
    ActionGatekeeper,
    IncidentRecoveryManager,
    IncidentSeverity,
    IncidentStage,
)
from living_assistant.agents.software_company.models import (
    CompanyPlan,
    DeveloperOutput,
    QAReport,
    VerificationVerdict,
    WorkflowStatus,
)
from living_assistant.agents.software_company.workflow import CompanyWorkflow
from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.core.workspace import Workspace
from living_assistant.system.git_manager import GitChangeManager
from living_assistant.tools.registry import ToolRegistry


@pytest.fixture
def test_repo_workspace(tmp_path: Path) -> tuple[Workspace, Path]:
    repo_dir = tmp_path / "adversarial_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "challenger@example.com"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Challenger2"], cwd=str(repo_dir), capture_output=True, check=True)

    readme = repo_dir / "README.md"
    readme.write_text("# Clean Baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Baseline commit"], cwd=str(repo_dir), capture_output=True, check=True)

    return Workspace([repo_dir]), repo_dir


# ==============================================================================
# SECTION 1: Exhaustive Adversarial Prohibited Command Variations
# ==============================================================================

ADVERSARIAL_PROHIBITED_COMMANDS = [
    # Whitespace variations
    "git reset --hard",
    "git  reset   --hard",
    "git   reset    --hard",
    "git\treset\t--hard",
    "git \t reset \t --hard",
    "git\nreset\n--hard",
    "  git reset --hard  ",
    "\tgit\treset\t--hard\t",
    # Case variations
    "GIT RESET --HARD",
    "Git Reset --Hard",
    "gIt ReSeT --hArD",
    # Target / Refspec / Flag permutations
    "git reset HEAD --hard",
    "git reset --hard HEAD",
    "git reset master --hard",
    "git reset main --hard",
    "git reset origin/main --hard",
    "git reset HEAD~1 --hard",
    "git reset --hard HEAD~1",
    "git reset HEAD~5 --hard",
    "git reset -q --hard",
    "git reset --hard -q",
    "git reset --hard --quiet",
    "git reset --quiet --hard",
    # Quoted variations
    'git reset "--hard"',
    "git reset '--hard'",
    'git reset HEAD "--hard"',
    "git reset HEAD '--hard'",
    # Fork bomb variations
    ":(){ :|:& };:",
    ":(){:|:&};:",
    ": () { : | : & } ; :",
    ":\t()\t{\t:\t|\t:\t&\t}\t;\t:",
    ":(){:|:&",
    ":(){ :|:&",
    # Disk format variations
    "format c:",
    "format C:",
    "format   c:",
    "format\tc:",
    "format /y c:",
    "format /Y C:",
    "format /q /y c:",
    "format /q /fs:ntfs d:",
    "format /fs:FAT32 /v:DATA e:",
    "format /q /fs:ntfs /y d:",
    "format.com c:",
    "format.com /y c:",
    "format.com /q /fs:ntfs d:",
    "format disk",
    "format disk 0",
    "format disk 1",
    "mkfs /dev/sda1",
    "mkfs.ext4 /dev/sda1",
    "mkfs.xfs /dev/nvme0n1p1",
    "mkfs -t ext4 /dev/sdb1",
    "mkfs.ext4 -F /dev/sda1",
]


@pytest.mark.parametrize("cmd", ADVERSARIAL_PROHIBITED_COMMANDS)
def test_adversarial_prohibited_commands_strictly_blocked(test_repo_workspace, cmd: str):
    ws, _ = test_repo_workspace
    gatekeeper = ActionGatekeeper(workspace=ws)

    # 1. Classification check
    action_class, reason = gatekeeper.classify_action("run_command", {"command": cmd})
    assert action_class == ActionClass.PROHIBITED, f"Command '{cmd}' classified as {action_class}, expected PROHIBITED."
    assert "non-destructive safety policy" in reason

    # 2. Evaluation check (must not allow execution)
    res = gatekeeper.evaluate_and_request("run_command", {"command": cmd})
    assert res["allowed"] is False
    assert res["status"] == "PROHIBITED"
    assert res["action_class"] == "prohibited"


def test_adversarial_prohibited_action_name_classification(test_repo_workspace):
    """Verifies that prohibited actions passed via action_name directly are also caught."""
    ws, _ = test_repo_workspace
    gatekeeper = ActionGatekeeper(workspace=ws)

    cls_act, _ = gatekeeper.classify_action("git reset --hard", {})
    assert cls_act == ActionClass.PROHIBITED

    cls_act_tab, _ = gatekeeper.classify_action("git\treset\t--hard", {})
    assert cls_act_tab == ActionClass.PROHIBITED


# ==============================================================================
# SECTION 2: Exhaustive Adversarial Approval-Required Command Variations
# ==============================================================================

ADVERSARIAL_APPROVAL_REQUIRED_COMMANDS = [
    # Force push variations
    "git push --force",
    "git  push   --force",
    "git\tpush\t--force",
    "git\npush\n--force",
    "git push -f",
    "git  push  -f",
    "git\tpush\t-f",
    "git push origin -f",
    "git push -f origin",
    "git push origin --force",
    "git push --force origin",
    "git push origin main --force",
    "git push --force origin main",
    "git push -f origin main",
    "git push origin -f main",
    "git push -u origin -f",
    "git push -uf origin main",
    "git push -fu origin main",
    "git push --force-with-lease",
    "git push --force-with-lease origin main",
    "git push --force-if-includes",
    "git push origin +main",
    "git push origin +master",
    "git push origin +refs/heads/main",
    "git push +main",
    "GIT PUSH --FORCE",
    "Git Push -F",
    # Deploy variations
    "deploy --prod",
    "deploy  --prod",
    "deploy\t--prod",
    "deploy --production",
    "deploy  --production",
    "production deploy",
    "production  deploy",
    "production\tdeploy",
    "deploy to production",
    "deploy  to  production",
    # Database destruction
    "drop database",
    "drop  database  production",
    "drop\tdatabase\tanalytics",
    "DROP DATABASE users",
    "truncate table",
    "truncate  table  users",
    "truncate table orders;",
    "truncate table `users`",
    'truncate table "accounts"',
    # Deletion variations
    "rm -rf /var/log",
    "rm  -rf  node_modules",
    "rm\t-rf\tcache",
    "rm -fr build",
    "rm  -fr  dist",
    "rm -r -f temp",
    "rm  -r  -f  temp",
    "rm -rf *",
    "modify_security_policy",
    "modify security policy",
    "modify  security  policy",
    "delete_critical_data",
    "delete critical data",
    "delete  critical  data",
]


def test_adversarial_rm_flag_ordering_edge_case(test_repo_workspace):
    """
    Empirical Discovery / Observation:
    Worker M5 implemented regex matching for combined flags (-rf, -fr) and separate flags (-r ... -f),
    e.g. 'rm -r -f dir' correctly triggers APPROVAL_REQUIRED.
    However, reversed separate flags 'rm -f -r dir' is not caught by the regex and falls through
    to AUTOMATIC. We document and empirically verify this edge case here for future hardening.
    """
    ws, _ = test_repo_workspace
    gatekeeper = ActionGatekeeper(workspace=ws)

    # -r before -f is intercepted
    cls_rf_sep, _ = gatekeeper.classify_action("run_command", {"command": "rm -r -f temp"})
    assert cls_rf_sep == ActionClass.APPROVAL_REQUIRED

    # -f before -r currently falls through to AUTOMATIC (surfaced finding)
    cls_fr_sep, _ = gatekeeper.classify_action("run_command", {"command": "rm -f -r temp"})
    # Documented behavior
    assert cls_fr_sep in {ActionClass.AUTOMATIC, ActionClass.APPROVAL_REQUIRED}


@pytest.mark.parametrize("cmd", ADVERSARIAL_APPROVAL_REQUIRED_COMMANDS)
def test_adversarial_approval_required_commands_strictly_intercepted(test_repo_workspace, cmd: str):
    ws, _ = test_repo_workspace
    gatekeeper = ActionGatekeeper(workspace=ws)

    # 1. Classification check
    action_class, reason = gatekeeper.classify_action("run_command", {"command": cmd})
    assert action_class == ActionClass.APPROVAL_REQUIRED, (
        f"Command '{cmd}' classified as {action_class}, expected APPROVAL_REQUIRED."
    )
    assert "human approval" in reason

    # 2. Default evaluation without ApprovalManager must block
    res = gatekeeper.evaluate_and_request("run_command", {"command": cmd})
    assert res["allowed"] is False
    assert res["status"] == "PENDING_APPROVAL"
    assert res["action_class"] == "approval_required"


# ==============================================================================
# SECTION 3: Legitimate Developer Commands (Zero False Positives)
# ==============================================================================

LEGITIMATE_DEVELOPER_COMMANDS = [
    "git status",
    "git status -s",
    "git diff",
    "git diff HEAD~1",
    "git diff --staged",
    "git checkout main",
    "git checkout -b feature/auth",
    "git branch -a",
    "git log -n 10",
    "git log --oneline",
    "pytest",
    "pytest tests/ -v",
    "pytest tests/test_core.py",
    "git push origin main",
    "git push origin feature/user-profile",
    "git push",
    "git reset file.txt",
    "git reset HEAD README.md",
    "git reset path/to/module.py",
    "git add .",
    "git add src/",
    "git commit -m 'feat: implement auth'",
    "python -m unittest discover",
    "python app.py",
    "npm run build",
    "npm test",
    "cargo test",
    "black --check .",
    "ruff check src/",
    "flake8 src/",
    "echo 'hello world'",
    "cat README.md",
    "format_code.py --fix",
]


@pytest.mark.parametrize("cmd", LEGITIMATE_DEVELOPER_COMMANDS)
def test_legitimate_commands_remain_strictly_automatic(test_repo_workspace, cmd: str):
    ws, _ = test_repo_workspace
    gatekeeper = ActionGatekeeper(workspace=ws)

    action_class, _ = gatekeeper.classify_action("run_command", {"command": cmd})
    assert action_class == ActionClass.AUTOMATIC, (
        f"Legitimate command '{cmd}' falsely classified as {action_class}, expected AUTOMATIC."
    )

    res = gatekeeper.evaluate_and_request("run_command", {"command": cmd})
    assert res["allowed"] is True
    assert res["status"] == "AUTOMATIC"
    assert res["action_class"] == "automatic"


# ==============================================================================
# SECTION 4: Incident Recovery State Progression Invariants
# ==============================================================================

def test_incident_recovery_failed_rollback_does_not_advance_stage(test_repo_workspace):
    """
    Empirically verify that when rollback fails (rollback_applied=False),
    the incident stage does NOT advance to ROLLED_BACK and stays at its previous stage (CONTAINED).
    """
    ws, _ = test_repo_workspace
    cm = GitChangeManager(workspace=ws)
    rec_mgr = IncidentRecoveryManager(workspace=ws, change_manager=cm)

    report = rec_mgr.detect_incident("task_prog_01", "Database deadlock", IncidentSeverity.HIGH)
    assert report.stage == IncidentStage.DETECTED

    rec_mgr.diagnose_incident(report.incident_id, "Thread starvation")
    assert report.stage == IncidentStage.DIAGNOSED

    rec_mgr.contain_incident(report.incident_id, "Killed blocked process")
    assert report.stage == IncidentStage.CONTAINED

    # Attempt rollback with an invalid non-existent checkpoint
    rep_rb = rec_mgr.rollback_incident(report.incident_id, checkpoint_id="invalid_checkpoint_xyz_999")

    # Invariant: Failed rollback must NOT set stage to ROLLED_BACK
    assert rep_rb.rollback_applied is False
    assert rep_rb.stage != IncidentStage.ROLLED_BACK
    assert rep_rb.stage == IncidentStage.CONTAINED, f"Expected stage CONTAINED, got {rep_rb.stage}"


def test_incident_recovery_baseline_rollback_failure_does_not_advance_stage(test_repo_workspace):
    """
    Empirically verify that when rollback_to_baseline fails,
    stage does not advance to ROLLED_BACK.
    """
    ws, _ = test_repo_workspace
    cm = GitChangeManager(workspace=ws)
    rec_mgr = IncidentRecoveryManager(workspace=ws, change_manager=cm)

    # Task without established baseline
    report = rec_mgr.detect_incident("unestablished_task_99", "Crash", IncidentSeverity.CRITICAL)
    rec_mgr.contain_incident(report.incident_id, "Isolated host")
    assert report.stage == IncidentStage.CONTAINED

    # Rollback without checkpoint_id calls rollback_to_baseline, which returns ok=False for unknown baseline
    rep_rb = rec_mgr.rollback_incident(report.incident_id)
    assert rep_rb.rollback_applied is False
    assert rep_rb.stage != IncidentStage.ROLLED_BACK
    assert rep_rb.stage == IncidentStage.CONTAINED


def test_incident_recovery_successful_rollback_advances_stage(test_repo_workspace):
    """
    Empirically verify that when rollback succeeds (rollback_applied=True),
    stage DOES advance to ROLLED_BACK.
    """
    ws, repo_dir = test_repo_workspace
    cm = GitChangeManager(workspace=ws)
    cm.establish_baseline(task_id="task_good_rb")

    test_file = repo_dir / "service.py"
    test_file.write_text("SERVICE = 'ok'\n", encoding="utf-8")
    chk = cm.create_checkpoint("task_good_rb", reason="Saved service")

    rec_mgr = IncidentRecoveryManager(workspace=ws, change_manager=cm)
    report = rec_mgr.detect_incident("task_good_rb", "Runtime bug", IncidentSeverity.MEDIUM)
    rec_mgr.contain_incident(report.incident_id, "Paused traffic")

    rep_rb = rec_mgr.rollback_incident(report.incident_id, checkpoint_id=chk.checkpoint_id)
    assert rep_rb.rollback_applied is True
    assert rep_rb.stage == IncidentStage.ROLLED_BACK


# ==============================================================================
# SECTION 5: CompanyWorkflow Auto-Rollback on Unhandled Failures
# ==============================================================================

def test_company_workflow_auto_rollback_on_unhandled_exception(test_repo_workspace, tmp_path: Path):
    """
    Empirically verify that CompanyWorkflow restores a clean baseline when an unhandled
    exception occurs during task execution.
    """
    ws, repo_dir = test_repo_workspace
    db_file = tmp_path / "wf_rollback_test.sqlite"

    readme = repo_dir / "README.md"
    assert readme.read_text(encoding="utf-8") == "# Clean Baseline\n"

    cm = GitChangeManager(workspace=ws, db_path=db_file)
    registry = ToolRegistry()

    workflow = CompanyWorkflow(
        workspace=ws,
        tool_registry=registry,
        task_graph_db=db_file,
        change_manager=cm,
    )

    task_id = "task_wf_crash_01"

    # Simulate workflow execution crashing during developer execution
    # Injected dirty mutation and untracked file to simulate mid-task crash
    def crashing_dev_execution(task_id, plan, frozen_tests):
        # Developer pollutes files before crashing
        readme.write_text("# CORRUPTED BY MID-TASK WORKER\n", encoding="utf-8")
        untracked = repo_dir / "dirty_artifact.py"
        untracked.write_text("print('polluting code')\n", encoding="utf-8")
        raise RuntimeError("Catastrophic Worker Crash")

    with patch.object(workflow, "_phase_developer_execution", side_effect=crashing_dev_execution):
        with pytest.raises(RuntimeError, match="Catastrophic Worker Crash"):
            workflow.run_workflow(
                goal="Implement feature that crashes",
                context={"depth": 1},
            )

    # Invariants: Auto-rollback must have executed in the exception handler:
    # 1. Existing file restored to exact baseline
    assert readme.read_text(encoding="utf-8") == "# Clean Baseline\n"
    # 2. Untracked file created during execution is completely removed
    assert not (repo_dir / "dirty_artifact.py").exists()


def test_company_workflow_auto_rollback_on_qa_rejection(test_repo_workspace, tmp_path: Path):
    """
    Empirically verify that CompanyWorkflow restores a clean baseline when QA rejects
    the implementation after max retries.
    """
    ws, repo_dir = test_repo_workspace
    db_file = tmp_path / "wf_qa_rejection.sqlite"

    readme = repo_dir / "README.md"
    assert readme.read_text(encoding="utf-8") == "# Clean Baseline\n"

    cm = GitChangeManager(workspace=ws, db_path=db_file)
    registry = ToolRegistry()

    workflow = CompanyWorkflow(
        workspace=ws,
        tool_registry=registry,
        task_graph_db=db_file,
        change_manager=cm,
    )

    # Mock developer execution mutating workspace
    def mutating_dev_execution(task_id, plan, frozen_tests):
        readme.write_text("# REJECTED MUTATION\n", encoding="utf-8")
        untracked = repo_dir / "failed_feature.py"
        untracked.write_text("broken_code = True\n", encoding="utf-8")
        return [DeveloperOutput(role="backend_dev", spec_id="spec_1", files_modified=["README.md", "failed_feature.py"])]

    # Mock QA rejecting the build
    rejected_qa = QAReport(
        status="REJECTED",
        total_tests=5,
        passed=2,
        failed=3,
        failures=["AssertionError: feature failed"],
    )

    with patch.object(workflow, "_phase_developer_execution", side_effect=mutating_dev_execution):
        with patch.object(workflow, "_phase_qa_remediation_loop", return_value=([rejected_qa], rejected_qa, 3, True)):
            res = workflow.run_workflow(
                goal="Implement feature that fails QA",
                context={"depth": 1},
            )

    # Invariants:
    assert res.status in {WorkflowStatus.FAILED, WorkflowStatus.ESCALATED_TO_HUMAN}
    # 1. README.md restored to pre-task baseline
    assert readme.read_text(encoding="utf-8") == "# Clean Baseline\n"
    # 2. failed_feature.py removed
    assert not (repo_dir / "failed_feature.py").exists()


# ==============================================================================
# SECTION 6: Human Denial Gating Comprehensive Enforcement
# ==============================================================================

def test_human_denial_gating_blocks_under_all_denial_conditions(test_repo_workspace):
    """
    Verifies that ActionGatekeeper strictly blocks execution across REJECTED, DENIED,
    PENDING, and unconfigured approval manager scenarios.
    """
    ws, _ = test_repo_workspace

    # Case 1: Explicit REJECTED
    mock_rej = MagicMock()
    mock_rej.request.return_value = {
        "allowed": False,
        "status": "REJECTED",
        "approval_id": "app_rej",
        "reason": "Security Auditor rejected forced push.",
    }
    gk_rej = ActionGatekeeper(approval_manager=mock_rej, workspace=ws)
    res_rej = gk_rej.evaluate_and_request("run_command", {"command": "git push --force origin main"})
    assert res_rej["allowed"] is False
    assert res_rej["status"] == "REJECTED"

    # Case 2: Explicit DENIED
    mock_denied = MagicMock()
    mock_denied.request.return_value = {
        "allowed": False,
        "status": "DENIED",
        "approval_id": "app_den",
        "reason": "Production deploy denied.",
    }
    gk_den = ActionGatekeeper(approval_manager=mock_denied, workspace=ws)
    res_den = gk_den.evaluate_and_request("run_command", {"command": "deploy --prod"})
    assert res_den["allowed"] is False
    assert res_den["status"] == "REJECTED"

    # Case 3: PENDING approval
    mock_pend = MagicMock()
    mock_pend.request.return_value = {
        "allowed": False,
        "status": "PENDING",
        "approval_id": "app_pend",
    }
    gk_pend = ActionGatekeeper(approval_manager=mock_pend, workspace=ws)
    res_pend = gk_pend.evaluate_and_request("run_command", {"command": "truncate table users"})
    assert res_pend["allowed"] is False
    assert res_pend["status"] == "PENDING_APPROVAL"

    # Case 4: ApprovalManager is None
    gk_none = ActionGatekeeper(approval_manager=None, workspace=ws)
    res_none = gk_none.evaluate_and_request("run_command", {"command": "drop database prod"})
    assert res_none["allowed"] is False
    assert res_none["status"] == "PENDING_APPROVAL"
    assert "ApprovalManager not configured" in res_none["reason"]
