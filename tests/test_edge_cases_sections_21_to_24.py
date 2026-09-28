from __future__ import annotations

import base64
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from living_assistant.desktop.desktop_intelligence import DesktopController, DesktopError


class DummyWorkspace:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path

    def resolve(self, path: str) -> Path:
        return self.root / path


class DummyApproval:
    def request(self, action: str, reason: str, kind: str = "DESKTOP_WRITE") -> dict:
        return {"allowed": True, "action": action, "kind": kind}


def test_section_21_multi_monitor_detection_and_invalid_id(tmp_path: Path):
    """Section 21: Verify multi-monitor enumeration and monitor ID validation."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    ctrl = DesktopController(ws, approval, config={})

    mock_monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},  # all-in-one index 0
        {"left": 0, "top": 0, "width": 1920, "height": 1080},  # monitor 1
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},  # monitor 2
    ]

    mock_mss_mod = MagicMock()
    mock_instance = MagicMock()
    mock_instance.monitors = mock_monitors
    mock_mss_mod.mss.return_value.__enter__.return_value = mock_instance

    with patch.dict(sys.modules, {"mss": mock_mss_mod}):
        monitors = ctrl.monitors()
        assert len(monitors) == 2
        assert monitors[0]["id"] == 1
        assert monitors[0]["primary"] is True
        assert monitors[0]["width"] == 1920
        assert monitors[1]["id"] == 2
        assert monitors[1]["primary"] is False
        assert monitors[1]["left"] == 1920

        # Invalid monitor ID must fail gracefully without crash
        res_invalid = ctrl.screenshot(monitor_id=99)
        assert res_invalid["ok"] is False
        assert res_invalid["error"] == "Unknown monitor id"


def test_section_22_screen_privacy_temporary_cleanup(tmp_path: Path):
    """Section 22: Verify temporary screenshots are cleaned up after analysis."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    provider = MagicMock()
    provider.base_url = "http://127.0.0.1:11434"
    provider.chat.return_value = {"message": {"content": "Window showing terminal."}}
    mm = MagicMock()
    mm.lease.return_value.__enter__.return_value = 45

    ctrl = DesktopController(
        ws,
        approval,
        config={"desktop": {"vision_enabled": True, "vision_model": "llava:7b"}},
        provider=provider,
        model_manager=mm,
    )

    created_tmp_files: list[Path] = []

    # Create a non-blank test image
    img = Image.new("RGB", (100, 100), color=(10, 20, 30))
    img.putpixel((50, 50), (255, 255, 255))  # make it non-uniform

    mock_grab = MagicMock()
    mock_grab.size = (100, 100)
    mock_grab.rgb = img.tobytes()

    mock_mss_mod = MagicMock()
    mock_instance = MagicMock()
    mock_instance.monitors = [{"left": 0, "top": 0, "width": 100, "height": 100}, {"left": 0, "top": 0, "width": 100, "height": 100}]
    mock_instance.grab.return_value = mock_grab
    mock_mss_mod.mss.return_value.__enter__.return_value = mock_instance

    with patch.dict(sys.modules, {"mss": mock_mss_mod}):
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            before = set(tmp_path.rglob("*"))
            res = ctrl.analyze_screen()
            assert res["ok"] is True
            assert res["analysis"] == "Window showing terminal."
            # Screenshots are encoded in memory: nothing is written to disk.
            mock_tmp.assert_not_called()
            assert set(tmp_path.rglob("*")) == before


def test_section_22_screen_privacy_remote_endpoint_blocked(tmp_path: Path):
    """Section 22: Remote vision is blocked if allow_remote_vision is false."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    provider = MagicMock()
    provider.base_url = "https://api.openai.com/v1"
    mm = MagicMock()

    ctrl = DesktopController(
        ws,
        approval,
        config={"desktop": {"vision_enabled": True, "vision_model": "gpt-4o", "allow_remote_vision": False}},
        provider=provider,
        model_manager=mm,
    )

    res = ctrl.analyze_screen()
    assert res["ok"] is False
    assert "Remote desktop vision is blocked" in res["error"]


def test_section_23_screen_freshness_timestamp_included(tmp_path: Path):
    """Section 23: Screenshots must include an internal capture timestamp."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    ctrl = DesktopController(ws, approval, config={})

    img = Image.new("RGB", (50, 50), color=(100, 150, 200))
    mock_grab = MagicMock()
    mock_grab.size = (50, 50)
    mock_grab.width = 50
    mock_grab.height = 50
    mock_grab.rgb = img.tobytes()

    mock_mss_mod = MagicMock()
    mock_instance = MagicMock()
    mock_instance.monitors = [{"left": 0, "top": 0, "width": 50, "height": 50}]
    mock_instance.grab.return_value = mock_grab
    mock_mss_mod.mss.return_value.__enter__.return_value = mock_instance

    with patch.dict(sys.modules, {"mss": mock_mss_mod}):
        res = ctrl.screenshot("test.png", monitor_id=0)
        assert res["ok"] is True
        assert "captured_at" in res
        # Verify valid ISO timestamp
        parsed = datetime.fromisoformat(res["captured_at"])
        assert parsed.tzinfo is not None


def test_section_24_vision_failure_blank_black_frame_detected(tmp_path: Path):
    """Section 24: Detect black/blank frames (UAC/DRM) and report actionable error."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    provider = MagicMock()
    provider.base_url = "http://127.0.0.1:11434"
    mm = MagicMock()

    ctrl = DesktopController(
        ws,
        approval,
        config={"desktop": {"vision_enabled": True, "vision_model": "llava:7b"}},
        provider=provider,
        model_manager=mm,
    )

    # Pure black frame (e.g. UAC secure desktop or DRM protected content)
    black_img = Image.new("RGB", (100, 100), color=(0, 0, 0))
    mock_grab = MagicMock()
    mock_grab.size = (100, 100)
    mock_grab.rgb = black_img.tobytes()

    mock_mss_mod = MagicMock()
    mock_instance = MagicMock()
    mock_instance.monitors = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    mock_instance.grab.return_value = mock_grab
    mock_mss_mod.mss.return_value.__enter__.return_value = mock_instance

    with patch.dict(sys.modules, {"mss": mock_mss_mod}):
        res = ctrl.analyze_screen()
        assert res["ok"] is False
        assert res.get("blank_frame") is True
        assert "blank/solid frame" in res["error"]
        assert "captured_at" in res
        # Ensure model provider chat was NEVER called to prevent hallucination
        provider.chat.assert_not_called()
