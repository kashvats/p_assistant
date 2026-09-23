from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import ModelDeleteRequest, ModelRequest
from living_assistant.core.model_provider import AirLLMProvider

router = APIRouter(tags=["models"])


@router.get("/models/status")
def model_status(
    refresh: bool = False,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    status = rt.model_manager.status(refresh=refresh)
    return {**status, "selected_model": rt.orchestrator.model}


@router.post("/models/select")
def model_select(
    req: ModelRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    manager = runtime().model_manager
    validator = getattr(manager, "validate_model_selection", None)
    if validator is not None:
        validation = validator(req.model)
        if not validation["ok"]:
            raise HTTPException(status_code=409, detail=validation["error"])
    if AirLLMProvider.is_airllm_model(req.model):
        raise HTTPException(
            status_code=400,
            detail="AirLLM models cannot be selected as the tool-calling Orchestrator model.",
        )
    rt = runtime()
    loaded = rt.model_manager.preload(req.model)
    if not loaded.get("ok", False):
        raise HTTPException(status_code=409, detail=loaded.get("error", "Model preload failed."))
    rt.orchestrator.model = req.model
    profile_cfg = rt.config.setdefault("profiles", {}).setdefault(rt.profile, {})
    profile_cfg.setdefault("models", {})["orchestrator"] = req.model
    if getattr(rt, "events_bus", None):
        rt.events_bus.publish("model.selected", model=req.model, profile=rt.profile)
    return {"ok": True, "model": req.model, "runtime": loaded.get("runtime", {})}


@router.post("/models/preload")
def model_preload(
    req: ModelRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    manager = runtime().model_manager
    validator = getattr(manager, "validate_model_selection", None)
    if validator is not None:
        validation = validator(req.model)
        if not validation["ok"]:
            raise HTTPException(status_code=409, detail=validation["error"])
    return manager.preload(req.model)


@router.post("/models/unload")
def model_unload(
    req: ModelRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().model_manager.unload(req.model)


@router.get("/models/local")
def model_local_catalog(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().model_manager.local_model_catalog()


@router.post("/models/pull")
def model_pull(
    req: ModelRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().model_manager.pull_local_model(req.model)


@router.post("/models/delete")
def model_delete(
    req: ModelDeleteRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().model_manager.delete_local_model(req.model, confirmed=req.confirm)

@router.get("/models/usage")
def model_usage(
    days: int = Query(default=30, ge=1, le=3650),
    session_id: str | None = Query(default=None, max_length=200),
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().model_usage.summary(session_id=session_id, days=days)
