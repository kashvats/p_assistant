from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.graft import GraftAdapter


def build_graft_tools(adapter: GraftAdapter) -> list[Tool]:
    """Build tool definitions for Graft persistent agent memory."""

    def graft_query(prompt: str, profile: str | None = None) -> dict[str, Any]:
        """Check if this problem, gotcha, or decision has already been solved previously."""
        return adapter.query(prompt=prompt, profile=profile)

    def graft_retrieve(query: str, limit: int = 5, profile: str | None = None) -> dict[str, Any]:
        """Retrieve relevant past memories, fixes, and architectural decisions."""
        return adapter.retrieve(query=query, limit=limit, profile=profile)

    def graft_insert(
        title: str,
        body: str,
        keywords: list[str] | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Save a newly discovered fix, architectural decision, gotcha, or convention."""
        return adapter.insert(title=title, body=body, keywords=keywords, profile=profile)

    def graft_explore(id_or_query: str, depth: int = 2, profile: str | None = None) -> dict[str, Any]:
        """Explore related memories, concepts, and gotchas across the knowledge graph."""
        return adapter.explore(id_or_query=id_or_query, depth=depth, profile=profile)

    def graft_list(limit: int = 50, profile: str | None = None) -> dict[str, Any]:
        """List recently saved memories and learned gotchas."""
        return adapter.list_memories(limit=limit, profile=profile)

    def graft_delete(memory_id: str | int, profile: str | None = None) -> dict[str, Any]:
        """Delete an obsolete or invalid memory entry by ID."""
        return adapter.delete(memory_id=memory_id, profile=profile)

    def graft_stats(profile: str | None = None) -> dict[str, Any]:
        """Get Graft memory store statistics and health metrics."""
        return adapter.stats(profile=profile)

    return [
        Tool(
            "graft_query",
            "Verified recall: Check if a difficult bug, gotcha, or architectural decision was previously solved.",
            {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The issue or question to check in persistent memory"},
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
                "required": ["prompt"],
            },
            graft_query,
        ),
        Tool(
            "graft_retrieve",
            "Hybrid retrieval: Search past coding solutions, gotchas, and architectural decisions.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "limit": {"type": "integer", "default": 5, "description": "Maximum number of results to return"},
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
                "required": ["query"],
            },
            graft_retrieve,
        ),
        Tool(
            "graft_insert",
            "Save a solution, fix, gotcha, constraint, or architectural decision to persistent memory.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Concise summary of the solution or gotcha"},
                    "body": {"type": "string", "description": "Detailed explanation of the fix and root cause"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords or tags (e.g. ['spring', 'validation', 'gotcha'])",
                    },
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
                "required": ["title", "body"],
            },
            graft_insert,
        ),
        Tool(
            "graft_explore",
            "Graph exploration: Walk semantic and keyword relationships connected to a memory.",
            {
                "type": "object",
                "properties": {
                    "id_or_query": {"type": "string", "description": "Memory ID or search topic to explore"},
                    "depth": {"type": "integer", "default": 2, "description": "Search traversal depth"},
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
                "required": ["id_or_query"],
            },
            graft_explore,
        ),
        Tool(
            "graft_list",
            "List recently stored memories and decisions.",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50, "description": "Max entries to list"},
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
            },
            graft_list,
        ),
        Tool(
            "graft_delete",
            "Delete an obsolete or incorrect memory by ID.",
            {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "ID of the memory to delete"},
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
                "required": ["memory_id"],
            },
            graft_delete,
        ),
        Tool(
            "graft_stats",
            "Get Graft memory store statistics and health.",
            {
                "type": "object",
                "properties": {
                    "profile": {"type": "string", "description": "Optional agent profile name"},
                },
            },
            graft_stats,
        ),
    ]
