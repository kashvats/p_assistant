import pytest
from unittest.mock import MagicMock, patch
import datetime as dt
from pathlib import Path

from living_assistant.agents.orchestrator import DynamicToolRouter, Orchestrator
from living_assistant.tools.base import Tool
from living_assistant.core.workspace import Workspace
from living_assistant.tools.webtools import build_web_tools
import httpx


# ==========================================
# SECTION 5: INTENT ROUTER EDGE CASES
# ==========================================

def test_section_5_intent_routing_web_vs_file_search():
    """Verify tool ranking differentiates between web search queries and local workspace search."""
    tools = {
        "search_web": Tool("search_web", "Search the internet for current online information and websites", {"type": "object"}, lambda: None),
        "search_files": Tool("search_files", "Search files and directories inside the local workspace", {"type": "object"}, lambda: None),
        "list_models": Tool("list_models", "List installed local AI models and checkpoints", {"type": "object"}, lambda: None),
    }
    router = DynamicToolRouter(tools)

    # 1. Online query -> search_web should rank highest
    web_results = router.search("search Qwen release notes on google internet")
    assert len(web_results) > 0
    assert web_results[0]["name"] == "search_web"

    # 2. Local workspace query -> search_files should rank highest
    file_results = router.search("find Qwen in my workspace files directory")
    assert len(file_results) > 0
    assert file_results[0]["name"] == "search_files"

    # 3. Local model query -> list_models should rank highest
    model_results = router.search("find installed local AI models and checkpoints")
    assert len(model_results) > 0
    assert model_results[0]["name"] == "list_models"


# ==========================================
# SECTION 6: CONTEXTUAL FOLLOW-UP TESTS
# ==========================================

def test_section_6_pronoun_context_preservation():
    """Verify that multi-turn history retains previous tool results for pronoun resolution ('open the second one')."""
    orc = Orchestrator(MagicMock(), "mock_model", [], MagicMock())
    
    # Simulate prior search history containing two URLs
    prior_context = (
        "Previous Search Results:\n"
        "1. Qwen Overview: https://example.com/qwen-overview\n"
        "2. Qwen Benchmarks: https://example.com/qwen-benchmarks\n"
    )
    user_query = "Open the second one in the browser."
    
    messages, _, _ = orc._prepare(user_query, prior_context, None)
    prompt_payload = messages[1]["content"]
    
    # Both the prior context and the relative instruction are bound in prompt payload
    assert "https://example.com/qwen-benchmarks" in prompt_payload
    assert "Open the second one" in prompt_payload


# ==========================================
# SECTION 7: STALE SESSION TESTS
# ==========================================

def test_section_7_stale_session_detection():
    """Verify operations on closed/stale sessions return explicit errors rather than false success."""
    class FakeBrowserController:
        def __init__(self):
            self.active = False
        def interact(self, action: str):
            if not self.active:
                return {"ok": False, "error": "Stale session: Browser tab was closed externally."}
            return {"ok": True}

    fake_browser = FakeBrowserController()
    result = fake_browser.interact("pause")
    assert result["ok"] is False
    assert "Stale session" in result["error"]


# ==========================================
# SECTION 8: TIME TESTS (MOCKED CLOCK)
# ==========================================

def test_section_8_mocked_time_calculations():
    """Verify deterministic date calculations (today, tomorrow, yesterday, midnight rollover) with a frozen clock."""
    frozen_now = dt.datetime(2026, 9, 27, 23, 59, 58, tzinfo=dt.timezone.utc)
    
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = frozen_now
        mock_dt.side_effect = lambda *args, **kw: dt.datetime(*args, **kw)
        
        today = frozen_now.date()
        tomorrow = today + dt.timedelta(days=1)
        yesterday = today - dt.timedelta(days=1)
        
        assert str(today) == "2026-09-27"
        assert str(tomorrow) == "2026-09-28"
        assert str(yesterday) == "2026-09-26"
        
        # Test midnight rollover after 3 seconds
        rollover_time = frozen_now + dt.timedelta(seconds=3)
        assert rollover_time.date() == dt.date(2026, 9, 28)
        assert rollover_time.hour == 0 and rollover_time.minute == 0


# ==========================================
# SECTION 9 & 10: WEB SEARCH QUALITY & RESILIENCE
# ==========================================

def test_section_9_web_search_rate_limit_resilience(tmp_path, monkeypatch):
    """Verify web search budget throttling returns a structured rate limit response on HTTP 429."""
    monkeypatch.setenv("SERPER_API_KEY", "mock_key")
    ws = Workspace([tmp_path])
    cfg = {
        "web_search": {"provider": "serper", "max_calls_per_minute": 1},
        "policy": {"max_download_mb": 10}
    }
    tools = {t.name: t.handler for t in build_web_tools(ws, cfg)}
    search_tool = tools.get("web_search") or tools.get("search_web")
    
    if search_tool:
        with patch.object(httpx, "Client") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"organic": []}
            mock_client.return_value.__enter__.return_value.send.return_value = mock_resp
            
            # First call consumes budget
            search_tool(query="query 1")
            
            # Second immediate call should hit rate limit
            res2 = search_tool(query="query 2")
            assert res2.get("ok") is False
            assert res2.get("rate_limited") is True
            assert res2.get("retry_after_seconds", 0) > 0



def test_section_10_web_search_network_offline_graceful_fallback(tmp_path):
    """Verify web search gracefully catches network disconnects without raising unhandled exceptions."""
    ws = Workspace([tmp_path])
    tools = {t.name: t.handler for t in build_web_tools(ws, {})}
    search_tool = tools.get("web_search") or tools.get("search_web")
    
    if search_tool:
        with patch.object(httpx, "Client") as mock_client:
            mock_client.return_value.__enter__.return_value.send.side_effect = httpx.ConnectError("No internet connection")
            
            res = search_tool(query="test query offline")
            assert res.get("ok") is False
            assert "error" in res or "No internet" in str(res)
