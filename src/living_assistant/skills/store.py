from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.skills.manifest import SkillManifest


SKILLS_SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_lifecycle (
  skill_id TEXT PRIMARY KEY,
  current_version TEXT NOT NULL,
  state TEXT NOT NULL, -- DRAFT | ACTIVE | DISABLED | ARCHIVED
  approval_id TEXT,
  approved_version TEXT,
  approved_hash TEXT,
  approved_package_hash TEXT,
  snapshot_dir TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_versions (
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  skill_md TEXT NOT NULL,
  snapshot_dir TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (skill_id, version)
);

CREATE TABLE IF NOT EXISTS skill_executions (
  run_id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  trigger TEXT,
  inputs_json TEXT,
  status TEXT NOT NULL, -- QUEUED | RUNNING | COMPLETED | FAILED | CANCELLED
  dry_run INTEGER NOT NULL DEFAULT 0,
  trace_json TEXT,
  outputs_json TEXT,
  error TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS skill_action_records (
  action_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  step_id TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  idempotency_key TEXT NOT NULL,
  operation TEXT NOT NULL,
  preconditions_json TEXT,
  target_source TEXT,
  target_destination TEXT,
  status TEXT NOT NULL, -- PLANNED | STARTED | SUCCEEDED | FAILED | UNCERTAIN
  evidence_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_undo_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  step_id TEXT NOT NULL,
  action TEXT NOT NULL,
  reverse_data_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_exec_skill ON skill_executions(skill_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_skill_undo_run ON skill_undo_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_skill_action_run ON skill_action_records(run_id);
CREATE INDEX IF NOT EXISTS idx_skill_action_idemp ON skill_action_records(idempotency_key);
"""


class SkillStore:
    """Thread-safe SQLite store for application-managed skill lifecycles, version snapshots, and run traces."""

    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SKILLS_SCHEMA)
        self.conn.commit()

        # Migrate existing skill_lifecycle table if missing columns
        for col, col_type in [("approved_package_hash", "TEXT"), ("snapshot_dir", "TEXT")]:
            try:
                self.conn.execute(f"ALTER TABLE skill_lifecycle ADD COLUMN {col} {col_type}")
                self.conn.commit()
            except Exception:
                pass

    def register_skill(self, manifest: SkillManifest, skill_md: str, initial_state: str = "DRAFT",
                       snapshot_dir: str = "") -> dict:
        now = dt.datetime.now().isoformat(timespec="seconds")
        row = self.conn.execute("SELECT * FROM skill_lifecycle WHERE skill_id=?", (manifest.id,)).fetchone()
        state = initial_state if not row else row["state"]

        self.conn.execute(
            """INSERT OR REPLACE INTO skill_lifecycle
               (skill_id, current_version, state, snapshot_dir, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (manifest.id, manifest.version, state, snapshot_dir, now),
        )
        self.conn.execute(
            """INSERT OR REPLACE INTO skill_versions
               (skill_id, version, manifest_json, skill_md, snapshot_dir, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (manifest.id, manifest.version, manifest.to_json(), skill_md, snapshot_dir, now),
        )
        self.conn.commit()
        return self.get_lifecycle(manifest.id) or {}

    def save_version(self, skill_id: str, manifest: SkillManifest, skill_md: str, snapshot_dir: str = ""):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT OR REPLACE INTO skill_versions
               (skill_id, version, manifest_json, skill_md, snapshot_dir, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (skill_id, manifest.version, manifest.to_json(), skill_md, snapshot_dir, now),
        )
        self.conn.execute(
            """UPDATE skill_lifecycle
               SET current_version=?, snapshot_dir=?, updated_at=?
               WHERE skill_id=?""",
            (manifest.version, snapshot_dir, now, skill_id),
        )
        self.conn.commit()

    def get_lifecycle(self, skill_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM skill_lifecycle WHERE skill_id=?", (skill_id,)).fetchone()
        return dict(row) if row else None

    def set_state(self, skill_id: str, state: str) -> bool:
        valid_states = {"DRAFT", "ACTIVE", "DISABLED", "ARCHIVED"}
        if state not in valid_states:
            raise ValueError(f"Invalid skill state '{state}'. Must be one of {valid_states}")
        now = dt.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "UPDATE skill_lifecycle SET state=?, updated_at=? WHERE skill_id=?",
            (state, now, skill_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def approve_skill(
        self,
        skill_id: str,
        approval_id: str,
        version: str,
        permission_hash: str,
        package_hash: str = "",
        snapshot_dir: str = "",
    ) -> bool:
        now = dt.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            """UPDATE skill_lifecycle
               SET approval_id=?, approved_version=?, approved_hash=?, approved_package_hash=?, snapshot_dir=?, updated_at=?
               WHERE skill_id=?""",
            (approval_id, version, permission_hash, package_hash, snapshot_dir, now, skill_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def is_approved(
        self,
        skill_id: str,
        version: str,
        current_permission_hash: str,
        current_package_hash: str | None = None,
    ) -> bool:
        lifecycle = self.get_lifecycle(skill_id)
        if not lifecycle:
            return False
        if lifecycle.get("approved_version") != version:
            return False
        if lifecycle.get("approved_hash") != current_permission_hash:
            return False
        if not lifecycle.get("approval_id"):
            return False
        if current_package_hash and lifecycle.get("approved_package_hash"):
            if lifecycle.get("approved_package_hash") != current_package_hash:
                return False
        return True

    def invalidate_approval(self, skill_id: str) -> bool:
        now = dt.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            """UPDATE skill_lifecycle
               SET approval_id=NULL, approved_version=NULL, approved_hash=NULL, approved_package_hash=NULL,
                   state=CASE WHEN state='ACTIVE' THEN 'DRAFT' ELSE state END,
                   updated_at=?
               WHERE skill_id=?""",
            (now, skill_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_skills(self, state: str | None = None) -> list[dict]:
        if state:
            rows = self.conn.execute(
                "SELECT * FROM skill_lifecycle WHERE state=? ORDER BY skill_id ASC", (state,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM skill_lifecycle ORDER BY skill_id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_version(self, skill_id: str, version: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM skill_versions WHERE skill_id=? AND version=?", (skill_id, version)
        ).fetchone()
        return dict(row) if row else None

    def get_versions(self, skill_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT skill_id, version, created_at, snapshot_dir FROM skill_versions WHERE skill_id=? ORDER BY created_at DESC",
            (skill_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def rollback_version(self, skill_id: str, target_version: str) -> tuple[SkillManifest, str]:
        target = self.get_version(skill_id, target_version)
        if not target:
            raise ValueError(f"Version '{target_version}' not found for skill '{skill_id}'.")

        manifest = SkillManifest.from_json(target["manifest_json"])
        skill_md = target["skill_md"]

        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """UPDATE skill_lifecycle
               SET current_version=?, approval_id=NULL, approved_version=NULL, approved_hash=NULL,
                   state='DRAFT', updated_at=?
               WHERE skill_id=?""",
            (target_version, now, skill_id),
        )
        self.conn.commit()
        return manifest, skill_md

    def record_execution_start(self, skill_id: str, version: str, inputs: dict, dry_run: bool = False,
                               trigger: str = "") -> str:
        run_id = uuid.uuid4().hex[:14]
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO skill_executions
               (run_id, skill_id, version, trigger, inputs_json, status, dry_run, started_at)
               VALUES (?, ?, ?, ?, ?, 'RUNNING', ?, ?)""",
            (run_id, skill_id, version, trigger, json.dumps(inputs), 1 if dry_run else 0, now),
        )
        self.conn.commit()
        return run_id

    def record_execution_finish(self, run_id: str, status: str, outputs: dict | None = None,
                                trace: list[dict] | None = None, error: str | None = None):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """UPDATE skill_executions
               SET status=?, outputs_json=?, trace_json=?, error=?, finished_at=?
               WHERE run_id=?""",
            (
                status,
                json.dumps(outputs or {}),
                json.dumps(trace or []),
                error,
                now,
                run_id,
            ),
        )
        self.conn.commit()

    def record_undo_action(self, run_id: str, step_id: str, action: str, reverse_data: dict):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO skill_undo_logs (run_id, step_id, action, reverse_data_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (run_id, step_id, action, json.dumps(reverse_data), now),
        )
        self.conn.commit()

    def get_undo_actions(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM skill_undo_logs WHERE run_id=? ORDER BY id DESC", (run_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["reverse_data"] = json.loads(d["reverse_data_json"])
            result.append(d)
        return result

    def get_executions(self, skill_id: str | None = None, limit: int = 50) -> list[dict]:
        if skill_id:
            rows = self.conn.execute(
                "SELECT * FROM skill_executions WHERE skill_id=? ORDER BY started_at DESC LIMIT ?",
                (skill_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM skill_executions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["inputs"] = json.loads(item["inputs_json"]) if item.get("inputs_json") else {}
            item["outputs"] = json.loads(item["outputs_json"]) if item.get("outputs_json") else {}
            item["trace"] = json.loads(item["trace_json"]) if item.get("trace_json") else []
            out.append(item)
        return out

    def record_action_planned(
        self,
        run_id: str,
        skill_id: str,
        step_id: str,
        idempotency_key: str,
        operation: str,
        preconditions: dict,
        target_source: str | None = None,
        target_destination: str | None = None,
        attempt: int = 1,
    ) -> str:
        action_id = str(uuid.uuid4())
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO skill_action_records
               (action_id, run_id, skill_id, step_id, attempt, idempotency_key, operation,
                preconditions_json, target_source, target_destination, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PLANNED', ?, ?)""",
            (
                action_id,
                run_id,
                skill_id,
                step_id,
                attempt,
                idempotency_key,
                operation,
                json.dumps(preconditions),
                target_source,
                target_destination,
                now,
                now,
            ),
        )
        self.conn.commit()
        return action_id

    def record_action_started(self, action_id: str):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE skill_action_records SET status='STARTED', updated_at=? WHERE action_id=?",
            (now, action_id),
        )
        self.conn.commit()

    def record_action_succeeded(self, action_id: str, evidence: dict | None = None):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE skill_action_records SET status='SUCCEEDED', evidence_json=?, updated_at=? WHERE action_id=?",
            (json.dumps(evidence or {}), now, action_id),
        )
        self.conn.commit()

    def record_action_failed(self, action_id: str, error: str):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE skill_action_records SET status='FAILED', error=?, updated_at=? WHERE action_id=?",
            (error, now, action_id),
        )
        self.conn.commit()

    def record_action_uncertain(self, action_id: str, reason: str):
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE skill_action_records SET status='UNCERTAIN', error=?, updated_at=? WHERE action_id=?",
            (reason, now, action_id),
        )
        self.conn.commit()

    def get_action_records(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM skill_action_records WHERE run_id=? ORDER BY created_at ASC",
            (run_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["preconditions"] = json.loads(d["preconditions_json"]) if d.get("preconditions_json") else {}
            d["evidence"] = json.loads(d["evidence_json"]) if d.get("evidence_json") else {}
            out.append(d)
        return out

    def reconcile_interrupted_run(self, run_id: str) -> dict[str, Any]:
        """Inspects actions for an interrupted run and reconciles against actual filesystem state."""
        records = self.get_action_records(run_id)
        reconciled = []
        needs_review = False
        uncertain_actions = []

        for rec in records:
            if rec["status"] in ("PLANNED", "STARTED"):
                action_id = rec["action_id"]
                op = rec["operation"]
                src_path = Path(rec["target_source"]) if rec.get("target_source") else None
                dst_path = Path(rec["target_destination"]) if rec.get("target_destination") else None

                if op == "files.move" and src_path and dst_path:
                    # Case 1: Destination exists and source is gone -> action succeeded before recording!
                    if dst_path.exists() and not src_path.exists():
                        self.record_action_succeeded(action_id, {"reconciled": True, "evidence": "destination_found_source_absent"})
                        reconciled.append({"action_id": action_id, "status": "SUCCEEDED", "reconciled": True})
                    # Case 2: Source exists and destination does not -> action aborted cleanly before move
                    elif src_path.exists() and not dst_path.exists():
                        self.record_action_failed(action_id, "Interrupted prior to file move.")
                        reconciled.append({"action_id": action_id, "status": "FAILED", "reconciled": True})
                    # Case 3: Both exist or neither exists -> uncertain!
                    else:
                        needs_review = True
                        reason = f"Ambiguous move state: source exists={src_path.exists()}, destination exists={dst_path.exists()}"
                        self.record_action_uncertain(action_id, reason)
                        uncertain_actions.append({"action_id": action_id, "reason": reason})
                elif op == "files.write" and dst_path:
                    if dst_path.exists():
                        self.record_action_succeeded(action_id, {"reconciled": True, "evidence": "target_file_exists"})
                        reconciled.append({"action_id": action_id, "status": "SUCCEEDED", "reconciled": True})
                    else:
                        self.record_action_failed(action_id, "Interrupted before file written.")
                        reconciled.append({"action_id": action_id, "status": "FAILED", "reconciled": True})
                else:
                    self.record_action_uncertain(action_id, "Unknown or unverifiable interrupted operation.")
                    needs_review = True
                    uncertain_actions.append({"action_id": action_id, "reason": "unverifiable operation"})

        return {
            "run_id": run_id,
            "reconciled_actions": reconciled,
            "needs_review": needs_review,
            "uncertain_actions": uncertain_actions,
        }

