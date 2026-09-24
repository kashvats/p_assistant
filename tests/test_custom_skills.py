from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
import pytest

from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.skills import (
    SkillManifest,
    SkillPermissionScope,
    SkillStep,
    SkillPackage,
    SkillStore,
    SkillPermissionGuard,
    SkillPermissionViolation,
    DocumentExtractor,
    PortableToolAdapter,
    SkillCreator,
    SkillExecutor,
    ExternalSkillCollections,
    SkillManager,
    SkillRegistry,
)
from living_assistant.skills.examples import (
    get_daily_briefing_manifest,
    get_downloads_organizer_manifest,
    get_invoice_organizer_manifest,
)
from living_assistant.tools.base import Tool
from living_assistant.tools.registry import ToolRegistry


@pytest.fixture
def mock_env(tmp_path):
    ws_root = tmp_path / "workspace"
    ws_root.mkdir()
    ws = Workspace([ws_root])

    db_path = tmp_path / "test.sqlite3"
    appr_store = ApprovalStore(db_path)
    appr_mgr = ApprovalManager(interactive=False, store=appr_store)

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_store = SkillStore(db_path)

    tool_reg = ToolRegistry()
    tool_reg.register(Tool("dummy_tool", "Dummy", {}, lambda: {"status": "ok"}))

    mgr = SkillManager(
        workspace=ws,
        tool_registry=tool_reg,
        skills_dir=skills_dir,
        store=skill_store,
        approval_manager=appr_mgr,
    )
    return {
        "ws_root": ws_root,
        "ws": ws,
        "db_path": db_path,
        "skills_dir": skills_dir,
        "store": skill_store,
        "appr_mgr": appr_mgr,
        "tool_reg": tool_reg,
        "mgr": mgr,
    }


# -------------------------------------------------------------------------
# 1. Manifest Validation & Tool Checking
# -------------------------------------------------------------------------
def test_manifest_validation_success():
    m = SkillManifest(
        id="test-skill",
        name="Test Skill",
        version="1.0.0",
        required_tools=["files.list", "dummy_tool"],
    )
    assert m.id == "test-skill"
    errors = m.validate_against_tools({"dummy_tool"})
    assert errors == []


def test_manifest_validation_rejects_invalid_id():
    with pytest.raises(ValueError):
        SkillManifest(id="Invalid ID With Spaces!", name="Bad")


def test_manifest_validation_rejects_invalid_version():
    with pytest.raises(ValueError):
        SkillManifest(id="test-skill", name="Bad", version="beta-1")


def test_manifest_flags_unknown_tools():
    m = SkillManifest(
        id="test-skill",
        name="Test",
        required_tools=["nonexistent_hallucinated_tool"],
    )
    errors = m.validate_against_tools({"files.list"})
    assert len(errors) == 1
    assert "nonexistent_hallucinated_tool" in errors[0]


