from __future__ import annotations

from fastapi import APIRouter, Header

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
