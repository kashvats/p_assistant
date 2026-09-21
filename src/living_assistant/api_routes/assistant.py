from __future__ import annotations

import json

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import AskRequest

router = APIRouter(tags=["assistant"])


def _sse(
    payload: dict,
    event: str | None = None,
    event_id: int | None = None,
) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    parts: list[str] = []
    if event_id is not None:
        parts.append(f"id: {event_id}")
    if event:
        parts.append(f"event: {event}")
    parts.append(f"data: {body}")
    return "\n".join(parts) + "\n\n"


@router.post("/ask")
def ask(
    req: AskRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    if req.session_id:
        rt.sessions.ensure(req.session_id)
    return {
        "answer": rt.orchestrator.run(
            req.message,
            req.context,
            session_id=req.session_id,
        ),
        "session_id": req.session_id,
    }


@router.get("/activity")
def activity(
    limit: int = 100,
    after_id: int = 0,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().events_bus.recent(limit, after_id)


@router.get("/activity/stream")
def activity_stream(
    after_id: int = 0,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    bus = runtime().events_bus

    def generate():
        for item in bus.stream(after_id=after_id, heartbeat_seconds=12):
            if item is None:
                yield ": heartbeat\n\n"
            else:
                yield _sse(
                    item,
                    event="activity",
                    event_id=int(item["id"]),
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/stream")
def chat_stream(
    req: AskRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    if req.session_id:
        rt.sessions.ensure(req.session_id)

    def generate():
        for event in rt.orchestrator.run_stream(
            req.message,
            req.context,
            session_id=req.session_id,
        ):
            yield _sse(event, event=str(event.get("type", "message")))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )
