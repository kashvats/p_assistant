from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.scientific_skills import ScientificSkillsAdapter


def build_scientific_skills_tools(adapter: ScientificSkillsAdapter) -> list[Tool]:
    """Build tool definitions for scientific-agent-skills capabilities."""

    def scientific_search_skills(query: str = "", domain: str = "", limit: int = 10) -> dict[str, Any]:
        """Search the scientific and analytical skills library by keyword, tool, or method."""
        return adapter.search_skills(query=query, domain=domain, limit=limit)

    def scientific_get_skill(name: str) -> dict[str, Any]:
        """Retrieve complete guidance, patterns, and instructions for a scientific skill."""
        return adapter.get_skill(name_or_path=name)

    return [
        Tool(
            "scientific_search_skills",
            "Search across the scientific and analytical skills library by keyword, method, or computational biology tool.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'biopython', 'data synthesis', 'genomics')",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results to return",
                    },
                },
            },
            scientific_search_skills,
        ),
        Tool(
            "scientific_get_skill",
            "Retrieve full instructions, code patterns, and best practices for a scientific skill.",
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact or partial name of the skill (e.g. 'biopython')",
                    },
                },
                "required": ["name"],
            },
            scientific_get_skill,
        ),
    ]
