from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from living_assistant.core.model_provider import (
    LlamaCppProvider,
    CompositeModelProvider,
    ModelManager,
    model_provider_info,
)


def test_llamacpp_provider_init_and_clean_name():
    p = LlamaCppProvider(base_url="http://127.0.0.1:8080")
    assert p.base_url == "http://127.0.0.1:8080"
    
    clean = p._clean_model_name(r"C:\models\Qwen_Qwen3-30B-Instruct.gguf")
    assert clean == "Qwen_Qwen3-30B-Instruct"

    clean2 = p._clean_model_name("llama-3-8b.Q4_K_M.gguf")
    assert clean2 == "llama-3-8b.Q4_K_M"

    assert p._clean_model_name("") == "local-model"


def test_llamacpp_model_provider_info_classification():
    info = model_provider_info("openai/local-model")
    assert info["id"] == "llamacpp"
    assert info["mode"] == "local"
    assert info["local"] is True
    assert "llama.cpp" in info["name"]
    assert info["credentials_required"] is False


def test_llamacpp_model_inventory_parsing():
    p = LlamaCppProvider(base_url="http://127.0.0.1:8080")
    
    fake_models_response = {
        "models": [
            {
                "name": r"C:\cache\models--bartowski--Qwen3-30B-GGUF\Qwen3-30B-Q4_K_M.gguf",
                "meta": {"size": 18626213888},
            }
        ]
    }
    
    with patch.object(p, "_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_models_response
        mock_client.get.return_value = mock_resp
        mock_client_factory.return_value.__enter__.return_value = mock_client
        
        inv = p.model_inventory()
        assert "Qwen3-30B-Q4_K_M" in inv
        assert inv["Qwen3-30B-Q4_K_M"]["provider"] == "llamacpp"
        assert inv["Qwen3-30B-Q4_K_M"]["loaded"] is True
        assert inv["Qwen3-30B-Q4_K_M"]["size_bytes"] == 18626213888


def test_llamacpp_chat_completion_mapping():
    p = LlamaCppProvider(base_url="http://127.0.0.1:8080")
    
    fake_completion = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello world",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {"name": "test_tool", "arguments": "{\"x\": 1}"}
                        }
                    ]
                }
            }
        ],
        "model": "Qwen3-30B"
    }
    
    with patch.object(p, "_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_completion
        mock_client.post.return_value = mock_resp
        mock_client_factory.return_value.__enter__.return_value = mock_client
        
        res = p.chat("local-model", [{"role": "user", "content": "hi"}])
        assert res["done"] is True
        assert res["message"]["content"] == "Hello world"
        assert len(res["message"]["tool_calls"]) == 1
        assert res["message"]["tool_calls"][0]["function"]["name"] == "test_tool"


def test_model_manager_resolves_stale_name_to_llamacpp():
    p = LlamaCppProvider(base_url="http://127.0.0.1:8080")
    p.model_inventory = lambda: {
        "Qwen3-30B-Q4_K_M": {"name": "Qwen3-30B-Q4_K_M", "loaded": True},
        "openai/local-model": {"name": "openai/local-model", "loaded": True},
    }
    
    mm = ModelManager(p)
    # Prefix match:
    assert mm.resolve_local_model("Qwen3-30B") == "Qwen3-30B-Q4_K_M"
    assert mm.resolve_local_model("openai/local-model") == "openai/local-model"
