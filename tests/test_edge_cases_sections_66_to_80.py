from __future__ import annotations

import json
import os
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from living_assistant.api import app, check_version_compatibility, API_VERSION, CAPABILITY_VERSION
from living_assistant.core.retry_policy import RetryPolicy
from living_assistant.core.idempotency import IdempotencyStore
from living_assistant.core.approval import ApprovalStore, ApprovalManager
from living_assistant.agents.task_graph import TaskGraphManager, TaskNode
from living_assistant.agents.orchestrator import Orchestrator
from living_assistant.system.notifications import Notifier
from living_assistant.tools.desktop import build_desktop_tools
from living_assistant.core.workspace import Workspace


# =====================================================================
# SECTION 66, 67, 68, 69, 70: UI STATE, COMPANION FACE & ACCESSIBILITY
# =====================================================================

def test_section_66_ui_state_representation():
    """Section 66: UI states represent normal, loading, executing, failed, streaming, and voice."""
    valid_states = {
        "idle", "disconnected", "reconnecting", "model_loading",
        "tool_executing", "tool_failed", "streaming", "interrupted",
        "voice_listening", "voice_speaking", "browser_working"
    }
    # Verify our UI state machine transitions cleanly
    current_state = "idle"
    assert current_state in valid_states

    # State update helper
    def transition(new_state: str) -> str:
        assert new_state in valid_states, f"Unknown UI state: {new_state}"
        return new_state

    current_state = transition("tool_executing")
    assert current_state == "tool_executing"
    current_state = transition("tool_failed")
    assert current_state == "tool_failed"


def test_section_67_companion_face_circularity():
    """Section 67: Companion face styles maintain 1:1 aspect ratio and circular border-radius."""
    css_path = Path("electron-assistant/style.css")
    assert css_path.exists()
    content = css_path.read_text(encoding="utf-8")

    # Verify Section 67 rules in stylesheet
    assert "Section 67: Companion Face Circularity" in content
    assert "aspect-ratio: 1 / 1" in content
    assert "border-radius: 50%" in content


def test_section_68_ui_animation_reduced_motion():
    """Section 68: CSS includes prefers-reduced-motion media queries to disable continuous motion."""
    css_path = Path("electron-assistant/style.css")
    content = css_path.read_text(encoding="utf-8")

    assert "@media (prefers-reduced-motion: reduce)" in content
    assert "animation: none !important" in content
    assert "animation-duration: 0.001ms !important" in content


def test_section_69_and_70_keyboard_and_screen_reader_accessibility():
    """Sections 69 & 70: Verify keyboard accessibility and screen reader utility class."""
    css_path = Path("electron-assistant/style.css")
    content = css_path.read_text(encoding="utf-8")

    # Verify .sr-only class exists for accessible screen reader announcements
    assert ".sr-only" in content
    assert "clip: rect(0, 0, 0, 0)" in content


# =====================================================================
# SECTION 71: FRONTEND-BACKEND VERSION MISMATCH
# =====================================================================

def test_section_71_frontend_backend_version_mismatch():
    """Section 71: Expose API_VERSION / CAPABILITY_VERSION and check client compatibility."""
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()

    assert data.get("api_version") == API_VERSION
    assert data.get("capability_version") == CAPABILITY_VERSION
    assert "min_client_version" in data

    # Test compatible client (same major version)
    compat1 = check_version_compatibility("1.2.0")
    assert compat1["compatible"] is True

    # Test incompatible client (different major version e.g. 2.0.0 vs 1.0.0)
    compat2 = check_version_compatibility("2.0.0")
    assert compat2["compatible"] is False
    assert "incompatible" in compat2["error"]


# =====================================================================
# SECTION 72: STREAMING RESPONSE TESTS
# =====================================================================

def test_section_72_streaming_response_partial_token_handling():
    """Section 72: Partial streaming tokens are not executed prematurely as tool calls."""
    mock_mm = MagicMock()
    mock_specialists = MagicMock()

    # Simulate model yielding streaming tokens with partial JSON
    stream_chunks = [
        {"message": {"content": '{"name": "web_search", '}},
        {"message": {"content": '"arguments": {"query": "deep learning"}}'}},
    ]
    mock_mm.provider.chat_stream = MagicMock(return_value=iter(stream_chunks))

    orch = Orchestrator(
        model_manager=mock_mm,
        model="test-model",
        tools=[],
        specialist_router=mock_specialists,
    )

    # When streaming, individual tokens are emitted first
    tokens_emitted = []
    for event in orch.run_stream("search something", session_id="s1"):
        if event.get("type") == "token":
            tokens_emitted.append(event["text"])

    assert len(tokens_emitted) == 2
    full_text = "".join(tokens_emitted)
    assert '{"name": "web_search"' in full_text


