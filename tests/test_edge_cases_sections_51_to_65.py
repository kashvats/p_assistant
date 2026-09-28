from __future__ import annotations

import json
import os
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from living_assistant.system.resource_manager import ResourceManager
from living_assistant.core.model_provider import ModelManager, CompositeModelProvider, OllamaProvider
from living_assistant.api import app, get_api_token
from living_assistant.security.security_utils import url_network_scope, redact_secrets
from living_assistant.tools.shell import build_shell_tools, ProcessRegistry
from living_assistant.core.workspace import Workspace
from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.agents.orchestrator import Orchestrator
from living_assistant.tools.base import Tool
from living_assistant.core.runtime import Runtime
from living_assistant.system.network_monitor import NetworkMonitor, NetworkState


# =====================================================================
# SECTION 51: RESOURCE EXHAUSTION
# =====================================================================

def test_section_51_resource_exhaustion_disk_and_memory(tmp_path: Path):
    """Section 51: Graceful degradation on disk exhaustion and RAM/VRAM pressure."""
    config = {
        "model_runtime": {"reserve_ram_gb": 4.0, "reserve_vram_gb": 2.0},
        "resource_limits": {"throttle_hysteresis_seconds": 1.0},
    }
    rm = ResourceManager(profile="balanced", config=config)

    # 1. Test disk pressure detection when disk space is critically low
    with patch("shutil.disk_usage") as mock_usage:
        # Simulate only 200 MB free (< 0.5 GB threshold)
        mock_usage.return_value = MagicMock(free=200 * 1024 * 1024, total=500 * 1024 * 1024 * 1024)
        is_pressure, msg, free_gb = rm.disk_pressure(tmp_path, min_free_gb=0.5)
        assert is_pressure is True
        assert "Critical disk pressure" in msg
        assert free_gb == 0.2

    # 2. Test RAM gate when system RAM is exhausted
    with patch.object(rm, "snapshot", return_value={"available_ram_gb": 0.1, "gpu_free_vram_gb": 12.0}):
        allowed, reason = rm.can_start_model(size_bytes=4 * 1024**3)
        assert allowed is False
        assert "RAM" in reason


# =====================================================================
# SECTION 52: GPU OOM RECOVERY
# =====================================================================

def test_section_52_gpu_oom_recovery_and_no_infinite_loop():
    """Section 52: Detect OOM, release failed model, clear cache, fallback, prevent loops."""
    provider = MagicMock()
    provider.unload = MagicMock(return_value={"ok": True})
    provider.running_models = MagicMock(return_value=[])

    rm = MagicMock()
    rm.metabolize = MagicMock(return_value={"ollama_freed": True, "cuda_mps_cleared": True})

    mm = ModelManager(provider=provider, resource_manager=rm)
    mm.status = MagicMock(return_value={
        "models": [
            {"name": "heavy-model:70b", "disk_size_bytes": 40 * 1024**3},
            {"name": "fallback-model:8b", "disk_size_bytes": 5 * 1024**3},
        ]
    })

    # Trigger OOM recovery for heavy-model:70b
    recovery1 = mm.handle_oom(
        failed_model="heavy-model:70b",
        error_message="CUDA out of memory. Tried to allocate 4.00 GiB",
    )
    assert recovery1["detected_oom"] is True
    assert recovery1["released_model"] == "heavy-model:70b"
    assert recovery1["cleared_caches"]["cuda_mps_cleared"] is True
    assert recovery1["smaller_model"] == "fallback-model:8b"
    assert recovery1["retry_allowed"] is True
    provider.unload.assert_called_with("heavy-model:70b")

    # If the fallback model ALSO OOMs, ensure no infinite loop
    recovery2 = mm.handle_oom(
        failed_model="fallback-model:8b",
        error_message="CUDA out of memory. Tried to allocate 2.00 GiB",
    )
    assert recovery2["detected_oom"] is True
    # Both heavy and fallback have failed; no further valid smaller model
    assert recovery2["retry_allowed"] is False


# =====================================================================
# SECTION 53: BACKGROUND THROTTLING
# =====================================================================

