"""
Automated Tier 1-4 Test Suite for Milestone 5 (F11 & F12).
Tests:
- Autonomous Git Change Manager: baselines, checkpoints, non-destructive rollbacks, SQLite persistence (F11).
- Incident Recovery & Action Classification: automatic vs approval-required, prohibited command blocking, 8-stage incident recovery loop (F12).
- Boundary and adversarial edge cases: multi-checkpoint isolation, invalid checkpoints, workspace confinement, human denial gates, negative verification holding.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from living_assistant.agents.software_company.change_manager import (
    CheckpointRecord,
    GitChangeManager,
    TaskBaseline,
)
from living_assistant.agents.software_company.incident_recovery import (
    ActionClass,
    ActionGatekeeper,
    IncidentRecoveryManager,
    IncidentSeverity,
    IncidentStage,
)
from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.core.workspace import Workspace, WorkspaceViolation


@pytest.fixture
def test_workspace(tmp_path: Path) -> Workspace:
    ws_dir = tmp_path / "test_repo"
    ws_dir.mkdir(parents=True, exist_ok=True)
    # Initialize real local git repository for testing GitChangeManager
    subprocess.run(["git", "init"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(ws_dir), capture_output=True, check=True)

    init_file = ws_dir / "README.md"
    init_file.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(ws_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(ws_dir), capture_output=True, check=True)

    return Workspace([ws_dir])


# =============================================================================
# Tier 1: Unit Tests (Change Manager Baselines & Checkpoints)
# =============================================================================


def test_f11_tier1_git_status_and_baseline_establishment(test_workspace: Workspace):
    cm = GitChangeManager(workspace=test_workspace)
    status = cm.get_git_status()
    assert status["commit_sha"] != "unknown"
    assert status["is_dirty"] is False
    assert len(status["uncommitted_files"]) == 0

    baseline = cm.establish_baseline(task_id="task_101")
    assert isinstance(baseline, TaskBaseline)
    assert baseline.task_id == "task_101"
    assert baseline.commit_sha == status["commit_sha"]
    assert cm.get_baseline("task_101") is baseline


def test_f11_tier1_create_checkpoint_records_snapshot_and_changed_files(test_workspace: Workspace):
    ws_dir = test_workspace.roots[0]
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_102")

    # Touch a new file
    work_file = ws_dir / "feature.py"
    work_file.write_text("def work(): pass\n", encoding="utf-8")

    chk = cm.create_checkpoint(task_id="task_102", reason="Added feature.py")
    assert isinstance(chk, CheckpointRecord)
    assert chk.task_id == "task_102"
    assert chk.snapshot_id is not None
    assert "feature.py" in chk.files_changed_since_baseline


# =============================================================================
# Tier 2: Safe Rollback & Confinement (Non-Destructive Operations)
# =============================================================================


def test_f11_tier2_safe_rollback_to_checkpoint_restores_file(test_workspace: Workspace):
    ws_dir = test_workspace.roots[0]
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_103")

    initial_file = ws_dir / "config.yaml"
    initial_file.write_text("version: 1.0\n", encoding="utf-8")
    chk = cm.create_checkpoint(task_id="task_103", reason="Known good config")

    # Mutate with corrupt configuration
    initial_file.write_text("version: corrupted_garbage\n", encoding="utf-8")
    assert "corrupted" in initial_file.read_text(encoding="utf-8")

    # Non-destructive rollback
    res = cm.rollback_to_checkpoint(chk.checkpoint_id)
    assert res["ok"] is True
    assert res["method"] == "workspace_snapshot_restore"
    assert initial_file.read_text(encoding="utf-8") == "version: 1.0\n"


def test_f11_tier2_rollback_to_baseline_cleans_dirty_changes(test_workspace: Workspace):
    ws_dir = test_workspace.roots[0]
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_104")

    # Modify committed file
    readme = ws_dir / "README.md"
    readme.write_text("# Contaminated README\n", encoding="utf-8")
    assert "Contaminated" in readme.read_text(encoding="utf-8")

    res = cm.rollback_to_baseline(task_id="task_104")
    assert res["ok"] is True
    assert readme.read_text(encoding="utf-8") == "# Test Repo\n"


# =============================================================================
# Tier 3: Action Classification & Human Approval Gates (F12)
# =============================================================================


def test_f12_tier3_action_classification_automatic_vs_approval_vs_prohibited(test_workspace: Workspace):
    gatekeeper = ActionGatekeeper(workspace=test_workspace)

    # 1. Automatic action
    cls1, r1 = gatekeeper.classify_action("read_file", {"path": "src/main.py"})
    assert cls1 == ActionClass.AUTOMATIC

    # 2. Approval required (force push, prod deploy, destructive db)
    cls2, r2 = gatekeeper.classify_action("run_command", {"command": "git push --force origin main"})
    assert cls2 == ActionClass.APPROVAL_REQUIRED
    assert "human approval" in r2.lower()

    cls3, r3 = gatekeeper.classify_action("deploy", {"is_production_deploy": True})
    assert cls3 == ActionClass.APPROVAL_REQUIRED

    # 3. Prohibited action (git reset --hard)
    cls4, r4 = gatekeeper.classify_action("run_command", {"command": "git reset --hard HEAD~1"})
    assert cls4 == ActionClass.PROHIBITED
    assert "non-destructive" in r4.lower()


def test_f12_tier3_approval_manager_interaction_when_approval_required(tmp_path: Path, test_workspace: Workspace):
    db_file = tmp_path / "approvals.sqlite3"
    app_store = ApprovalStore(db_path=db_file)
    app_mgr = ApprovalManager(store=app_store, interactive=False)

    gatekeeper = ActionGatekeeper(approval_manager=app_mgr, workspace=test_workspace)

    # Privileged command requests approval
    res = gatekeeper.evaluate_and_request("run_command", {"command": "git push -f origin main"}, task_id="task_105")
    assert res["allowed"] is False
    assert res["status"] == "PENDING_APPROVAL"
    assert res["approval_id"] is not None


# =============================================================================
# Tier 4: Incident Recovery 8-Stage Workflow Integration
# =============================================================================


def test_f12_tier4_incident_recovery_workflow_detect_contain_rollback_resolve(test_workspace: Workspace):
    ws_dir = test_workspace.roots[0]
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_106")

    # Step 0: Save healthy code
    service_file = ws_dir / "service.py"
    service_file.write_text("def ping(): return 'pong'\n", encoding="utf-8")
    chk = cm.create_checkpoint(task_id="task_106", reason="Working service")

    # Step 1: Defect introduced
    service_file.write_text("def ping(): raise RuntimeError('Deadlock')\n", encoding="utf-8")

    rec_mgr = IncidentRecoveryManager(workspace=test_workspace, change_manager=cm)

    # 1. Detect
    inc = rec_mgr.detect_incident(task_id="task_106", error_context="RuntimeError: Deadlock in service.py", severity=IncidentSeverity.CRITICAL)
    assert inc.stage == IncidentStage.DETECTED

    # 2. Diagnose
    inc = rec_mgr.diagnose_incident(inc.incident_id, analysis="Deadlock triggered by concurrent lock contention.")
    assert inc.stage == IncidentStage.DIAGNOSED

    # 3. Contain
    inc = rec_mgr.contain_incident(inc.incident_id, action="Isolated traffic and suspended worker.")
    assert inc.stage == IncidentStage.CONTAINED

    # 4. Rollback
    inc = rec_mgr.rollback_incident(inc.incident_id, checkpoint_id=chk.checkpoint_id)
    assert inc.stage == IncidentStage.ROLLED_BACK
    assert inc.rollback_applied is True
    assert "pong" in service_file.read_text(encoding="utf-8")

    # 5. Repair
    fixed_file = ws_dir / "service.py"
    fixed_file.write_text("def ping(): return 'repaired_pong'\n", encoding="utf-8")
    inc = rec_mgr.record_repair(inc.incident_id, repaired_artifacts=["service.py"])
    assert inc.stage == IncidentStage.REPAIRED

    # 6, 7 & 8: Test -> Verify -> Document/Resolve
    inc = rec_mgr.verify_and_resolve(inc.incident_id, tests_passed=True)
    assert inc.stage == IncidentStage.RESOLVED
    assert inc.verification_passed is True
    assert inc.resolved_at is not None


# =============================================================================
# Milestone 5 Extensions: Edge Cases, Confinement, Denial, & SQLite Persistence
# =============================================================================


def test_f11_multi_level_checkpoint_rollback_isolation(test_workspace: Workspace):
    """Verifies that rolling back to Checkpoint 2 accurately isolates state despite subsequent Checkpoint 3 mutations."""
    ws_dir = test_workspace.roots[0]
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_multi_chk")

    file_a = ws_dir / "module_a.py"
    file_b = ws_dir / "module_b.py"

    # State 1: File A = v1
    file_a.write_text("VERSION_A = 1\n", encoding="utf-8")
    chk1 = cm.create_checkpoint(task_id="task_multi_chk", reason="Checkpoint 1: File A v1")

    # State 2: File A = v2, File B = v1
    file_a.write_text("VERSION_A = 2\n", encoding="utf-8")
    file_b.write_text("VERSION_B = 1\n", encoding="utf-8")
    chk2 = cm.create_checkpoint(task_id="task_multi_chk", reason="Checkpoint 2: File A v2, File B v1")

    # State 3: File A = v3, File B = v2
    file_a.write_text("VERSION_A = 3\n", encoding="utf-8")
    file_b.write_text("VERSION_B = 2\n", encoding="utf-8")
    chk3 = cm.create_checkpoint(task_id="task_multi_chk", reason="Checkpoint 3: File A v3, File B v2")
    assert chk3.checkpoint_id is not None

    # Rollback to Checkpoint 2
    res2 = cm.rollback_to_checkpoint(chk2.checkpoint_id)
    assert res2["ok"] is True
    assert file_a.read_text(encoding="utf-8") == "VERSION_A = 2\n"
    assert file_b.read_text(encoding="utf-8") == "VERSION_B = 1\n"

    # Rollback to Checkpoint 1
    res1 = cm.rollback_to_checkpoint(chk1.checkpoint_id)
    assert res1["ok"] is True
    assert file_a.read_text(encoding="utf-8") == "VERSION_A = 1\n"
    assert not file_b.exists()


def test_f11_rollback_invalid_checkpoint_fails_gracefully(test_workspace: Workspace):
    """Verifies that rolling back an invalid or non-existent checkpoint returns an error dictionary rather than throwing an unhandled exception."""
    cm = GitChangeManager(workspace=test_workspace)
    res = cm.rollback_to_checkpoint("chk_non_existent_id")
    assert res["ok"] is False
    assert "not found" in res["error"].lower()


def test_f11_workspace_confinement_boundary_violations(test_workspace: Workspace, tmp_path: Path):
    """Verifies that attempting git operations outside workspace root raises WorkspaceViolation."""
    outside_dir = tmp_path / "outside_escape_dir"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret_data\n", encoding="utf-8")

    # Initialization with repo_path outside allowed workspace roots raises WorkspaceViolation
    with pytest.raises(WorkspaceViolation):
        GitChangeManager(workspace=test_workspace, repo_path=outside_dir)

    # get_diff targeting a path outside allowed workspace roots raises WorkspaceViolation
    cm = GitChangeManager(workspace=test_workspace)
    with pytest.raises(WorkspaceViolation):
        cm.get_diff(paths=[str(outside_file)])


def test_f11_sqlite_persistence_across_manager_instances(test_workspace: Workspace, tmp_path: Path):
    """Verifies that baselines and checkpoints persist into SQLite across distinct GitChangeManager instances."""
    db_file = tmp_path / "test_persistence.sqlite3"
    cm1 = GitChangeManager(workspace=test_workspace, db_path=db_file)
    baseline1 = cm1.establish_baseline(task_id="task_persist_01")
    assert baseline1.task_id == "task_persist_01"

    ws_dir = test_workspace.roots[0]
    test_file = ws_dir / "persisted_script.py"
    test_file.write_text("INITIAL_STATE = True\n", encoding="utf-8")

    chk1 = cm1.create_checkpoint(task_id="task_persist_01", reason="Saved initial script")
    assert chk1.checkpoint_id == "chk_task_persist_01_1"

    # Second instance pointing to identical SQLite database file
    cm2 = GitChangeManager(workspace=test_workspace, db_path=db_file)
    loaded_baseline = cm2.get_baseline("task_persist_01")
    assert loaded_baseline is not None
    assert loaded_baseline.task_id == "task_persist_01"
    assert loaded_baseline.commit_sha == baseline1.commit_sha

    loaded_checkpoints = cm2.get_checkpoints("task_persist_01")
    assert len(loaded_checkpoints) == 1
    assert loaded_checkpoints[0].checkpoint_id == chk1.checkpoint_id
    assert loaded_checkpoints[0].snapshot_id == chk1.snapshot_id

    # Mutate file and verify cm2 can roll back using loaded checkpoint
    test_file.write_text("INITIAL_STATE = CORRUPT\n", encoding="utf-8")
    res = cm2.rollback_to_checkpoint(loaded_checkpoints[0].checkpoint_id)
    assert res["ok"] is True
    assert test_file.read_text(encoding="utf-8") == "INITIAL_STATE = True\n"


def test_f12_prohibited_commands_blocked(test_workspace: Workspace):
    """Verifies that dangerous commands (git reset --hard, fork bombs, disk formats) are unconditionally blocked as PROHIBITED."""
    gatekeeper = ActionGatekeeper(workspace=test_workspace)

    prohibited_samples = [
        "git reset --hard HEAD~1",
        ":(){ :|:& };:",
        "format c:",
        "format d:",
        "mkfs.ext4 /dev/sda1",
    ]

    for cmd in prohibited_samples:
        cls, r = gatekeeper.classify_action("run_command", {"command": cmd})
        assert cls == ActionClass.PROHIBITED
        res = gatekeeper.evaluate_and_request("run_command", {"command": cmd})
        assert res["allowed"] is False
        assert res["status"] == "PROHIBITED"


def test_f12_human_denial_blocks_destructive_action(test_workspace: Workspace):
    """Verifies that human denial (status REJECTED) strictly blocks execution of approval-required actions."""
    mock_approval = MagicMock()
    mock_approval.request.return_value = {
        "allowed": False,
        "status": "REJECTED",
        "approval_id": "appr_denied_test",
        "reason": "Security auditor denied forced push.",
    }

    gatekeeper = ActionGatekeeper(approval_manager=mock_approval, workspace=test_workspace)
    res = gatekeeper.evaluate_and_request(
        "run_command",
        {"command": "git push --force origin main"},
        task_id="task_denied_test",
    )
    assert res["allowed"] is False
    assert res["status"] == "REJECTED"
    assert res["action_class"] == "approval_required"


def test_f12_negative_incident_workflow_verify_fails_holds_stage(test_workspace: Workspace):
    """Verifies that when verification tests fail during verify_and_resolve, incident remains at TESTED and does NOT transition to RESOLVED."""
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_neg_inc")
    rec_mgr = IncidentRecoveryManager(workspace=test_workspace, change_manager=cm)

    inc = rec_mgr.detect_incident("task_neg_inc", "AssertionError in tests")
    assert inc.stage == IncidentStage.DETECTED

    rec_mgr.diagnose_incident(inc.incident_id, "Syntax error in math utility")
    rec_mgr.contain_incident(inc.incident_id, "Suspended agent loop")
    rec_mgr.record_repair(inc.incident_id, ["math_util.py"])

    # Negative verification: tests_passed=False
    inc_after_verify = rec_mgr.verify_and_resolve(inc.incident_id, tests_passed=False)
    assert inc_after_verify.stage == IncidentStage.TESTED
    assert inc_after_verify.verification_passed is False
    assert inc_after_verify.resolved_at is None
    assert inc_after_verify.stage != IncidentStage.RESOLVED


def test_f11_diff_inspection_and_clean_rollback_noop(test_workspace: Workspace):
    """Verifies diff inspection targeting specific paths and clean baseline rollback no-op behavior."""
    ws_dir = test_workspace.roots[0]
    cm = GitChangeManager(workspace=test_workspace)
    cm.establish_baseline(task_id="task_diff_test")

    # Clean rollback is no-op
    res = cm.rollback_to_baseline(task_id="task_diff_test")
    assert res["ok"] is True
    assert res["restored_files"] == 0

    # Modify file and verify targeted get_diff
    readme = ws_dir / "README.md"
    readme.write_text("# Test Repo\nNew Line Added\n", encoding="utf-8")
    diff = cm.get_diff(paths=["README.md"])
    assert "New Line Added" in diff


# =============================================================================
# Milestone 5 Iteration 2 Remediation Test Invariants
# =============================================================================


def test_f12_prohibited_command_whitespace_and_token_obfuscation(test_workspace: Workspace):
    """Verifies that all obfuscated prohibited command variations are blocked as PROHIBITED."""
    gatekeeper = ActionGatekeeper(workspace=test_workspace)

    prohibited_cases = [
        "git  reset   --hard",
        "git\treset\t--hard",
        "git \t reset \t --hard",
        "   git reset --hard   ",
        "git reset HEAD --hard",
        "git reset master --hard",
        "git reset --hard HEAD~2",
        "git reset -q --hard",
        "git reset --hard -q",
        ":(){ :|:& };:",
        ":(){:|:&};:",
        ": () { : | : & } ; :",
        "format c:",
        "format   d:",
        "format /y c:",
        "format /q /y c:",
        "format.com c:",
        "format c: /fs:ntfs",
        "mkfs.ext4 /dev/sda1",
        "mkfs -t ext4 /dev/sda1",
        "format disk 0",
    ]

    for cmd in prohibited_cases:
        cls, reason = gatekeeper.classify_action("run_command", {"command": cmd})
        assert cls == ActionClass.PROHIBITED, f"Command '{cmd}' must be PROHIBITED, got {cls}"
        assert "non-destructive" in reason.lower()
        res = gatekeeper.evaluate_and_request("run_command", {"command": cmd})
        assert res["allowed"] is False
        assert res["status"] == "PROHIBITED"


def test_f12_approval_required_command_whitespace_and_obfuscation(test_workspace: Workspace):
    """Verifies that all obfuscated approval-required command variations require approval."""
    gatekeeper = ActionGatekeeper(workspace=test_workspace)

    approval_cases = [
        "git  push   --force",
        "git\tpush\t--force",
        "git push  origin  --force",
        "git push origin -f",
        "git push --force origin main",
        "git push -f origin main",
        "git\tpush\t-f",
        "git push -uf origin main",
        "git push origin +main",
        "git push --force-with-lease",
        "rm  -rf   node_modules",
        "rm\t-rf\t/tmp/cache",
        "drop  database  production",
        "drop\tdatabase\tanalytics",
        "truncate  table  users",
        "truncate table users;",
        "deploy  --prod",
        "deploy\t--prod",
        "production  deploy",
        "modify_security_policy",
        "modify security policy",
        "delete_critical_data",
        "delete critical data",
    ]

    for cmd in approval_cases:
        cls, reason = gatekeeper.classify_action("run_command", {"command": cmd})
        assert cls == ActionClass.APPROVAL_REQUIRED, f"Command '{cmd}' must be APPROVAL_REQUIRED, got {cls}"
        assert "human approval" in reason.lower()


def test_f12_legitimate_commands_remain_automatic_no_false_positives(test_workspace: Workspace):
    """Verifies that normal non-destructive developer commands remain AUTOMATIC."""
    gatekeeper = ActionGatekeeper(workspace=test_workspace)

    automatic_cases = [
        "git status",
        "git diff",
        "git log -n 5",
        "git checkout feature-branch",
        "git reset file.txt",
        "git reset HEAD README.md",
        "git push origin feature-branch",
        "git push",
        "pytest tests/ -v",
        "rm file.txt",
        "format_code.py --fix",
    ]

    for cmd in automatic_cases:
        cls, _ = gatekeeper.classify_action("run_command", {"command": cmd})
        assert cls == ActionClass.AUTOMATIC, f"Command '{cmd}' should be AUTOMATIC, got {cls}"


def test_f11_deep_multi_checkpoint_baseline_restoration(test_workspace: Workspace, tmp_path: Path):
    """Verifies that intermediate checkpoints created during task do not leak when rolling back to baseline."""
    db_file = tmp_path / "deep_test.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    ws_dir = test_workspace.roots[0]
    task_id = "task_deep_01"

    readme = ws_dir / "README.md"
    assert readme.read_text(encoding="utf-8") == "# Test Repo\n"

    baseline = cm.establish_baseline(task_id=task_id)
    assert baseline.is_dirty is False

    # Step 1: mutates README.md, adds step1.py, creates checkpoint 1
    readme.write_text("# Test Repo\nStep 1 Mutation\n", encoding="utf-8")
    (ws_dir / "step1.py").write_text("# step 1\n", encoding="utf-8")
    chk1 = cm.create_checkpoint(task_id=task_id, reason="Step 1 complete")
    assert chk1.checkpoint_id == f"chk_{task_id}_1"

    # Step 2: mutates README.md, adds step2.py, creates checkpoint 2
    readme.write_text("# Test Repo\nStep 2 Mutation\n", encoding="utf-8")
    (ws_dir / "step2.py").write_text("# step 2\n", encoding="utf-8")
    chk2 = cm.create_checkpoint(task_id=task_id, reason="Step 2 complete")
    assert chk2.checkpoint_id == f"chk_{task_id}_2"

    # Step 3: corrupts README.md, adds step3.py, creates checkpoint 3
    readme.write_text("# Test Repo\nCORRUPT Step 3 Mutation\n", encoding="utf-8")
    (ws_dir / "step3.py").write_text("# step 3\n", encoding="utf-8")
    chk3 = cm.create_checkpoint(task_id=task_id, reason="Step 3 complete")
    assert chk3.checkpoint_id == f"chk_{task_id}_3"

    # Rollback to baseline: must restore to baseline (clean repo), NOT checkpoint 1, 2, or 3
    res = cm.rollback_to_baseline(task_id=task_id)
    assert res["ok"] is True
    assert readme.read_text(encoding="utf-8") == "# Test Repo\n"
    assert not (ws_dir / "step1.py").exists()
    assert not (ws_dir / "step2.py").exists()
    assert not (ws_dir / "step3.py").exists()

    st = cm.get_git_status()
    assert st["is_dirty"] is False


def test_f11_pretask_dirty_baseline_snapshot_restoration_with_checkpoints(test_workspace: Workspace, tmp_path: Path):
    """Verifies that pre-task dirty state is faithfully restored even when intermediate checkpoints exist."""
    db_file = tmp_path / "dirty_test.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    ws_dir = test_workspace.roots[0]
    task_id = "task_dirty_pre"

    user_file = ws_dir / "user_work.txt"
    user_file.write_text("PRE_TASK_UNCOMMITTED_WORK\n", encoding="utf-8")

    baseline = cm.establish_baseline(task_id=task_id)
    assert baseline.is_dirty is True
    assert baseline.baseline_snapshot_id is not None

    # Intermediate checkpoint during task
    user_file.write_text("POLLUTED_BY_TASK\n", encoding="utf-8")
    task_trash = ws_dir / "task_trash.py"
    task_trash.write_text("trash\n", encoding="utf-8")
    chk1 = cm.create_checkpoint(task_id=task_id, reason="Task step 1")
    assert chk1.checkpoint_id == f"chk_{task_id}_1"

    res = cm.rollback_to_baseline(task_id=task_id)
    assert res["ok"] is True
    assert user_file.read_text(encoding="utf-8") == "PRE_TASK_UNCOMMITTED_WORK\n"
    assert not task_trash.exists()


def test_f11_rollback_safe_external_symlink_handling(test_workspace: Workspace, tmp_path: Path):
    """Verifies that untracked external symlinks are cleanly unlinked without raising WorkspaceViolation."""
    db_file = tmp_path / "sym_test.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    ws_dir = test_workspace.roots[0]
    task_id = "task_symlink_test"

    cm.establish_baseline(task_id=task_id)

    outside_dir = tmp_path / "outside_secret"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret_data\n", encoding="utf-8")

    link_path = ws_dir / "bad_link"
    try:
        link_path.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this environment")

    assert link_path.is_symlink()

    rb_res = cm.rollback_to_baseline(task_id=task_id)
    assert rb_res["ok"] is True
    assert not link_path.exists()
    assert not link_path.is_symlink()
    assert outside_file.exists()


def test_f11_rollback_safe_external_symlink_logic_mocked(test_workspace: Workspace, tmp_path: Path):
    """Verifies lexical path check and unlinking branch when a symlink is reported, regardless of OS privileges."""
    from unittest.mock import patch
    db_file = tmp_path / "mock_sym.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    ws_dir = test_workspace.roots[0]
    task_id = "task_symlink_mock"

    cm.establish_baseline(task_id=task_id)
    dummy_file = ws_dir / "dummy_link"
    dummy_file.write_text("symlink_placeholder\n", encoding="utf-8")

    with patch.object(Path, "is_symlink", return_value=True):
        rb_res = cm.rollback_to_baseline(task_id=task_id)
        assert rb_res["ok"] is True
        assert not dummy_file.exists()


def test_f11_rollback_reverts_task_commits_when_working_tree_clean(test_workspace: Workspace, tmp_path: Path):
    """Verifies that Level 3 commit revert executes during baseline rollback even when working tree is clean."""
    db_file = tmp_path / "revert_test.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    ws_dir = test_workspace.roots[0]
    task_id = "task_commit_revert_test"

    cm.establish_baseline(task_id=task_id)
    feat_file = ws_dir / "feature.py"
    feat_file.write_text("def broken_feature(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.py"], cwd=str(ws_dir), check=True)

    commit_res = cm.safe_commit(task_id=task_id, message="feat: add broken feature")
    assert commit_res["ok"] is True

    # At this point working tree is clean, but a commit exists
    status_before = cm.get_git_status()
    assert status_before["is_dirty"] is False

    # Rollback to baseline must execute safe_revert_commit
    rb_res = cm.rollback_to_baseline(task_id=task_id)
    assert rb_res["ok"] is True
    assert len(rb_res["reverted_commits"]) == 1
    assert rb_res["reverted_commits"][0] == commit_res["commit_sha"]

    # In working tree, the feature file content is removed by the revert
    assert not feat_file.exists()


def test_f11_thread_safe_checkpoint_id_generation(test_workspace: Workspace, tmp_path: Path):
    """Verifies concurrent checkpoint creation produces unique IDs without collisions or overwrites."""
    db_file = tmp_path / "concurrency_test.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    task_id = "task_concurrency_test"
    cm.establish_baseline(task_id=task_id)

    created_ids: list[str] = []
    errors: list[Exception] = []

    def worker(worker_id: int):
        try:
            chk = cm.create_checkpoint(task_id=task_id, reason=f"Worker {worker_id} checkpoint")
            created_ids.append(chk.checkpoint_id)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(created_ids) == 10
    assert len(set(created_ids)) == 10, "All checkpoint IDs must be unique"
    all_checkpoints = cm.get_checkpoints(task_id)
    assert len(all_checkpoints) == 10


def test_f12_incident_rollback_failure_does_not_advance_stage(test_workspace: Workspace, tmp_path: Path):
    """Verifies that failed incident rollback does not falsely advance stage to ROLLED_BACK."""
    db_file = tmp_path / "inc_rb.sqlite3"
    cm = GitChangeManager(workspace=test_workspace, db_path=db_file)
    cm.establish_baseline(task_id="task_fail_rb")
    rec_mgr = IncidentRecoveryManager(workspace=test_workspace, change_manager=cm)

    inc = rec_mgr.detect_incident("task_fail_rb", "Test failure")
    rec_mgr.diagnose_incident(inc.incident_id, "Bad logic")
    rec_mgr.contain_incident(inc.incident_id, "Branch isolated")
    assert inc.stage == IncidentStage.CONTAINED

    rep_rb = rec_mgr.rollback_incident(inc.incident_id, checkpoint_id="invalid_nonexistent_chk")
    assert rep_rb.rollback_applied is False
    assert rep_rb.stage != IncidentStage.ROLLED_BACK
    assert rep_rb.stage == IncidentStage.CONTAINED
