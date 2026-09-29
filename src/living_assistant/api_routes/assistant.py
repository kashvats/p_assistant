from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import AskRequest
from living_assistant.core.model_provider import ModelError

router = APIRouter(tags=["assistant"])

def _model_http_error(exc: ModelError) -> HTTPException:
    detail = str(exc)
    if "runner has unexpectedly stopped" in detail:
        detail = (
            "The local model runner stopped, usually because the selected model "
            "needs more memory than is currently available. Close other Ollama "
            "models/apps or select a smaller installed Ollama model, then retry."
        )
    return HTTPException(status_code=503, detail=detail)


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
    try:
        answer = rt.orchestrator.run(
            req.message,
            req.context,
            session_id=req.session_id,
        )
    except ModelError as exc:
        raise _model_http_error(exc) from exc
    return {"answer": answer, "session_id": req.session_id}


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
        try:
            for event in rt.orchestrator.run_stream(
                req.message,
                req.context,
                session_id=req.session_id,
            ):
                yield _sse(event, event=str(event.get("type", "message")))
        except ModelError as exc:
            error = _model_http_error(exc)
            yield _sse(
                {"type": "error", "error": error.detail, "status_code": error.status_code},
                event="error",
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


class GoalRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    check_command: str = Field(default="", max_length=1000)
    cwd: str = Field(default=".", max_length=1000)
    max_rounds: int = Field(default=12, ge=1, le=50)


def _goals():
    runner = getattr(runtime(), "goals", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Long-running goals are unavailable.")
    return runner


def _goal_result(result: dict) -> dict:
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Goal request failed."))
    return result


@router.get("/goals")
def goals_list(limit: int = 20, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _goals().store.list(max(1, min(limit, 100)))


@router.post("/goals")
def goals_create(req: GoalRequest, authorization: str | None = Header(default=None)):
    """Start a goal typed by the user; their check command is authorized by this request."""
    authorize(authorization)
    return _goal_result(_goals().start(req.goal, check_command=req.check_command, cwd=req.cwd,
                                       max_rounds=req.max_rounds, check_approved=True))


@router.get("/goals/{goal_id}")
def goals_get(goal_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    record = _goals().store.get(goal_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown goal.")
    return record


@router.post("/goals/{goal_id}/resume")
def goals_resume(goal_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _goal_result(_goals().resume(goal_id))


@router.post("/goals/{goal_id}/cancel")
def goals_cancel(goal_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _goal_result(_goals().cancel(goal_id))
