"""One conversation system: shared active conversation, sources, titles, stop and regenerate."""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from living_assistant.core.sessions import SessionStore


class Bus:
    def __init__(self):
        self.events = []

    def publish(self, event, **data):
        self.events.append((event, data))


class Orch:
    """Stands in for the orchestrator: records the user turn like the real one, then streams."""

    def __init__(self, sessions, slow=False):
        self.sessions, self.slow, self.calls = sessions, slow, []

    def run_stream(self, message, context="", session_id=None, source="text"):
        self.calls.append((message, source))
        self.sessions.add_message(session_id, "user", message, source=source)
        yield {"type": "status", "status": "generating"}
        for word in ("Hello", " there", " friend"):
            if self.slow:
                time.sleep(0.4)
            yield {"type": "token", "text": word}
        self.sessions.add_message(session_id, "assistant", "Hello there friend")
        yield {"type": "final", "text": "Hello there friend", "session_id": session_id}


@pytest.fixture
def client(tmp_path, monkeypatch):
    import living_assistant.api as api

    sessions = SessionStore(tmp_path / "a.sqlite3")
    rt = SimpleNamespace(sessions=sessions, events_bus=Bus())
    rt.orchestrator = Orch(sessions)
    monkeypatch.setattr(api, "runtime", rt)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "t")
    c = TestClient(api.app, headers={"Authorization": "Bearer t"})
    c.rt = rt
    return c


def _chat(client, **body):
    with client.stream("POST", "/chat/stream", json=body) as r:
        assert r.status_code == 200
        return "".join(r.iter_text())


def test_every_interface_continues_the_same_active_conversation(client):
    active = client.get("/conversations/active").json()["id"]
    _chat(client, message="What is the weather?")                   # dashboard, no session given
    _chat(client, message="And tomorrow?", source="voice")           # floating agent by voice
    convo = client.get(f"/conversations/{active}/messages").json()
    assert [(m["role"], m["source"]) for m in convo["messages"]] == [
        ("user", "text"), ("assistant", "text"), ("user", "voice"), ("assistant", "text")]
    assert convo["title"] == "What is the weather?"                # named after the first request
    listing = client.get("/conversations").json()
    assert listing["active"] == active and listing["conversations"][0]["last_message"]


def test_new_conversation_becomes_active_and_is_announced(client):
    new = client.post("/conversations", json={"title": "Trip plans"}).json()
    assert client.get("/conversations/active").json()["id"] == new["id"]
    assert ("conversation.active", {"session_id": new["id"]}) in client.rt.events_bus.events
    client.patch(f"/conversations/{new['id']}", json={"title": "Japan trip"})
    assert client.get("/conversations").json()["conversations"][0]["title"] == "Japan trip"
    assert client.put("/conversations/active", json={"session_id": "nope"}).status_code == 404


def test_regenerate_replays_the_last_request_without_duplicating_it(client):
    sid = client.post("/conversations", json={}).json()["id"]
    _chat(client, message="Tell me a joke", session_id=sid, source="voice")
    with client.stream("POST", "/chat/regenerate", json={"session_id": sid}) as r:
        body = "".join(r.iter_text())
    assert "final" in body
    msgs = client.get(f"/conversations/{sid}/messages").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]  # replaced, not appended
    assert msgs[0]["source"] == "voice"  # a spoken request stays spoken when regenerated
    assert client.post("/chat/regenerate", json={"session_id": "empty-convo"}).status_code == 404


def test_stop_ends_the_turn_server_side_and_keeps_the_partial_answer(client):
    client.rt.orchestrator.slow = True
    sid = client.post("/conversations", json={}).json()["id"]
    chunks = []

    def consume():
        with client.stream("POST", "/chat/stream", json={"message": "Write an essay", "session_id": sid}) as r:
            for text in r.iter_text():
                chunks.append(text)

    worker = threading.Thread(target=consume)
    worker.start()
    time.sleep(0.6)
    assert client.post("/chat/stop", json={"session_id": sid}).json()["stopped"] is True
    worker.join(timeout=10)
    body = "".join(chunks)
    assert "stopped" in body and '"final"' not in body
    last = client.get(f"/conversations/{sid}/messages").json()["messages"][-1]
    assert last["role"] == "assistant" and last["content"].endswith("[stopped]")


def test_existing_databases_gain_message_sources(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE sessions(id TEXT PRIMARY KEY,title TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);"
                       "CREATE TABLE session_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,session_id TEXT NOT NULL,role TEXT NOT NULL,"
                       "content TEXT NOT NULL,created_at TEXT NOT NULL);"
                       "INSERT INTO sessions VALUES('old','Old chat','2026-01-01','2026-01-01');"
                       "INSERT INTO session_messages(session_id,role,content,created_at) VALUES('old','user','hi','2026-01-01');")
    conn.commit()
    conn.close()
    store = SessionStore(path)
    assert store.recent_messages("old")[0]["source"] == "text"
    store.add_message("old", "user", "spoken", source="voice")
    assert store.recent_messages("old")[-1]["source"] == "voice"