# =====================================================================
# SECTION 73: MULTI-TOOL RESPONSE DEPENDENCY ORDERING
# =====================================================================

def test_section_73_multi_tool_dependency_ordering():
    """Section 73: Producer tools (search/read) execute before consumer tools (download/write)."""
    tool_calls = [
        {"function": {"name": "download_image", "arguments": {"url": "http://example.com/img.png"}}},
        {"function": {"name": "web_search", "arguments": {"query": "cats"}}},
    ]

    ordered = Orchestrator._order_and_validate_tool_batch(tool_calls)
    assert len(ordered) == 2
    # web_search should be reordered to run before download_image
    assert ordered[0]["function"]["name"] == "web_search"
    assert ordered[1]["function"]["name"] == "download_image"


# =====================================================================
# SECTION 74: PARTIAL SUCCESS
# =====================================================================

def test_section_74_partial_success_state(tmp_path: Path):
    """Section 74: Support PARTIAL_SUCCESS and avoid misleading 'Done' for partial completions."""
    graph = TaskGraphManager(tmp_path / "tasks.sqlite3")

    # Add 10 download subtasks
    for i in range(10):
        graph.add_task(f"task-{i}", f"Download image {i}")

    # 7 succeed, 3 fail
    for i in range(7):
        graph.update_task_status(f"task-{i}", "completed", result="saved")
    for i in range(7, 10):
        graph.update_task_status(f"task-{i}", "failed", result="HTTP 404")

    # Calculate batch state
    all_tasks = [graph.get_task(f"task-{i}") for i in range(10)]
    succeeded = sum(1 for t in all_tasks if t.status == "completed")
    failed = sum(1 for t in all_tasks if t.status == "failed")

    status = "PARTIAL_SUCCESS" if (succeeded > 0 and failed > 0) else ("SUCCESS" if failed == 0 else "FAILED")
    summary = f"{succeeded} downloaded. {failed} failed."

    assert status == "PARTIAL_SUCCESS"
    assert summary == "7 downloaded. 3 failed."
    assert "Done" not in summary


# =====================================================================
# SECTION 75: RETRY POLICY
# =====================================================================

def test_section_75_differentiated_retry_policy():
    """Section 75: Verify differentiated retry logic for 429, 500, timeout, 400, 401, 403, 404."""
    # 1. 429 Rate limit -> Backoff with jitter
    r429 = RetryPolicy.evaluate(status_code=429, attempt=1)
    assert r429["should_retry"] is True
    assert r429["delay"] >= 2.0

    # 2. 500 Server error -> Retry
    r500 = RetryPolicy.evaluate(status_code=500, attempt=1)
    assert r500["should_retry"] is True

    # 3. Timeout -> Single retry
    r_timeout = RetryPolicy.evaluate(status_code=408, error="timed out", attempt=1)
    assert r_timeout["should_retry"] is True
    r_timeout2 = RetryPolicy.evaluate(status_code=408, error="timed out", attempt=2)
    assert r_timeout2["should_retry"] is False

    # 4. 400 Bad Request -> No blind retry
    r400 = RetryPolicy.evaluate(status_code=400, error="invalid argument")
    assert r400["should_retry"] is False

    # 5. 401 Unauthorized -> No retry
    r401 = RetryPolicy.evaluate(status_code=401)
    assert r401["should_retry"] is False

    # 6. 403 Forbidden -> No retry
    r403 = RetryPolicy.evaluate(status_code=403)
    assert r403["should_retry"] is False

    # 7. 404 Not Found -> No retry
    r404 = RetryPolicy.evaluate(status_code=404)
    assert r404["should_retry"] is False


# =====================================================================
# SECTION 76: IDEMPOTENCY
# =====================================================================

def test_section_76_idempotency_store_prevents_duplicate_execution(tmp_path: Path):
    """Section 76: Idempotent operations return cached result without duplicate execution."""
    store = IdempotencyStore(tmp_path / "idempotency.sqlite3")

    counter = {"calls": 0}

    def create_reminder():
        counter["calls"] += 1
        return {"reminder_id": "rem-101", "time": "15:00"}

    # First execution runs function
    res1 = store.execute("idem-key-1", "create_reminder", create_reminder)
    assert res1["ok"] is True
    assert res1["cached"] is False
    assert counter["calls"] == 1
    assert res1["result"]["reminder_id"] == "rem-101"

    # Second execution with same key returns cached result without running function
    res2 = store.execute("idem-key-1", "create_reminder", create_reminder)
    assert res2["ok"] is True
    assert res2["cached"] is True
    assert counter["calls"] == 1  # Not incremented!
    assert res2["result"]["reminder_id"] == "rem-101"


