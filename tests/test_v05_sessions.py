import datetime as dt
from living_assistant.sessions import SessionStore


def test_session_history_search_and_delete(tmp_path):
    s=SessionStore(tmp_path/'s.sqlite3',retention_days=30)
    sid=s.create('RetailEye debug')['id']
    s.add_message(sid,'user','why is port 8000 down')
    s.add_message(sid,'assistant','check FastAPI logs')
    assert [x['role'] for x in s.recent_messages(sid,10)]==['user','assistant']
    assert s.search('FastAPI')[0]['session_id']==sid
    assert s.list()[0]['message_count']==2
    assert s.delete(sid) is True


def test_session_prune(tmp_path):
    import json
    s=SessionStore(tmp_path/'s.sqlite3',retention_days=1)
    sid=s.create('old')['id']
    s.add_message(sid,'user','archived conversation')
    s.conn.execute("UPDATE sessions SET updated_at='2026-01-01T00:00:00' WHERE id=?",(sid,)); s.conn.commit()
    assert s.prune(dt.datetime(2026,1,3,0,0))==1
    assert s.get(sid) is None
    archives=list((tmp_path/'session_archives').glob('sessions-*.json'))
    assert len(archives)==1
    payload=json.loads(archives[0].read_text())
    assert payload['session_count']==1
    assert payload['sessions'][0]['id']==sid
    assert payload['sessions'][0]['messages'][0]['content']=='archived conversation'

def test_session_redacts_common_secrets(tmp_path):
    s=SessionStore(tmp_path/'s2.sqlite3')
    sid=s.create('secret')['id']
    s.add_message(sid,'user','password=hunter2 Authorization: Bearer abc.def token=xyz')
    text=s.recent_messages(sid,1)[0]['content']
    assert 'hunter2' not in text and 'abc.def' not in text and 'token=[REDACTED]' in text


def test_session_search_rebuilds_fts_for_existing_database(tmp_path):
    import sqlite3

    path = tmp_path / 'legacy.sqlite3'
    conn = sqlite3.connect(path)
    conn.executescript('''
      CREATE TABLE sessions(id TEXT PRIMARY KEY,title TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
      CREATE TABLE session_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
      );
      INSERT INTO sessions VALUES('legacy','Legacy','2026-01-01T00:00:00','2026-01-01T00:00:00');
      INSERT INTO session_messages(session_id,role,content,created_at)
      VALUES('legacy','user','historical searchable phrase','2026-01-01T00:00:00');
    ''')
    conn.commit(); conn.close()

    store = SessionStore(path)
    rows = store.search('historical searchable phrase')
    assert rows and rows[0]['session_id'] == 'legacy'
    assert store.conn.execute("SELECT 1 FROM living_assistant_migrations WHERE name='sessions_fts_v1'").fetchone()


def test_session_prune_does_not_delete_when_archive_write_fails(tmp_path, monkeypatch):
    import living_assistant.sessions as sessions_module

    store=SessionStore(tmp_path/'s.sqlite3',retention_days=1)
    sid=store.create('old')['id']
    store.conn.execute("UPDATE sessions SET updated_at='2026-01-01T00:00:00' WHERE id=?",(sid,)); store.conn.commit()
    monkeypatch.setattr(sessions_module,'atomic_write_json',lambda *a,**k: (_ for _ in ()).throw(OSError('disk full')))

    import pytest
    with pytest.raises(OSError):
        store.prune(dt.datetime(2026,1,3,0,0))
    assert store.get(sid) is not None
