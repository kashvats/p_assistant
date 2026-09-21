from __future__ import annotations

import hmac
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from living_assistant.api_routes.assistant import router as assistant_router
from living_assistant.api_routes.desktop import router as desktop_router
from living_assistant.api_routes.improvements import router as improvements_router
from living_assistant.api_routes.integrations import router as integrations_router
from living_assistant.api_routes.models import router as models_router
from living_assistant.api_routes.personal import router as personal_router
from living_assistant.api_routes.peers import router as peers_router
from living_assistant.api_routes.schemas import (
    ApprovalDecision,
    AskRequest,
    BackupBaselineCreateRequest,
    BrowserInteractRequest,
    BrowserNavigateRequest,
    BrowserStartRequest,
    CalendarEventRequest,
    CanaryRequest,
    ConnectorCallRequest,
    DesktopAnalyzeRequest,
    EvaluationSuiteRequest,
    ExperienceConfirmRequest,
    ExperienceRecordRequest,
    ExperienceVerifyRequest,
    FocusRequest,
    ImprovementEvaluateRequest,
    IntegrityBaselineRequest,
    ModelRequest,
    QuietRequest,
    SecurityPathRequest,
    TodoRequest,
)
from living_assistant.api_routes.security import router as security_router
from living_assistant.api_routes.ui import router as ui_router
from living_assistant.api_routes.workspace import router as workspace_router
from living_assistant.core.runtime import Runtime, get_runtime
from living_assistant.security.api_auth import get_api_token
from living_assistant.system.platform_hardening import platform_status, service_status

app = FastAPI(title="Living Assistant Local API", version="0.17.0")

# Kept as a public compatibility attribute. Runtime resolution intentionally
# continues through get_runtime(), matching the pre-router behavior.
runtime = None

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}


def _allowed_hostnames() -> set[str]:
    extra = {
        item.strip().lower()
        for item in os.environ.get("ASSISTANT_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    return _LOCAL_HOSTS | extra


def _host_only(value: str) -> str:
    try:
        return (urlparse("//" + value).hostname or "").lower()
    except Exception:
        return ""


def _origin_is_local_or_same(origin: str, request_host: str) -> bool:
    try:
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and (
            parsed.hostname or ""
        ).lower() in (_allowed_hostnames() | {request_host})
    except Exception:
        return False


@app.middleware("http")
async def local_api_boundary(request: Request, call_next):
    host = _host_only(request.headers.get("host", ""))
    if host not in _allowed_hostnames():
        return JSONResponse(
            {"detail": "Invalid Host header for local assistant API."},
            status_code=400,
        )
    origin = request.headers.get("origin")
    if origin and not _origin_is_local_or_same(origin, host):
        return JSONResponse(
            {
                "detail": (
                    "Cross-origin browser access to the local assistant API "
                    "is blocked."
                )
            },
            status_code=403,
        )
    return await call_next(request)


def _rt() -> Runtime:
    return get_runtime()


def _auth(authorization: str | None) -> None:
    token = get_api_token()
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    # Byte comparison preserves constant-time behavior and safely handles
    # non-ASCII header values.
    if not hmac.compare_digest(
        authorization.encode("utf-8"),
        f"Bearer {token}".encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/health")
def health():
    return {"ok": True, "service": "living-assistant", "version": "0.17.0"}


@app.get("/status")
def status(authorization: str | None = Header(default=None)):
    _auth(authorization)
    rt = _rt()
    model_runtime = rt.model_manager.status(refresh=False)
    return {
        "profile": rt.profile,
        "hardware": rt.hardware.to_dict(),
        "resources": rt.resources.snapshot(),
        "personal": rt.personal.status(),
        "active_model": rt.model_manager.active_model,
        "model_runtime": model_runtime,
    }


@app.get("/platform/status")
def platform_status_endpoint(
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    return platform_status().to_dict()


@app.get("/platform/service-status")
def platform_service_status_endpoint(
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    return service_status()


# Keep application assembly explicit so api.py owns transport policy while each
# domain router owns its route handlers.
app.include_router(models_router)
app.include_router(peers_router)
app.include_router(desktop_router)
app.include_router(assistant_router)
app.include_router(workspace_router)
app.include_router(personal_router)
app.include_router(security_router)
app.include_router(improvements_router)
app.include_router(integrations_router)
app.include_router(ui_router)


__all__ = [
    "app",
    "runtime",
    "get_runtime",
    "get_api_token",
    "platform_status",
    "service_status",
    "AskRequest",
    "ApprovalDecision",
    "TodoRequest",
    "BrowserStartRequest",
    "BrowserInteractRequest",
    "BrowserNavigateRequest",
    "CalendarEventRequest",
    "FocusRequest",
    "QuietRequest",
    "IntegrityBaselineRequest",
    "EvaluationSuiteRequest",
    "SecurityPathRequest",
    "BackupBaselineCreateRequest",
    "ImprovementEvaluateRequest",
    "CanaryRequest",
    "ExperienceRecordRequest",
    "ExperienceVerifyRequest",
    "ExperienceConfirmRequest",
    "ConnectorCallRequest",
    "ModelRequest",
    "DesktopAnalyzeRequest",
]
