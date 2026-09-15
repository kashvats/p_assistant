from __future__ import annotations
from dataclasses import dataclass, field
import wave
from .workspace import Workspace
from .approval import ApprovalManager

@dataclass
class VoiceEngine:
    """Optional local push-to-talk voice layer.

    The daemon never records audio. Recording only happens when an explicit tool/CLI
    action requests it and the approval policy allows microphone access.
    """
    workspace: Workspace
    approval: ApprovalManager
    config: dict
    profile: str = 'balanced'
    _stt_model: object | None = field(default=None, init=False, repr=False)
    _stt_model_name: str | None = field(default=None, init=False, repr=False)
    _approved_audio: set[str] = field(default_factory=set, init=False, repr=False)

    def enabled(self) -> bool:
        cfg = self.config.get('voice', {})
        if self.profile == 'lite' and not cfg.get('lite_enabled', False):
            return False
        return bool(cfg.get('enabled', False))

    def record(self, destination: str = 'artifacts/voice-input.wav', seconds: float = 6.0,
               sample_rate: int = 16000) -> dict:
        if not self.enabled():
            return {'ok': False, 'error': 'Voice is disabled for this hardware/config profile.'}
        seconds = max(0.5, min(float(seconds), 60.0))
        sample_rate = max(8000, min(int(sample_rate), 48000))
        target = self.workspace.resolve(destination)
        req = self.approval.request(
            f'Record microphone for {seconds:.1f}s -> {target}',
            'Microphone audio can contain sensitive conversations or ambient information.',
            'SENSITIVE_READ',
        )
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError as e:
            raise RuntimeError('Voice recording is optional. Install with: pip install -e ".[voice]"') from e
        frames = int(seconds * sample_rate)
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(np.asarray(audio, dtype='int16').tobytes())
        self._approved_audio.add(str(target))
        return {'ok': True, 'path': str(target), 'seconds': seconds, 'sample_rate': sample_rate}

    def _load_stt(self, model_name: str):
        if self._stt_model is not None and self._stt_model_name == model_name:
            return self._stt_model
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError('Local STT is optional. Install with: pip install -e ".[voice]"') from e
        cfg = self.config.get('voice', {})
        device = str(cfg.get('stt_device', 'cpu'))
        compute_type = str(cfg.get('stt_compute_type', 'int8'))
        self._stt_model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self._stt_model_name = model_name
        return self._stt_model

    def transcribe(self, path: str, language: str | None = None) -> dict:
        if not self.enabled():
            return {'ok': False, 'error': 'Voice is disabled for this hardware/config profile.'}
        source = self.workspace.resolve(path)
        if not source.exists():
            return {'ok': False, 'error': f'Audio file not found: {source}'}
        if str(source) not in self._approved_audio:
            req = self.approval.request(
                f'Transcribe local audio file {source}',
                'Audio files can contain sensitive speech or ambient information.',
                'SENSITIVE_READ',
            )
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req}
            self._approved_audio.add(str(source))
        cfg = self.config.get('voice', {})
        model_name = str(cfg.get('stt_model_lite' if self.profile == 'lite' else 'stt_model', 'tiny'))
        model = self._load_stt(model_name)
        segments, info = model.transcribe(str(source), language=language or None, vad_filter=True)
        parts = []
        for seg in segments:
            text = (seg.text or '').strip()
            if text:
                parts.append(text)
        return {
            'ok': True,
            'text': ' '.join(parts).strip(),
            'language': getattr(info, 'language', language),
            'model': model_name,
        }

    def speak(self, text: str) -> dict:
        if not self.enabled():
            return {'ok': False, 'error': 'Voice is disabled for this hardware/config profile.'}
        try:
            import pyttsx3
        except ImportError as e:
            raise RuntimeError('Local TTS is optional. Install with: pip install -e ".[voice]"') from e
        engine = pyttsx3.init()
        rate = self.config.get('voice', {}).get('tts_rate')
        if rate:
            engine.setProperty('rate', int(rate))
        engine.say(text[:12000])
        engine.runAndWait()
        return {'ok': True, 'characters': min(len(text), 12000)}

    def sleep(self):
        self._stt_model = None
        self._stt_model_name = None
        self._approved_audio.clear()
