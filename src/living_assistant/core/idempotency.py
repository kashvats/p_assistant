from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite


class IdempotencyStore:
    """Section 76: Idempotent action execution and deduplication store."""

    def __init__(self, db_path: Path | None = None, retention_seconds: float = 86400.0):
        self.path = db_path or (data_dir() / "idempotency.sqlite3")
        self.retention_seconds = retention_seconds
        self.conn = ThreadLocalSQLite(self.path, timeout=10.0)
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                created_at REAL NOT NULL,
                completed_at REAL
            )
        """)
        self.conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT idempotency_key, action_type, status, result, created_at, completed_at FROM idempotency_records WHERE idempotency_key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        res_val = None
        if row[3]:
            try:
                res_val = json.loads(row[3])
            except Exception:
                res_val = row[3]
        return {
            "key": row[0],
            "action_type": row[1],
            "status": row[2],
            "result": res_val,
            "created_at": row[4],
            "completed_at": row[5],
        }

    def execute(self, key: str, action_type: str, fn: Callable[[], Any]) -> dict[str, Any]:
        """Execute action idempotently. Retries with the same key return the stored result without duplicate execution."""
        existing = self.get(key)
        if existing and existing["status"] == "completed":
            return {
                "ok": True,
                "idempotent": True,
                "cached": True,
                "action_type": action_type,
                "key": key,
                "result": existing["result"],
            }

        now = time.time()
        self.conn.execute(
            "INSERT OR REPLACE INTO idempotency_records (idempotency_key, action_type, status, result, created_at, completed_at) VALUES (?, ?, 'in_progress', NULL, ?, NULL)",
            (key, action_type, now),
        )
        self.conn.commit()

        try:
            output = fn()
            serialized = json.dumps(output, default=str)
            completed_now = time.time()
            self.conn.execute(
                "UPDATE idempotency_records SET status = 'completed', result = ?, completed_at = ? WHERE idempotency_key = ?",
                (serialized, completed_now, key),
            )
            self.conn.commit()
            return {
                "ok": True,
                "idempotent": True,
                "cached": False,
                "action_type": action_type,
                "key": key,
                "result": output,
            }
        except Exception as exc:
            self.conn.execute(
                "UPDATE idempotency_records SET status = 'failed', result = ?, completed_at = ? WHERE idempotency_key = ?",
                (str(exc), time.time(), key),
            )
            self.conn.commit()
            raise
