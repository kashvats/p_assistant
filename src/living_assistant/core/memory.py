from __future__ import annotations
from pathlib import Path
import sqlite3, json, datetime as dt
from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.security.security_utils import redact_secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, content='memories', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
  INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TABLE IF NOT EXISTS todos(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  due_at TEXT,
  done INTEGER NOT NULL DEFAULT 0,
  notified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS living_assistant_migrations(
  name TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);
"""

class MemoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        migration = 'memories_fts_v1'
        if not self.conn.execute('SELECT 1 FROM living_assistant_migrations WHERE name=?', (migration,)).fetchone():
            self.conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
            self.conn.execute(
                'INSERT INTO living_assistant_migrations(name,applied_at) VALUES(?,?)',
                (migration, dt.datetime.now().isoformat(timespec='seconds')),
            )
        self.conn.commit()

    def _migrate(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(todos)").fetchall()}
        if "notified" not in cols:
            self.conn.execute("ALTER TABLE todos ADD COLUMN notified INTEGER NOT NULL DEFAULT 0")

    def remember(self, content: str, kind: str = "fact", metadata: dict | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO memories(kind, content, metadata, created_at) VALUES(?,?,?,?)",
            (kind, redact_secrets(content, 12000), json.dumps(metadata or {}), dt.datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit(); return int(cur.lastrowid)

    def search(self, query: str, limit: int = 8) -> list[dict]:
        query = (query or '').strip()
        if not query:
            return []
        bounded_limit = max(1, min(int(limit), 200))
        fts_query = '"' + query.replace('"', '""') + '"'
        rows = self.conn.execute(
            """SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.rowid
               WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT ?""",
            (fts_query, bounded_limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_todo(self, title: str, due_at: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO todos(title, due_at, created_at) VALUES(?,?,?)",
            (redact_secrets(title, 2000), due_at, dt.datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit(); return int(cur.lastrowid)

    def list_todos(self, include_done: bool = False) -> list[dict]:
        q = "SELECT * FROM todos" + ("" if include_done else " WHERE done=0") + " ORDER BY COALESCE(due_at,'9999'), id"
        return [dict(r) for r in self.conn.execute(q).fetchall()]

    def due_todos(self, now: dt.datetime | None = None) -> list[dict]:
        now = now or dt.datetime.now()
        rows = self.conn.execute(
            "SELECT * FROM todos WHERE done=0 AND notified=0 AND due_at IS NOT NULL AND due_at<=? ORDER BY due_at",
            (now.isoformat(timespec="seconds"),)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_todo_notified(self, todo_id: int):
        self.conn.execute("UPDATE todos SET notified=1 WHERE id=?", (todo_id,)); self.conn.commit()

    def complete_todo(self, todo_id: int) -> bool:
        cur = self.conn.execute("UPDATE todos SET done=1 WHERE id=?", (todo_id,)); self.conn.commit(); return cur.rowcount > 0

    def add_event(self, kind: str, payload: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)",
            (kind, json.dumps(payload), dt.datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit(); return int(cur.lastrowid)

    def list_events(self, limit: int = 100, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self.conn.execute("SELECT * FROM events WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, limit)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try: d["payload"] = json.loads(d["payload"])
            except Exception: pass
            out.append(d)
        return out
