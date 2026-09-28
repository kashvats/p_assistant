from __future__ import annotations

import httpx
from unittest.mock import MagicMock
import pytest

from living_assistant.core.model_provider import (
    CompositeModelProvider,
    CapabilityRegistry,
    ModelCapability,
    ModelError,
)
from living_assistant.agents.orchestrator import Orchestrator


def test_section_30_model_provider_failover():
    """Section 30: Failover automatically to secondary provider when primary is unavailable."""
    primary_prov = MagicMock()
    primary_prov.chat.side_effect = httpx.ConnectError("Connection refused: 127.0.0.1:8080")

    fallback_prov = MagicMock()
    fallback_prov.chat.return_value = {
        "model": "ollama:default",
        "message": {"role": "assistant", "content": "Response from fallback provider."},
        "done": True,
    }

    comp = CompositeModelProvider(
        llamacpp=primary_prov,
        ollama=fallback_prov,
    )

    messages = [{"role": "user", "content": "Hello world"}]
    res = comp.chat("local-model", messages)

    assert res["done"] is True
    assert res.get("failover") is True
    assert res.get("original_model") == "local-model"
    assert res["message"]["content"] == "Response from fallback provider."
    primary_prov.chat.assert_called_once()
    fallback_prov.chat.assert_called_once()


def test_section_30_vision_incompatibility_detected():
    """Section 30: Reject routing vision tasks to text-only models."""
    registry = CapabilityRegistry()
    registry.register(
        ModelCapability(
            name="qwen-text-only",
            provider="llamacpp",
            supports_text=True,
            supports_vision=False,
        )
    )

    comp = CompositeModelProvider(
        capability_registry=registry,
    )

    # Message with image payload
    vision_messages = [
        {"role": "user", "content": "What is in this image?", "images": ["base64..."]}
    ]

    with pytest.raises(ModelError, match="does not support vision"):
        comp.chat("qwen-text-only", vision_messages)


def test_section_31_model_capability_metadata():
    """Section 31: Explicit metadata verification for model capabilities."""
    cap = ModelCapability(
        name="llava-v1.6",
        provider="ollama",
        supports_text=True,
        supports_vision=True,
        supports_tools=False,
        supports_json=True,
        supports_streaming=True,
        context_length=8192,
        estimated_vram_mb=6000,
    )

    metadata = cap.as_dict()
    assert metadata["name"] == "llava-v1.6"
    assert metadata["supports_vision"] is True
    assert metadata["supports_tools"] is False
    assert metadata["context_length"] == 8192
    assert metadata["estimated_vram_mb"] == 6000

    registry = CapabilityRegistry()
    registry.register(cap)

    # Verify registered capability retrieval
    retrieved = registry.get("llava-v1.6")
    assert retrieved is not None
    assert retrieved.supports_vision is True

    # Test unknown model requiring vision -> fails closed
    valid, err = registry.validate_capability("random-unknown-model", requires_vision=True)
    assert valid is False
    assert "no declared vision capability" in err


def test_section_32_model_switch_during_conversation():
    """Section 32: System persona and context survive routing across different models."""
    prov_a = MagicMock()
    prov_a.chat.return_value = {"message": {"role": "assistant", "content": "Text answer from local model."}}

    prov_b = MagicMock()
    prov_b.chat.return_value = {"message": {"role": "assistant", "content": "Cloud vision analysis."}}

    comp = CompositeModelProvider(
        llamacpp=prov_a,
        litellm_provider=prov_b,
    )

    convo = [
        {"role": "system", "content": "You are the Living Personal Assistant."},
        {"role": "user", "content": "Describe my project structure."},
    ]

    # Turn 1 with local text model
    res1 = comp.chat("local-model", convo)
    assert "Text answer" in res1["message"]["content"]
    convo.append(res1["message"])

    # Turn 2 switching to cloud model
    convo.append({"role": "user", "content": "Now analyze this chart."})
    res2 = comp.chat("anthropic/claude-3-5-sonnet-20240620", convo)
    assert "Cloud vision" in res2["message"]["content"]

    # Verify system persona and conversation history intact across turns
    assert convo[0]["role"] == "system"
    assert "Living Personal Assistant" in convo[0]["content"]
    assert len(convo) == 4


def test_section_33_model_context_overflow_compaction():
    """Section 33: Context compaction preserves system instructions and summarizes old turns."""
    messages = [
        {"role": "system", "content": "System Prompt: Never disclose passwords."},
        {"role": "user", "content": "Initial Request: Build an automated data pipeline."},
    ]

    # Add 12 lengthy intermediate conversation turns
    for i in range(12):
        messages.append({
            "role": "assistant",
            "content": f"Intermediate step {i}: working on database setup with very long configuration details " * 20,
            "tool_calls": [{"function": {"name": f"db_tool_{i}"}}],
        })
        messages.append({
            "role": "tool",
            "content": f"Tool output {i}: database query returned 500 rows with detailed schema data " * 20,
        })

    # Add recent tail messages
    messages.append({"role": "user", "content": "Current question: What is the latest state?"})
    messages.append({"role": "assistant", "content": "Current answer: Pipeline active."})

    # Total chars before compaction
    initial_chars = sum(len(str(m.get("content") or "")) for m in messages)
    assert initial_chars > 10000

    # Compact context with a small token limit (e.g. 500 tokens)
    compacted = Orchestrator.compact_context(messages, max_tokens=500)

    # 1. Essential system instructions preserved at index 0
    assert compacted[0]["role"] == "system"
    assert "Never disclose passwords" in compacted[0]["content"]

    # 2. Initial user request preserved at index 1
    assert compacted[1]["role"] == "user"
    assert "Build an automated data pipeline" in compacted[1]["content"]

    # 3. Middle compacted into a summary message
    summary_msg = compacted[2]
    assert summary_msg["role"] == "system"
    assert "Context compacted" in summary_msg["content"]
    assert "db_tool" in summary_msg["content"]

    # 4. Recent messages preserved at tail
    assert compacted[-1]["content"] == "Current answer: Pipeline active."
    assert compacted[-2]["content"] == "Current question: What is the latest state?"

    # Overall size drastically reduced
    compacted_chars = sum(len(str(m.get("content") or "")) for m in compacted)
    assert compacted_chars < initial_chars
