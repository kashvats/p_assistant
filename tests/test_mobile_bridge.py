import json

from living_assistant.connectors.mobile_bridge import MobileBridge
from living_assistant.system.daemon import NervousSystem
from living_assistant.core.memory import MemoryStore


class Registry:
    def __init__(self, connector=None):
        self.connector = connector or {
            'name': 'phone', 'provider': 'telegram', 'enabled': True,
            'capabilities': ['messages.read', 'messages.send'], 'settings': {},
        }
    def get(self, name):
        return self.connector if name == self.connector.get('name') else None


class Manager:
    def __init__(self, updates):
        self.registry = Registry()
        self.updates = list(updates)
        self.sent = []
        self.read_params = []
    def _dispatch(self, connector, action, params):
        assert connector['name'] == 'phone'
        if action == 'messages.updates':
            self.read_params.append(dict(params))
            result = self.updates
            self.updates = []
            return {'ok': True, 'result': result}
        if action == 'messages.send':
            self.sent.append(dict(params))
            return {'ok': True, 'result': {'message_id': len(self.sent)}}
        raise AssertionError(action)


class Orch:
    def __init__(self, answer='ok'):
        self.answer = answer
        self.calls = []
    def run(self, text, context='', session_id=None):
        self.calls.append((text, context, session_id))
        return self.answer


def cfg(**overrides):
    value = {
        'enabled': True,
        'connector': 'phone',
        'allowed_chat_ids': ['42'],
        'allowed_user_ids': ['7'],
        'private_only': True,
        'poll_interval_seconds': 1,
        'max_messages_per_poll': 10,
        'max_messages_per_minute': 10,
        'max_message_chars': 8000,
        'max_response_chars': 3900,
    }
    value.update(overrides)
    return {'mobile_bridge': value}


def message(update_id=10, chat_id=42, user_id=7, text='hello', chat_type='private', is_bot=False):
    return {
        'update_id': update_id,
        'message': {
            'message_id': 1,
            'text': text,
            'chat': {'id': chat_id, 'type': chat_type},
            'from': {'id': user_id, 'is_bot': is_bot},
        },
    }


def test_authorized_message_runs_orchestrator_and_redacts_reply(tmp_path):
    manager = Manager([message()])
    orch = Orch('done sk-live-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')
    state = tmp_path / 'mobile.json'
    bridge = MobileBridge(cfg(), manager, orch, state_path=state)

    events = bridge.poll_once()

    assert orch.calls == [('hello', 'Mobile bridge: authenticated Telegram user.', 'mobile:telegram:42')]
    assert manager.sent and manager.sent[0]['chat_id'] == '42'
    assert 'sk-live-' not in manager.sent[0]['text']
    assert '[REDACTED' in manager.sent[0]['text']
    assert json.loads(state.read_text())['offset'] == 11
    assert any(e['kind'] == 'mobile_bridge_replied' for e in events)


def test_unauthorized_and_bot_messages_never_run_or_reply(tmp_path):
    manager = Manager([
        message(update_id=1, chat_id=99),
        message(update_id=2, is_bot=True),
        message(update_id=3, chat_type='group'),
    ])
    orch = Orch()
    bridge = MobileBridge(cfg(), manager, orch, state_path=tmp_path/'state.json')

    events = bridge.poll_once()

    assert orch.calls == []
    assert manager.sent == []
    reasons = {e.get('reason') for e in events if e['kind'] == 'mobile_bridge_rejected'}
    assert {'chat_not_allowed', 'bot_sender', 'non_private_chat'} <= reasons
    assert json.loads((tmp_path/'state.json').read_text())['offset'] == 4


def test_empty_allowlist_fails_closed(tmp_path):
    manager = Manager([message()])
    orch = Orch()
    bridge = MobileBridge(cfg(allowed_chat_ids=[], allowed_user_ids=[]), manager, orch, state_path=tmp_path/'state.json')
    events = bridge.poll_once()
    assert orch.calls == []
    assert manager.sent == []
    assert any(e.get('reason') == 'allowlist_empty' for e in events)


def test_rate_limit_prevents_extra_model_calls(tmp_path):
    manager = Manager([message(update_id=1, text='one'), message(update_id=2, text='two')])
    orch = Orch()
    bridge = MobileBridge(cfg(max_messages_per_minute=1), manager, orch, state_path=tmp_path/'state.json')
    events = bridge.poll_once()
    assert [x[0] for x in orch.calls] == ['one']
    assert len(manager.sent) == 1
    assert any(e['kind'] == 'mobile_bridge_rate_limited' for e in events)


def test_disabled_bridge_does_not_touch_connector(tmp_path):
    manager = Manager([message()])
    bridge = MobileBridge(cfg(enabled=False), manager, Orch(), state_path=tmp_path/'state.json')
    assert bridge.poll_once() == []
    assert manager.read_params == []


def test_persisted_offset_is_used_after_restart(tmp_path):
    state = tmp_path/'state.json'
    state.write_text('{"offset": 77}')
    manager = Manager([])
    bridge = MobileBridge(cfg(), manager, Orch(), state_path=state)
    bridge.poll_once()
    assert manager.read_params[0]['offset'] == 77


class Processes:
    def list(self): return []

class Watches:
    def poll(self, **kwargs): return []
    def rebaseline(self): return {'refreshed': 0, 'missing': []}

class Note:
    def __init__(self): self.sent=[]
    def flush(self, **kwargs): return {'ok': True}
    def send(self, title, message): self.sent.append((title, message)); return {'ok': True}
    def is_quiet(self): return False

class Bridge:
    def __init__(self): self.calls=0
    def poll_once(self):
        self.calls += 1
        return [{'kind': 'mobile_bridge_error', 'error': 'temporary failure'}]


def test_daemon_polls_mobile_bridge_and_surfaces_error(tmp_path):
    bridge=Bridge(); note=Note()
    ns=NervousSystem(
        {
            'daemon': {'alert_on_new_listening_port': False, 'watch_files': False},
            'routines': {'enabled': False},
            'security_guardian': {'enabled': False},
            'security_sensors': {'enabled': False},
            'connectors': {'enabled': False},
        },
        MemoryStore(tmp_path/'db.sqlite3'), Processes(), Watches(), note, mobile_bridge=bridge,
    )
    ns.power_monitor.observe=lambda:{'resumed':False}
    events=ns.tick()
    assert bridge.calls == 1
    assert any(e['kind']=='mobile_bridge_error' for e in events)
    assert note.sent and 'Mobile bridge error' in note.sent[-1][1]