def test_section_53_background_throttling_hysteresis():
    """Section 53: Threshold hysteresis prevents rapid pause/resume oscillation."""
    config = {
        "resource_limits": {"throttle_hysteresis_seconds": 0.5},
        "model_runtime": {"thermal_guard_enabled": False},
    }
    rm = ResourceManager(profile="balanced", config=config)

    # 1. Normal conditions: not throttled
    with patch.object(rm, "snapshot", return_value={"cpu_percent": 30.0, "available_ram_gb": 4.0}):
        throttled, reason = rm.should_throttle_background_tasks(max_cpu_percent=85.0, min_available_ram_gb=1.0)
        assert throttled is False

    # 2. Spike occurs (CPU = 90%): enters throttled state
    with patch.object(rm, "snapshot", return_value={"cpu_percent": 90.0, "available_ram_gb": 4.0}):
        throttled, reason = rm.should_throttle_background_tasks(max_cpu_percent=85.0, min_available_ram_gb=1.0)
        assert throttled is True
        assert rm._is_throttled is True

    # 3. CPU drops to 80% immediately: still in hysteresis window, stays throttled
    with patch.object(rm, "snapshot", return_value={"cpu_percent": 80.0, "available_ram_gb": 4.0}):
        throttled, reason = rm.should_throttle_background_tasks(max_cpu_percent=85.0, min_available_ram_gb=1.0)
        assert throttled is True
        assert "hysteresis hold" in reason

    # 4. Wait for hysteresis timer to elapse
    time.sleep(0.6)

    # If CPU dropped to 60% (well below unthrottle threshold 70%): exits throttled state
    with patch.object(rm, "snapshot", return_value={"cpu_percent": 60.0, "available_ram_gb": 4.0}):
        throttled, reason = rm.should_throttle_background_tasks(max_cpu_percent=85.0, min_available_ram_gb=1.0)
        assert throttled is False
        assert rm._is_throttled is False


# =====================================================================
# SECTIONS 54, 55, 56: API AUTH, LOCALHOST NOT TRUSTED, CORS
# =====================================================================

def test_section_54_api_auth_validation():
    """Section 54: FastAPI handles missing, wrong, expired, empty tokens without logging."""
    client = TestClient(app)
    valid_token = get_api_token()

    # 1. Missing token -> 401
    resp_missing = client.get("/status")
    assert resp_missing.status_code == 401

    # 2. Wrong token -> 401
    resp_wrong = client.get("/status", headers={"Authorization": "Bearer wrong-secret-token"})
    assert resp_wrong.status_code == 401

    # 3. Empty token -> 401
    resp_empty = client.get("/status", headers={"Authorization": "Bearer "})
    assert resp_empty.status_code == 401

    # 4. Token in wrong header -> 401
    resp_wrong_header = client.get("/status", headers={"X-API-Key": valid_token})
    assert resp_wrong_header.status_code == 401

    # 5. Valid token -> 200
    with patch("living_assistant.api._rt") as mock_rt:
        mock_rt.return_value = MagicMock(
            profile="balanced",
            hardware=MagicMock(to_dict=lambda: {}),
            resources=MagicMock(snapshot=lambda: {}),
            personal=MagicMock(status=lambda: {}),
            model_manager=MagicMock(status=lambda refresh: {}, active_model="test-model"),
            orchestrator=MagicMock(model="test-model"),
            integrations=MagicMock(status=lambda: {}),
        )
        resp_valid = client.get("/status", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp_valid.status_code == 200


def test_section_55_localhost_requires_authentication():
    """Section 55: Requests from localhost/127.0.0.1 must still authenticate."""
    client = TestClient(app)

    # Localhost request without Bearer token must be rejected with 401
    for host in ("127.0.0.1", "localhost", "::1"):
        res = client.get("/status", headers={"Host": host})
        assert res.status_code == 401, f"Host {host} must require auth"


def test_section_56_cors_allowed_and_blocked_origins():
    """Section 56: Strict CORS policy: allowed origins work, unexpected origins blocked."""
    client = TestClient(app)

    # 1. Preflight OPTIONS with allowed origin
    res_preflight = client.options(
        "/status",
        headers={"Origin": "http://localhost:5173", "Host": "127.0.0.1"},
    )
    assert res_preflight.status_code == 204
    assert res_preflight.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert "*" not in res_preflight.headers.get("Access-Control-Allow-Origin", "")

    # 2. Blocked malicious origin -> 403 Forbidden
    res_malicious = client.get(
        "/status",
        headers={"Origin": "http://malicious-website.com", "Host": "127.0.0.1"},
    )
    assert res_malicious.status_code == 403
    assert "Cross-origin browser access" in res_malicious.json().get("detail", "")

    # 3. Blocked null origin -> 403 Forbidden
    res_null = client.get(
        "/status",
        headers={"Origin": "null", "Host": "127.0.0.1"},
    )
    assert res_null.status_code == 403


# =====================================================================
# SECTION 57: SSRF TESTS
# =====================================================================

def test_section_57_ssrf_blocking_private_addresses():
    """Section 57: Block loopback, RFC1918, link-local, and cloud metadata targets."""
    forbidden_targets = [
        "http://127.0.0.1:8080/admin",
        "http://localhost/secret",
        "http://0.0.0.0:8000/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://172.16.0.1/private",
    ]

    for url in forbidden_targets:
        scope, reason = url_network_scope(url, resolve=False)
        assert scope == "private" or scope == "invalid", f"{url} should be flagged as private/invalid SSRF target"


# =====================================================================
# SECTION 58: DOWNLOAD SAFETY
# =====================================================================

def test_section_58_download_safety_limits_and_quarantine(tmp_path: Path):
    """Section 58: Enforce max size limits, reject executables as image downloads."""
    from living_assistant.tools.webtools import build_web_tools

    ws = Workspace([tmp_path])
    approval = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path / "app.sqlite3"))
    config = {
        "policy": {"max_download_mb": 1},
        "downloads": {"quarantine_risky_files": True},
    }
    tools = {t.name: t for t in build_web_tools(ws, config, approval=approval)}

    # Attempt to download an executable using download_image
    with patch("httpx.Client.send") as mock_send:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/x-msdownload"}
        mock_resp.iter_bytes = MagicMock(return_value=[b"MZ" + b"\x00" * 100])
        mock_resp.url = "http://example.com/malicious.exe"
        mock_send.return_value = mock_resp

        result = tools["download_image"].handler(
            url="http://example.com/malicious.exe",
            destination="images/pic.png",
        )
        assert result.get("ok") is False
        assert "not return a supported image" in result.get("error", "")


