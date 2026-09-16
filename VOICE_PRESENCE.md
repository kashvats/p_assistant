# Voice Presence — v0.11.0

v0.11 adds an optional local hands-free voice path while keeping push-to-talk as the conservative fallback.

## Architecture

`microphone -> tiny wake-word model -> adaptive local VAD -> faster-whisper -> orchestrator -> local TTS`

The wake detector is the only component intended to stay active during a presence session. Whisper is loaded lazily after wake activation and can be released with the rest of the voice stack.

## Privacy and approval boundaries

- Hands-free mode is disabled by default.
- Starting `organism voice presence` is an explicit user action.
- Microphone listening requires approval and uses a bounded lease rather than permanent permission.
- Wake/STT/TTS processing is local unless the user separately configures non-local components elsewhere.
- Wake models are never downloaded automatically. `organism voice wake-model-download` is an explicit network action and requires approval.
- Barge-in microphone monitoring is separately approval-aware; denial falls back to ordinary TTS instead of failing speech output.

## Wake models

The default configuration names the openWakeWord `hey_jarvis` model because it is a commonly available pretrained model. A custom phrase such as `Hey Assistant` requires a compatible local `.onnx` or `.tflite` wake model. Set:

```yaml
voice:
  hands_free:
    enabled: true
    wake_model: /absolute/path/to/hey_assistant.onnx
    wake_phrase_text: "hey assistant"
```

You can also use the configured official model name:

```bash
organism voice wake-model-download hey_jarvis
```

## Commands

```bash
organism voice status
organism voice record-utterance
organism voice wake --timeout 30
organism voice wake-model-download hey_jarvis
organism voice presence
```

`presence` keeps listening until Ctrl+C by default. Use `--max-turns` for bounded testing. After an answer, an optional short follow-up window allows conversational continuation without another wake phrase. TTS can be interrupted when barge-in is enabled.

## Resource behavior

- `lite`: hands-free disabled unless separately opted in.
- `balanced/power`: wake listener may be enabled, but still remains opt-in.
- Wake model and Whisper model are lazy-loaded.
- `VoiceEngine.sleep()` releases model references and microphone leases.

## Known limitations

- No acoustic echo cancellation is bundled; loud speaker output can make RMS-based barge-in less reliable. Headphones improve behavior.
- Speaker identification is not part of v0.11.
- Neural emotional/prosody-aware TTS is not part of v0.11; TTS remains the existing local engine.
- A custom `Hey Assistant` wake phrase requires a custom/pretrained compatible model; v0.11 does not train one automatically.
