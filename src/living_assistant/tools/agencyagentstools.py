from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.agency_agents import AgencyAgentsAdapter


def build_agency_agents_tools(adapter: AgencyAgentsAdapter) -> list[Tool]:
    """Build tool definitions for agency-agents personas and workflows."""

    def agency_list_categories() -> dict[str, Any]:
        """List all available categories of specialized AI agents."""
        return adapter.list_categories()

    def agency_list_agents(category: str = "") -> dict[str, Any]:
        """List available AI agents, optionally filtered by a specific category."""
        return adapter.list_agents(category=category)

    def agency_get_agent(name: str) -> dict[str, Any]:
        """Retrieve the complete instructions and workflow definitions for a specialized agent."""
        return adapter.get_agent(name=name)

    def agency_search_agents(query: str) -> dict[str, Any]:
        """Search across all agent definitions for specific capabilities, frameworks, or roles."""
        return adapter.search_agents(query=query)

    return [
        Tool(
            "agency_list_categories",
            "List all available categories of specialized AI agents (e.g. engineering, design, marketing).",
            {
                "type": "object",
                "properties": {},
            },
            agency_list_categories,
        ),
        Tool(
            "agency_list_agents",
            "List available AI agents, optionally filtered by category.",
            {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category name to filter by (e.g. 'engineering')",
                    },
                },
            },
            agency_list_agents,
        ),
        Tool(
            "agency_get_agent",
            "Retrieve the complete persona instructions, processes, and workflow definitions for a specialized agent.",
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the agent (e.g. 'engineering-code-reviewer')",
                    },
                },
                "required": ["name"],
            },
            agency_get_agent,
        ),
        Tool(
            "agency_search_agents",
            "Search across all agent definitions for a specific capability, keyword, or framework.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g. 'react', 'code review', 'social media')",
                    },
                },
                "required": ["query"],
            },
            agency_search_agents,
        ),
    ]