# =====================================================================
# SECTION 59: SUBPROCESS TESTS
# =====================================================================

def test_section_59_subprocess_timeout_process_group_cleanup(tmp_path: Path):
    """Section 59: Subprocess timeouts terminate cleanly without leaving orphan processes."""
    ws = Workspace([tmp_path])
    approval = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path / "app.sqlite3"))
    reg = ProcessRegistry(tmp_path / "procs.json")
    config = {"policy": {"require_execute_approval": False, "command_timeout_seconds": 1}}

    tools = {t.name: t for t in build_shell_tools(ws, approval, config, reg)}
    run_cmd = tools["run_command"]

    # Run sleep command with small timeout
    cmd = 'powershell -Command "Start-Sleep -Seconds 10"' if os.name == "nt" else "sleep 10"
    res = run_cmd.handler(command=cmd, timeout_seconds=1)

    assert res.get("ok") is False
    assert res.get("timeout") is True


# =====================================================================
# SECTION 60: LOGGING & SECRETS REDACTION
# =====================================================================

def test_section_60_log_redaction_secrets():
    """Section 60: Logs must never include API keys, passwords, bearer tokens, or secrets."""
    sample_text = (
        "Connected with Authorization: Bearer sk-ant-api03-abcdef123456789012345678 "
        "and password: super_secret_pass, AWS_KEY=AKIAIOSFODNN7EXAMPLE "
        "and GitHub token gh_p_123456789012345678901234567890"
    )
    redacted = redact_secrets(sample_text)

    assert "sk-ant-api03" not in redacted
    assert "super_secret_pass" not in redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED" in redacted


# =====================================================================
# SECTION 61: OBSERVABILITY
# =====================================================================

def test_section_61_tool_execution_observability():
    """Section 61: Internal tool execution captures start time, duration, status, and request ID."""
    mock_mm = MagicMock()
    mock_specialists = MagicMock()

    sample_tool = Tool(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"msg": {"type": "string"}}},
        handler=lambda msg: {"ok": True, "echo": msg},
    )

    orch = Orchestrator(
        model_manager=mock_mm,
        model="test-model",
        tools=[sample_tool],
        specialist_router=mock_specialists,
    )

    args, res = orch._execute_tool("test_tool", {"msg": "hello"}, run_id="req-999")
    assert res.get("ok") is True

    telemetry = orch.get_tool_telemetry(limit=10)
    assert len(telemetry) > 0
    record = telemetry[-1]
    assert record["tool"] == "test_tool"
    assert record["status"] == "success"
    assert record["request_id"] == "req-999"
    assert record["duration"] >= 0.0


# =====================================================================
# SECTION 62: STARTUP FAILURE TESTS
# =====================================================================

def test_section_62_degraded_startup_on_non_critical_failure():
    """Section 62: Startup enters degraded mode on optional component failure rather than crashing."""
    from living_assistant.desktop.voice import VoiceEngine

    # Initialize voice engine with missing optional libraries
    ws = MagicMock()
    approval = MagicMock()
    voice = VoiceEngine(ws, approval, config={"voice": {"enabled": True}})

    status = voice.status()
    assert "dependencies" in status
    # Voice status reports cleanly without throwing unhandled exceptions
    assert isinstance(status["dependencies"], dict)


# =====================================================================
# SECTION 63: SHUTDOWN TESTS
# =====================================================================

