from __future__ import annotations
from pathlib import Path
import datetime as dt
import sqlite3, uuid, re
from .config import data_dir
from .sqlite_utils import ThreadLocalSQLite
from .security_utils import redact_secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY,
  title TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS session_messages_session ON session_messages(session_id,id);
"""

class SessionStore:
    def __init__(self, path: Path | None = None, retention_days: int = 30, redact_secrets: bool = True):
        self.path=path or (data_dir()/'assistant.sqlite3')
        self.retention_days=max(1,int(retention_days))
        self.redact_secrets=bool(redact_secrets)
        self.conn=ThreadLocalSQLite(self.path)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(SCHEMA); self.conn.commit()

    def create(self,title: str | None=None, session_id: str | None=None) -> dict:
        sid=session_id or uuid.uuid4().hex[:12]
        now=dt.datetime.now().isoformat(timespec='seconds')
        self.conn.execute('INSERT OR IGNORE INTO sessions(id,title,created_at,updated_at) VALUES(?,?,?,?)',(sid,title,now,now))
        if title: self.conn.execute('UPDATE sessions SET title=?,updated_at=? WHERE id=?',(title,now,sid))
        self.conn.commit(); return self.get(sid)

    def ensure(self,session_id: str,title: str | None=None) -> dict:
        return self.get(session_id) or self.create(title,session_id)

    def get(self,session_id: str) -> dict | None:
        row=self.conn.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone(); return dict(row) if row else None

    @staticmethod
    def _redact(content: str) -> str:
        return redact_secrets(content)

    def add_message(self,session_id: str,role: str,content: str) -> int:
        if role not in {'user','assistant','system','tool'}: raise ValueError('Unsupported message role.')
        self.ensure(session_id)
        if self.redact_secrets: content=self._redact(content)
        now=dt.datetime.now().isoformat(timespec='seconds')
        cur=self.conn.execute('INSERT INTO session_messages(session_id,role,content,created_at) VALUES(?,?,?,?)',(session_id,role,content,now))
        self.conn.execute('UPDATE sessions SET updated_at=? WHERE id=?',(now,session_id)); self.conn.commit(); return int(cur.lastrowid)

    def recent_messages(self,session_id: str,limit: int=12) -> list[dict]:
        rows=self.conn.execute('SELECT * FROM session_messages WHERE session_id=? ORDER BY id DESC LIMIT ?',(session_id,max(1,min(int(limit),100)))).fetchall()
        return [dict(r) for r in reversed(rows)]

    def list(self,limit: int=100) -> list[dict]:
        rows=self.conn.execute('''SELECT s.*,COUNT(m.id) AS message_count FROM sessions s LEFT JOIN session_messages m ON m.session_id=s.id GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?''',(max(1,min(int(limit),500)),)).fetchall()
        return [dict(r) for r in rows]

    def search(self,query: str,limit: int=50) -> list[dict]:
        rows=self.conn.execute('''SELECT m.id,m.session_id,m.role,m.content,m.created_at,s.title FROM session_messages m JOIN sessions s ON s.id=m.session_id WHERE m.content LIKE ? ORDER BY m.id DESC LIMIT ?''',(f'%{query}%',max(1,min(int(limit),200)))).fetchall()
        return [dict(r) for r in rows]

    def delete(self,session_id: str) -> bool:
        cur=self.conn.execute('DELETE FROM sessions WHERE id=?',(session_id,)); self.conn.commit(); return cur.rowcount>0

    def prune(self,now: dt.datetime | None=None) -> int:
        now=now or dt.datetime.now(); cutoff=(now-dt.timedelta(days=self.retention_days)).isoformat(timespec='seconds')
        ids=[r['id'] for r in self.conn.execute('SELECT id FROM sessions WHERE updated_at<?',(cutoff,)).fetchall()]
        if not ids: return 0
        self.conn.executemany('DELETE FROM sessions WHERE id=?',[(x,) for x in ids]); self.conn.commit(); return len(ids)
