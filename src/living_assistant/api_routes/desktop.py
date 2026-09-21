from __future__ import annotations

from fastapi import APIRouter, Header

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import DesktopAnalyzeRequest

router = APIRouter(tags=["desktop"])


@router.get("/desktop/status")
def desktop_status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().desktop_controller.status()


@router.get("/desktop/monitors")
def desktop_monitors(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().desktop_controller.monitors()


@router.get("/desktop/windows")
def desktop_windows(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().desktop_controller.windows()


@router.post("/desktop/analyze-screen")
def desktop_analyze_screen(
    req: DesktopAnalyzeRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().desktop_controller.analyze_screen(req.prompt, req.monitor_id)
