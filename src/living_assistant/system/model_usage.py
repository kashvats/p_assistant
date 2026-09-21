from __future__ import annotations

import datetime as dt
import math
import threading
from pathlib import Path
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_usage(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  run_id TEXT,
  model TEXT NOT NULL,
  role TEXT NOT NULL,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  latency_ms REAL NOT NULL,
  token_source TEXT NOT NULL DEFAULT 'unknown',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS model_usage_time_idx ON model_usage(created_at);
CREATE INDEX IF NOT EXISTS model_usage_model_time_idx ON model_usage(model,created_at);
CREATE INDEX IF NOT EXISTS model_usage_session_time_idx ON model_usage(session_id,created_at);
"""


class ModelUsageStore:
    """Persist model-call counters without storing prompt or response content.

    Token counts are recorded only when the provider reports them. This intentionally
    avoids inventing token estimates for custom providers, where tokenizer differences
    would make analytics misleading.
    """

    def __init__(self, path: Path | None = None, retention_days: int = 365):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.retention_days = max(7, min(int(retention_days), 3650))
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = __import__("sqlite3").Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._prune_lock = threading.RLock()
        self._last_prune_day: dt.date | None = None
        self._maybe_prune()

    @staticmethod
    def _now() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    @staticmethod
    def _bounded_identifier(value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text[:limit] if text else None

    @staticmethod
    def _as_nonnegative_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if number >= 0 else None

    @classmethod
    def _extract_tokens(cls, response: dict | None) -> tuple[int | None, int | None, str]:
        payload = response if isinstance(response, dict) else {}

        # Ollama reports exact tokenizer counts at the top level.
        prompt = cls._as_nonnegative_int(payload.get("prompt_eval_count"))
        completion = cls._as_nonnegative_int(payload.get("eval_count"))
        if prompt is not None or completion is not None:
            return prompt, completion, "ollama"

        # Keep compatibility with providers exposing OpenAI-style usage metadata.
        usage = payload.get("usage")
        if isinstance(usage, dict):
            prompt = cls._as_nonnegative_int(
                usage.get("prompt_tokens", usage.get("input_tokens"))
            )
            completion = cls._as_nonnegative_int(
                usage.get("completion_tokens", usage.get("output_tokens"))
            )
            if prompt is not None or completion is not None:
                return prompt, completion, "provider_usage"

        return None, None, "unknown"

    def _maybe_prune(self, now: dt.datetime | None = None) -> None:
        now = now or self._now()
        day = now.date()
        with self._prune_lock:
            if self._last_prune_day == day:
                return
            self.prune(now)
            self._last_prune_day = day

    def record_response(
        self,
        model: str,
        response: dict | None,
        latency_seconds: float,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        role: str = "orchestrator",
        created_at: dt.datetime | None = None,
    ) -> dict:
        model_name = self._bounded_identifier(model, 300)
        if not model_name:
            raise ValueError("model is required for usage accounting")
        try:
            latency = float(latency_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("latency_seconds must be a finite non-negative number") from exc
        if not math.isfinite(latency) or latency < 0:
            raise ValueError("latency_seconds must be a finite non-negative number")

        prompt_tokens, completion_tokens, token_source = self._extract_tokens(response)
        when = created_at or self._now()
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        else:
            when = when.astimezone(dt.timezone.utc)
        created = when.isoformat(timespec="milliseconds")

        cur = self.conn.execute(
            """INSERT INTO model_usage(
                   session_id,run_id,model,role,prompt_tokens,completion_tokens,
                   latency_ms,token_source,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                self._bounded_identifier(session_id, 200),
                self._bounded_identifier(run_id, 200),
                model_name,
                self._bounded_identifier(role, 160) or "orchestrator",
                prompt_tokens,
                completion_tokens,
                latency * 1000.0,
                token_source,
                created,
            ),
        )
        self.conn.commit()
        self._maybe_prune(when)
        row = self.conn.execute(
            "SELECT * FROM model_usage WHERE id=?", (int(cur.lastrowid),)
        ).fetchone()
        return dict(row) if row else {}

    def summary(
        self,
        *,
        session_id: str | None = None,
        days: int = 30,
        limit_models: int = 20,
    ) -> dict:
        days = max(1, min(int(days), 3650))
        limit_models = max(1, min(int(limit_models), 100))
        cutoff = (self._now() - dt.timedelta(days=days)).isoformat(timespec="milliseconds")
        clauses = ["created_at>=?"]
        params: list[Any] = [cutoff]
        bounded_session = self._bounded_identifier(session_id, 200)
        if bounded_session:
            clauses.append("session_id=?")
            params.append(bounded_session)
        where = " AND ".join(clauses)

        total = self.conn.execute(
            f"""SELECT
                    COUNT(*) AS calls,
                    COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens),0) AS completion_tokens,
                    SUM(CASE WHEN prompt_tokens IS NULL AND completion_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_token_calls,
                    COALESCE(AVG(latency_ms),0) AS avg_latency_ms
                FROM model_usage WHERE {where}""",
            tuple(params),
        ).fetchone()

        rows = self.conn.execute(
            f"""SELECT
                    model,
                    COUNT(*) AS calls,
                    COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens),0) AS completion_tokens,
                    SUM(CASE WHEN prompt_tokens IS NULL AND completion_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_token_calls,
                    COALESCE(AVG(latency_ms),0) AS avg_latency_ms,
                    COALESCE(MAX(latency_ms),0) AS max_latency_ms,
                    MAX(created_at) AS last_used_at
                FROM model_usage
                WHERE {where}
                GROUP BY model
                ORDER BY calls DESC,last_used_at DESC,model ASC
                LIMIT ?""",
            (*params, limit_models),
        ).fetchall()

        models = []
        for row in rows:
            item = dict(row)
            item["calls"] = int(item.get("calls") or 0)
            item["prompt_tokens"] = int(item.get("prompt_tokens") or 0)
            item["completion_tokens"] = int(item.get("completion_tokens") or 0)
            item["total_tokens"] = item["prompt_tokens"] + item["completion_tokens"]
            item["unknown_token_calls"] = int(item.get("unknown_token_calls") or 0)
            item["avg_latency_ms"] = round(float(item.get("avg_latency_ms") or 0.0), 2)
            item["max_latency_ms"] = round(float(item.get("max_latency_ms") or 0.0), 2)
            models.append(item)

        totals = dict(total) if total else {}
        prompt_total = int(totals.get("prompt_tokens") or 0)
        completion_total = int(totals.get("completion_tokens") or 0)
        result_totals = {
            "calls": int(totals.get("calls") or 0),
            "prompt_tokens": prompt_total,
            "completion_tokens": completion_total,
            "total_tokens": prompt_total + completion_total,
            "unknown_token_calls": int(totals.get("unknown_token_calls") or 0),
            "avg_latency_ms": round(float(totals.get("avg_latency_ms") or 0.0), 2),
        }
        return {
            "ok": True,
            "days": days,
            "session_id": bounded_session,
            "totals": result_totals,
            "models": models,
        }

    def prune(self, now: dt.datetime | None = None) -> int:
        now = now or self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=dt.timezone.utc)
        else:
            now = now.astimezone(dt.timezone.utc)
        cutoff = (now - dt.timedelta(days=self.retention_days)).isoformat(timespec="milliseconds")
        cur = self.conn.execute("DELETE FROM model_usage WHERE created_at<?", (cutoff,))
        self.conn.commit()
        return int(cur.rowcount or 0)
