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
    assert 'steps available for one request' in answer and 'continue as a goal' in answer
    assert provider.calls == 3


def test_compact_context_clamps_huge_messages_even_when_message_count_is_small():
    # 4 messages total: system, user, assistant, huge tool output
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Analyze the codebase."},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file"}}]},
        {"role": "tool", "content": "X" * 60000},
    ]
    # For context_tokens = 4096: threshold is ~3072 tokens ≈ 10,752 chars.
    compacted = Orchestrator.compact_context(messages, max_tokens=4096)
    total_chars = sum(len(str(m.get("content") or "")) for m in compacted)
    # The huge tool output must have been clamped
    assert total_chars < 15000
    assert "... [content truncated to fit context budget]" in compacted[-1]["content"]
    assert compacted[0]["role"] == "system"
    assert compacted[1]["content"] == "Analyze the codebase."


def test_emergency_compact_strictly_clamps_tail_content():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Old request"},
        {"role": "assistant", "content": "Old response"},
        {"role": "user", "content": "Latest query"},
        {"role": "tool", "content": "A" * 70000},
    ]
    compacted = Orchestrator._emergency_compact(messages, max_tokens=16384)
    # Must preserve system prompt + notice + 2 clamped tail messages
    assert len(compacted) == 4
    assert compacted[0]["role"] == "system"
    assert "dropped because the request exceeded" in compacted[1]["content"]
    # Tail messages must be strictly clamped
    last_msg = compacted[-1]
    assert len(last_msg["content"]) <= 9000
    assert "... [truncated due to context limit]" in last_msg["content"]


def test_tool_result_respects_context_proportional_budget():
    orch = Orchestrator(
        MM(SequenceProvider(1)), 'fake',
        [Tool('noop','No-op tool',{'type':'object','properties':{}},noop)],
        Specialists(), context_tokens=16384,
    )
    limit = orch._tool_result_char_limit()
    # For 16384 tokens, limit should be around 14336 chars (25% of context chars)
    assert 10000 <= limit <= 16000
    huge_data = {"data": "Z" * 80000}
    serialized = orch._serialized_tool_result(huge_data, max_chars=limit)
    assert len(serialized) <= limit + 200
    assert "... [tool result truncated:" in serialized

