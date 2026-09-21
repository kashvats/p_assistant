from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from rich.console import Console
from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.security.security_utils import redact_secrets
import sqlite3, hashlib, json, datetime as dt, uuid

console = Console()

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals(
  id TEXT PRIMARY KEY,
  action_hash TEXT NOT NULL,
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  consumed_at TEXT
);
CREATE INDEX IF NOT EXISTS approvals_hash_status ON approvals(action_hash, status);
"""

class ApprovalStore:
    def __init__(self, path: Path | None = None, pending_ttl_hours: float = 24.0):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.pending_ttl_hours = max(0.0, float(pending_ttl_hours))
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @staticmethod
    def action_hash(action: str, reason: str, kind: str) -> str:
        # Approval retries must be stable across harmless boundary whitespace
        # differences, while preserving internal whitespace that may be
        # semantically meaningful (for example in shell commands or SQL).
        raw = json.dumps(
            {"action": action.strip(), "reason": reason.strip(), "kind": kind.strip()},
            sort_keys=True,
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def expire_pending(self, *, max_age_hours: float | None = None, now: dt.datetime | None = None) -> int:
        """Expire stale pending approvals so they cannot block a fresh request forever."""
        ttl = self.pending_ttl_hours if max_age_hours is None else max(0.0, float(max_age_hours))
        now = now or dt.datetime.now()
        cutoff = (now - dt.timedelta(hours=ttl)).isoformat(timespec="seconds")
        resolved_at = now.isoformat(timespec="seconds")
        cur = self.conn.execute(
            """UPDATE approvals
               SET status='expired', resolved_at=?
               WHERE status='pending' AND created_at<?""",
            (resolved_at, cutoff),
        )
        self.conn.commit()
        return int(cur.rowcount or 0)

    def consume_preapproval(self, action: str, reason: str, kind: str) -> str | None:
        h = self.action_hash(action, reason, kind)
        now = dt.datetime.now().isoformat(timespec="seconds")
        # Atomic one-shot consumption: concurrent workers cannot consume the same approval.
        row = self.conn.execute(
            """UPDATE approvals SET consumed_at=?
               WHERE id=(SELECT id FROM approvals
                         WHERE action_hash=? AND status='approved' AND consumed_at IS NULL
                         ORDER BY created_at DESC LIMIT 1)
                 AND consumed_at IS NULL
               RETURNING id""",
            (now, h),
        ).fetchone()
        self.conn.commit()
        return str(row["id"]) if row else None

    def create(self, action: str, reason: str, kind: str = "execute") -> dict:
        self.expire_pending()
        h = self.action_hash(action, reason, kind)
        existing = self.conn.execute(
            "SELECT * FROM approvals WHERE action_hash=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (h,),
        ).fetchone()
        if existing:
            item = dict(existing); item["_created"] = False; return item
        item_id = uuid.uuid4().hex[:12]
        now = dt.datetime.now().isoformat(timespec="seconds")
        stored_action = redact_secrets(action, 4000)
        stored_reason = redact_secrets(reason, 6000)
        self.conn.execute(
            "INSERT INTO approvals(id, action_hash, action, reason, kind, status, created_at) VALUES(?,?,?,?,?,'pending',?)",
            (item_id, h, stored_action, stored_reason, kind, now),
        )
        self.conn.commit()
        item = dict(self.conn.execute("SELECT * FROM approvals WHERE id=?", (item_id,)).fetchone()); item["_created"] = True; return item

    def list(self, status: str | None = "pending", limit: int = 100) -> list[dict]:
        if status in {None, "pending"}:
            self.expire_pending()
        if status:
            rows = self.conn.execute(
                "SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def resolve(self, approval_id: str, approved: bool) -> dict:
        status = "approved" if approved else "denied"
        now = dt.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "UPDATE approvals SET status=?, resolved_at=? WHERE id=? AND status='pending'",
            (status, now, approval_id),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            row = self.conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "Unknown approval id"}
            return {"ok": False, "error": f"Approval is already {row['status']}", "approval": dict(row)}
        return {"ok": True, "approval": dict(self.conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone())}

@dataclass
class ApprovalManager:
    interactive: bool = True
    store: ApprovalStore | None = None
    notifier: object | None = None

    def __post_init__(self):
        if self.store is None:
            self.store = ApprovalStore()

    def request(self, action: str, reason: str, kind: str = "execute") -> dict:
        consumed = self.store.consume_preapproval(action, reason, kind)
        if consumed:
            return {"allowed": True, "approval_id": consumed, "preapproved": True}

        if self.interactive:
            if self.notifier is not None:
                try:
                    self.notifier.send('Living Assistant approval', f'{kind}: {redact_secrets(action, 180)}', sound='approval')
                except TypeError:
                    try: self.notifier.send('Living Assistant approval', f'{kind}: {redact_secrets(action, 180)}')
                    except Exception: pass
                except Exception:
                    pass
            console.print(f"[yellow]Approval required[/yellow]: {action}")
            console.print(f"[dim]{reason}[/dim]")
            answer = input("Allow? [y/N]: ").strip().lower()
            return {"allowed": answer in {"y", "yes"}, "interactive": True}

        item = self.store.create(action, reason, kind)
        if self.notifier is not None and item.get('_created'):
            try:
                self.notifier.send('Living Assistant approval', f'{kind}: {redact_secrets(action, 180)}', sound='approval')
            except TypeError:
                try: self.notifier.send('Living Assistant approval', f'{kind}: {redact_secrets(action, 180)}')
                except Exception: pass
            except Exception:
                pass
        return {
            "allowed": False,
            "pending": True,
            "approval_id": item["id"],
            "message": "Approval is required. Approve this request, then retry the same action.",
        }

    def approve(self, action: str, reason: str) -> bool:
        return bool(self.request(action, reason).get("allowed"))
