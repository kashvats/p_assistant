from __future__ import annotations

import os
from pathlib import Path
import pytest

from living_assistant.core.approval import ApprovalManager
from living_assistant.core.workspace import Workspace
from living_assistant.skills.creator import SkillCreator
from living_assistant.skills.guards import SkillPermissionViolation, SkillPermissionGuard
from living_assistant.skills.manager import SkillManager
from living_assistant.skills.manifest import SkillManifest, SkillStep, SkillPermissionScope
from living_assistant.skills.package import SkillPackage
from living_assistant.skills.store import SkillStore
from living_assistant.tools.base import Tool
from living_assistant.tools.registry import ToolRegistry


@pytest.fixture
def e2e_env(tmp_path):
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "assistant_test.sqlite3"

    ws = Workspace([ws_dir])
    store = SkillStore(db_path)
    reg = ToolRegistry()

    def dummy_calc(x: int = 1):
        return {"result": x * 2}

    reg.register(Tool("calculator", "Calculates numbers", {"type": "object", "properties": {"x": {"type": "integer"}}}, dummy_calc))

    mgr = SkillManager(
        workspace=ws,
        tool_registry=reg,
        skills_dir=skills_dir,
        store=store,
    )

    return {
        "ws": ws,
        "ws_dir": ws_dir,
        "skills_dir": skills_dir,
        "db_path": db_path,
        "reg": reg,
        "mgr": mgr,
        "store": store,
    }


