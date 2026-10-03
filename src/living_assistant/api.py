from __future__ import annotations

import sys

# Libraries (GPT Researcher, crawlers) print emoji; on Windows a console or a redirected log
# defaults to cp1252 and the print raises UnicodeEncodeError inside the tool. Never let output
# encoding break work.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # replaced or detached streams (tests, services)
        pass

from fastapi import FastAPI, Header, HTTPException, Request, Response

from living_assistant.api_routes.agents import router as agents_router
from living_assistant.api_routes.career import router as career_router
from living_assistant.api_routes.assistant import router as assistant_router
from living_assistant.api_routes.conversations import router as conversations_router
from living_assistant.api_routes.vision import router as vision_router
from living_assistant.api_routes.files import router as files_router
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
from living_assistant.api_routes.skills import router as skills_router
from living_assistant.api_routes.system import router as system_router
from living_assistant.api_routes.ui import router as ui_router
from living_assistant.api_routes.workspace import router as workspace_router
from living_assistant.core.runtime import Runtime, get_runtime
from living_assistant.security import local_api
from living_assistant.security.api_auth import get_api_token
from living_assistant.system.platform_hardening import platform_status, service_status

app = FastAPI(title="Living Assistant Local API", version="0.17.0")

# Kept as a public compatibility attribute. Runtime resolution intentionally
# continues through get_runtime(), matching the pre-router behavior.
runtime = None

_LOCAL_HOSTS = local_api.LOCAL_HOSTS
# The boundary lives in security.local_api (shared with the research server); these names stay for compatibility.
_allowed_hostnames = local_api.allowed_hostnames
_host_only = local_api.host_only
_origin_is_local_or_same = local_api.origin_is_local_or_same


@app.middleware("http")
async def local_api_boundary(request: Request, call_next):
    return await local_api.local_boundary(request, call_next)


def _rt() -> Runtime:
    return runtime if runtime is not None else get_runtime()


def _auth(authorization: str | None = None, token_param: str | None = None) -> None:
    local_api.check_token(authorization, token_param)


API_VERSION = "1.0.0"
CAPABILITY_VERSION = "2.0.0"
MIN_CLIENT_VERSION = "0.15.0"


def check_version_compatibility(client_api_version: str | None = None) -> dict:
    """Section 71: Verify frontend/backend version compatibility."""
    if not client_api_version:
        return {"compatible": True, "api_version": API_VERSION, "warning": "Unspecified client version"}
    try:
        c_major = int(client_api_version.split(".")[0])
        s_major = int(API_VERSION.split(".")[0])
        if c_major != s_major:
            return {
                "compatible": False,
                "api_version": API_VERSION,
                "client_api_version": client_api_version,
                "error": f"Client API version {client_api_version} is incompatible with server version {API_VERSION}. Please upgrade client.",
            }
        return {"compatible": True, "api_version": API_VERSION}
    except Exception:
        return {"compatible": True, "api_version": API_VERSION}


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "living-assistant",
        "version": "0.17.0",
        "api_version": API_VERSION,
        "capability_version": CAPABILITY_VERSION,
        "min_client_version": MIN_CLIENT_VERSION,
    }


# Keep application assembly explicit so api.py owns transport policy while each
# domain router owns its route handlers.
app.include_router(system_router)
app.include_router(models_router)
app.include_router(peers_router)
app.include_router(desktop_router)
app.include_router(assistant_router)
app.include_router(conversations_router)
app.include_router(vision_router)
app.include_router(files_router)
app.include_router(workspace_router)
app.include_router(personal_router)
app.include_router(security_router)
app.include_router(improvements_router)
app.include_router(integrations_router)
app.include_router(skills_router)
app.include_router(agents_router)
app.include_router(career_router)
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
