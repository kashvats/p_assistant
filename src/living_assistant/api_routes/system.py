from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.system.platform_hardening import platform_status, service_status

router = APIRouter(tags=["system"])

_UNKNOWN_PROVIDER = {
    "id": "unknown",
    "name": "Provider unavailable",
    "mode": "unknown",
    "local": None,
    "credentials_required": None,
    "credentials_configured": None,
    "credential_env": None,
    "credential_label": None,
    "supported": None,
}


@router.get("/status")
def status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    selected_model = rt.model_manager.active_model or rt.orchestrator.model
    provider_info = getattr(rt.model_manager, "provider_info", None)
    model_provider = provider_info(selected_model) if callable(provider_info) else {**_UNKNOWN_PROVIDER, "model": selected_model}
    return {
        "profile": rt.profile,
        "hardware": rt.hardware.to_dict(),
        "resources": rt.resources.snapshot(),
        "personal": rt.personal.status(),
        "active_model": selected_model,
        "model_runtime": rt.model_manager.status(refresh=False),
        "model_provider": model_provider,
        "integrations": rt.integrations.status() if getattr(rt, "integrations", None) is not None else {},
    }


@router.get("/platform/status")
def platform_status_endpoint(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return platform_status().to_dict()


@router.get("/platform/service-status")
def platform_service_status_endpoint(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return service_status()


# Exit code run.bat recognises: the kill switch closes its window instead of pausing on "stopped".
KILL_EXIT_CODE = 99


def kill_marker() -> Path:
    """Written on shutdown; the desktop shell watches it and quits (and never restarts the backend)."""
    return Path(tempfile.gettempdir()) / "LivingAssistant" / "killed.json"


def _terminate_children() -> int:
    """End every process the backend started (model servers, shells, browsers) before exiting."""
    try:
        import psutil

        children = psutil.Process().children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.Error:
                pass
        _gone, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.Error:
                pass
        return len(children)
    except Exception:
        return 0


def _exit_now() -> None:
    _terminate_children()
    os._exit(KILL_EXIT_CODE)


class KillRequest(BaseModel):
    mode: str = Field(default="shutdown", pattern="^(stop|shutdown)$")
    reason: str = Field(default="kill switch", max_length=200)


@router.post("/system/kill")
def kill_switch(req: KillRequest, authorization: str | None = Header(default=None)):
    """Kill switch. ``shutdown`` (default): stop every activity, end every process the assistant
    started, close the desktop app and exit. ``stop``: stop every activity but keep the server up, idle."""
    authorize(authorization)
    rt = runtime()
    result = rt.halt(req.reason) if hasattr(rt, "halt") else {"error": "This runtime cannot halt."}
    if req.mode == "shutdown":
        try:
            marker = kill_marker()
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"at": time.time(), "reason": req.reason, "pid": os.getpid()}), encoding="utf-8")
        except OSError:
            pass
        bus = getattr(rt, "events_bus", None)
        if bus is not None:
            try:
                bus.publish("system.killed", reason=req.reason)
            except Exception:
                pass
        # Answer first, then exit: the response and the event need a moment to leave.
        threading.Timer(1.5, _exit_now).start()
    return {"ok": True, "mode": req.mode, **result}
