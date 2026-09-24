from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.agents.custom.manifest import AgentManifest


AGENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_lifecycle (
  agent_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  current_version TEXT NOT NULL,
  state TEXT NOT NULL, -- DRAFT | ACTIVE | DISABLED | ARCHIVED
  approval_id TEXT,
  approved_version TEXT,
  approved_hash TEXT,
  approved_package_hash TEXT,
  snapshot_dir TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_versions (
  agent_id TEXT NOT NULL,
  version TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  agent_md TEXT NOT NULL,
  package_hash TEXT,
  snapshot_dir TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (agent_id, version)
);

CREATE TABLE IF NOT EXISTS agent_executions (
  run_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  version TEXT NOT NULL,
  task TEXT NOT NULL,
  inputs_json TEXT,
  status TEXT NOT NULL, -- QUEUED | RUNNING | COMPLETED | FAILED | CANCELLED
  dry_run INTEGER NOT NULL DEFAULT 0,
  steps_taken INTEGER NOT NULL DEFAULT 0,
  tool_call_count INTEGER NOT NULL DEFAULT 0,
  trace_json TEXT,
  output_text TEXT,
  error TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_action_records (
  action_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  parent_run_id TEXT,
  step_number INTEGER NOT NULL DEFAULT 1,
  action_type TEXT NOT NULL, -- tool_call | delegation | skill_invocation
  target_name TEXT NOT NULL,
  arguments_json TEXT,
  result_json TEXT,
  status TEXT NOT NULL, -- PLANNED | STARTED | SUCCEEDED | FAILED
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_memory_entries (
  namespace TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (namespace, agent_id, key)
);
"""


class AgentStore:
    """SQLite-backed persistence for custom agent lifecycles, versions, executions, actions, and memory."""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = data_dir() / "assistant.sqlite3"
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = ThreadLocalSQLite(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(AGENTS_SCHEMA)
        self.conn.commit()

    def close(self):
        if hasattr(self.conn, "close_all"):
            self.conn.close_all()

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    def register_agent(
        self,
        manifest: AgentManifest,
        agent_md: str,
        initial_state: str = "DRAFT",
        package_hash: str | None = None,
        snapshot_dir: str | None = None,
    ) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO agent_lifecycle (
                    agent_id, name, role, current_version, state,
                    approval_id, approved_version, approved_hash, approved_package_hash,
                    snapshot_dir, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    name=excluded.name,
                    role=excluded.role,
                    current_version=excluded.current_version,
                    state=excluded.state,
                    approved_package_hash=COALESCE(excluded.approved_package_hash, agent_lifecycle.approved_package_hash),
                    snapshot_dir=COALESCE(excluded.snapshot_dir, agent_lifecycle.snapshot_dir),
                    updated_at=excluded.updated_at
                """,
                (
                    manifest.id,
                    manifest.name,
                    manifest.role,
                    manifest.version,
                    initial_state,
                    None,
                    None,
                    None,
                    package_hash,
                    snapshot_dir,
                    now,
                ),
            )
            self.conn.execute(
                """
                INSERT INTO agent_versions (
                    agent_id, version, manifest_json, agent_md, package_hash, snapshot_dir, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id, version) DO UPDATE SET
                    manifest_json=excluded.manifest_json,
                    agent_md=excluded.agent_md,
                    package_hash=excluded.package_hash,
                    snapshot_dir=excluded.snapshot_dir
                """,
                (
                    manifest.id,
                    manifest.version,
                    json.dumps(manifest.model_dump()),
                    agent_md,
                    package_hash,
                    snapshot_dir,
                    now,
                ),
            )

    def get_lifecycle(self, agent_id: str) -> dict[str, Any] | None:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM agent_lifecycle WHERE agent_id = ?", (agent_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_state(self, agent_id: str, state: str) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "UPDATE agent_lifecycle SET state = ?, updated_at = ? WHERE agent_id = ?",
                (state, now, agent_id),
            )

    def approve_agent(
        self,
        agent_id: str,
        approval_id: str,
        version: str,
        permission_hash: str,
        package_hash: str | None = None,
        snapshot_dir: str | None = None,
    ) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                UPDATE agent_lifecycle
                SET approval_id = ?,
                    approved_version = ?,
                    approved_hash = ?,
                    approved_package_hash = ?,
                    snapshot_dir = COALESCE(?, snapshot_dir),
                    updated_at = ?
                WHERE agent_id = ?
                """,
                (approval_id, version, permission_hash, package_hash, snapshot_dir, now, agent_id),
            )

    def is_approved(
        self,
        agent_id: str,
        version: str,
        permission_hash: str,
        package_hash: str | None = None,
    ) -> bool:
        lifecycle = self.get_lifecycle(agent_id)
        if not lifecycle:
            return False
        if lifecycle.get("state") != "ACTIVE":
            return False
        if lifecycle.get("approved_version") != version:
            return False
        if lifecycle.get("approved_hash") != permission_hash:
            return False
        if package_hash is not None and lifecycle.get("approved_package_hash"):
            if lifecycle.get("approved_package_hash") != package_hash:
                return False
        return True

    def list_agents(self, state: str | None = None) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        if state:
            cursor.execute(
                "SELECT * FROM agent_lifecycle WHERE state = ? ORDER BY name ASC",
                (state,),
            )
        else:
            cursor.execute("SELECT * FROM agent_lifecycle ORDER BY name ASC")
        return [dict(r) for r in cursor.fetchall()]

    def get_versions(self, agent_id: str) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? ORDER BY created_at DESC",
            (agent_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Execution History
    # -------------------------------------------------------------------------

    def record_execution_start(
        self,
        agent_id: str,
        version: str,
        task: str,
        inputs: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> str:
        run_id = f"arun_{uuid.uuid4().hex[:12]}"
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO agent_executions (
                    run_id, agent_id, version, task, inputs_json,
                    status, dry_run, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    agent_id,
                    version,
                    task,
                    json.dumps(inputs or {}),
                    "RUNNING",
                    1 if dry_run else 0,
                    now,
                ),
            )
        return run_id

    def record_execution_finish(
        self,
        run_id: str,
        status: str,
        steps_taken: int = 0,
        tool_call_count: int = 0,
        trace: list[dict[str, Any]] | None = None,
        output_text: str = "",
        error: str | None = None,
    ) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                UPDATE agent_executions
                SET status = ?,
                    steps_taken = ?,
                    tool_call_count = ?,
                    trace_json = ?,
                    output_text = ?,
                    error = ?,
                    finished_at = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    steps_taken,
                    tool_call_count,
                    json.dumps(trace or []),
                    output_text,
                    error,
                    now,
                    run_id,
                ),
            )

    def get_executions(
        self,
        agent_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        if agent_id:
            cursor.execute(
                """
                SELECT * FROM agent_executions
                WHERE agent_id = ?
                ORDER BY started_at DESC LIMIT ?
                """,
                (agent_id, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM agent_executions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        rows = cursor.fetchall()
        out = []
        for r in rows:
            item = dict(r)
            if item.get("inputs_json"):
                try:
                    item["inputs"] = json.loads(item["inputs_json"])
                except Exception:
                    item["inputs"] = {}
            if item.get("trace_json"):
                try:
                    item["trace"] = json.loads(item["trace_json"])
                except Exception:
                    item["trace"] = []
            out.append(item)
        return out

    # -------------------------------------------------------------------------
    # Action Records (Recovery & Auditing)
    # -------------------------------------------------------------------------

    def record_action(
        self,
        run_id: str,
        agent_id: str,
        action_type: str,
        target_name: str,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        status: str = "SUCCEEDED",
        parent_run_id: str | None = None,
        step_number: int = 1,
        error: str | None = None,
    ) -> str:
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO agent_action_records (
                    action_id, run_id, agent_id, parent_run_id, step_number,
                    action_type, target_name, arguments_json, result_json,
                    status, error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    run_id,
                    agent_id,
                    parent_run_id,
                    step_number,
                    action_type,
                    target_name,
                    json.dumps(arguments or {}, default=str),
                    json.dumps(result, default=str),
                    status,
                    error,
                    now,
                    now,
                ),
            )
        return action_id

    # -------------------------------------------------------------------------
    # Scoped Memory Persistence
    # -------------------------------------------------------------------------

    def set_memory(self, namespace: str, agent_id: str, key: str, value: Any) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO agent_memory_entries (
                    namespace, agent_id, key, value_json, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, agent_id, key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (namespace, agent_id, key, json.dumps(value, default=str), now),
            )

    def get_memory(self, namespace: str, agent_id: str, key: str) -> Any | None:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT value_json FROM agent_memory_entries WHERE namespace = ? AND agent_id = ? AND key = ?",
            (namespace, agent_id, key),
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return None

    def list_memory(self, namespace: str, agent_id: str) -> dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT key, value_json FROM agent_memory_entries WHERE namespace = ? AND agent_id = ?",
            (namespace, agent_id),
        )
        out = {}
        for k, val_json in cursor.fetchall():
            try:
                out[k] = json.loads(val_json)
            except Exception:
                out[k] = val_json
        return out

    def clear_memory(self, namespace: str, agent_id: str) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM agent_memory_entries WHERE namespace = ? AND agent_id = ?",
                (namespace, agent_id),
            )
