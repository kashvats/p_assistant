from types import SimpleNamespace

from fastapi.testclient import TestClient


class FakeVoice:
    def __init__(self):
        self.recorded = False
        self.hands_free = False

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

    def start_hands_free(self, callback):
        self.hands_free = True
        self.callback = callback
        return {"ok": True, "hands_free_running": True}

    def stop_hands_free(self):
        self.hands_free = False
        return {"ok": True, "hands_free_running": False}


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
        ("open my project", "The user issued this request by voice.", "desktop-companion")
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


def test_voice_status_exposes_hands_free_readiness(monkeypatch):
    import living_assistant.api as api

    voice = FakeVoice()
    voice.status = lambda: {
        "enabled": True,
        "hands_free_enabled": True,
        "hands_free_running": False,
        "dependencies": {"openwakeword": True},
    }
    runtime = SimpleNamespace(
        voice=voice,
        model_manager=FakeModels(),
    )
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "voice-status-token")
    response = TestClient(api.app).get(
        "/voice/status",
        headers={"Authorization": "Bearer voice-status-token"},
    )
    assert response.status_code == 200
    assert response.json()["hands_free_enabled"] is True
    assert response.json()["model_provider"]["mode"] == "local"


def test_hands_free_start_and_stop_use_local_model(monkeypatch):
    import living_assistant.api as api

    voice = FakeVoice()
    voice.status = lambda: {
        "enabled": True,
        "hands_free_enabled": True,
        "hands_free_running": voice.hands_free,
    }
    runtime = SimpleNamespace(
        voice=voice,
        model_manager=FakeModels(),
        orchestrator=SimpleNamespace(model="qwen3.5:4b"),
        events_bus=None,
    )
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setattr(api, "_auth", lambda authorization: None)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "voice-hands-free-token")
    client = TestClient(api.app)

    started = client.post(
        "/voice/hands-free",
        headers={"Authorization": "******"},
        json={"enabled": True},
    )
    stopped = client.post(
        "/voice/hands-free",
        headers={"Authorization": "******"},
        json={"enabled": False},
    )

    assert started.status_code == 200
    assert started.json()["hands_free_running"] is True
    assert stopped.status_code == 200
    assert stopped.json()["hands_free_running"] is False