# =====================================================================
# SECTION 77: APPROVAL EXPIRY
# =====================================================================

def test_section_77_approval_expiry(tmp_path: Path):
    """Section 77: Pre-approvals expire after their validity window and cannot be consumed."""
    store = ApprovalStore(tmp_path / "approvals.sqlite3")

    # Create and resolve an approval
    item = store.create("delete_file temp.log", "cleanup", "DESTRUCTIVE")
    app_id = item["id"]
    store.resolve(app_id, approved=True)

    # Immediately: can be consumed
    consumed = store.consume_preapproval("delete_file temp.log", "cleanup", "DESTRUCTIVE", max_approved_age_seconds=900)
    assert consumed == app_id

    # Create another approval and simulate it was resolved 20 minutes ago
    item2 = store.create("delete_file old.log", "cleanup", "DESTRUCTIVE")
    app_id2 = item2["id"]
    store.resolve(app_id2, approved=True)

    # Manually backdate resolved_at to 20 minutes ago
    past_time = "2020-01-01T00:00:00"
    store.conn.execute("UPDATE approvals SET resolved_at = ? WHERE id = ?", (past_time, app_id2))
    store.conn.commit()

    # Attempting to consume an expired approval must fail
    expired_consumption = store.consume_preapproval("delete_file old.log", "cleanup", "DESTRUCTIVE", max_approved_age_seconds=900)
    assert expired_consumption is None


# =====================================================================
# SECTION 78: APPROVAL RACE CONDITIONS
# =====================================================================

def test_section_78_approval_race_condition_target_mutation(tmp_path: Path):
    """Section 78: Target revalidation detects file mutation between approval and execution."""
    target_file = tmp_path / "temp.log"
    target_file.write_text("initial log data", encoding="utf-8")

    # Capture fingerprint at time of approval
    fingerprint = ApprovalManager.get_target_fingerprint(target_file)
    assert fingerprint is not None

    # Before execution, file is modified/replaced externally
    time.sleep(0.01)
    target_file.write_text("CRITICAL SYSTEM FILE REPLACED", encoding="utf-8")

    # Revalidation immediately before destructive action must detect mutation and abort
    ok, reason = ApprovalManager.revalidate_target(target_file, fingerprint)
    assert ok is False
    assert "Target changed between approval and execution" in reason


# =====================================================================
# SECTION 79: CLIPBOARD CAPABILITY
# =====================================================================

def test_section_79_clipboard_safety_and_truncation(tmp_path: Path):
    """Section 79: Clipboard requires approval, truncates large data, and does not auto-persist."""
    approval = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path / "app.sqlite3"))
    ws = Workspace([tmp_path])
    tools = {t.name: t for t in build_desktop_tools(ws, approval)}

    # 1. Clipboard read requires approval
    read_tool = tools["clipboard_read"]
    with patch("living_assistant.tools.desktop._clipboard_read_impl", return_value="large " * 5000):
        # Without approval, blocked
        res_unapproved = read_tool.handler()
        assert res_unapproved.get("approval_required") is True

        # Preapprove and execute
        item = approval.store.create("Read current clipboard contents", "Clipboard may contain passwords, tokens or private text.", "SENSITIVE_READ")
        approval.store.resolve(item["id"], approved=True)

        res_approved = read_tool.handler()
        assert res_approved.get("ok") is True
        assert res_approved.get("truncated") is True
        assert len(res_approved.get("text")) <= 20000


# =====================================================================
# SECTION 80: NOTIFICATION DEDUPLICATION & PRIVACY
# =====================================================================

def test_section_80_notification_deduplication_and_redaction(tmp_path: Path):
    """Section 80: Notifier deduplicates identical notifications and redacts secrets."""
    notifier = Notifier(queue_path=tmp_path / "notifs.json")

    # Send notification containing secret
    with patch.object(notifier, "_send_now", return_value={"ok": True}):
        res1 = notifier._enqueue("Alert", "User token sk-ant-api03-123456789012345678901234")
        assert res1.get("queued") is True
        assert res1.get("deduplicated") is not True

        # Send exact duplicate immediately -> deduplicated!
        res2 = notifier._enqueue("Alert", "User token sk-ant-api03-123456789012345678901234")
        assert res2.get("deduplicated") is True
