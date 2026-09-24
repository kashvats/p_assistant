from __future__ import annotations

import base64
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel

from living_assistant.api_routes.dependencies import authorize, runtime

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentDraftRequest(BaseModel):
    description: str
    form_data: dict[str, Any] | None = None


class UpdateAgentRequest(BaseModel):
    manifest: dict[str, Any]
    agent_md: str


class ExecuteAgentRequest(BaseModel):
    task: str
    context: str = ""
    inputs: dict[str, Any] = {}
    dry_run: bool = False


class ImportAgentZipRequest(BaseModel):
    archive_base64: str


@router.get("")
def list_agents(state: str | None = None, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        return {"agents": []}
    return {"agents": mgr.list_agents(state=state)}


@router.post("/draft")
def create_draft(req: AgentDraftRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    pkg = mgr.create_draft(req.description, form_data=req.form_data)
    return {
        "ok": True,
        "agent_id": pkg.manifest.id,
        "manifest": pkg.manifest.model_dump(),
        "agent_md": pkg.agent_md,
    }


@router.get("/{agent_id}")
def get_agent(agent_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    data = mgr.get_agent(agent_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return data


@router.put("/{agent_id}")
def update_agent(
    agent_id: str,
    req: UpdateAgentRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    try:
        pkg = mgr.update_agent(agent_id, req.manifest, req.agent_md)
        return {"ok": True, "agent_id": pkg.manifest.id, "manifest": pkg.manifest.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{agent_id}/activate")
def activate_agent(agent_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    try:
        res = mgr.activate_agent(agent_id)
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{agent_id}/disable")
def disable_agent(agent_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    return mgr.disable_agent(agent_id)


@router.post("/{agent_id}/execute")
def execute_agent(
    agent_id: str,
    req: ExecuteAgentRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    try:
        res = mgr.execute_agent(
            agent_id=agent_id,
            task=req.task,
            context=req.context,
            inputs=req.inputs,
            dry_run=req.dry_run,
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{agent_id}/export")
def export_agent(agent_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_p = Path(tmp_dir) / f"{agent_id}.zip"
        try:
            mgr.export_agent(agent_id, zip_p)
            data = zip_p.read_bytes()
            return Response(
                content=data,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={agent_id}.zip"},
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))


@router.post("/import")
def import_agent(req: ImportAgentZipRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    mgr = getattr(rt, "agent_manager", None)
    if not mgr:
        raise HTTPException(status_code=500, detail="AgentManager is not initialized.")
    import tempfile
    from pathlib import Path
    try:
        raw_zip = base64.b64decode(req.archive_base64)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_zip = Path(tmp_dir) / "incoming.zip"
            tmp_zip.write_bytes(raw_zip)
            pkg = mgr.import_agent(tmp_zip)
            return {
                "ok": True,
                "agent_id": pkg.manifest.id,
                "name": pkg.manifest.name,
                "role": pkg.manifest.role,
                "version": pkg.manifest.version,
            }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
