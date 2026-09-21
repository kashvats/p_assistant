from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import importlib.util
from collections import deque
import math
import threading
import time
import wave

from living_assistant.core.workspace import Workspace
from living_assistant.core.approval import ApprovalManager
from living_assistant.core.config import data_dir


@dataclass
class VoiceEngine:
    """Optional local voice layer.

    Push-to-talk remains the safe fallback. Hands-free wake-word listening is opt-in,
    requires explicit microphone approval for each listener session, and keeps audio
    local. Heavy STT and wake models are loaded lazily and released by ``sleep()``.
    """

    workspace: Workspace
    approval: ApprovalManager
    config: dict
    profile: str = "balanced"
    _stt_model: object | None = field(default=None, init=False, repr=False)
    _stt_model_name: str | None = field(default=None, init=False, repr=False)
    _wake_model: object | None = field(default=None, init=False, repr=False)
    _wake_model_key: str | None = field(default=None, init=False, repr=False)
    _approved_audio: set[str] = field(default_factory=set, init=False, repr=False)
    _mic_lease_until: float = field(default=0.0, init=False, repr=False)

    def _cfg(self) -> dict:
        return self.config.get("voice", {})

    def enabled(self) -> bool:
        cfg = self._cfg()
        if self.profile == "lite" and not cfg.get("lite_enabled", False):
            return False
        return bool(cfg.get("enabled", False))

    def hands_free_enabled(self) -> bool:
        cfg = self._cfg().get("hands_free", {})
        if not self.enabled() or not bool(cfg.get("enabled", False)):
            return False
        if self.profile == "lite" and not bool(cfg.get("lite_enabled", False)):
            return False
        return True

    @staticmethod
    def _module_available(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, AttributeError, ValueError):
            return False

    def status(self) -> dict:
        cfg = self._cfg()
        hcfg = cfg.get("hands_free", {})
        return {
            "enabled": self.enabled(),
            "hands_free_enabled": self.hands_free_enabled(),
            "profile": self.profile,
            "dependencies": {
                "sounddevice": self._module_available("sounddevice"),
                "numpy": self._module_available("numpy"),
                "faster_whisper": self._module_available("faster_whisper"),
                "pyttsx3": self._module_available("pyttsx3"),
                "openwakeword": self._module_available("openwakeword"),
            },
            "wake_model": hcfg.get("wake_model") or hcfg.get("wake_model_name", "hey_jarvis"),
            "wake_threshold": float(hcfg.get("wake_threshold", 0.5)),
            "barge_in_enabled": bool(hcfg.get("barge_in_enabled", False)),
            "language": cfg.get("language") or "auto",
        }

    def _ensure_microphone_approval(self, action: str, reason: str, lease_seconds: float = 0.0) -> dict:
        now = time.monotonic()
        if now < self._mic_lease_until:
            return {"allowed": True, "leased": True}
        req = self.approval.request(action, reason, "SENSITIVE_READ")
        if req.get("allowed") and lease_seconds > 0:
            max_lease = float(self._cfg().get("max_microphone_lease_seconds", 300.0))
            self._mic_lease_until = now + min(max(0.0, lease_seconds), max(1.0, max_lease))
        return req

    @staticmethod
    def _import_audio():
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError as e:
            raise RuntimeError('Voice recording is optional. Install with: pip install -e ".[voice]"') from e
        return sd, np

    @staticmethod
    def _write_wav(path: Path, audio, sample_rate: int, np) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(np.asarray(audio, dtype="int16").tobytes())

    def record(
        self,
        destination: str = "artifacts/voice-input.wav",
        seconds: float = 6.0,
        sample_rate: int = 16000,
    ) -> dict:
        seconds = max(0.5, min(float(seconds), 60.0))
        sample_rate = max(8000, min(int(sample_rate), 48000))
        target = self.workspace.resolve(destination)
        req = self._ensure_microphone_approval(
            f"Record microphone for {seconds:.1f}s -> {target}",
            "Microphone audio can contain sensitive conversations or ambient information.",
        )
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}
        sd, np = self._import_audio()
        frames = int(seconds * sample_rate)
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        self._write_wav(target, audio, sample_rate, np)
        self._approved_audio.add(str(target))
        return {"ok": True, "path": str(target), "seconds": seconds, "sample_rate": sample_rate}

    def record_until_silence(
        self,
        destination: str = "artifacts/voice-input.wav",
        max_seconds: float | None = None,
        min_seconds: float | None = None,
        silence_seconds: float | None = None,
        sample_rate: int = 16000,
    ) -> dict:
        """Record one utterance using a lightweight adaptive RMS VAD.

        The detector calibrates against ambient audio, waits for speech, preserves a
        small pre-roll, then stops after sustained silence. It intentionally avoids a
        second neural VAD process so hands-free mode remains viable on small machines.
        """
        if not self.enabled():
            return {"ok": False, "error": "Voice is disabled for this hardware/config profile."}
        cfg = self._cfg()
        vcfg = cfg.get("vad", {})
        max_seconds = min(max(float(max_seconds or vcfg.get("max_seconds", 15.0)), 1.0), 60.0)
        min_seconds = min(max(float(min_seconds or vcfg.get("min_seconds", 0.35)), 0.1), max_seconds)
        silence_seconds = min(max(float(silence_seconds or vcfg.get("silence_seconds", 0.9)), 0.2), 5.0)
        sample_rate = max(8000, min(int(sample_rate), 48000))
        block_ms = min(max(int(vcfg.get("block_ms", 80)), 20), 250)
        block_frames = max(1, int(sample_rate * block_ms / 1000))
        calibration_seconds = min(max(float(vcfg.get("calibration_seconds", 0.4)), 0.08), 2.0)
        pre_roll_seconds = min(max(float(vcfg.get("pre_roll_seconds", 0.24)), 0.0), 1.0)
        min_rms = max(float(vcfg.get("min_rms", 250.0)), 1.0)
        noise_multiplier = max(float(vcfg.get("noise_multiplier", 3.0)), 1.1)
        target = self.workspace.resolve(destination)

        req = self._ensure_microphone_approval(
            f"Listen for one spoken utterance -> {target}",
            "Voice activity capture uses the microphone and can contain sensitive ambient information.",
            lease_seconds=max_seconds + 5.0,
        )
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}

        sd, np = self._import_audio()
        calibration_blocks = max(1, math.ceil(calibration_seconds * 1000 / block_ms))
        pre_roll_blocks = max(0, math.ceil(pre_roll_seconds * 1000 / block_ms))
        silence_blocks_needed = max(1, math.ceil(silence_seconds * 1000 / block_ms))
        min_speech_blocks = max(1, math.ceil(min_seconds * 1000 / block_ms))
        max_blocks = max(1, math.ceil(max_seconds * 1000 / block_ms))

        noise_levels: list[float] = []
        pre_roll: list[object] = []
        captured: list[object] = []
        speech_started = False
        speech_blocks = 0
        quiet_blocks = 0
        threshold = min_rms

        with sd.RawInputStream(samplerate=sample_rate, blocksize=block_frames, channels=1, dtype="int16") as stream:
            for i in range(max_blocks):
                raw, overflowed = stream.read(block_frames)
                if overflowed:
                    # Overflow does not invalidate the utterance; continue with the available block.
                    pass
                samples = np.frombuffer(raw, dtype=np.int16).copy()
                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) if samples.size else 0.0

                if i < calibration_blocks:
                    noise_levels.append(rms)
                    pre_roll.append(samples)
                    pre_roll = pre_roll[-pre_roll_blocks:] if pre_roll_blocks else []
                    continue

                if noise_levels:
                    threshold = max(min_rms, float(np.median(noise_levels)) * noise_multiplier)

                if not speech_started:
                    pre_roll.append(samples)
                    pre_roll = pre_roll[-pre_roll_blocks:] if pre_roll_blocks else []
                    if rms >= threshold:
                        speech_started = True
                        captured.extend(pre_roll)
                        pre_roll.clear()
                        speech_blocks = 1
                    continue

                captured.append(samples)
                speech_blocks += 1
                if rms < threshold:
                    quiet_blocks += 1
                else:
                    quiet_blocks = 0
                if speech_blocks >= min_speech_blocks and quiet_blocks >= silence_blocks_needed:
                    break

        if not speech_started or not captured:
            return {"ok": False, "error": "No speech detected before timeout.", "threshold_rms": round(threshold, 2)}
        audio = np.concatenate(captured)
        self._write_wav(target, audio, sample_rate, np)
        self._approved_audio.add(str(target))
        return {
            "ok": True,
            "path": str(target),
            "sample_rate": sample_rate,
            "seconds": round(len(audio) / sample_rate, 3),
            "threshold_rms": round(threshold, 2),
        }

    def _load_stt(self, model_name: str):
        if self._stt_model is not None and self._stt_model_name == model_name:
            return self._stt_model
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError('Local STT is optional. Install with: pip install -e ".[voice]"') from e
        cfg = self._cfg()
        device = str(cfg.get("stt_device", "cpu"))
        compute_type = str(cfg.get("stt_compute_type", "int8"))
        self._stt_model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self._stt_model_name = model_name
        return self._stt_model

    def transcribe(self, path: str, language: str | None = None) -> dict:
        source = self.workspace.resolve(path)
        if not source.exists():
            return {"ok": False, "error": f"Audio file not found: {source}"}
        if str(source) not in self._approved_audio:
            req = self.approval.request(
                f"Transcribe local audio file {source}",
                "Audio files can contain sensitive speech or ambient information.",
                "SENSITIVE_READ",
            )
            if not req.get("allowed"):
                return {"ok": False, "approval_required": True, **req}
            self._approved_audio.add(str(source))
        cfg = self._cfg()
        model_name = str(cfg.get("stt_model_lite" if self.profile == "lite" else "stt_model", "tiny"))
        model = self._load_stt(model_name)
        configured_language = cfg.get("language")
        selected_language = language or (None if configured_language in {None, "", "auto"} else str(configured_language))
        segments, info = model.transcribe(str(source), language=selected_language, vad_filter=True)
        parts = []
        for seg in segments:
            text = (seg.text or "").strip()
            if text:
                parts.append(text)
        return {
            "ok": True,
            "text": " ".join(parts).strip(),
            "language": getattr(info, "language", selected_language),
            "model": model_name,
        }

    def _wake_model_paths(self) -> list[str]:
        cfg = self._cfg().get("hands_free", {})
        explicit = str(cfg.get("wake_model", "") or "").strip()
        if explicit:
            p = Path(explicit).expanduser()
            if not p.is_absolute():
                p = self.workspace.resolve(explicit)
            if not p.exists():
                raise RuntimeError(f"Configured wake-word model does not exist: {p}")
            return [str(p)]
        try:
            import openwakeword
        except ImportError as e:
            raise RuntimeError('Wake-word detection is optional. Install with: pip install -e ".[voice,wakeword]"') from e
        name = str(cfg.get("wake_model_name", "hey_jarvis") or "hey_jarvis").lower()
        local_dir = data_dir() / "wake_models"
        if local_dir.exists():
            framework = str(cfg.get("inference_framework", "onnx")).lower()
            preferred = ".onnx" if framework == "onnx" else ".tflite"
            local = [p for p in local_dir.iterdir() if p.is_file() and name in p.name.lower()]
            local.sort(key=lambda p: (p.suffix.lower() != preferred, p.name))
            if local:
                return [str(local[0])]
        try:
            paths = list(openwakeword.get_pretrained_model_paths())
        except Exception:
            paths = []
        matched = [str(p) for p in paths if name in Path(str(p)).name.lower()]
        if matched:
            return matched[:1]
        raise RuntimeError(
            f'Wake model "{name}" is not installed. Install openWakeWord models explicitly or set voice.hands_free.wake_model to a local .onnx/.tflite model.'
        )

    def download_wake_model(self, model_name: str | None = None) -> dict:
        """Explicitly download an official openWakeWord model into user data.

        This is never performed automatically because model downloads are network and
        supply-chain actions. The user must invoke the command and approve it.
        """
        if not self.enabled():
            return {"ok": False, "error": "Voice is disabled for this hardware/config profile."}
        cfg = self._cfg().get("hands_free", {})
        name = str(model_name or cfg.get("wake_model_name", "hey_jarvis") or "hey_jarvis").strip()
        req = self.approval.request(
            f'Download official openWakeWord model "{name}"',
            "This fetches model files from the upstream openWakeWord release URLs into the local assistant data directory.",
            "NETWORK_FETCH",
        )
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}
        try:
            from openwakeword import utils as oww_utils
        except ImportError as e:
            raise RuntimeError('Wake-word detection is optional. Install with: pip install -e ".[voice,wakeword]"') from e
        target = data_dir() / "wake_models"
        target.mkdir(parents=True, exist_ok=True)
        oww_utils.download_models(model_names=[name], target_directory=str(target))
        matches = sorted(str(p) for p in target.iterdir() if p.is_file() and name.lower() in p.name.lower())
        if not matches:
            return {"ok": False, "error": f'No downloaded model matched "{name}". Check the official openWakeWord model name.'}
        return {"ok": True, "model_name": name, "directory": str(target), "files": matches}

    def clean_command_text(self, text: str, wake_word: str | None = None) -> str:
        """Remove a configured wake phrase only when it is a leading transcript prefix."""
        value = (text or "").strip()
        cfg = self._cfg().get("hands_free", {})
        phrases = []
        configured = str(cfg.get("wake_phrase_text", "") or "").strip()
        if configured:
            phrases.append(configured)
        if wake_word:
            phrases.append(str(wake_word).replace("_", " "))
        lower = value.casefold()
        for phrase in phrases:
            p = phrase.casefold().strip()
            if p and lower.startswith(p):
                remainder = value[len(phrase):].lstrip(" ,.!?:;-\t")
                if remainder:
                    return remainder
        return value

    def _load_wake_model(self):
        cfg = self._cfg().get("hands_free", {})
        paths = self._wake_model_paths()
        framework = str(cfg.get("inference_framework", "onnx"))
        key = f"{framework}:{'|'.join(paths)}"
        if self._wake_model is not None and self._wake_model_key == key:
            return self._wake_model
        try:
            from openwakeword.model import Model
        except ImportError as e:
            raise RuntimeError('Wake-word detection is optional. Install with: pip install -e ".[voice,wakeword]"') from e
        kwargs = {
            "wakeword_models": paths,
            "inference_framework": framework,
        }
        if "vad_threshold" in cfg:
            kwargs["vad_threshold"] = float(cfg.get("vad_threshold", 0.0))
        if bool(cfg.get("noise_suppression", False)):
            kwargs["enable_speex_noise_suppression"] = True
        self._wake_model = Model(**kwargs)
        self._wake_model_key = key
        return self._wake_model

    def listen_for_wake_word(self, timeout_seconds: float | None = None) -> dict:
        if not self.hands_free_enabled():
            return {"ok": False, "error": "Hands-free wake-word mode is disabled for this profile/config."}
        cfg = self._cfg().get("hands_free", {})
        timeout = float(cfg.get("wake_timeout_seconds", 0.0) if timeout_seconds is None else timeout_seconds)
        timeout = max(0.0, min(timeout, 86400.0))
        threshold = min(max(float(cfg.get("wake_threshold", 0.5)), 0.01), 0.99)
        sample_rate = 16000
        chunk_ms = min(max(int(cfg.get("wake_chunk_ms", 80)), 40), 240)
        chunk_frames = int(sample_rate * chunk_ms / 1000)
        lease = (timeout if timeout > 0 else float(cfg.get("max_listener_lease_seconds", 300.0))) + 30.0
        req = self._ensure_microphone_approval(
            "Start hands-free local wake-word microphone listener",
            "Always-listening wake-word detection continuously samples local microphone audio until stopped or timed out.",
            lease_seconds=lease,
        )
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}

        sd, np = self._import_audio()
        model = self._load_wake_model()
        started = time.monotonic()
        best_score = 0.0
        best_label = None
        with sd.RawInputStream(samplerate=sample_rate, blocksize=chunk_frames, channels=1, dtype="int16") as stream:
            while True:
                if timeout and time.monotonic() - started >= timeout:
                    return {"ok": False, "timeout": True, "best_score": round(best_score, 4)}
                raw, _overflowed = stream.read(chunk_frames)
                samples = np.frombuffer(raw, dtype=np.int16).copy()
                prediction = model.predict(samples) or {}
                for label, score in prediction.items():
                    try:
                        value = float(score)
                    except (TypeError, ValueError):
                        continue
                    if value > best_score:
                        best_score, best_label = value, str(label)
                    if value >= threshold:
                        return {
                            "ok": True,
                            "detected": True,
                            "wake_word": str(label),
                            "score": round(value, 4),
                            "threshold": threshold,
                        }

    def listen_for_command(
        self,
        destination: str = "artifacts/voice-input.wav",
        timeout_seconds: float | None = None,
    ) -> dict:
        """Wait for the wake word and capture the following utterance on one stream.

        A small rolling audio tail is kept so speech that starts immediately after the
        wake phrase is not lost while the microphone device is being reopened.
        """
        if not self.hands_free_enabled():
            return {"ok": False, "error": "Hands-free wake-word mode is disabled for this profile/config."}
        cfg = self._cfg()
        hcfg = cfg.get("hands_free", {})
        vcfg = cfg.get("vad", {})
        timeout = float(hcfg.get("wake_timeout_seconds", 0.0) if timeout_seconds is None else timeout_seconds)
        timeout = max(0.0, min(timeout, 86400.0))
        threshold = min(max(float(hcfg.get("wake_threshold", 0.5)), 0.01), 0.99)
        sample_rate = 16000
        chunk_ms = min(max(int(hcfg.get("wake_chunk_ms", 80)), 40), 240)
        chunk_frames = int(sample_rate * chunk_ms / 1000)
        max_command_seconds = min(max(float(vcfg.get("max_seconds", 15.0)), 1.0), 60.0)
        silence_seconds = min(max(float(vcfg.get("silence_seconds", 0.9)), 0.2), 5.0)
        min_seconds = min(max(float(vcfg.get("min_seconds", 0.35)), 0.1), max_command_seconds)
        min_rms = max(float(vcfg.get("min_rms", 250.0)), 1.0)
        noise_multiplier = max(float(vcfg.get("noise_multiplier", 3.0)), 1.1)
        tail_seconds = min(max(float(hcfg.get("wake_audio_tail_seconds", 0.32)), 0.08), 1.0)
        tail_blocks = max(1, math.ceil(tail_seconds * 1000 / chunk_ms))
        silence_blocks_needed = max(1, math.ceil(silence_seconds * 1000 / chunk_ms))
        min_command_blocks = max(1, math.ceil(min_seconds * 1000 / chunk_ms))
        max_command_blocks = max(1, math.ceil(max_command_seconds * 1000 / chunk_ms))
        lease = (timeout if timeout > 0 else float(hcfg.get("max_listener_lease_seconds", 300.0))) + max_command_seconds + 30.0
        target = self.workspace.resolve(destination)

        req = self._ensure_microphone_approval(
            f"Wait for local wake word and capture the following utterance -> {target}",
            "Hands-free mode continuously samples local microphone audio until a wake word, then stores one spoken utterance.",
            lease_seconds=lease,
        )
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}

        sd, np = self._import_audio()
        model = self._load_wake_model()
        started = time.monotonic()
        tail = deque(maxlen=tail_blocks)
        ambient = deque(maxlen=max(10, math.ceil(3.0 * 1000 / chunk_ms)))
        best_score = 0.0
        best_label = None

        with sd.RawInputStream(samplerate=sample_rate, blocksize=chunk_frames, channels=1, dtype="int16") as stream:
            while True:
                if timeout and time.monotonic() - started >= timeout:
                    return {"ok": False, "timeout": True, "best_score": round(best_score, 4)}
                raw, _ = stream.read(chunk_frames)
                samples = np.frombuffer(raw, dtype=np.int16).copy()
                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) if samples.size else 0.0
                tail.append(samples)
                ambient.append(rms)
                prediction = model.predict(samples) or {}
                detected = None
                for label, score in prediction.items():
                    try:
                        value = float(score)
                    except (TypeError, ValueError):
                        continue
                    if value > best_score:
                        best_score, best_label = value, str(label)
                    if value >= threshold:
                        detected = (str(label), value)
                        break
                if detected is None:
                    continue

                # The median remains robust to the brief wake phrase itself while still
                # adapting to room noise accumulated during the listener phase.
                base_noise = float(np.median(list(ambient))) if ambient else 0.0
                speech_threshold = max(min_rms, base_noise * noise_multiplier)
                captured = list(tail)
                quiet_blocks = 0
                command_blocks = 0
                for _ in range(max_command_blocks):
                    raw, _ = stream.read(chunk_frames)
                    block = np.frombuffer(raw, dtype=np.int16).copy()
                    captured.append(block)
                    command_blocks += 1
                    rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2))) if block.size else 0.0
                    if rms < speech_threshold:
                        quiet_blocks += 1
                    else:
                        quiet_blocks = 0
                    if command_blocks >= min_command_blocks and quiet_blocks >= silence_blocks_needed:
                        break

                audio = np.concatenate(captured) if captured else np.zeros(0, dtype=np.int16)
                if audio.size == 0:
                    return {"ok": False, "error": "Wake word detected but no utterance audio was captured."}
                self._write_wav(target, audio, sample_rate, np)
                self._approved_audio.add(str(target))
                return {
                    "ok": True,
                    "detected": True,
                    "wake_word": detected[0],
                    "score": round(float(detected[1]), 4),
                    "threshold": threshold,
                    "path": str(target),
                    "seconds": round(len(audio) / sample_rate, 3),
                    "speech_threshold_rms": round(speech_threshold, 2),
                }

    def speak(self, text: str, allow_barge_in: bool = False) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "Voice is disabled for this hardware/config profile."}
        try:
            import pyttsx3
        except ImportError as e:
            raise RuntimeError('Local TTS is optional. Install with: pip install -e ".[voice]"') from e
        cfg = self._cfg()
        max_chars = int(cfg.get("tts_max_chars", 12000))
        spoken = text[:max(1, min(max_chars, 50000))]
        engine = pyttsx3.init()
        rate = cfg.get("tts_rate")
        if rate:
            engine.setProperty("rate", int(rate))
        volume = cfg.get("tts_volume")
        if volume is not None:
            engine.setProperty("volume", min(max(float(volume), 0.0), 1.0))
        hcfg = cfg.get("hands_free", {})
        if not (allow_barge_in and bool(hcfg.get("barge_in_enabled", False))):
            engine.say(spoken)
            engine.runAndWait()
            return {"ok": True, "characters": len(spoken), "interrupted": False}

        req = self._ensure_microphone_approval(
            "Monitor microphone for voice barge-in while assistant is speaking",
            "Barge-in detection samples microphone levels while TTS is active.",
            lease_seconds=90.0,
        )
        if not req.get("allowed"):
            # Refusing microphone monitoring should not prevent ordinary TTS.
            engine.say(spoken)
            engine.runAndWait()
            return {"ok": True, "characters": len(spoken), "interrupted": False, "barge_in_denied": True}

        sd, np = self._import_audio()
        threshold = max(float(hcfg.get("barge_in_rms", 1600.0)), 1.0)
        consecutive_needed = max(1, int(hcfg.get("barge_in_blocks", 3)))
        block_ms = 80
        block_frames = int(16000 * block_ms / 1000)
        done = threading.Event()
        interrupted = False

        def _speak() -> None:
            try:
                engine.say(spoken)
                engine.runAndWait()
            finally:
                done.set()

        thread = threading.Thread(target=_speak, name="living-assistant-tts", daemon=True)
        thread.start()
        loud_blocks = 0
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=block_frames, channels=1, dtype="int16") as stream:
                while not done.wait(0.01):
                    raw, _ = stream.read(block_frames)
                    samples = np.frombuffer(raw, dtype=np.int16)
                    rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) if samples.size else 0.0
                    loud_blocks = loud_blocks + 1 if rms >= threshold else 0
                    if loud_blocks >= consecutive_needed:
                        interrupted = True
                        engine.stop()
                        done.set()
                        break
        finally:
            thread.join(timeout=2.0)
        return {"ok": True, "characters": len(spoken), "interrupted": interrupted}

    def sleep(self):
        self._stt_model = None
        self._stt_model_name = None
        self._wake_model = None
        self._wake_model_key = None
        self._approved_audio.clear()
        self._mic_lease_until = 0.0
