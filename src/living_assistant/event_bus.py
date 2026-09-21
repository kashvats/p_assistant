from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
import datetime as dt
import threading
import time
from typing import Iterator
from pathlib import Path
import json

from .sqlite_utils import ThreadLocalSQLite


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

    def __init__(self, max_events: int = 500, path: str | Path | None = None):
        self._max_events = max(50, int(max_events))
        self._events: deque[ActivityEvent] = deque(maxlen=self._max_events)
        self._next_id = 1
        self._cond = threading.Condition()
        self._db = ThreadLocalSQLite(path) if path is not None else None
        if self._db is not None:
            self._db.execute(
                '''CREATE TABLE IF NOT EXISTS activity_events(
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     type TEXT NOT NULL,
                     data TEXT NOT NULL,
                     created_at TEXT NOT NULL
                   )'''
            )
            self._db.commit()
            rows = self._db.execute(
                'SELECT id,type,data,created_at FROM activity_events ORDER BY id DESC LIMIT ?',
                (self._max_events,),
            ).fetchall()
            loaded = []
            for row in reversed(rows):
                try:
                    data = json.loads(row[2])
                    if not isinstance(data, dict):
                        data = {'value': data}
                except Exception:
                    data = {'value': str(row[2])}
                loaded.append(ActivityEvent(int(row[0]), str(row[1]), data, str(row[3])))
            self._events.extend(loaded)
            if loaded:
                self._next_id = loaded[-1].id + 1

    def publish(self, event_type: str, **data) -> dict:
        with self._cond:
            created_at = dt.datetime.now().isoformat(timespec="seconds")
            event_id = self._next_id
            if self._db is not None:
                payload = json.dumps(data, ensure_ascii=False, default=str, separators=(',', ':'))
                cur = self._db.execute(
                    'INSERT INTO activity_events(type,data,created_at) VALUES(?,?,?)',
                    (str(event_type), payload, created_at),
                )
                event_id = int(cur.lastrowid)
                # Keep the durable history bounded to the same retention window as the
                # in-memory deque. This prevents an observability log from growing
                # without limit across long-running installations.
                cutoff = event_id - self._max_events
                if cutoff > 0:
                    self._db.execute('DELETE FROM activity_events WHERE id<=?', (cutoff,))
                self._db.commit()

            event = ActivityEvent(
                id=event_id,
                type=str(event_type),
                data=data,
                created_at=created_at,
            )
            self._next_id = max(self._next_id, event_id + 1)
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
