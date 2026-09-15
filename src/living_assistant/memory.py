from __future__ import annotations
from pathlib import Path
import sqlite3, json, datetime as dt
from .config import data_dir

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
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

class MemoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "assistant.sqlite3")
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def remember(self, content: str, kind: str = "fact", metadata: dict | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO memories(kind, content, metadata, created_at) VALUES(?,?,?,?)",
            (kind, content, json.dumps(metadata or {}), dt.datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def search(self, query: str, limit: int = 8) -> list[dict]:
        try:
            rows = self.conn.execute(
                """SELECT m.* FROM memories_fts f
                   JOIN memories m ON m.id=f.rowid
                   WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT ?""",
                (query, limit)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def add_todo(self, title: str, due_at: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO todos(title, due_at, created_at) VALUES(?,?,?)",
            (title, due_at, dt.datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_todos(self, include_done: bool = False) -> list[dict]:
        q = "SELECT * FROM todos" + ("" if include_done else " WHERE done=0") + " ORDER BY COALESCE(due_at,'9999'), id"
        return [dict(r) for r in self.conn.execute(q).fetchall()]

    def add_event(self, kind: str, payload: dict):
        self.conn.execute(
            "INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)",
            (kind, json.dumps(payload), dt.datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit()
