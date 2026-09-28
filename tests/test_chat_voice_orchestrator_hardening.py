from __future__ import annotations

import json

from living_assistant.core.model_provider import CompositeModelProvider, LiteLLMProvider, to_openai_messages
from living_assistant.core.typesafe import JevClient
from living_assistant.integrations.openmontage import OpenMontageAdapter
from living_assistant.tools.logtools import _analyze


def test_openai_messages_link_tool_results_and_convert_images():
    msgs = to_openai_messages([
        {"role": "user", "content": "look", "images": ["QUJD"]},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "a", "arguments": {"x": 1}}},
            {"id": "given", "function": {"name": "b", "arguments": "{}"}},
        ]},
        {"role": "tool", "tool_name": "a", "content": "{}"},
        {"role": "tool", "tool_name": "b", "tool_call_id": "given", "content": "{}"},
    ])
    assert msgs[0]["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD"
    calls = msgs[1]["tool_calls"]
    assert calls[0]["function"]["arguments"] == json.dumps({"x": 1})
    assert msgs[2]["tool_call_id"] == calls[0]["id"]
    assert msgs[3]["tool_call_id"] == "given"
    assert "tool_name" not in msgs[2]


def test_collibri_alias_routes_through_litellm_only_when_enabled():
    enabled = CompositeModelProvider(litellm_provider=LiteLLMProvider(base_url="http://127.0.0.1:8080/v1"))
    assert isinstance(enabled._route("openai/local-model")[0], LiteLLMProvider)
    disabled = CompositeModelProvider()
    assert not isinstance(disabled._route("openai/local-model")[0], LiteLLMProvider)


def test_jev_mock_lesson_relevance_distinguishes_topics():
    jev = JevClient(api_key="")
    related, _ = jev.is_lesson_relevant({"situation": "python tests failing with import error", "lesson": "set PYTHONPATH before pytest"}, "python tests fail with import error")
    unrelated, _ = jev.is_lesson_relevant({"situation": "calendar reminder", "lesson": "use local timezone"}, "download a youtube video")
    assert related is True
    assert unrelated is False


def test_offline_jev_never_vetoes_or_short_circuits():
    from living_assistant.agents.orchestrator import Orchestrator

    orch = Orchestrator.__new__(Orchestrator)
    orch.jev = JevClient(api_key="")
    assert orch._jev_block_reason("web_search", {"query": "how to reset my password"}) is None


def test_openmontage_inputs_survive_json_booleans(monkeypatch):
    import living_assistant.integrations.openmontage as mod

    captured = {}

    def fake_run(script, timeout):
        captured["script"] = script
        return {"ok": True}

    monkeypatch.setattr(mod, "run_isolated_tool", fake_run)
    OpenMontageAdapter(path=".").execute_tool("x", {"flag": True, "none": None})
    compile(captured["script"], "<generated>", "exec")


def test_log_analysis_groups_repeated_errors_and_tracebacks():
    lines = [
        "INFO boot",
        "ERROR db timeout after 30s id=1",
        "ERROR db timeout after 31s id=2",
        "Traceback (most recent call last):",
        '  File "a.py", line 3, in x',
        "ValueError: bad value 7",
        "WARNING slow",
    ]
    report = _analyze(lines)
    assert report["error_count"] == 3
    assert report["distinct_errors"] == 2
    assert report["warning_count"] == 1
    assert report["top_errors"][0]["count"] == 2
    assert report["tracebacks"] and "ValueError" in report["tracebacks"][0]
