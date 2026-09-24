from __future__ import annotations

import json
from typing import Any

from .base import Tool
from living_assistant.integrations.edge0 import Edge0Adapter


def build_edge0_tools(adapter: Edge0Adapter) -> list[Tool]:
    """Build tool definitions for Edge0 local model execution."""

    def edge0_list_models() -> dict[str, Any]:
        """List available local quantized models through Edge0."""
        return adapter.list_models()

    def edge0_generate(model: str, prompt: str, max_tokens: int = 1024) -> dict[str, Any]:
        """Generate text using a local Edge0 quantized model."""
        return adapter.generate(model=model, prompt=prompt, max_tokens=max_tokens)

    def edge0_chat(model: str, messages: str) -> dict[str, Any]:
        """Send a chat conversation to a local Edge0 model."""
        try:
            parsed_messages = json.loads(messages) if isinstance(messages, str) else messages
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"Invalid JSON messages: {e}"}

        return adapter.chat(model=model, messages=parsed_messages)

    return [
        Tool(
            "edge0_list_models",
            "List available local quantized models supported by Edge0.",
            {
                "type": "object",
                "properties": {},
            },
            edge0_list_models,
        ),
        Tool(
            "edge0_generate",
            "Generate text using a local Edge0 quantized model (useful for fallback execution).",
            {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "The name or path of the model (e.g. 'edge0-35b')",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to send to the model",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum number of tokens to generate",
                        "default": 1024,
                    },
                },
                "required": ["model", "prompt"],
            },
            edge0_generate,
        ),
        Tool(
            "edge0_chat",
            "Send a chat conversation to a local Edge0 model.",
            {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "The name or path of the model",
                    },
                    "messages": {
                        "type": "string",
                        "description": "JSON string of conversation history: [{'role': 'user', 'content': '...'}]",
                    },
                },
                "required": ["model", "messages"],
            },
            edge0_chat,
        ),
    ]
