from __future__ import annotations
from pathlib import Path
import datetime as dt
import sqlite3, uuid
from .config import data_dir
from .sqlite_utils import ThreadLocalSQLite

SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_events(
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  start_at TEXT NOT NULL,
  end_at TEXT,
  location TEXT,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'scheduled',
  source TEXT NOT NULL DEFAULT 'local',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS calendar_events_start ON calendar_events(start_at);
"""

class CalendarStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'assistant.sqlite3')
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA); self.conn.commit()

    @staticmethod
    def _validate_iso(value: str) -> str:
        try:
            return dt.datetime.fromisoformat(value).isoformat(timespec='seconds')
        except Exception as exc:
            raise ValueError('Date/time must be ISO format, e.g. 2026-09-15T14:30:00') from exc

    def add(self, title: str, start_at: str, end_at: str | None = None,
            location: str | None = None, notes: str | None = None, source: str = 'local') -> dict:
        start = self._validate_iso(start_at)
        end = self._validate_iso(end_at) if end_at else None
        if end and dt.datetime.fromisoformat(end) < dt.datetime.fromisoformat(start):
            raise ValueError('end_at cannot be before start_at.')
        event_id = uuid.uuid4().hex[:12]
        now = dt.datetime.now().isoformat(timespec='seconds')
        self.conn.execute(
            "INSERT INTO calendar_events(id,title,start_at,end_at,location,notes,source,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (event_id,title,start,end,location,notes,source,now),
        ); self.conn.commit()
        return self.get(event_id)

    def get(self, event_id: str) -> dict | None:
        row = self.conn.execute('SELECT * FROM calendar_events WHERE id=?',(event_id,)).fetchone()
        return dict(row) if row else None

    def list(self, start: str | None = None, end: str | None = None, include_cancelled: bool = False,
             limit: int = 200) -> list[dict]:
        clauses=[]; args=[]
        if start: clauses.append('start_at>=?'); args.append(self._validate_iso(start))
        if end: clauses.append('start_at<?'); args.append(self._validate_iso(end))
        if not include_cancelled: clauses.append("status!='cancelled'")
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        args.append(max(1,min(int(limit),1000)))
        rows=self.conn.execute(f'SELECT * FROM calendar_events{where} ORDER BY start_at LIMIT ?',args).fetchall()
        return [dict(r) for r in rows]

    def upcoming(self, now: dt.datetime | None = None, hours: int = 24, limit: int = 50) -> list[dict]:
        now = now or dt.datetime.now()
        end = now + dt.timedelta(hours=max(1,min(int(hours),24*30)))
        return self.list(now.isoformat(timespec='seconds'), end.isoformat(timespec='seconds'), limit=limit)

    def cancel(self, event_id: str) -> bool:
        cur=self.conn.execute("UPDATE calendar_events SET status='cancelled' WHERE id=?",(event_id,)); self.conn.commit(); return cur.rowcount>0

    def delete(self, event_id: str) -> bool:
        cur=self.conn.execute('DELETE FROM calendar_events WHERE id=?',(event_id,)); self.conn.commit(); return cur.rowcount>0

    def export_ics(self, destination: Path, events: list[dict] | None = None) -> str:
        events = events if events is not None else self.list(include_cancelled=False, limit=1000)
        def esc(s): return str(s or '').replace('\\','\\\\').replace('\n','\\n').replace(',','\\,').replace(';','\\;')
        def ics_dt(value):
            d=dt.datetime.fromisoformat(value)
            if d.tzinfo:
                d=d.astimezone(dt.timezone.utc).replace(tzinfo=None)
                return d.strftime('%Y%m%dT%H%M%SZ')
            return d.strftime('%Y%m%dT%H%M%S')
        lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Living Assistant//Local Calendar//EN']
        for e in events:
            lines += ['BEGIN:VEVENT',f"UID:{esc(e['id'])}@living-assistant",f"DTSTART:{ics_dt(e['start_at'])}"]
            if e.get('end_at'): lines.append(f"DTEND:{ics_dt(e['end_at'])}")
            lines.append(f"SUMMARY:{esc(e['title'])}")
            if e.get('location'): lines.append(f"LOCATION:{esc(e['location'])}")
            if e.get('notes'): lines.append(f"DESCRIPTION:{esc(e['notes'])}")
            lines.append('END:VEVENT')
        lines.append('END:VCALENDAR')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text('\r\n'.join(lines)+'\r\n',encoding='utf-8')
        return str(destination)
