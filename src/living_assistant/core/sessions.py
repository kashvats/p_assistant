from __future__ import annotations
from pathlib import Path
import datetime as dt
import json, sqlite3, uuid, re
from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.security.security_utils import redact_secrets
from living_assistant.core.storage_utils import atomic_write_json

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
CREATE VIRTUAL TABLE IF NOT EXISTS session_messages_fts USING fts5(
  content, content='session_messages', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS session_messages_ai AFTER INSERT ON session_messages BEGIN
  INSERT INTO session_messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS session_messages_ad AFTER DELETE ON session_messages BEGIN
  INSERT INTO session_messages_fts(session_messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS session_messages_au AFTER UPDATE ON session_messages BEGIN
  INSERT INTO session_messages_fts(session_messages_fts, rowid, content) VALUES('delete', old.id, old.content);
  INSERT INTO session_messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TABLE IF NOT EXISTS living_assistant_migrations(
  name TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ui_state(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""
# Columns added after the first release; applied once to older databases.
MESSAGE_COLUMNS = {'source': "TEXT NOT NULL DEFAULT 'text'", 'meta': "TEXT NOT NULL DEFAULT '{}'"}
MESSAGE_SOURCES = {'text', 'voice', 'agent', 'system', 'goal'}

def _title_from(text: str) -> str:
    title=re.sub(r'\s+',' ',str(text or '')).strip()
    return (title[:57]+'...') if len(title)>60 else (title or 'New conversation')


def _message(row) -> dict:
    item=dict(row)
    try:
        item['meta']=json.loads(item.get('meta') or '{}')
    except ValueError:
        item['meta']={}
    item.setdefault('source','text')
    return item


class SessionStore:
    def __init__(self, path: Path | None = None, retention_days: int = 30, redact_secrets: bool = True):
        self.path=path or (data_dir()/'assistant.sqlite3')
        self.archive_dir=self.path.parent/'session_archives'
        self.retention_days=max(1,int(retention_days))
        self.redact_secrets=bool(redact_secrets)
        self.conn=ThreadLocalSQLite(self.path)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(SCHEMA)
        # FTS triggers only index rows written after they exist. Rebuild exactly once
        # for databases created by older releases so historical messages are searchable
        # without paying an O(n) rebuild on every process start.
        migration = 'sessions_fts_v1'
        if not self.conn.execute('SELECT 1 FROM living_assistant_migrations WHERE name=?', (migration,)).fetchone():
            self.conn.execute("INSERT INTO session_messages_fts(session_messages_fts) VALUES('rebuild')")
            self.conn.execute(
                'INSERT INTO living_assistant_migrations(name,applied_at) VALUES(?,?)',
                (migration, dt.datetime.now().isoformat(timespec='seconds')),
            )
        existing = {r['name'] for r in self.conn.execute('PRAGMA table_info(session_messages)').fetchall()}
        for column, ddl in MESSAGE_COLUMNS.items():
            if column not in existing:
                self.conn.execute(f'ALTER TABLE session_messages ADD COLUMN {column} {ddl}')
        self.conn.commit()

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

    def add_message(self,session_id: str,role: str,content: str,source: str='text',meta: dict | None=None) -> int:
        if role not in {'user','assistant','system','tool'}: raise ValueError('Unsupported message role.')
        source=source if source in MESSAGE_SOURCES else 'text'
        self.ensure(session_id)
        if self.redact_secrets: content=self._redact(content)
        now=dt.datetime.now().isoformat(timespec='seconds')
        try:
            cur=self.conn.execute('INSERT INTO session_messages(session_id,role,content,created_at,source,meta) VALUES(?,?,?,?,?,?)',
                                  (session_id,role,content,now,source,json.dumps(meta or {})))
            self.conn.execute('UPDATE sessions SET updated_at=? WHERE id=?',(now,session_id))
            if role=='user':
                # A conversation is named after its first request until the user renames it.
                self.conn.execute("UPDATE sessions SET title=? WHERE id=? AND (title IS NULL OR title='')",(_title_from(content),session_id))
            self.conn.commit()
            return int(cur.lastrowid)
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise

    def merge_last_meta(self,session_id: str,role: str,patch: dict) -> int | None:
        """Merge ``patch`` into the meta of the latest message with this role (e.g. files shown with a reply)."""
        row=self.conn.execute('SELECT id,meta FROM session_messages WHERE session_id=? AND role=? ORDER BY id DESC LIMIT 1',
                              (session_id,role)).fetchone()
        if row is None: return None
        try:
            meta=json.loads(row['meta'] or '{}')
        except ValueError:
            meta={}
        meta.update(patch)
        self.conn.execute('UPDATE session_messages SET meta=? WHERE id=?',(json.dumps(meta),row['id'])); self.conn.commit()
        return int(row['id'])

    def recent_messages(self,session_id: str,limit: int=12) -> list[dict]:
        rows=self.conn.execute('SELECT * FROM session_messages WHERE session_id=? ORDER BY id DESC LIMIT ?',(session_id,max(1,min(int(limit),100)))).fetchall()
        return [_message(r) for r in reversed(rows)]

    def messages(self,session_id: str,after_id: int=0,limit: int=500) -> list[dict]:
        rows=self.conn.execute('SELECT * FROM session_messages WHERE session_id=? AND id>? ORDER BY id LIMIT ?',
                               (session_id,int(after_id),max(1,min(int(limit),2000)))).fetchall()
        return [_message(r) for r in rows]

    def list(self,limit: int=100) -> list[dict]:
        rows=self.conn.execute('''SELECT s.*,COUNT(m.id) AS message_count,
                                         (SELECT content FROM session_messages x WHERE x.session_id=s.id ORDER BY x.id DESC LIMIT 1) AS last_message
                                  FROM sessions s LEFT JOIN session_messages m ON m.session_id=s.id
                                  GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?''',(max(1,min(int(limit),500)),)).fetchall()
        out=[]
        for r in rows:
            item=dict(r)
            item['last_message']=(item.get('last_message') or '')[:160]
            out.append(item)
        return out

    def rename(self,session_id: str,title: str) -> dict | None:
        title=re.sub(r'\s+',' ',str(title or '')).strip()[:120]
        if not title or not self.get(session_id): return self.get(session_id)
        self.conn.execute('UPDATE sessions SET title=? WHERE id=?',(title,session_id)); self.conn.commit()
        return self.get(session_id)

    def pop_last_turn(self,session_id: str) -> dict | None:
        """Remove the last user message and everything after it; return that message (for regenerate)."""
        row=self.conn.execute("SELECT * FROM session_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",(session_id,)).fetchone()
        if row is None: return None
        self.conn.execute('DELETE FROM session_messages WHERE session_id=? AND id>=?',(session_id,row['id'])); self.conn.commit()
        return _message(row)

    # The conversation every interface (dashboard, floating agent, voice) continues by default.
    def active(self) -> dict:
        row=self.conn.execute("SELECT value FROM ui_state WHERE key='active_session'").fetchone()
        current=self.get(row['value']) if row else None
        return current or self.set_active(self.create()['id'])

    def set_active(self,session_id: str) -> dict:
        session=self.ensure(session_id)
        self.conn.execute("INSERT INTO ui_state(key,value) VALUES('active_session',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(session_id,))
        self.conn.commit()
        return session

    def search(self,query: str,limit: int=50) -> list[dict]:
        query=(query or '').strip()
        if not query:
            return []
        bounded_limit=max(1,min(int(limit),200))
        # Quote the entire user string as an FTS phrase. Doubling quotes prevents
        # user input from becoming FTS query syntax while still using the index.
        fts_query='"'+query.replace('"','""')+'"'
        rows=self.conn.execute(
            '''SELECT m.id,m.session_id,m.role,m.content,m.created_at,s.title
               FROM session_messages_fts f
               JOIN session_messages m ON m.id=f.rowid
               JOIN sessions s ON s.id=m.session_id
               WHERE session_messages_fts MATCH ?
               ORDER BY m.id DESC LIMIT ?''',
            (fts_query,bounded_limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self,session_id: str) -> bool:
        cur=self.conn.execute('DELETE FROM sessions WHERE id=?',(session_id,)); self.conn.commit(); return cur.rowcount>0

    def prune(self,now: dt.datetime | None=None) -> int:
        now=now or dt.datetime.now(); cutoff=(now-dt.timedelta(days=self.retention_days)).isoformat(timespec='seconds')
        rows=self.conn.execute('SELECT * FROM sessions WHERE updated_at<? ORDER BY updated_at,id',(cutoff,)).fetchall()
        if not rows: return 0

        archived=[]
        for row in rows:
            session=dict(row)
            messages=[dict(item) for item in self.conn.execute(
                'SELECT id,session_id,role,content,created_at FROM session_messages WHERE session_id=? ORDER BY id',
                (session['id'],),
            ).fetchall()]
            archived.append({**session,'messages':messages})

        # Archive is written atomically before destructive retention cleanup. If
        # this write fails, the exception propagates and no session rows are
        # deleted, preferring retained history over silent data loss.
        stamp=now.strftime('%Y%m%dT%H%M%S')
        archive_path=self.archive_dir/f'sessions-{stamp}-{uuid.uuid4().hex[:8]}.json'
        atomic_write_json(archive_path,{
            'version':1,
            'archived_at':now.isoformat(timespec='seconds'),
            'retention_days':self.retention_days,
            'session_count':len(archived),
            'sessions':archived,
        },mode=0o600)

        ids=[item['id'] for item in archived]
        self.conn.executemany('DELETE FROM sessions WHERE id=?',[(x,) for x in ids]); self.conn.commit(); return len(ids)