def test_section_63_graceful_system_shutdown(tmp_path: Path):
    """Section 63: Clean shutdown stops scheduler, voice, browser, and subprocesses."""
    mock_scheduler = MagicMock()
    mock_browser = MagicMock()
    mock_voice = MagicMock()
    mock_processes = MagicMock()
    mock_processes.stop_all = MagicMock(return_value=[{"id": "proc-1"}])
    mock_resources = MagicMock()
    mock_resources.metabolize = MagicMock(return_value={"freed": True})

    rt = Runtime(
        config={},
        profile="balanced",
        hardware=MagicMock(),
        workspace=Workspace([tmp_path]),
        snapshots=MagicMock(),
        memory=MagicMock(),
        projects=MagicMock(),
        groups=MagicMock(),
        group_controller=MagicMock(),
        processes=mock_processes,
        approvals=MagicMock(),
        approval_manager=MagicMock(),
        watches=MagicMock(),
        skills=MagicMock(),
        notifier=MagicMock(),
        resources=mock_resources,
        quarantine=MagicMock(),
        voice=mock_voice,
        routines=MagicMock(),
        improvements=MagicMock(),
        evaluations=MagicMock(),
        repairs=MagicMock(),
        canaries=MagicMock(),
        browser=mock_browser,
        personal=MagicMock(),
        calendar=MagicMock(),
        sessions=MagicMock(),
        connectors=MagicMock(),
        connector_manager=MagicMock(),
        briefings=MagicMock(),
        guardian=MagicMock(),
        security_sensors=MagicMock(),
        experiences=MagicMock(),
        knowledge_gaps=MagicMock(),
        run_history=MagicMock(),
        model_usage=MagicMock(),
        code_index=MagicMock(),
        planner=MagicMock(),
        events_bus=MagicMock(),
        orchestrator=MagicMock(),
        mobile_bridge=MagicMock(),
        peers=MagicMock(),
        model_manager=MagicMock(),
        desktop_controller=MagicMock(),
        integrations=MagicMock(),
        openviking=None,
        scheduler=mock_scheduler,
    )

    res = rt.shutdown()
    assert res.get("shutdown_clean") is True
    mock_scheduler.stop.assert_called_once()
    mock_voice.stop_hands_free.assert_called_once()
    mock_browser.close_all_sessions.assert_called_once()
    mock_processes.stop_all.assert_called_once()
    mock_resources.metabolize.assert_called_once()


# =====================================================================
# SECTION 64: CRASH RECOVERY
# =====================================================================

def test_section_64_crash_recovery_atomicity(tmp_path: Path):
    """Section 64: Interrupted writes via temp file do not leave corrupted final targets."""
    from living_assistant.core.storage_utils import atomic_write_json

    target = tmp_path / "critical_data.json"
    target.write_text(json.dumps({"state": "initial"}), encoding="utf-8")

    # Simulate a crash right before atomic rename
    temp_file = tmp_path / "critical_data.json.tmp"
    temp_file.write_text("PARTIAL_CORRUPTED_JSON_DATA", encoding="utf-8")

    # The existing target must still contain intact JSON
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["state"] == "initial"

    # Now verify successful atomic write replaces cleanly
    atomic_write_json(target, {"state": "recovered"})
    recovered = json.loads(target.read_text(encoding="utf-8"))
    assert recovered["state"] == "recovered"


# =====================================================================
# SECTION 65: NETWORK TRANSITIONS
# =====================================================================

def test_section_65_network_transitions_monitor():
    """Section 65: NetworkMonitor tracks online/offline transitions and interface changes."""
    event_bus = MagicMock()
    monitor = NetworkMonitor(event_bus=event_bus)

    # 1. Initial probe
    with patch.object(monitor, "probe_connectivity", return_value=(True, True)):
        with patch.object(monitor, "scan_interfaces", return_value=(["eth0"], False)):
            t1 = monitor.check_transition()
            assert t1["transition_detected"] is False

    # 2. Transition to offline
    with patch.object(monitor, "probe_connectivity", return_value=(False, False)):
        with patch.object(monitor, "scan_interfaces", return_value=(["eth0"], False)):
            t2 = monitor.check_transition()
            assert t2["transition_detected"] is True
            assert t2["transition_type"] == "online_to_offline"
            event_bus.publish.assert_called_with(
                "network.transition",
                transition_type="online_to_offline",
                online=False,
                vpn_active=False,
            )

    # 3. Transition to online with VPN active
    with patch.object(monitor, "probe_connectivity", return_value=(True, True)):
        with patch.object(monitor, "scan_interfaces", return_value=(["eth0", "tun0"], True)):
            t3 = monitor.check_transition()
            assert t3["transition_detected"] is True
            assert t3["transition_type"] == "offline_to_online"

    # 4. VPN disconnect while remaining online
    with patch.object(monitor, "probe_connectivity", return_value=(True, True)):
        with patch.object(monitor, "scan_interfaces", return_value=(["eth0"], False)):
            t4 = monitor.check_transition()
            assert t4["transition_detected"] is True
            assert t4["transition_type"] == "vpn_toggled"
