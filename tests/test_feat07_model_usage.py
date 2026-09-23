from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from fastapi.testclient import TestClient

from living_assistant.agents.agents import SpecialistRouter
from living_assistant.agents.orchestrator import Orchestrator
from living_assistant.system.model_usage import ModelUsageStore


class _Specialists:
    def delegate(self, role, task, context=""):
        return {"ok": True, "role": role}


class _NonStreamingProvider:
    def chat(self, model, messages, tools=None, keep_alive=45, options=None):
        return {
            "message": {"role": "assistant", "content": "done", "tool_calls": []},
            "prompt_eval_count": 17,
            "eval_count": 5,
        }


class _StreamingProvider:
    def chat_stream(self, model, messages, tools=None, keep_alive=45, options=None):
        yield {"message": {"role": "assistant", "content": "do"}}
        yield {
            "message": {"role": "assistant", "content": "ne"},
            "done": True,
            "prompt_eval_count": 19,
            "eval_count": 7,
        }


class _MM:
    max_concurrent_generations = 1

    def __init__(self, provider):
        self.provider = provider
        self.active_model = None

    def activate(self, model, priority=50):
        self.active_model = model

    def lease(self, model, timeout=None, priority=50):
        self.active_model = model
        return nullcontext(45)

    def sleep(self):
        self.active_model = None


def test_model_usage_store_tracks_exact_provider_counts_and_session_filter(tmp_path):
    store = ModelUsageStore(tmp_path / "usage.sqlite3")
    row = store.record_response(
        "qwen:test",
        {"prompt_eval_count": 11, "eval_count": 4},
        0.125,
        session_id="session-a",
        run_id="run-a",
    )
    store.record_response(
        "custom:test",
        {"message": {"content": "no usage metadata"}},
        0.2,
        session_id="session-b",
    )

    assert row["prompt_tokens"] == 11
    assert row["completion_tokens"] == 4
    assert row["token_source"] == "ollama"

    summary = store.summary(session_id="session-a", days=30)
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["prompt_tokens"] == 11
    assert summary["totals"]["completion_tokens"] == 4
    assert summary["totals"]["total_tokens"] == 15
    assert summary["models"][0]["model"] == "qwen:test"

    all_usage = store.summary(days=30)
    assert all_usage["totals"]["calls"] == 2
    assert all_usage["totals"]["unknown_token_calls"] == 1

    columns = {r[1] for r in store.conn.execute("PRAGMA table_info(model_usage)").fetchall()}
    assert "prompt" not in columns
    assert "response" not in columns
    assert "content" not in columns


def test_orchestrator_records_non_streaming_usage_per_session(tmp_path):
    store = ModelUsageStore(tmp_path / "usage.sqlite3")
    orchestrator = Orchestrator(
        _MM(_NonStreamingProvider()),
        "qwen:test",
        [],
        _Specialists(),
        model_usage=store,
    )

    assert orchestrator.run("hello", session_id="session-one") == "done"
    summary = store.summary(session_id="session-one")
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["total_tokens"] == 22


def test_orchestrator_records_streaming_final_usage_metadata(tmp_path):
    store = ModelUsageStore(tmp_path / "usage.sqlite3")
    orchestrator = Orchestrator(
        _MM(_StreamingProvider()),
        "qwen:stream",
        [],
        _Specialists(),
        model_usage=store,
    )

    events = list(orchestrator.run_stream("hello", session_id="stream-session"))
    assert events[-1]["type"] == "final"
    assert events[-1]["text"] == "done"
    summary = store.summary(session_id="stream-session")
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["total_tokens"] == 26


def test_specialist_usage_keeps_session_and_run_identity(tmp_path):
    class Provider:
        def chat(self, model, messages, keep_alive=45, options=None):
            return {
                "message": {"content": "specialist answer"},
                "usage": {"input_tokens": 23, "output_tokens": 9},
            }

    store = ModelUsageStore(tmp_path / "usage.sqlite3")
    router = SpecialistRouter(
        _MM(Provider()),
        {"coder": "coder:test", "general": "general:test"},
        timeout_seconds=2,
        model_usage=store,
    )
    result = router.delegate(
        "coder",
        "fix it",
        session_id="special-session",
        run_id="special-run",
    )

    assert result["ok"] is True
    row = store.conn.execute(
        "SELECT session_id,run_id,role,prompt_tokens,completion_tokens FROM model_usage"
    ).fetchone()
    assert dict(row) == {
        "session_id": "special-session",
        "run_id": "special-run",
        "role": "specialist:coder",
        "prompt_tokens": 23,
        "completion_tokens": 9,
    }


def test_delegate_agent_propagates_internal_usage_identity_without_model_arguments():
    captured = {}

    class Specialists:
        def delegate(self, role, task, context="", session_id=None, run_id=None):
            captured.update(
                role=role,
                task=task,
                session_id=session_id,
                run_id=run_id,
            )
            return {"ok": True}

    orchestrator = Orchestrator(
        _MM(_NonStreamingProvider()), "qwen:test", [], Specialists()
    )
    schema = orchestrator.tools["delegate_agent"].parameters
    assert "session_id" not in schema["properties"]
    assert "run_id" not in schema["properties"]

    _, result = orchestrator._execute_tool(
        "delegate_agent",
        {"role": "coder", "task": "inspect"},
        session_id="s-hidden",
        run_id="r-hidden",
    )
    assert result["ok"] is True
    assert captured["session_id"] == "s-hidden"
    assert captured["run_id"] == "r-hidden"


def test_model_usage_api_is_authenticated_and_returns_summary(monkeypatch, tmp_path):
    import living_assistant.api as api

    store = ModelUsageStore(tmp_path / "usage.sqlite3")
    store.record_response(
        "qwen:test",
        {"prompt_eval_count": 3, "eval_count": 2},
        0.01,
        session_id="api-session",
    )
    monkeypatch.setattr(api, "get_runtime", lambda: SimpleNamespace(model_usage=store))
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "usage-test-token")

    anonymous = TestClient(api.app).get("/models/usage")
    assert anonymous.status_code == 401
    response = TestClient(
        api.app, headers={"Authorization": "Bearer usage-test-token"}
    ).get("/models/usage?days=7&session_id=api-session")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "api-session"
    assert payload["totals"]["total_tokens"] == 5


def test_dashboard_exposes_model_usage_without_rendering_provider_html():
    from importlib import resources

    page = (
        resources.files("living_assistant")
        .joinpath("webui/src/main.js")
        .read_text(encoding="utf-8")
    )
    # The dashboard is a Vite/React SPA (BROKEN-08); model usage is polled and
    # rendered through UsageTable rather than hand-built DOM/innerHTML, so no
    # provider-supplied text is ever assigned as raw HTML.
    assert "async loadUsage()" in page
    assert "this.api('/models/usage?days=30')" in page
    assert "setInterval(() => this.loadUsage(), 10000)" in page
    assert "function UsageTable({usage})" in page
    assert "dangerouslySetInnerHTML" not in page
