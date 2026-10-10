"""Images and local vision: attach images to conversations, analyze them, manage vision models."""
from __future__ import annotations

import base64
import binascii
import json

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.core.config import save_model_preference, source_root
from living_assistant.vision import attachments
from living_assistant.vision.engine import TASKS

router = APIRouter(tags=["vision"])


def _engine():
    rt = runtime()
    if getattr(rt, "vision", None) is None:
        raise HTTPException(status_code=503, detail="Vision is disabled (vision.enabled=false).")
    return rt.vision()


class AttachmentUpload(BaseModel):
    data: str = Field(min_length=8, description="base64 image bytes, or a data: URL")
    name: str = Field(default="", max_length=200)


class AnalyzeRequest(BaseModel):
    image: str = Field(pattern=r"^img_[0-9a-f]{16}$")
    question: str = Field(default="", max_length=4000)
    task: str = "general"
    model: str | None = None
    ocr_only: bool = False


@router.post("/attachments")
def attachment_upload(req: AttachmentUpload, authorization: str | None = Header(default=None)):
    authorize(authorization)
    raw = req.data.split(",", 1)[1] if req.data.startswith("data:") else req.data
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="The image data is not valid base64.")
    try:
        return attachments.save(data, req.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/attachments/{image_id}")
def attachment_get(image_id: str, token: str | None = Query(default=None),
                   authorization: str | None = Header(default=None)):
    authorize(authorization, token=token)
    path = attachments.path_of(image_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Unknown image.")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable",
                                       "X-Content-Type-Options": "nosniff"})


@router.post("/vision/analyze")
def vision_analyze(req: AnalyzeRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    if req.task not in TASKS:
        raise HTTPException(status_code=400, detail=f"task must be one of {list(TASKS)}")
    try:
        data = attachments.load(req.image)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    engine = _engine()
    if req.ocr_only:
        return engine.ocr_only(data)
    try:
        return engine.analyze(data, question=req.question, task=req.task, model=req.model)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)[:1500]}


@router.get("/vision/status")
def vision_status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _engine().status()


@router.get("/vision/models")
def vision_models(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"models": _engine().list_models()}


class DefaultModel(BaseModel):
    model: str = Field(min_length=1, max_length=80)


@router.put("/vision/default")
def vision_set_default(req: DefaultModel, authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine = _engine()
    try:
        engine.set_default(req.model)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    save_model_preference("vision", req.model)
    return engine.status()


@router.get("/vision/benchmark")
def vision_benchmark(authorization: str | None = Header(default=None)):
    """Summary of the latest benchmarks/vision run on this machine (source checkouts only)."""
    authorize(authorization)
    root = source_root()
    folder = root / "benchmarks" / "vision" / "results" if root else None
    rows = []
    for path in sorted(folder.glob("*.json")) if folder and folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for variant in sorted({r.get("variant") for r in data.get("rows") or []}):
            cases = [r for r in data["rows"] if r.get("variant") == variant]
            secs = sorted(r["seconds"] for r in cases if r.get("seconds"))
            by_cat: dict[str, list[int]] = {}
            for r in cases:
                by_cat.setdefault(r.get("category") or "other", [0, 0])
                by_cat[r["category"]][0] += bool(r.get("ok"))
                by_cat[r["category"]][1] += 1
            rows.append({"model": data.get("model"), "variant": variant, "passed": sum(bool(r.get("ok")) for r in cases),
                         "total": len(cases), "categories": by_cat,
                         "median_seconds": secs[len(secs) // 2] if secs else None,
                         "peak_rss_mb": data.get("peak_rss_mb"), "device": data.get("device"), "at": data.get("at")})
    return {"results": rows}


@router.post("/vision/models/{name}/download")
def vision_model_download(name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine = _engine()
    if name not in engine.models:
        raise HTTPException(status_code=404, detail="Unknown vision model.")
    return engine.start_download(name)
