from __future__ import annotations

import base64
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.skills.collections import ExternalSkillCollections

router = APIRouter(prefix="/skills", tags=["skills"])


class DraftRequest(BaseModel):
    description: str


class UpdateSkillRequest(BaseModel):
    manifest: dict[str, Any]
    skill_md: str


class ExecuteRequest(BaseModel):
    inputs: dict[str, Any] = {}
    dry_run: bool = False


class RollbackRequest(BaseModel):
    version: str


class UndoRequest(BaseModel):
    run_id: str


class ImportCollectionRequest(BaseModel):
    collection: str
    folder: str


class ImportZipRequest(BaseModel):
    archive_base64: str


@router.get("")
def list_skills(state: str | None = None, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None)
    if not mgr and hasattr(rt.skills, "manager"):
        mgr = rt.skills.manager
    if not mgr:
        return {"skills": list(rt.skills.list().values())}
    return {"skills": mgr.list_skills(state=state)}


@router.post("/draft")
def create_draft(req: DraftRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    pkg = mgr.create_draft(req.description)
    return {
        "ok": True,
        "skill_id": pkg.manifest.id,
        "manifest": pkg.manifest.model_dump(),
        "skill_md": pkg.skill_md,
    }


@router.get("/{skill_id}")
def get_skill(skill_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    data = mgr.get_skill(skill_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
    return data


@router.put("/{skill_id}")
def update_skill(skill_id: str, req: UpdateSkillRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        pkg = mgr.update_skill(skill_id, req.manifest, req.skill_md)
        return {
            "ok": True,
            "skill_id": pkg.manifest.id,
            "version": pkg.manifest.version,
            "manifest": pkg.manifest.model_dump(),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{skill_id}/activate")
def activate_skill(skill_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        return mgr.activate_skill(skill_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{skill_id}/disable")
def disable_skill(skill_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    ok = mgr.disable_skill(skill_id)
    return {"ok": ok, "state": "DISABLED"}


@router.post("/{skill_id}/archive")
def archive_skill(skill_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    ok = mgr.archive_skill(skill_id)
    return {"ok": ok, "state": "ARCHIVED"}


@router.post("/{skill_id}/execute")
def execute_skill(skill_id: str, req: ExecuteRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        result = mgr.execute_skill(skill_id, inputs=req.inputs, dry_run=req.dry_run, trigger="api")
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{skill_id}/rollback")
def rollback_skill(skill_id: str, req: RollbackRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        pkg = mgr.rollback_skill(skill_id, req.version)
        return {
            "ok": True,
            "skill_id": pkg.manifest.id,
            "version": pkg.manifest.version,
            "manifest": pkg.manifest.model_dump(),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{skill_id}/undo")
def undo_skill(skill_id: str, req: UndoRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        return mgr.undo_execution(req.run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{skill_id}/reconcile")
def reconcile_skill(skill_id: str, req: UndoRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        return mgr.reconcile_execution(req.run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{skill_id}/export")
def export_skill(skill_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        data = mgr.export_skill(skill_id)
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=skill_{skill_id}.zip"},
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/import")
def import_skill(req: ImportZipRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="SkillManager is not initialized.")
    try:
        raw_zip = base64.b64decode(req.archive_base64)
        pkg = mgr.import_skill_archive(raw_zip)
        return {
            "ok": True,
            "skill_id": pkg.manifest.id,
            "version": pkg.manifest.version,
            "state": "DRAFT",
            "manifest": pkg.manifest.model_dump(),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}")


@router.get("/collections/browse")
def browse_collections(authorization: str | None = Header(default=None)):
    authorize(authorization)
    finder = ExternalSkillCollections()
    return finder.scan_collections()


@router.post("/collections/import")
def import_collection_skill(req: ImportCollectionRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "skill_manager", None) or getattr(rt.skills, "manager", None)
    finder = ExternalSkillCollections(skill_store=mgr.store if mgr else None)
    try:
        pkg = finder.import_skill(req.collection, req.folder)
        return {
            "ok": True,
            "skill_id": pkg.manifest.id,
            "state": "DRAFT",
            "manifest": pkg.manifest.model_dump(),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
