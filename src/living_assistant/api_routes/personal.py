from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import (
    CalendarEventRequest,
    FocusRequest,
    QuietRequest,
    TodoRequest,
)

router = APIRouter(tags=["personal"])


@router.get("/events")
def events(
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().memory.list_events(min(max(limit, 1), 500))


@router.get("/todos")
def todos(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().memory.list_todos(include_done=True)


@router.post("/todos")
def todo_add(
    req: TodoRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return {"ok": True, "id": runtime().memory.add_todo(req.title, req.due_at)}


@router.post("/todos/{todo_id}/complete")
def todo_complete(
    todo_id: int,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return {"ok": runtime().memory.complete_todo(todo_id)}


@router.get("/calendar")
def calendar(
    start: str | None = None,
    end: str | None = None,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().calendar.list(start, end)


@router.post("/calendar")
def calendar_add(
    req: CalendarEventRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().calendar.add(
        req.title,
        req.start_at,
        req.end_at,
        req.location,
        req.notes,
    )


@router.delete("/calendar/{event_id}")
def calendar_cancel(
    event_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return {"ok": runtime().calendar.cancel(event_id)}


@router.get("/briefing/{kind}")
def briefing(
    kind: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    if kind not in {"morning", "evening"}:
        raise HTTPException(
            status_code=400,
            detail="kind must be morning or evening",
        )
    return runtime().briefings.build(kind)


@router.get("/personal")
def personal(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    return {
        **rt.personal.status(),
        "queued_notifications": rt.notifier.queued(),
    }


@router.post("/personal/focus")
def focus(
    req: FocusRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().personal.start_focus(req.minutes, req.label)


@router.delete("/personal/focus")
def focus_stop(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    state = rt.personal.stop_focus()
    rt.notifier.flush(20)
    return state


@router.post("/personal/quiet")
def quiet(
    req: QuietRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().personal.set_quiet_hours(
        req.start,
        req.end,
        req.enabled,
    )


@router.get("/sessions")
def sessions(
    limit: int = 50,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().sessions.list(limit)


@router.get("/sessions/{session_id}")
def session_get(
    session_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    return {
        "session": rt.sessions.get(session_id),
        "messages": rt.sessions.recent_messages(session_id, 50),
    }


@router.delete("/sessions/{session_id}")
def session_delete(
    session_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return {"ok": runtime().sessions.delete(session_id)}


@router.get("/notifications/queued")
def queued_notifications(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().notifier.queued()


@router.post("/notifications/flush")
def flush_notifications(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().notifier.flush(50)
