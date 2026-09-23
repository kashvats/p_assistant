from living_assistant.core.model_provider import ModelManager, OllamaProvider


def manager():
    return ModelManager(OllamaProvider("http://127.0.0.1:11434"))


def test_no_selected_model_is_not_presented_as_local():
    info = manager().provider_info()
    assert info["mode"] == "unknown"
    assert info["local"] is None


def test_local_models_never_require_provider_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated")
    info = manager().provider_info("qwen3.5:4b")
    assert info["mode"] == "local"
    assert info["credentials_required"] is False
    assert info["credential_env"] is None


def test_online_provider_requires_only_its_credential(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "configured")
    info = manager().provider_info("anthropic:claude-3-5-sonnet")
    assert info["id"] == "anthropic"
    assert info["credential_env"] == "ANTHROPIC_API_KEY"
    assert info["credentials_configured"] is True
    assert manager().validate_model_selection("anthropic:claude-3-5-sonnet")["ok"] is False


def test_online_provider_missing_key_names_only_selected_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = manager().validate_model_selection("openai:gpt-4o")
    assert result["ok"] is False
    assert "OPENAI_API_KEY" in result["error"]
    assert "GOOGLE_API_KEY" not in result["error"]


def test_switching_back_to_local_disables_online_credential_prompt(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    local = manager().provider_info("qwen3.5:4b")
    online = manager().provider_info("openai:gpt-4o")
    assert online["mode"] == "online"
    assert local["mode"] == "local"
    assert local["credentials_required"] is False
