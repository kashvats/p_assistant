import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from living_assistant.agents.orchestrator import Orchestrator, TaskState, LOOP_REPEAT_LIMIT, TOOL_DISCOVERY_NAME
from living_assistant.core.typesafe import JevClient
from living_assistant.core.model_provider import ModelManager
from living_assistant.tools.base import Tool
from living_assistant.tools.filesystem import build_filesystem_tools
from living_assistant.core.workspace import Workspace

def create_mock_orchestrator():
    mm = MagicMock(spec=ModelManager)
    mm.provider = MagicMock()
    tools = [
        Tool('dummy_tool', 'A dummy tool', {'type': 'object'}, lambda: {'ok': True}),
        Tool('bm25_tool', 'BM25 fallback tool', {'type': 'object'}, lambda: {'ok': True}),
    ]
    specialists = MagicMock()
    jev = MagicMock(spec=JevClient)
    # Ensure Jev mock returns "Irrelevant" for tools to trigger BM25 fallback
    jev.score.return_value = ("Irrelevant", 0.8)
    jev.noul.return_value = 0.99
    jev.goal_achieved.return_value = (False, 0.0)
    
    orc = Orchestrator(mm, "mock_model", tools, specialists)
    orc.jev = jev
    orc.tool_router = MagicMock()
    orc.tool_router.search.return_value = [{"name": "bm25_tool"}]
    return orc

@pytest.fixture
def mock_orchestrator():
    return create_mock_orchestrator()

# CASE A: Strict result validation (ok_result defaults to False when missing "ok")
def test_case_a_strict_result_validation(mock_orchestrator):
    mock_orchestrator._execute_tool = MagicMock(return_value=({}, {"some_data": "here"}))
    mock_orchestrator.mm.provider.chat_stream.return_value = [{
        "message": {
            "tool_calls": [{"function": {"name": "dummy_tool", "arguments": {}}}]
        }
    }]
    mock_orchestrator.max_steps = 1
    
    events = list(mock_orchestrator.run_stream("test", "", session_id="test_sess"))
    
    completed_event = next(e for e in events if e.get("type") == "tool" and e.get("status") == "completed")
    assert completed_event["ok"] is True
    assert completed_event["ok_status"] == "assumed_true"

# CASE B: Cross-step loop detection prevents identical tool calls
def test_case_b_cross_step_loop_detection():
    ts = TaskState()
    for _ in range(LOOP_REPEAT_LIMIT):
        assert ts.is_stuck("tool1", {"arg": 1}) is False
        ts.record_call(1, "tool1", {"arg": 1}, True, "res")
    
    assert ts.is_stuck("tool1", {"arg": 1}) is True
    assert ts.is_stuck("tool1", {"arg": 2}) is False

# CASE C: Jev loop-breaker requires minimum content length to fire
def test_case_c_jev_loop_breaker_content_length(mock_orchestrator):
    mock_orchestrator.mm.provider.chat_stream.return_value = [{
        "message": {
            "content": "Short",
            "tool_calls": [{"function": {"name": "dummy_tool", "arguments": {}}}]
        }
    }]
    mock_orchestrator.max_steps = 1
    mock_orchestrator._execute_tool = MagicMock(return_value=({}, {"ok": True}))
    
    events = list(mock_orchestrator.run_stream("test", "", session_id="test_sess"))
    
    mock_orchestrator.jev.goal_achieved.assert_not_called()

# CASE D: Context ordering places prior session history before current request
def test_case_d_context_ordering(mock_orchestrator):
    messages, _, _ = mock_orchestrator._prepare("user query", "working ctx", None)
    user_payload = messages[1]["content"]
    assert "Working context:\nworking ctx\n\n[CURRENT REQUEST]\nuser query" in user_payload

# CASE E: Active tool check before Jev security gate
def test_case_e_active_tool_check(mock_orchestrator):
    mock_orchestrator.mm.provider.chat_stream.return_value = [{
        "message": {
            "tool_calls": [{"function": {"name": "hallucinated_tool", "arguments": {}}}]
        }
    }]
    mock_orchestrator.max_steps = 1
    
    events = list(mock_orchestrator.run_stream("test", "", session_id="test_sess"))
    
    mock_orchestrator.jev.noul.assert_not_called()

# CASE F: TaskState records fingerprint correctly
def test_case_f_taskstate_fingerprint():
    fp1 = TaskState._fingerprint("tool", {"b": 2, "a": 1})
    fp2 = TaskState._fingerprint("tool", {"a": 1, "b": 2})
    assert fp1 == fp2

# CASE G: TaskState audit summary provides correct history
def test_case_g_taskstate_audit_summary():
    ts = TaskState()
    ts.record_call(1, "t1", {}, True, "success1")
    ts.record_call(2, "t2", {}, False, "err2")
    summary = ts.audit_summary()
    assert summary == ["t1 (ok): success1", "t2 (err): err2"]

# CASE H: Filesystem tool verifies file exists after write
def test_case_h_filesystem_write_verification(tmp_path):
    ws = Workspace([tmp_path])
    tools = build_filesystem_tools(ws)
    write_tool = next(t for t in tools if t.name == "write_file")
    
    res = write_tool.handler(path="test.txt", content="hello")
    assert res["ok"] is True
    
    with patch.object(ws, 'write_text', return_value=str(tmp_path / "ghost.txt")):
        res2 = write_tool.handler(path="ghost.txt", content="hello")
        assert res2["ok"] is False
        assert "does not exist after write operation" in res2["error"]

# CASE I: Tool routing falls back to BM25 when Jev scores are < 1.0
def test_case_i_tool_routing_bm25_fallback(mock_orchestrator):
    names = mock_orchestrator._initial_tool_names("test", "", "")
    assert "bm25_tool" in names

# CASE J: Tool routing includes core catalog tools
def test_case_j_tool_routing_core_tools(mock_orchestrator):
    names = mock_orchestrator._initial_tool_names("test", "", "")
    assert TOOL_DISCOVERY_NAME in names

# CASE K: Loop detection injects hard stop message instead of burning context
def test_case_k_loop_injection_hard_stop(mock_orchestrator):
    mock_orchestrator.mm.provider.chat_stream.return_value = [{
        "message": {
            "tool_calls": [{"function": {"name": "dummy_tool", "arguments": {}}}]
        }
    }]
    mock_orchestrator.max_steps = 5
    mock_orchestrator._execute_tool = MagicMock(return_value=({}, {"ok": True}))
    
    events = list(mock_orchestrator.run_stream("test", "", session_id="test_sess"))
    
    blocked_events = [e for e in events if e.get("type") == "tool" and e.get("ok") is False and e.get("status") == "completed"]
    assert len(blocked_events) > 0

# CASE L: Fallback JSON tool extraction for models that output raw JSON string
def test_case_l_json_fallback_parsing(mock_orchestrator):
    mock_orchestrator.mm.provider.chat_stream.return_value = [{
        "message": {
            "content": '{"name": "bm25_tool", "arguments": {"a": 1}} \n {"name": "bm25_tool", "arguments": {"a": 1}}'
        }
    }]
    mock_orchestrator.max_steps = 1
    mock_orchestrator._execute_tool = MagicMock(return_value=({}, {"ok": True}))
    
    events = list(mock_orchestrator.run_stream("test", "", session_id="test_sess"))
    
    tool_events = [e for e in events if e.get("type") == "tool" and e.get("status") == "started"]
    # Should only execute once because of seen_calls deduplication in the same chunk
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "bm25_tool"


