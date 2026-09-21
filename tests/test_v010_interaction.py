from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from living_assistant.event_bus import EventBus
from living_assistant.model_provider import ModelManager
from living_assistant.orchestrator import Orchestrator
from living_assistant.tools.base import Tool


class FakeProvider:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.calls = 0
        self.unloaded = []

    def chat_stream(self, model, messages, tools=None, keep_alive=45, options=None):
        chunks = self.chunks[self.calls]
        self.calls += 1
        yield from chunks

    def unload(self, model):
        self.unloaded.append(model)


class NoPressure:
    def can_start_model(self):
        return True, 'ok'


class DummySpecialists:
    def delegate(self, role, task, context=''):
        return {'ok': True, 'role': role}


def _orchestrator(provider, tools=None, bus=None):
    mm = ModelManager(provider)
    return Orchestrator(
        mm,
        'fake:1b',
        tools or [],
        DummySpecialists(),
        resource_manager=NoPressure(),
        event_bus=bus,
        max_steps=4,
    )


def test_event_bus_records_ordered_activity():
    bus = EventBus(max_events=50)
    a = bus.publish('chat.started', session_id='a')
    b = bus.publish('tool.started', tool='pwd')
    assert b['id'] == a['id'] + 1
    assert [x['type'] for x in bus.recent(10)] == ['chat.started', 'tool.started']
    assert bus.recent(10, after_id=a['id'])[0]['type'] == 'tool.started'


def test_orchestrator_streams_tokens_and_final_without_bypassing_normal_context():
    bus = EventBus()
    provider = FakeProvider([[{'message': {'content': 'Hel'}}, {'message': {'content': 'lo'}, 'done': True}]])
    orch = _orchestrator(provider, bus=bus)
    events = list(orch.run_stream('say hello'))
    assert ''.join(x['text'] for x in events if x['type'] == 'token') == 'Hello'
    assert [x for x in events if x['type'] == 'final'][0]['text'] == 'Hello'
    kinds = [x['type'] for x in bus.recent(20)]
    assert 'chat.started' in kinds and 'model.generating' in kinds and 'chat.completed' in kinds


def test_streaming_tool_call_runs_through_registered_tool_then_continues():
    bus = EventBus()
    provider = FakeProvider([
        [{'message': {'content': '', 'tool_calls': [{'function': {'name': 'echo', 'arguments': {'value': 'x'}}}]}, 'done': True}],
        [{'message': {'content': 'done'}, 'done': True}],
    ])
    calls = []
    tool = Tool('echo', 'echo', {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value']}, lambda value: calls.append(value) or {'ok': True, 'value': value})
    orch = _orchestrator(provider, [tool], bus)
    events = list(orch.run_stream('use echo'))
    assert calls == ['x']
    assert any(x['type'] == 'tool' and x['status'] == 'started' for x in events)
    assert any(x['type'] == 'tool' and x['status'] == 'completed' for x in events)
    assert events[-1]['type'] == 'final' and events[-1]['text'] == 'done'


def test_streaming_error_redacts_secret_like_values():
    class Broken(FakeProvider):
        def chat_stream(self, *args, **kwargs):
            raise RuntimeError('Authorization: Bearer secret-token')
            yield
    orch = _orchestrator(Broken([]), bus=EventBus())
    events = list(orch.run_stream('x'))
    err = [x for x in events if x['type'] == 'error'][0]['error']
    assert 'secret-token' not in err
    assert 'REDACTED' in err


def test_dashboard_is_bundled_and_no_longer_disabled_by_api_token(monkeypatch):
    import living_assistant.api as api
    monkeypatch.setenv('ASSISTANT_API_TOKEN', 'abc')
    client = TestClient(api.app)
    r = client.get('/dashboard')
    assert r.status_code == 200
    assert 'Living Assistant' in r.text
    assert 'chat/stream' in r.text
    assert 'Resource history' in r.text
    assert 'API token' in r.text
    assert 'Content-Security-Policy' in r.headers


def test_chat_stream_api_emits_sse(monkeypatch):
    import living_assistant.api as api

    class Sessions:
        def ensure(self, sid):
            return {'id': sid}

    class Orch:
        def run_stream(self, message, context='', session_id=None):
            yield {'type': 'status', 'status': 'generating'}
            yield {'type': 'token', 'text': 'Hi'}
            yield {'type': 'final', 'text': 'Hi', 'session_id': session_id}

    fake = SimpleNamespace(sessions=Sessions(), orchestrator=Orch())
    monkeypatch.setattr(api, 'runtime', fake)
    monkeypatch.delenv('ASSISTANT_API_TOKEN', raising=False)
    monkeypatch.setenv('ASSISTANT_API_TOKEN', 'test-token')
    client = TestClient(api.app, headers={'Authorization':'Bearer test-token'})
    with client.stream('POST', '/chat/stream', json={'message': 'hello', 'session_id': 's1'}) as r:
        body = ''.join(r.iter_text())
    assert r.status_code == 200
    assert 'text/event-stream' in r.headers['content-type']
    assert 'event: token' in body
    assert '"text":"Hi"' in body
    assert 'event: final' in body


def test_activity_endpoint_is_authenticated_like_other_local_data(monkeypatch):
    import living_assistant.api as api
    bus = EventBus(); bus.publish('test.event', value=1)
    fake = SimpleNamespace(events_bus=bus)
    monkeypatch.setattr(api, 'runtime', fake)
    monkeypatch.setenv('ASSISTANT_API_TOKEN', 'secret')
    client = TestClient(api.app)
    assert client.get('/activity').status_code == 401
    ok = client.get('/activity', headers={'Authorization': 'Bearer secret'})
    assert ok.status_code == 200
    assert ok.json()[0]['type'] == 'test.event'


def test_event_bus_persists_recent_activity_across_restart(tmp_path):
    path = tmp_path / 'activity.sqlite3'
    first = EventBus(max_events=50, path=path)
    a = first.publish('chat.started', session_id='abc')
    b = first.publish('tool.completed', tool='pwd')

    restarted = EventBus(max_events=50, path=path)
    rows = restarted.recent(10)
    assert [row['type'] for row in rows] == ['chat.started', 'tool.completed']
    assert rows[0]['id'] == a['id'] and rows[1]['id'] == b['id']
    c = restarted.publish('chat.completed', session_id='abc')
    assert c['id'] > b['id']
