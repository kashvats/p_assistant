from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.awesome_agent_tools import AwesomeAgentToolsAdapter

def build_awesome_agent_tools(adapter: AwesomeAgentToolsAdapter) -> list[Tool]:
    def agent_tools_read_reference() -> dict[str, Any]:
        """Read the awesome-ai-agent-tools curated tool catalog and dynamic capability registry."""
        return adapter.read_reference()

    def agent_tools_list_categories() -> dict[str, Any]:
        """List the tool categories in awesome-ai-agent-tools."""
        return adapter.list_categories()

    return [
        Tool(
            "agent_tools_read_reference",
            "Read the awesome-ai-agent-tools curated tool catalog and dynamic capability registry.",
            {
                "type": "object",
                "properties": {},
            },
            agent_tools_read_reference,
        ),
        Tool(
            "agent_tools_list_categories",
            "List tool categories (e.g., hooks, loops, mcps, plugins, tools) in awesome-ai-agent-tools.",
            {
                "type": "object",
                "properties": {},
            },
            agent_tools_list_categories,
        )
    ]
