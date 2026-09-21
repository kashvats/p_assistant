from contextlib import nullcontext

from living_assistant.orchestrator import Orchestrator
from living_assistant.tools.base import Tool


class SequenceProvider:
    def __init__(self, tool_steps: int, final_text: str = 'done'):
        self.tool_steps = tool_steps
        self.final_text = final_text
        self.calls = 0

    def chat(self, model, messages, tools=None, keep_alive=None, options=None):
        self.calls += 1
        if self.calls <= self.tool_steps:
            return {
                'message': {
                    'role': 'assistant',
                    'content': '',
                    'tool_calls': [{'function': {'name': 'noop', 'arguments': {}}}],
                }
            }
        return {'message': {'role': 'assistant', 'content': self.final_text}}


class MM:
    def __init__(self, provider): self.provider = provider
    def lease(self, model, priority=0): return nullcontext(0)
    def sleep(self): pass


class Specialists:
    def delegate(self, role, task, context=''): return {'ok':True}


def noop():
    return {'ok': True}


def test_configured_tool_step_limit_can_exceed_ten():
    provider = SequenceProvider(tool_steps=11, final_text='completed after eleven tools')
    orch = Orchestrator(
        MM(provider), 'fake',
        [Tool('noop','No-op tool',{'type':'object','properties':{}},noop)],
        Specialists(), max_steps=12,
    )
    answer = orch.run('do a long task')
    assert answer == 'completed after eleven tools'
    assert provider.calls == 12


def test_tool_step_limit_returns_explicit_user_message():
    provider = SequenceProvider(tool_steps=50)
    orch = Orchestrator(
        MM(provider), 'fake',
        [Tool('noop','No-op tool',{'type':'object','properties':{}},noop)],
        Specialists(), max_steps=3,
    )
    answer = orch.run('do an unbounded task')
    assert 'configured tool-step limit' in answer
    assert 'retry with a narrower goal' in answer
    assert provider.calls == 3
