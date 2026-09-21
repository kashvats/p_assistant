from contextlib import nullcontext

from living_assistant.orchestrator import Orchestrator
from living_assistant.sessions import SessionStore


class Provider:
    def chat(self, *a, **k): return {'message': {'role':'assistant','content':'ok'}}


class MM:
    provider = Provider()
    def lease(self, model, priority=0): return nullcontext(0)
    def sleep(self): pass


class Specialists:
    def delegate(self, *a, **k): return {'ok':True}


def test_session_context_keeps_more_than_twelve_short_messages(tmp_path):
    store=SessionStore(tmp_path/'s.sqlite3')
    sid='long-chat'; store.ensure(sid)
    for i in range(20):
        store.add_message(sid,'user' if i%2==0 else 'assistant',f'message-{i}')
    orch=Orchestrator(MM(),'fake',[],Specialists(),context_tokens=8192,session_store=store,max_session_messages=24)
    ctx=orch._session_context(sid)
    assert 'message-0' in ctx and 'message-19' in ctx
    assert ctx.count('message-') == 20


def test_session_context_budget_prioritizes_newest_history(tmp_path):
    store=SessionStore(tmp_path/'s.sqlite3')
    sid='bounded-chat'; store.ensure(sid)
    for i in range(30):
        store.add_message(sid,'user',f'message-{i}-' + ('x'*3500))
    orch=Orchestrator(MM(),'fake',[],Specialists(),context_tokens=4096,session_store=store,max_session_messages=30)
    ctx=orch._session_context(sid)
    assert 'message-29-' in ctx
    assert 'message-0-' not in ctx
    assert len(ctx) <= int(4096*4*0.45) + 200
