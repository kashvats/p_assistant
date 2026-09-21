from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.security.security_utils import redact_secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_run_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  project TEXT,
  session_id TEXT,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  tool_name TEXT,
  status TEXT,
  summary TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS run_history_run_idx ON agent_run_history(run_id,id);
CREATE INDEX IF NOT EXISTS run_history_project_time_idx ON agent_run_history(project,created_at);
CREATE INDEX IF NOT EXISTS run_history_time_idx ON agent_run_history(created_at);
"""

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class RunHistoryStore:
    """Persistent, redacted audit trail for agent work on projects."""

    def __init__(self, path: Path | None = None, retention_days: int = 365):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.retention_days = max(30, min(int(retention_days), 3650))
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = __import__("sqlite3").Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @staticmethod
    def _now() -> dt.datetime:
        return dt.datetime.now()

    @staticmethod
    def _safe_metadata(metadata: dict | None) -> str:
        safe: dict[str, Any] = {}
        for key, value in (metadata or {}).items():
            name = str(key)[:120]
            if name in {"result", "output", "stdout", "stderr", "content"}:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[name] = redact_secrets(value, 1600) if isinstance(value, str) else value
            elif isinstance(value, (list, tuple)):
                safe[name] = [redact_secrets(x, 500) for x in list(value)[:20]]
            elif isinstance(value, dict):
                safe[name] = redact_secrets(json.dumps(value, default=str, sort_keys=True), 2000)
            else:
                safe[name] = redact_secrets(value, 800)
        return json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def record(
        self,
        run_id: str,
        action: str,
        *,
        project: str | None = None,
        session_id: str | None = None,
        actor: str = "orchestrator",
        tool_name: str | None = None,
        status: str | None = None,
        summary: str = "",
        metadata: dict | None = None,
        created_at: dt.datetime | None = None,
    ) -> dict:
        when = (created_at or self._now()).isoformat(timespec="seconds")
        cur = self.conn.execute(
            """INSERT INTO agent_run_history(run_id,project,session_id,actor,action,tool_name,status,summary,metadata_json,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                str(run_id),
                redact_secrets(project, 300) if project else None,
                redact_secrets(session_id, 200) if session_id else None,
                str(actor)[:100],
                str(action)[:160],
                str(tool_name)[:160] if tool_name else None,
                str(status)[:80] if status else None,
                redact_secrets(summary, 3000),
                self._safe_metadata(metadata),
                when,
            ),
        )
        self.conn.commit()
        return self.get_event(int(cur.lastrowid)) or {}

    def start_run(self, request: str, project: str | None = None, session_id: str | None = None) -> str:
        run_id = uuid.uuid4().hex[:16]
        self.prune()
        self.record(
            run_id,
            "run_started",
            project=project,
            session_id=session_id,
            actor="orchestrator",
            status="running",
            summary=request,
        )
        return run_id

    def record_tool(self, run_id: str, tool_name: str, arguments: dict, result: Any, *, project: str | None = None, session_id: str | None = None) -> dict:
        ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
        error = result.get("error") if isinstance(result, dict) else None
        return self.record(
            run_id,
            "tool_call",
            project=project,
            session_id=session_id,
            actor="tool",
            tool_name=tool_name,
            status="completed" if ok else "failed",
            summary=(f"{tool_name} completed" if ok else f"{tool_name} failed: {redact_secrets(error or 'unknown error', 1000)}"),
            metadata={"arguments": arguments, "ok": ok},
        )

    def finish_run(self, run_id: str, *, project: str | None = None, session_id: str | None = None, status: str = "completed", summary: str = "") -> dict:
        return self.record(
            run_id,
            "run_finished",
            project=project,
            session_id=session_id,
            actor="orchestrator",
            status=status,
            summary=summary or f"Run {status}.",
        )

    def get_event(self, event_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM agent_run_history WHERE id=?", (int(event_id),)).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json"))
        except Exception:
            item["metadata"] = {}
            item.pop("metadata_json", None)
        return item

    @classmethod
    def _time_range(cls, when: str | None, now: dt.datetime | None = None) -> tuple[dt.datetime | None, dt.datetime | None]:
        if not when or not str(when).strip():
            return None, None
        now = now or cls._now()
        text = str(when).strip().lower()
        today = now.date()
        if text == "today":
            start = dt.datetime.combine(today, dt.time.min)
            return start, start + dt.timedelta(days=1)
        if text == "yesterday":
            day = today - dt.timedelta(days=1)
            start = dt.datetime.combine(day, dt.time.min)
            return start, start + dt.timedelta(days=1)
        if text in {"this week", "this_week"}:
            day = today - dt.timedelta(days=today.weekday())
            start = dt.datetime.combine(day, dt.time.min)
            return start, start + dt.timedelta(days=7)
        if text in {"last week", "last_week"}:
            this_monday = today - dt.timedelta(days=today.weekday())
            day = this_monday - dt.timedelta(days=7)
            start = dt.datetime.combine(day, dt.time.min)
            return start, start + dt.timedelta(days=7)
        m = re.fullmatch(r"last\s+(\d{1,3})\s+days?", text)
        if m:
            days = max(1, min(int(m.group(1)), 3650))
            return now - dt.timedelta(days=days), now
        m = re.fullmatch(r"last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
        if m:
            target = _WEEKDAYS[m.group(1)]
            delta = (today.weekday() - target) % 7
            if delta == 0:
                delta = 7
            day = today - dt.timedelta(days=delta)
            start = dt.datetime.combine(day, dt.time.min)
            return start, start + dt.timedelta(days=1)
        try:
            day = dt.date.fromisoformat(text)
            start = dt.datetime.combine(day, dt.time.min)
            return start, start + dt.timedelta(days=1)
        except ValueError as exc:
            raise ValueError("Unsupported history period. Use today, yesterday, this week, last week, last N days, last <weekday>, or YYYY-MM-DD.") from exc

    def query(
        self,
        project: str | None = None,
        when: str | None = None,
        run_id: str | None = None,
        limit: int = 200,
    ) -> dict:
        start, end = self._time_range(when)
        clauses: list[str] = []
        params: list[Any] = []
        if project:
            clauses.append("LOWER(project)=LOWER(?)")
            params.append(str(project))
        if run_id:
            clauses.append("run_id=?")
            params.append(str(run_id))
        if start:
            clauses.append("created_at>=?")
            params.append(start.isoformat(timespec="seconds"))
        if end:
            clauses.append("created_at<?")
            params.append(end.isoformat(timespec="seconds"))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        bounded = max(1, min(int(limit), 1000))
        rows = self.conn.execute(
            "SELECT id FROM agent_run_history" + where + " ORDER BY created_at DESC,id DESC LIMIT ?",
            (*params, bounded),
        ).fetchall()
        events = [event for event in (self.get_event(int(row[0])) for row in rows) if event]
        events.reverse()
        run_ids = list(dict.fromkeys(event["run_id"] for event in events))
        return {
            "ok": True,
            "project": project,
            "when": when,
            "run_count": len(run_ids),
            "runs": run_ids,
            "events": events,
        }

    def prune(self, now: dt.datetime | None = None) -> int:
        now = now or self._now()
        cutoff = (now - dt.timedelta(days=self.retention_days)).isoformat(timespec="seconds")
        cur = self.conn.execute("DELETE FROM agent_run_history WHERE created_at<?", (cutoff,))
        self.conn.commit()
        return int(cur.rowcount or 0)
