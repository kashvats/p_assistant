from __future__ import annotations

from fastapi import APIRouter, Header

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import (
    BrowserInteractRequest,
    BrowserNavigateRequest,
    BrowserStartRequest,
    ConnectorCallRequest,
    EnabledRequest,
)

router = APIRouter(tags=["integrations"])


@router.get("/voice/status")
def voice_status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    return {
        "enabled": rt.voice.enabled(),
        "profile": rt.profile,
        "config": rt.config.get("voice", {}),
    }


@router.post("/voice/enabled")
def voice_enabled(
    req: EnabledRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    rt.config.setdefault("voice", {})["enabled"] = bool(req.enabled)
    if not req.enabled:
        rt.voice.sleep()
    if getattr(rt, "events_bus", None):
        rt.events_bus.publish("voice.setting_changed", enabled=bool(req.enabled))
    return rt.voice.status()


@router.get("/browser/sessions")
def browser_sessions(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().browser.list_sessions()


@router.post("/browser/sessions")
def browser_session_start(
    req: BrowserStartRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().browser.start_session(
        req.name,
        req.url,
        req.persistent,
        req.allowed_hosts,
    )


@router.post("/browser/sessions/{name}/navigate")
def browser_session_navigate(
    name: str,
    req: BrowserNavigateRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().browser.navigate_session(name, req.url)


@router.post("/browser/sessions/{name}/interact")
def browser_session_interact(
    name: str,
    req: BrowserInteractRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().browser.interact_session(
        name,
        req.action,
        req.selector,
        req.value,
    )


@router.delete("/browser/sessions/{name}")
def browser_session_close(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().browser.close_session(name, False)


@router.get("/connectors")
def connectors(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().connectors.list()


@router.get("/connectors/{name}/status")
def connector_status(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().connector_manager.status(name)


@router.post("/connectors/{name}/call")
def connector_call(
    name: str,
    req: ConnectorCallRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().connector_manager.call(name, req.action, req.params)