# -------------------------------------------------------------------------
# 2. Package Zip Slip and Traversal Defenses
# -------------------------------------------------------------------------
def test_import_zip_slip_traversal_defense(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../evil.txt", "pwned")
        zf.writestr("manifest.json", json.dumps({"id": "malicious", "name": "Malicious", "version": "1.0.0"}))
        zf.writestr("SKILL.md", "# Malicious")

    with pytest.raises(ValueError, match="Security error"):
        SkillPackage.import_zip(buf.getvalue(), target_parent_dir=tmp_path)


def test_import_zip_absolute_path_defense(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("/etc/passwd", "root:x:0:0")
        zf.writestr("manifest.json", json.dumps({"id": "abs", "name": "Abs", "version": "1.0.0"}))

    with pytest.raises(ValueError, match="Security error"):
        SkillPackage.import_zip(buf.getvalue(), target_parent_dir=tmp_path)


def test_package_export_and_import_roundtrip(tmp_path):
    src_dir = tmp_path / "orig_skill"
    manifest = SkillManifest(
        id="roundtrip-skill",
        name="Roundtrip Skill",
        version="1.0.0",
        triggers=["roundtrip"],
    )
    pkg = SkillPackage(root=src_dir, manifest=manifest, skill_md="# Roundtrip Skill\n\nDocs")
    pkg.save()

    zip_bytes = pkg.export_zip()
    assert len(zip_bytes) > 0

    dest_dir = tmp_path / "imported_skills"
    imported = SkillPackage.import_zip(zip_bytes, target_parent_dir=dest_dir)
    assert imported.skill_id == "roundtrip-skill"
    assert imported.manifest.name == "Roundtrip Skill"
    assert "Roundtrip Skill" in imported.skill_md


# -------------------------------------------------------------------------
# 3. SQLite Lifecycle, Version Snapshots & Rollback
# -------------------------------------------------------------------------
def test_skill_store_lifecycle_and_rollback(mock_env):
    store = mock_env["store"]
    manifest = SkillManifest(id="versioned-skill", name="V1 Skill", version="1.0.0")
    store.register_skill(manifest, "# Version 1", initial_state="DRAFT")

    lc = store.get_lifecycle("versioned-skill")
    assert lc["state"] == "DRAFT"
    assert lc["current_version"] == "1.0.0"

    # Approve skill
    h1 = manifest.permissions.permission_hash()
    store.approve_skill("versioned-skill", "appr_123", "1.0.0", h1)
    assert store.is_approved("versioned-skill", "1.0.0", h1) is True

    # Update to V2 (which invalidates approval)
    manifest_v2 = SkillManifest(id="versioned-skill", name="V2 Skill", version="1.1.0")
    store.register_skill(manifest_v2, "# Version 2")
    store.invalidate_approval("versioned-skill")

    assert store.is_approved("versioned-skill", "1.1.0", manifest_v2.permissions.permission_hash()) is False

    versions = store.get_versions("versioned-skill")
    assert len(versions) == 2

    # Rollback to 1.0.0
    rolled_manifest, rolled_md = store.rollback_version("versioned-skill", "1.0.0")
    assert rolled_manifest.version == "1.0.0"
    assert "# Version 1" in rolled_md
    lc_rolled = store.get_lifecycle("versioned-skill")
    assert lc_rolled["current_version"] == "1.0.0"
    assert lc_rolled["state"] == "DRAFT"  # Reset to draft for review


# -------------------------------------------------------------------------
# 4. Out-of-Model Security & Scope Enforcement
# -------------------------------------------------------------------------
def test_guard_enforces_tool_allowlist(mock_env):
    manifest = SkillManifest(
        id="restricted-tools",
        name="Restricted",
        version="1.0.0",
        required_tools=["files.list"],
    )
    guard = SkillPermissionGuard(manifest, mock_env["ws"], mock_env["appr_mgr"])
    guard.check_tool_allowlist("files.list")  # Allowed

    with pytest.raises(SkillPermissionViolation, match="not in its required_tools allowlist"):
        guard.check_tool_allowlist("dangerous_unapproved_tool")


def test_guard_blocks_unauthorized_filesystem_scope(mock_env):
    manifest = SkillManifest(
        id="scoped-fs",
        name="Scoped FS",
        version="1.0.0",
        permissions=SkillPermissionScope(filesystem=["./allowed_subdir"]),
    )
    guard = SkillPermissionGuard(manifest, mock_env["ws"], mock_env["appr_mgr"])

    # Attempting to resolve outside the workspace
    with pytest.raises(WorkspaceViolation):
        guard.validate_path("../../etc/passwd")


def test_guard_blocks_unauthorized_destructive_actions(mock_env):
    ws_root = mock_env["ws_root"]
    existing_file = ws_root / "important.txt"
    existing_file.write_text("critical data", encoding="utf-8")

    manifest = SkillManifest(
        id="non-destructive",
        name="Safe",
        version="1.0.0",
        permissions=SkillPermissionScope(filesystem=["."], destructive=False),
    )
    guard = SkillPermissionGuard(manifest, mock_env["ws"], None)

    # Attempting to overwrite existing file without destructive permission or approval manager
    with pytest.raises(SkillPermissionViolation, match="lacks destructive permission"):
        guard.validate_path(existing_file, for_write=True)


# -------------------------------------------------------------------------
# 5. True Dry-Run & Reversible Undo Logs
# -------------------------------------------------------------------------
def test_portable_adapter_dry_run_suppresses_mutations(mock_env):
    ws_root = mock_env["ws_root"]
    src_file = ws_root / "report.txt"
    src_file.write_text("Quarterly results", encoding="utf-8")
    dst_file = ws_root / "Archived" / "report.txt"

    adapter = PortableToolAdapter(mock_env["ws"], dry_run=True)
    res = adapter.files_move(str(src_file), str(dst_file))

    assert res["ok"] is True
    assert res["dry_run"] is True
    # Verify file was NOT moved on disk
    assert src_file.exists()
    assert not dst_file.exists()


def test_portable_adapter_live_move_collision_and_undo(mock_env):
    ws_root = mock_env["ws_root"]
    src_file = ws_root / "doc.txt"
    src_file.write_text("Original Doc", encoding="utf-8")

    target_dir = ws_root / "Target"
    target_dir.mkdir()
    # Create an existing collision file
    (target_dir / "doc.txt").write_text("Pre-existing", encoding="utf-8")

    adapter = PortableToolAdapter(mock_env["ws"], dry_run=False)
    # Move should resolve collision by renaming to doc_1.txt
    res = adapter.files_move(str(src_file), str(target_dir))
    assert res["ok"] is True
    assert res["collision_renamed"] is True
    moved_path = Path(res["destination"])
    assert moved_path.name == "doc_1.txt"
    assert moved_path.exists()
    assert not src_file.exists()

    # Revert move using undo
    undo_rec = adapter.recorded_actions[0]["undo"]
    revert_res = adapter.undo_action(undo_rec)
    assert revert_res["ok"] is True
    assert src_file.exists()
    assert not moved_path.exists()


# -------------------------------------------------------------------------
# 6. Document Extractor (Invoices & Dates)
# -------------------------------------------------------------------------
def test_document_extractor_parses_invoice_fields(tmp_path):
    invoice_file = tmp_path / "acme_invoice.txt"
    invoice_file.write_text(
        """ACME CORPORATION
123 Industrial Way
Invoice #: INV-2026-992
Date: 2026-03-15
Total Due: $1,450.50
Thank you for your business!""",
        encoding="utf-8",
    )

    extracted = DocumentExtractor.extract_invoice_fields(invoice_file)
    assert extracted["vendor"] == "ACME CORPORATION"
    assert extracted["date"] == "2026-03-15"
    assert extracted["year_month"] == "2026-03"
    assert extracted["amount"] == 1450.50
    assert extracted["currency"] == "$"
    assert extracted["invoice_number"] == "INV-2026-992"
    assert extracted["confidence"] >= 0.70
    assert extracted["needs_review"] is False


def test_document_extractor_flags_uncertain_extractions(tmp_path):
    vague_file = tmp_path / "unclear.txt"
    vague_file.write_text("Here are some notes from yesterday.", encoding="utf-8")

    extracted = DocumentExtractor.extract_invoice_fields(vague_file)
    assert extracted["needs_review"] is True
    assert extracted["confidence"] < 0.50


# -------------------------------------------------------------------------
# 7. Natural-Language Draft Creator Flow
# -------------------------------------------------------------------------
def test_skill_creator_invoice_draft(mock_env):
    creator = SkillCreator(mock_env["tool_reg"], mock_env["store"])
    prompt = "Create a skill that organizes my invoices by vendor and month"
    pkg = creator.create_draft(prompt)

    assert pkg.manifest.id.startswith("invoice") or "organize" in pkg.manifest.id
    assert "documents.extract" in pkg.manifest.required_tools
    assert "files.move" in pkg.manifest.required_tools
    assert len(pkg.manifest.workflow) >= 2

    # Verify saved on disk
    assert (pkg.root / "manifest.json").exists()
    assert (pkg.root / "SKILL.md").exists()

    # Verify saved in SQLite as DRAFT
    lc = mock_env["store"].get_lifecycle(pkg.manifest.id)
    assert lc["state"] == "DRAFT"


# -------------------------------------------------------------------------
# 8. End-to-End Execution of Reference Skills
# -------------------------------------------------------------------------
def test_invoice_organizer_end_to_end(mock_env):
    mgr = mock_env["mgr"]
    ws_root = mock_env["ws_root"]

    # 1. Setup synthetic invoice fixture
    inbox = ws_root / "inbox"
    inbox.mkdir()
    inv_file = inbox / "techcorp_march.txt"
    inv_file.write_text(
        """TechCorp Global Inc.
Invoice Number: TC-8841
Date: 2026-03-10
Total: $599.00
Payment due upon receipt.""",
        encoding="utf-8",
    )

    out_root = ws_root / "Organized"

    # 2. Activate reference skill
    mgr.activate_skill("invoice-organizer")

    # 3. Dry-run execution
    dry_res = mgr.execute_skill(
        "invoice-organizer",
        inputs={"inbox_dir": str(inbox), "invoice_path": str(inv_file), "target_root": str(out_root)},
        dry_run=True,
    )
    assert dry_res["status"] == "COMPLETED"
    assert dry_res["dry_run"] is True
    assert inv_file.exists()  # Did not move

    # 4. Live execution
    live_res = mgr.execute_skill(
        "invoice-organizer",
        inputs={"inbox_dir": str(inbox), "invoice_path": str(inv_file), "target_root": str(out_root)},
        dry_run=False,
    )
    assert live_res["status"] == "COMPLETED"
    assert not inv_file.exists()  # Moved

    # Check organized file structure
    organized_file = out_root / "TechCorp Global Inc." / "2026-03" / "techcorp_march.txt"
    assert organized_file.exists()


def test_daily_briefing_execution(mock_env):
    mgr = mock_env["mgr"]
    mgr.activate_skill("daily-briefing")
    res = mgr.execute_skill("daily-briefing", dry_run=True)
    assert res["status"] == "COMPLETED"
    assert "daily-briefing" in res["skill_id"]


def test_downloads_organizer_execution(mock_env):
    mgr = mock_env["mgr"]
    ws_root = mock_env["ws_root"]
    dl_dir = ws_root / "downloads"
    dl_dir.mkdir()
    test_pdf = dl_dir / "user_manual.pdf"
    test_pdf.write_text("PDF content", encoding="utf-8")

    mgr.activate_skill("downloads-organizer")
    res = mgr.execute_skill(
        "downloads-organizer",
        inputs={"folder": str(dl_dir), "source_file": str(test_pdf), "target_dir": str(dl_dir / "Documents")},
        dry_run=False,
    )
    assert res["status"] == "COMPLETED"
    assert (dl_dir / "Documents" / "user_manual.pdf").exists()


# -------------------------------------------------------------------------
# 9. External Collections Discovery & Selective Import
# -------------------------------------------------------------------------
def test_external_collections_discovery(mock_env):
    finder = ExternalSkillCollections(skill_store=mock_env["store"])
    collections = finder.scan_collections()
    # Verify collections were discovered
    assert "cybersecurity" in collections
    assert len(collections["cybersecurity"]) > 0


# -------------------------------------------------------------------------
# 10. Backward Compatibility with SkillRegistry
# -------------------------------------------------------------------------
def test_skill_registry_syncs_with_manager(mock_env):
    reg = SkillRegistry(mock_env["skills_dir"] / "skills.json", manager=mock_env["mgr"])
    # Shipped defaults and custom package skills should appear
    skills = reg.list()
    assert "invoice-organizer" in skills or "daily-briefing" in skills
    # Matching works
    hits = reg.match("Organize my invoices by vendor and month")
    assert len(hits) > 0
    assert hits[0]["name"] == "invoice-organizer"


# -------------------------------------------------------------------------
# 11. REST API Endpoints Verification
# -------------------------------------------------------------------------
def test_skills_rest_api_lifecycle(mock_env, monkeypatch):
    from fastapi.testclient import TestClient
    from living_assistant.api import app
    import base64

    # Patch runtime() to return mock environment's runtime
    class _MockRT:
        skill_manager = mock_env["mgr"]
        skills = mock_env["mgr"]
        projects = []
        groups = []
        watches = []
        routines = []

    monkeypatch.setattr("living_assistant.api_routes.skills.runtime", lambda: _MockRT)
    monkeypatch.setattr("living_assistant.api_routes.dependencies.runtime", lambda: _MockRT)
    monkeypatch.setattr("living_assistant.api_routes.skills.authorize", lambda token: True)
    monkeypatch.setattr("living_assistant.api_routes.dependencies.authorize", lambda token: True)

    client = TestClient(app, headers={"Authorization": "Bearer test-token"})

    # 1. GET /skills
    r_list = client.get("/skills")
    assert r_list.status_code == 200
    skills = r_list.json()["skills"]
    assert any(s["skill_id"] == "daily-briefing" for s in skills)

    # 2. POST /skills/draft
    r_draft = client.post("/skills/draft", json={"description": "Organize my invoice documents by date"})
    assert r_draft.status_code == 200
    d_data = r_draft.json()
    assert d_data["ok"] is True
    draft_id = d_data["skill_id"]

    # 3. GET /skills/{id}
    r_get = client.get(f"/skills/{draft_id}")
    assert r_get.status_code == 200
    assert r_get.json()["lifecycle"]["state"] == "DRAFT"

    # 4. POST /skills/{id}/activate
    r_act = client.post(f"/skills/{draft_id}/activate")
    assert r_act.status_code == 200
    assert r_act.json()["state"] == "ACTIVE"

    # 5. POST /skills/{id}/execute in dry_run
    r_exec = client.post(f"/skills/{draft_id}/execute", json={"inputs": {}, "dry_run": True})
    assert r_exec.status_code == 200
    print("EXEC RES:", r_exec.json())
    assert r_exec.json()["status"] == "COMPLETED"

    # 6. POST /skills/{id}/disable
    r_dis = client.post(f"/skills/{draft_id}/disable")
    assert r_dis.status_code == 200
    assert r_dis.json()["state"] == "DISABLED"

    # 7. GET /skills/{id}/export
    r_exp = client.get(f"/skills/{draft_id}/export")
    assert r_exp.status_code == 200
    zip_bytes = r_exp.content
    assert len(zip_bytes) > 0

    # 8. POST /skills/import
    b64 = base64.b64encode(zip_bytes).decode("ascii")
    r_imp = client.post("/skills/import", json={"archive_base64": b64})
    assert r_imp.status_code == 200
    assert r_imp.json()["state"] == "DRAFT"

    # 9. GET /skills/collections/browse
    r_col = client.get("/skills/collections/browse")
    assert r_col.status_code == 200
    assert "cybersecurity" in r_col.json()
