from __future__ import annotations

import threading

from fastapi import APIRouter, Header

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import (
    BrowserInteractRequest,
    BrowserNavigateRequest,
    BrowserStartRequest,
    ConnectorCallRequest,
    EnabledRequest,
    VoiceAskRequest,
)

router = APIRouter(tags=["integrations"])


@router.get("/voice/status")
def voice_status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    status = rt.voice.status()
    manager = getattr(rt, "model_manager", None)
    if manager is not None and hasattr(manager, "provider_info"):
        status["model_provider"] = manager.provider_info(manager.active_model)
    return status


@router.post("/voice/ask")
def voice_ask(
    req: VoiceAskRequest,
    authorization: str | None = Header(default=None),
):
    """Capture one local utterance, transcribe it, and run the normal assistant flow."""
    authorize(authorization)
    rt = runtime()
    validator = getattr(rt.model_manager, "validate_model_selection", None)
    if validator is not None:
        validation = validator(rt.model_manager.active_model or rt.orchestrator.model)
        if not validation["ok"]:
            return {
                "ok": False,
                "stage": "model",
                "error": validation["error"],
                "model_provider": validation["provider"],
            }
    recording = rt.voice.record_until_silence(
        "artifacts/voice-input.wav",
        max_seconds=req.max_seconds,
    )
    if not recording.get("ok"):
        return {"ok": False, "stage": "record", **recording}
    transcript = rt.voice.transcribe("artifacts/voice-input.wav", req.language)
    if not transcript.get("ok"):
        return {"ok": False, "stage": "transcribe", **transcript}
    text = rt.voice.clean_command_text(str(transcript.get("text", "")))
    if not text:
        return {
            "ok": False,
            "stage": "transcribe",
            "error": "No speech was transcribed from the recording.",
            "transcript": transcript,
        }
    answer = rt.orchestrator.run(
        text,
        context="The user issued this request by voice.",
        session_id="voice-companion",
    )
    speech = rt.voice.speak(answer) if req.speak else {"ok": False, "skipped": True}
    return {
        "ok": True,
        "transcript": text,
        "answer": answer,
        "speech": speech,
        "model_provider": rt.model_manager.provider_info(rt.model_manager.active_model),
    }


@router.post("/voice/hands-free")
def voice_hands_free(
    req: EnabledRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    validator = getattr(rt.model_manager, "validate_model_selection", None)
    selected = rt.model_manager.active_model or rt.orchestrator.model
    if req.enabled and validator is not None:
        validation = validator(selected)
        if not validation["ok"]:
            return {
                "ok": False,
                "stage": "model",
                "error": validation["error"],
                "model_provider": validation["provider"],
            }

    def handle_command(text: str):
        try:
            answer = rt.orchestrator.run(
                text,
                context="The user issued this request after saying the configured local wake word.",
                session_id="voice-hands-free",
            )
            if getattr(rt, "events_bus", None):
                rt.events_bus.publish(
                    "voice.command.completed",
                    transcript=text,
                    answer_preview=str(answer)[:300],
                )
        except Exception as exc:
            if getattr(rt, "events_bus", None):
                rt.events_bus.publish("voice.command.failed", error=str(exc)[:500])

    result = rt.voice.start_hands_free(handle_command) if req.enabled else rt.voice.stop_hands_free()
    if getattr(rt, "events_bus", None):
        rt.events_bus.publish("voice.hands_free_changed", enabled=req.enabled, **result)
    return {**result, "voice": rt.voice.status()}


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