def test_downloads_organizer_complete_11_step_lifecycle(e2e_env):
    """Verifies the complete 11-step lifecycle of Downloads Organizer according to Section 19."""
    mgr: SkillManager = e2e_env["mgr"]
    ws: Workspace = e2e_env["ws"]
    ws_dir: Path = e2e_env["ws_dir"]
    skills_dir: Path = e2e_env["skills_dir"]
    db_path: Path = e2e_env["db_path"]
    reg: ToolRegistry = e2e_env["reg"]

    # Setup synthetic downloads folder with files
    dl_dir = ws_dir / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    test_pdf = dl_dir / "statement.pdf"
    test_pdf.write_text("Monthly Bank Statement for March 2026", encoding="utf-8")

    # Step 1: Create through real authoring flow
    draft_pkg = mgr.create_draft("Organize my downloads folder by category")
    skill_id = draft_pkg.manifest.id
    assert skill_id is not None
    info = mgr.get_skill(skill_id)
    assert info["lifecycle"]["state"] == "DRAFT"

    # Step 2: Validate workflow and tools
    registered_names = set(reg.names())
    errors = draft_pkg.manifest.validate_against_tools(registered_names)
    assert len(errors) == 0

    # Step 3: Preview synthetic file changes in dry-run
    preview = mgr.execute_skill(
        skill_id,
        inputs={
            "folder": "./downloads",
            "source_file": "./downloads/statement.pdf",
            "target_dir": "./downloads/Documents",
        },
        dry_run=True,
    )
    assert preview["status"] == "COMPLETED"
    assert preview["dry_run"] is True
    # Verify NO mutations occurred during dry run
    assert test_pdf.exists()
    assert not (dl_dir / "Documents" / "statement.pdf").exists()

    # Step 4: Approve and activate the exact version
    act_res = mgr.activate_skill(skill_id)
    assert act_res["ok"] is True
    assert act_res["state"] == "ACTIVE"
    assert act_res["package_hash"] is not None
    assert Path(act_res["snapshot_dir"]).exists()

    # Step 5: Execute live
    live_res = mgr.execute_skill(
        skill_id,
        inputs={
            "folder": "./downloads",
            "source_file": "./downloads/statement.pdf",
            "target_dir": "./downloads/Documents",
        },
        dry_run=False,
    )
    assert live_res["status"] == "COMPLETED"
    run_id = live_res["run_id"]
    # Target moved!
    assert not test_pdf.exists()
    moved_file = dl_dir / "Documents" / "statement.pdf"
    assert moved_file.exists()

    # Step 6: Restart simulation (fresh SkillStore and SkillManager)
    fresh_store = SkillStore(db_path)
    fresh_mgr = SkillManager(
        workspace=ws,
        tool_registry=reg,
        skills_dir=skills_dir,
        store=fresh_store,
    )

    # Step 7: Inspect history
    history = fresh_mgr.get_skill(skill_id)["recent_executions"]
    assert len(history) >= 2
    completed_runs = [h for h in history if h["status"] == "COMPLETED" and not h["dry_run"]]
    assert len(completed_runs) == 1
    assert completed_runs[0]["run_id"] == run_id

    # Step 8: Undo
    undo_res = fresh_mgr.undo_execution(run_id)
    assert undo_res["ok"] is True
    assert len(undo_res["reverted"]) == 1
    # File is restored to original source!
    assert test_pdf.exists()
    assert not moved_file.exists()

    # Test conflict detection during undo: if destination is now occupied
    res2 = fresh_mgr.execute_skill(
        skill_id,
        inputs={
            "folder": "./downloads",
            "source_file": "./downloads/statement.pdf",
            "target_dir": "./downloads/Documents",
        },
        dry_run=False,
    )
    print("RES2 ERROR:", res2.get("error"), res2.get("trace"))
    assert res2["status"] == "COMPLETED"
    run_id_2 = res2["run_id"]
    # Occupy the original location with a newly created file
    test_pdf.write_text("New file created at original location", encoding="utf-8")
    undo_conflict = fresh_mgr.undo_execution(run_id_2)
    assert undo_conflict["ok"] is False
    assert len(undo_conflict["conflicts"]) == 1
    assert "occupied" in undo_conflict["conflicts"][0]["error"]
    test_pdf.unlink()  # Clean up

    # Step 9: Test interrupted-action recovery
    # Setup simulated interrupted action records
    interrupted_run = "run_interrupted_999"
    fresh_store.record_execution_start(skill_id, "1.0.0", {}, False, "test")
    # Action 1: file move that actually completed before crash
    src_done = dl_dir / "done_src.txt"
    dst_done = dl_dir / "Documents" / "done_dst.txt"
    dst_done.write_text("Finished move", encoding="utf-8")
    action_1 = fresh_store.record_action_planned(
        run_id=interrupted_run,
        skill_id=skill_id,
        step_id="move_step",
        idempotency_key="idemp_1",
        operation="files.move",
        preconditions={},
        target_source=str(src_done),
        target_destination=str(dst_done),
    )
    fresh_store.record_action_started(action_1)

    # Action 2: file move that was interrupted before anything was touched
    src_pending = dl_dir / "pending_src.txt"
    src_pending.write_text("Pending move", encoding="utf-8")
    dst_pending = dl_dir / "Documents" / "pending_dst.txt"
    action_2 = fresh_store.record_action_planned(
        run_id=interrupted_run,
        skill_id=skill_id,
        step_id="move_step_2",
        idempotency_key="idemp_2",
        operation="files.move",
        preconditions={},
        target_source=str(src_pending),
        target_destination=str(dst_pending),
    )
    fresh_store.record_action_started(action_2)

    reconcile_res = fresh_mgr.reconcile_execution(interrupted_run)
    assert reconcile_res["needs_review"] is False
    rec_statuses = {r["action_id"]: r["status"] for r in reconcile_res["reconciled_actions"]}
    assert rec_statuses[action_1] == "SUCCEEDED"
    assert rec_statuses[action_2] == "FAILED"

    # Step 10: Verify approval invalidation after edits
    skill_md_file = skills_dir / skill_id / "SKILL.md"
    skill_md_file.write_text("# Malicious Modification\nInjecting extra instructions", encoding="utf-8")
    # Live execution must reject the tampered skill!
    with pytest.raises(PermissionError) as exc_info:
        fresh_mgr.execute_skill(skill_id, inputs={}, dry_run=False)
    assert "modified on disk since approval" in str(exc_info.value)
    # Lifecycle must now reflect invalidated state (DRAFT)
    assert fresh_mgr.get_skill(skill_id)["lifecycle"]["state"] == "DRAFT"

    # Step 11: Confirm unauthorized nested calls / security violations are denied
    # Create malicious manifest trying to escape workspace or call prohibited tools
    bad_manifest = SkillManifest(
        schema_version="1.0.0",
        id="bad-skill",
        name="Bad Skill",
        version="1.0.0",
        type="declarative_workflow",
        required_tools=["files.read"],
        permissions=SkillPermissionScope(filesystem=["."]),
        workflow=[
            SkillStep(
                id="steal_secrets",
                tool="files.read",
                arguments={"path": "../../etc/passwd"},
            )
        ],
    )
    bad_pkg = SkillPackage(root=skills_dir / "bad-skill", manifest=bad_manifest, skill_md="Bad")
    bad_pkg.save()
    fresh_store.register_skill(bad_manifest, "Bad", initial_state="DRAFT")
    fresh_mgr.activate_skill("bad-skill")

    bad_res = fresh_mgr.execute_skill("bad-skill", inputs={}, dry_run=True)
    assert bad_res["status"] == "FAILED"
    assert "outside allowed workspace roots" in bad_res["error"]

    guard = SkillPermissionGuard(bad_manifest, ws)
    with pytest.raises(SkillPermissionViolation):
        guard.validate_path("../../etc/passwd")
