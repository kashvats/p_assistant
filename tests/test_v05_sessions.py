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
    s=SessionStore(tmp_path/'s.sqlite3',retention_days=1)
    sid=s.create('old')['id']
    s.conn.execute("UPDATE sessions SET updated_at='2026-01-01T00:00:00' WHERE id=?",(sid,)); s.conn.commit()
    assert s.prune(dt.datetime(2026,1,3,0,0))==1

def test_session_redacts_common_secrets(tmp_path):
    s=SessionStore(tmp_path/'s2.sqlite3')
    sid=s.create('secret')['id']
    s.add_message(sid,'user','password=hunter2 Authorization: Bearer abc.def token=xyz')
    text=s.recent_messages(sid,1)[0]['content']
    assert 'hunter2' not in text and 'abc.def' not in text and 'token=[REDACTED]' in text
