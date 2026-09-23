from types import SimpleNamespace

from fastapi.testclient import TestClient


class FakeVoice:
    def __init__(self):
        self.recorded = False

    def status(self):
        return {"enabled": True, "hands_free_enabled": False}

    def record_until_silence(self, *args, **kwargs):
        self.recorded = True
        return {"ok": True, "path": "artifacts/voice-input.wav"}

    def transcribe(self, path, language=None):
        return {"ok": True, "text": "open my project"}

    def clean_command_text(self, text):
        return text

    def speak(self, text):
        return {"ok": True}


class FakeModels:
    active_model = "qwen3.5:4b"

    def provider_info(self, model=None):
        return {
            "id": "ollama",
            "name": "Ollama (local)",
            "mode": "local",
            "local": True,
            "credentials_required": False,
            "model": model or self.active_model,
        }

    def validate_model_selection(self, model):
        return {"ok": True, "provider": self.provider_info(model)}


def test_voice_ask_runs_local_record_transcribe_and_orchestrator(monkeypatch):
    import living_assistant.api as api

    voice = FakeVoice()
    calls = []
    runtime = SimpleNamespace(
        voice=voice,
        model_manager=FakeModels(),
        orchestrator=SimpleNamespace(
            model="qwen3.5:4b",
            run=lambda message, context="", session_id=None: calls.append(
                (message, context, session_id)
            )
            or "Done locally.",
        ),
    )
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "voice-local-token")
    client = TestClient(api.app)

    response = client.post(
        "/voice/ask",
        headers={"Authorization": "Bearer voice-local-token"},
        json={"max_seconds": 5, "speak": False},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["transcript"] == "open my project"
    assert calls == [
        ("open my project", "The user issued this request by voice.", "voice-companion")
    ]
    assert voice.recorded is True


def test_voice_ask_rejects_unconfigured_online_model_before_microphone(monkeypatch):
    import living_assistant.api as api

    voice = FakeVoice()
    models = FakeModels()
    models.active_model = "openai:gpt-4o"
    provider = {
        "id": "openai",
        "name": "OpenAI",
        "mode": "online",
        "local": False,
        "credentials_required": True,
        "credentials_configured": False,
        "credential_env": "OPENAI_API_KEY",
        "credential_label": "OpenAI API key",
        "model": models.active_model,
    }
    models.provider_info = lambda model=None: provider
    models.validate_model_selection = lambda model: {
        "ok": False,
        "provider": provider,
        "error": "OpenAI requires OPENAI_API_KEY.",
    }
    runtime = SimpleNamespace(
        voice=voice,
        model_manager=models,
        orchestrator=SimpleNamespace(model=models.active_model),
    )
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "voice-online-token")
    client = TestClient(api.app)

    response = client.post(
        "/voice/ask",
        headers={"Authorization": "Bearer voice-online-token"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["stage"] == "model"
    assert "OPENAI_API_KEY" in response.json()["error"]
    assert voice.recorded is False
