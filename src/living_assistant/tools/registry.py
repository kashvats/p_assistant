from __future__ import annotations

from collections.abc import Iterable, Iterator

from .base import Tool


class ToolRegistry:
    """Ordered tool collection with duplicate-name protection and lookup."""

    def __init__(self, tools: Iterable[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        if tools:
            self.extend(tools)

    def register(self, tool: Tool) -> Tool:
        if not isinstance(tool, Tool):
            raise TypeError("ToolRegistry only accepts Tool instances.")
        name = str(tool.name or "").strip()
        if not name:
            raise ValueError("Tool name is required.")
        if name in self._tools:
            raise ValueError(f"Duplicate tool name: {name}")
        self._tools[name] = tool
        return tool

    def extend(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools)

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())
