from __future__ import annotations

from dataclasses import dataclass, asdict
import datetime as dt
import json
from pathlib import Path
import sqlite3
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.security.security_utils import redact_secrets


AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS security_audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    initiator TEXT NOT NULL,
    capability TEXT NOT NULL,
    target TEXT NOT NULL,
    approval_id TEXT,
    result TEXT NOT NULL, -- "SUCCESS" | "DENIED" | "FAILED" | "BLOCKED"
    timestamp TEXT NOT NULL,
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON security_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_capability ON security_audit_log(capability);
"""


@dataclass
class AuditRecord:
    initiator: str
    capability: str
    target: str
    result: str
    approval_id: str | None = None
    timestamp: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLogger:
    """Maintains immutable, confidential audit trail for all privileged actions (Section 100)."""

    def __init__(self, db_path: Path | str | None = None):
        path = Path(db_path) if db_path else (data_dir() / "assistant.sqlite3")
        self.conn = ThreadLocalSQLite(path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript(AUDIT_SCHEMA)
        self.conn.commit()

    def record(
        self,
        initiator: str,
        capability: str,
        target: str,
        result: str,
        approval_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Record a privileged action with sensitive payloads redacted."""
        now = dt.datetime.now().isoformat()
        clean_target = redact_secrets(target, max_chars=500)
        clean_meta = {}
        if metadata:
            for k, v in metadata.items():
                if any(sec in k.lower() for sec in ["secret", "key", "password", "token", "auth"]):
                    clean_meta[k] = "[REDACTED]"
                else:
                    clean_meta[k] = redact_secrets(str(v), max_chars=200)

        cur = self.conn.execute(
            """
            INSERT INTO security_audit_log (initiator, capability, target, approval_id, result, timestamp, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (initiator, capability, clean_target, approval_id, result, now, json.dumps(clean_meta)),
        )
        self.conn.commit()
        return cur.lastrowid or 0

    def query(self, limit: int = 50, capability: str | None = None) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        if capability:
            cursor.execute(
                "SELECT * FROM security_audit_log WHERE capability = ? ORDER BY audit_id DESC LIMIT ?",
                (capability, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM security_audit_log ORDER BY audit_id DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in cursor.fetchall()]
