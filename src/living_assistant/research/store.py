"""Persistent project knowledge.

Every research object (evidence, claim, event, pattern, hypothesis, ...) is one row
with a stable, human-readable id (EV-41, E-81, P-14), typed links between objects,
and a history of every status/level change. Nothing is ever deleted: a failed
hypothesis stays as CONTRADICTED knowledge, which is the point.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from living_assistant.core.sqlite_utils import ThreadLocalSQLite

PREFIX = {
    "project": "PRJ", "source": "SRC", "evidence": "EV", "claim": "C", "event": "E", "entity": "N",
    "relationship": "R", "pattern": "P", "occurrence": "PO", "symbol": "S", "interpretation": "SI",
    "hypothesis": "H", "finding": "F", "experiment": "X", "verification": "V", "implementation": "IM",
    "question": "Q", "run": "RUN",
}
OBJECT_TYPES = tuple(t for t in PREFIX if t != "project")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:60] or "project"


class KnowledgeStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = ThreadLocalSQLite(self.path)
        self._lock = threading.RLock()
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', build_requested INTEGER NOT NULL DEFAULT 0,
                data TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS objects (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, type TEXT NOT NULL, kind TEXT, status TEXT,
                level TEXT, title TEXT NOT NULL, ts TEXT, data TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS objects_project_type ON objects(project_id, type);
            CREATE INDEX IF NOT EXISTS objects_type_kind ON objects(type, kind);
            CREATE INDEX IF NOT EXISTS objects_ts ON objects(project_id, type, ts);
            CREATE TABLE IF NOT EXISTS links (
                src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, PRIMARY KEY (src, rel, dst));
            CREATE INDEX IF NOT EXISTS links_dst ON links(dst, rel);
            CREATE TABLE IF NOT EXISTS history (
                object_id TEXT NOT NULL, field TEXT NOT NULL, old TEXT, new TEXT, reason TEXT, at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS history_object ON history(object_id);
            CREATE TABLE IF NOT EXISTS counters (prefix TEXT PRIMARY KEY, n INTEGER NOT NULL);
            CREATE VIRTUAL TABLE IF NOT EXISTS objects_fts USING fts5(id UNINDEXED, project_id UNINDEXED,
                type UNINDEXED, title, body);
            """
        )
        self.db.commit()

    # ---- ids --------------------------------------------------------------------------

    def _next_id(self, type_: str) -> str:
        prefix = PREFIX[type_]
        row = self.db.execute("SELECT n FROM counters WHERE prefix=?", (prefix,)).fetchone()
        n = (row["n"] if row else 0) + 1
        self.db.execute("INSERT INTO counters(prefix, n) VALUES(?,?) ON CONFLICT(prefix) DO UPDATE SET n=excluded.n",
                        (prefix, n))
        return f"{prefix}-{n}"

    # ---- projects ---------------------------------------------------------------------

    @staticmethod
    def _project(row) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        item["data"] = json.loads(item["data"] or "{}")
        item["build_requested"] = bool(item["build_requested"])
        return item

    def create_project(self, name: str, kind: str = "general", description: str = "", status: str = "RESEARCHING") -> dict:
        slug = slugify(name)
        with self._lock:
            existing = self.get_project(slug)
            if existing:
                return existing
            pid = self._next_id("project")
            self.db.execute(
                "INSERT INTO projects(id, slug, name, kind, status, description, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (pid, slug, name.strip() or slug, kind, status, description, now(), now()))
            self.db.commit()
        return self.get_project(pid)

    def get_project(self, ref: str) -> dict | None:
        ref = str(ref or "").strip()
        row = self.db.execute("SELECT * FROM projects WHERE id=? OR slug=? OR lower(name)=lower(?)",
                              (ref, slugify(ref), ref)).fetchone()
        return self._project(row)

    def list_projects(self) -> list[dict]:
        return [self._project(r) for r in self.db.execute("SELECT * FROM projects ORDER BY updated_at DESC")]

    def update_project(self, pid: str, reason: str = "", **fields) -> dict:
        allowed = {"name", "kind", "status", "description", "build_requested", "data"}
        with self._lock:
            current = self.get_project(pid)
            if current is None:
                raise KeyError(f"Unknown project {pid}")
            sets, values = [], []
            for key, value in fields.items():
                if key not in allowed:
                    continue
                if key in ("status", "kind", "build_requested") and value != current[key]:
                    self._history(current["id"], key, current[key], value, reason)
                sets.append(f"{key}=?")
                values.append(json.dumps(value) if key == "data" else int(value) if key == "build_requested" else value)
            if sets:
                self.db.execute(f"UPDATE projects SET {', '.join(sets)}, updated_at=? WHERE id=?", (*values, now(), current["id"]))
                self.db.commit()
        return self.get_project(current["id"])

    # ---- objects ----------------------------------------------------------------------

    @staticmethod
    def _object(row) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        item["data"] = json.loads(item["data"] or "{}")
        return item

    def add(self, project_id: str, type_: str, title: str, *, kind: str | None = None, status: str | None = None,
            level: str | None = None, ts: str | None = None, data: dict | None = None,
            links: Iterable[tuple[str, str]] = (), body: str = "") -> dict:
        if type_ not in OBJECT_TYPES:
            raise ValueError(f"Unknown object type {type_!r}")
        with self._lock:
            oid = self._next_id(type_)
            stamp = now()
            self.db.execute(
                "INSERT INTO objects(id, project_id, type, kind, status, level, title, ts, data, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (oid, project_id, type_, kind, status, level, str(title)[:2000], ts, json.dumps(data or {}, default=str), stamp, stamp))
            self.db.execute("INSERT INTO objects_fts(id, project_id, type, title, body) VALUES(?,?,?,?,?)",
                            (oid, project_id, type_, str(title), body or json.dumps(data or {}, default=str)[:20000]))
            for rel, dst in links:
                self._link(oid, rel, dst, {})
            self.db.execute("UPDATE projects SET updated_at=? WHERE id=?", (stamp, project_id))
            self.db.commit()
        return self.get(oid)

    def find_one(self, project_id: str | None, type_: str, kind: str) -> dict | None:
        """Look up an object by its natural key (kind), e.g. a pattern signature or evidence hash."""
        if project_id is None:
            row = self.db.execute("SELECT * FROM objects WHERE type=? AND kind=? LIMIT 1", (type_, kind)).fetchone()
        else:
            row = self.db.execute("SELECT * FROM objects WHERE project_id=? AND type=? AND kind=? LIMIT 1",
                                  (project_id, type_, kind)).fetchone()
        return self._object(row)

    def get(self, oid: str) -> dict | None:
        return self._object(self.db.execute("SELECT * FROM objects WHERE id=?", (oid,)).fetchone())

    def update(self, oid: str, reason: str = "", **fields) -> dict:
        allowed = {"status", "level", "title", "data", "kind", "ts"}
        with self._lock:
            current = self.get(oid)
            if current is None:
                raise KeyError(f"Unknown object {oid}")
            sets, values = [], []
            for key, value in fields.items():
                if key not in allowed:
                    continue
                if key in ("status", "level") and value != current[key]:
                    self._history(oid, key, current[key], value, reason)
                sets.append(f"{key}=?")
                values.append(json.dumps(value, default=str) if key == "data" else value)
            if sets:
                self.db.execute(f"UPDATE objects SET {', '.join(sets)}, updated_at=? WHERE id=?", (*values, now(), oid))
                self.db.commit()
        return self.get(oid)

    def merge_data(self, oid: str, reason: str = "", **values) -> dict:
        current = self.get(oid)
        if current is None:
            raise KeyError(f"Unknown object {oid}")
        return self.update(oid, reason, data={**current["data"], **values})

    def find(self, project_id: str | None = None, type_: str | None = None, *, kind: str | None = None,
             status: str | None = None, level: str | None = None, order: str = "created", limit: int = 500) -> list[dict]:
        where, args = [], []
        for col, value in (("project_id", project_id), ("type", type_), ("kind", kind), ("status", status), ("level", level)):
            if value is not None:
                where.append(f"{col}=?")
                args.append(value)
        order_sql = {"created": "created_at, rowid", "ts": "ts, rowid", "updated": "updated_at DESC"}[order]
        sql = f"SELECT * FROM objects {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY {order_sql} LIMIT ?"
        return [self._object(r) for r in self.db.execute(sql, (*args, int(limit)))]

    def count(self, project_id: str) -> dict[str, int]:
        rows = self.db.execute("SELECT type, count(*) AS n FROM objects WHERE project_id=? GROUP BY type", (project_id,))
        return {r["type"]: r["n"] for r in rows}

    # ---- links & history --------------------------------------------------------------

    def _link(self, src: str, rel: str, dst: str, data: dict) -> None:
        self.db.execute("INSERT OR IGNORE INTO links(src, rel, dst, data, created_at) VALUES(?,?,?,?,?)",
                        (src, rel, dst, json.dumps(data or {}, default=str), now()))

    def link(self, src: str, rel: str, dst: str, **data) -> None:
        with self._lock:
            self._link(src, rel, dst, data)
            self.db.commit()

    def links_from(self, oid: str, rel: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM links WHERE src=?", [oid]
        if rel:
            sql, args = sql + " AND rel=?", [oid, rel]
        return [{**dict(r), "data": json.loads(r["data"] or "{}")} for r in self.db.execute(sql + " ORDER BY created_at", args)]

    def links_to(self, oid: str, rel: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM links WHERE dst=?", [oid]
        if rel:
            sql, args = sql + " AND rel=?", [oid, rel]
        return [{**dict(r), "data": json.loads(r["data"] or "{}")} for r in self.db.execute(sql + " ORDER BY created_at", args)]

    def _history(self, oid: str, field: str, old: Any, new: Any, reason: str) -> None:
        self.db.execute("INSERT INTO history(object_id, field, old, new, reason, at) VALUES(?,?,?,?,?,?)",
                        (oid, field, None if old is None else str(old), None if new is None else str(new), reason, now()))

    def history(self, oid: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM history WHERE object_id=? ORDER BY rowid", (oid,))]

    # ---- search -----------------------------------------------------------------------

    def search(self, text: str, project_id: str | None = None, types: Iterable[str] | None = None, limit: int = 20) -> list[dict]:
        terms = [t for t in re.findall(r"[\w-]+", str(text or "").lower()) if len(t) > 2][:12]
        if not terms:
            return []
        query = " OR ".join(f'"{t}"' for t in terms)
        sql = "SELECT id, bm25(objects_fts) AS score FROM objects_fts WHERE objects_fts MATCH ?"
        args: list = [query]
        if project_id:
            sql += " AND project_id=?"
            args.append(project_id)
        types = list(types or [])
        if types:
            sql += f" AND type IN ({','.join('?' * len(types))})"
            args.extend(types)
        rows = self.db.execute(sql + " ORDER BY score LIMIT ?", (*args, int(limit))).fetchall()
        return [o for o in (self.get(r["id"]) for r in rows) if o]
