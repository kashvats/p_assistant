from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from rich.console import Console
from .config import data_dir
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
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @staticmethod
    def action_hash(action: str, reason: str, kind: str) -> str:
        raw = json.dumps({"action": action, "reason": reason, "kind": kind}, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()

    def consume_preapproval(self, action: str, reason: str, kind: str) -> str | None:
        h = self.action_hash(action, reason, kind)
        row = self.conn.execute(
            "SELECT id FROM approvals WHERE action_hash=? AND status='approved' AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (h,),
        ).fetchone()
        if not row:
            return None
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute("UPDATE approvals SET consumed_at=? WHERE id=?", (now, row["id"]))
        self.conn.commit()
        return str(row["id"])

    def create(self, action: str, reason: str, kind: str = "execute") -> dict:
        h = self.action_hash(action, reason, kind)
        existing = self.conn.execute(
            "SELECT * FROM approvals WHERE action_hash=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (h,),
        ).fetchone()
        if existing:
            item = dict(existing); item["_created"] = False; return item
        item_id = uuid.uuid4().hex[:12]
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO approvals(id, action_hash, action, reason, kind, status, created_at) VALUES(?,?,?,?,?,'pending',?)",
            (item_id, h, action, reason, kind, now),
        )
        self.conn.commit()
        item = dict(self.conn.execute("SELECT * FROM approvals WHERE id=?", (item_id,)).fetchone()); item["_created"] = True; return item

    def list(self, status: str | None = "pending", limit: int = 100) -> list[dict]:
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
            console.print(f"[yellow]Approval required[/yellow]: {action}")
            console.print(f"[dim]{reason}[/dim]")
            answer = input("Allow? [y/N]: ").strip().lower()
            return {"allowed": answer in {"y", "yes"}, "interactive": True}

        item = self.store.create(action, reason, kind)
        if self.notifier is not None and item.get('_created'):
            try:
                self.notifier.send('Living Assistant approval', f'{kind}: {action[:180]}')
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
