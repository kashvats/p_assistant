from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
import datetime as dt
import threading
import time
from typing import Iterator


@dataclass(frozen=True)
class ActivityEvent:
    id: int
    type: str
    data: dict
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class EventBus:
    """Small in-process activity bus for UI visibility.

    This is observability only. It is intentionally not used as a source of truth
    for approvals, security decisions, or durable task state.
    """

    def __init__(self, max_events: int = 500):
        self._events: deque[ActivityEvent] = deque(maxlen=max(50, int(max_events)))
        self._next_id = 1
        self._cond = threading.Condition()

    def publish(self, event_type: str, **data) -> dict:
        with self._cond:
            event = ActivityEvent(
                id=self._next_id,
                type=str(event_type),
                data=data,
                created_at=dt.datetime.now().isoformat(timespec="seconds"),
            )
            self._next_id += 1
            self._events.append(event)
            self._cond.notify_all()
            return event.to_dict()

    def recent(self, limit: int = 100, after_id: int = 0) -> list[dict]:
        with self._cond:
            rows = [e.to_dict() for e in self._events if e.id > int(after_id)]
        return rows[-max(1, min(int(limit), 500)):]

    def wait_for_events(self, after_id: int, timeout: float = 15.0) -> list[dict]:
        deadline = time.monotonic() + max(0.1, timeout)
        with self._cond:
            while True:
                rows = [e.to_dict() for e in self._events if e.id > int(after_id)]
                if rows:
                    return rows
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._cond.wait(timeout=remaining)

    def stream(self, after_id: int = 0, heartbeat_seconds: float = 15.0) -> Iterator[dict | None]:
        cursor = int(after_id)
        while True:
            rows = self.wait_for_events(cursor, heartbeat_seconds)
            if not rows:
                yield None
                continue
            for row in rows:
                cursor = max(cursor, int(row["id"]))
                yield row
