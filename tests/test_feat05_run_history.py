from __future__ import annotations

import datetime as dt

from living_assistant.agents.orchestrator import Orchestrator
from living_assistant.learning.run_history import RunHistoryStore
from living_assistant.model_provider import ModelManager
from living_assistant.tools.base import Tool
from living_assistant.tools.historytools import build_run_history_tools


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def chat(self, model, messages, tools=None, keep_alive=45, options=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "echo", "arguments": {"value": "hello"}}}
                    ],
                }
            }
        return {"message": {"role": "assistant", "content": "done"}}

    def unload(self, model):
        return None


class Specialists:
    def delegate(self, role, task, context=""):
        return {"ok": True, "role": role}


class NoPressure:
    def can_start_model(self):
        return True, "ok"


def test_run_history_persists_and_queries_last_tuesday(tmp_path):
    store = RunHistoryStore(tmp_path / "history.sqlite3")
    now = dt.datetime(2026, 9, 21, 12, 0, 0)  # Monday
    last_tuesday = dt.datetime(2026, 9, 15, 10, 30, 0)
    store.record("r1", "run_started", project="demo", summary="fix tests", created_at=last_tuesday)
    store.record("r1", "tool_call", project="demo", tool_name="pytest", summary="tests completed", created_at=last_tuesday + dt.timedelta(minutes=1))
    store.record("r2", "run_started", project="demo", summary="today", created_at=now)

    start, end = store._time_range("last Tuesday", now=now)
    assert start.date().isoformat() == "2026-09-15"
    assert end.date().isoformat() == "2026-09-16"

    # Query uses the real current clock, so exercise the same date range through
    # ISO date syntax for deterministic storage filtering.
    result = store.query(project="demo", when="2026-09-15")
    assert result["run_count"] == 1
    assert result["runs"] == ["r1"]
    assert [event["action"] for event in result["events"]] == ["run_started", "tool_call"]

    restarted = RunHistoryStore(tmp_path / "history.sqlite3")
    assert restarted.query(run_id="r1")["run_count"] == 1


def test_run_history_redacts_tool_arguments_and_does_not_store_raw_result(tmp_path):
    store = RunHistoryStore(tmp_path / "history.sqlite3")
    store.record_tool(
        "run1",
        "remote_call",
        {"api_key": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"},
        {"ok": False, "error": "Authorization: Bearer secret-value", "output": "do-not-store"},
        project="demo",
    )
    event = store.query(run_id="run1")["events"][0]
    serialized = str(event)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in serialized
    assert "secret-value" not in serialized
    assert "do-not-store" not in serialized
    assert "REDACTED" in serialized


def test_orchestrator_records_one_run_and_tool_action(tmp_path):
    history = RunHistoryStore(tmp_path / "history.sqlite3")
    provider = FakeProvider()
    mm = ModelManager(provider)
    tool = Tool(
        "echo",
        "echo",
        {"type": "object", "properties": {"value": {"type": "string"}}},
        lambda value: {"ok": True, "value": value},
    )
    orchestrator = Orchestrator(
        mm,
        "fake",
        [tool],
        Specialists(),
        resource_manager=NoPressure(),
        max_steps=3,
        run_history=history,
    )
    answer = orchestrator.run("use echo", context="Project path: /work/demo", session_id="s1")
    assert answer == "done"
    result = history.query(project="demo")
    assert result["run_count"] == 1
    actions = [event["action"] for event in result["events"]]
    assert actions == ["run_started", "tool_call", "run_finished"]
    tool_event = result["events"][1]
    assert tool_event["tool_name"] == "echo"
    assert tool_event["status"] == "completed"


def test_run_history_tool_supports_human_time_filter(tmp_path):
    history = RunHistoryStore(tmp_path / "history.sqlite3")
    tools = build_run_history_tools(history)
    assert [tool.name for tool in tools] == ["query_run_history"]
    result = tools[0].handler(project="repo", when="last 7 days", limit=20)
    assert result["ok"] is True
    assert result["project"] == "repo"
