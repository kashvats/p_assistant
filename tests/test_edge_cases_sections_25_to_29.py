from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from living_assistant.desktop.voice import VoiceEngine


class DummyWorkspace:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path

    def resolve(self, path: str) -> Path:
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


class DummyApproval:
    def request(self, action: str, reason: str, kind: str = "SENSITIVE_READ") -> dict:
        return {"allowed": True, "action": action, "kind": kind}


def test_section_25_voice_input_no_device_failure(tmp_path: Path):
    """Section 25: Handle missing/disconnected microphone gracefully without crash."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    engine = VoiceEngine(ws, approval, config={"voice": {"enabled": True}})

    mock_sd = MagicMock()
    mock_sd.rec.side_effect = RuntimeError("PortAudioError: No default input device")
    mock_np = MagicMock()

    with patch.object(engine, "_import_audio", return_value=(mock_sd, mock_np)):
        res = engine.record("test.wav", seconds=1.0)
        assert res["ok"] is False
        assert "Microphone capture failed" in res["error"]


def test_section_26_voice_interruption_barge_in(tmp_path: Path):
    """Section 26: Barge-in stops TTS playback when user starts talking."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    engine = VoiceEngine(
        ws,
        approval,
        config={
            "voice": {
                "enabled": True,
                "hands_free": {
                    "barge_in_enabled": True,
                    "barge_in_rms": 500.0,
                    "barge_in_blocks": 1,
                },
            }
        },
    )

    mock_pyttsx3 = MagicMock()
    mock_engine = MagicMock()
    # Simulate speech taking time so barge-in listener catches incoming audio
    import time
    mock_engine.runAndWait.side_effect = lambda: time.sleep(0.3)
    mock_pyttsx3.init.return_value = mock_engine

    import numpy as np
    mock_sd = MagicMock()
    mock_stream = MagicMock()
    # High RMS samples simulating user speaking over TTS
    loud_samples = np.full(1280, 2000, dtype=np.int16)
    mock_stream.__enter__.return_value.read.return_value = (loud_samples.tobytes(), False)
    mock_sd.RawInputStream.return_value = mock_stream

    with patch.dict(sys.modules, {"pyttsx3": mock_pyttsx3}):
        with patch.object(engine, "_import_audio", return_value=(mock_sd, np)):
            res = engine.speak("Here is a very long response that gets interrupted.", allow_barge_in=True)
            assert res["ok"] is True
            assert res["interrupted"] is True
            mock_engine.stop.assert_called()


def test_section_27_voice_echo_suppression(tmp_path: Path):
    """Section 27: Recording is suppressed while assistant is speaking to prevent echo."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    engine = VoiceEngine(ws, approval, config={"voice": {"enabled": True}})

    # Simulate speaking state
    engine._is_speaking = True
    assert engine.is_speaking() is True

    # Attempt to record while assistant speaks -> must be suppressed
    res_record = engine.record("echo.wav")
    assert res_record["ok"] is False
    assert res_record["suppressed"] is True
    assert "echo prevention" in res_record["error"]

    res_vad = engine.record_until_silence("echo_vad.wav")
    assert res_vad["ok"] is False
    assert res_vad["suppressed"] is True
    assert "echo prevention" in res_vad["error"]

    # When speaking ceases, suppression is lifted
    engine._is_speaking = False
    assert engine.is_speaking() is False


def test_section_28_stt_confidence_scoring(tmp_path: Path):
    """Section 28: STT returns confidence score for gating high-risk actions."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    engine = VoiceEngine(ws, approval, config={"voice": {"enabled": True}})

    test_wav = ws.resolve("sample.wav")
    test_wav.write_bytes(b"dummy wav data")

    mock_whisper = MagicMock()
    # Mock segments with avg_logprob: log(0.3) = -1.20397 (low confidence transcription)
    seg1 = MagicMock()
    seg1.text = "delete repo"
    seg1.avg_logprob = -1.20397  # approx 0.3 probability

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_whisper.transcribe.return_value = ([seg1], mock_info)

    with patch.object(engine, "_load_stt", return_value=mock_whisper):
        res = engine.transcribe(str(test_wav))
        assert res["ok"] is True
        assert res["text"] == "delete repo"
        assert "confidence" in res
        # Confidence reflects the low certainty (~0.3)
        assert res["confidence"] < 0.5


def test_section_29_tts_engine_failure_fallback(tmp_path: Path):
    """Section 29: TTS failure falls back gracefully without breaking text response."""
    ws = DummyWorkspace(tmp_path)
    approval = DummyApproval()
    engine = VoiceEngine(ws, approval, config={"voice": {"enabled": True}})

    # pyttsx3 init throws an error (e.g. sound driver missing or comtypes failure)
    mock_pyttsx3 = MagicMock()
    mock_pyttsx3.init.side_effect = RuntimeError("Audio driver initialization failed")

    with patch.dict(sys.modules, {"pyttsx3": mock_pyttsx3}):
        res = engine.speak("Important text information")
        assert res["ok"] is False
        assert "TTS engine failed" in res["error"]
        assert res["fallback_text"] == "Important text information"
        # Engine must not be stuck in speaking state
        assert engine.is_speaking() is False
