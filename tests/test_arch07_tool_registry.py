from __future__ import annotations

import pytest

from living_assistant.tools.base import Tool
from living_assistant.tools.registry import ToolRegistry


def _tool(name: str) -> Tool:
    return Tool(name, name, {"type": "object", "properties": {}}, lambda: name)


def test_registry_preserves_order_and_lookup():
    registry = ToolRegistry([_tool("a")])
    registry.extend([_tool("b"), _tool("c")])
    assert registry.names() == ["a", "b", "c"]
    assert [tool.name for tool in registry.all()] == ["a", "b", "c"]
    assert registry.get("b").name == "b"


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry([_tool("same")])
    with pytest.raises(ValueError, match="Duplicate tool name"):
        registry.register(_tool("same"))
