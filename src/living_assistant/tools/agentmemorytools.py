from __future__ import annotations

from .base import Tool
from living_assistant.integrations.agentmemory import AgentMemoryAdapter


def build_agentmemory_tools(adapter: AgentMemoryAdapter) -> list[Tool]:
    def agentmem_recall(
        query: str,
        limit: int = 10,
        format_type: str = "full",
        token_budget: int | None = None,
    ) -> dict:
        """Search past session observations for relevant context."""
        return adapter.recall(query, limit=limit, format_type=format_type, token_budget=token_budget)

    def agentmem_save(
        content: str,
        memory_type: str = "fact",
        concepts: str = "",
        files: str = "",
        project: str = "",
        agent_id: str = "",
    ) -> dict:
        """Explicitly save an important insight, decision, or pattern to persistent memory."""
        return adapter.save(
            content=content,
            memory_type=memory_type,
            concepts=concepts,
            files=files,
            project=project,
            agent_id=agent_id,
        )

    def agentmem_file_history(files: str, limit: int = 10) -> dict:
        """Get past observations about specific file paths."""
        return adapter.file_history(files=files, limit=limit)

    def agentmem_smart_search(query: str, limit: int = 10, token_budget: int | None = None) -> dict:
        """Smart hybrid search combining keyword, semantic, and structural graph recall."""
        return adapter.smart_search(query=query, limit=limit, token_budget=token_budget)

    def agentmem_list(project: str = "", agent_id: str = "", limit: int = 50) -> dict:
        """List stored memories by project or agent ID."""
        return adapter.list_memories(project=project, agent_id=agent_id, limit=limit)

    return [
        Tool(
            "agentmem_recall",
            (
                "Search past session observations, decisions, and lessons for relevant context. "
                "Use when you need to recall past project context or previous discussions."
            ),
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query keywords or concept"},
                    "limit": {"type": "integer", "default": 10, "description": "Max results to return"},
                    "format_type": {
                        "type": "string",
                        "enum": ["full", "compact", "narrative"],
                        "default": "full",
                        "description": "Result format",
                    },
                    "token_budget": {
                        "type": "integer",
                        "description": "Optional token budget to bound the output",
                    },
                },
                "required": ["query"],
            },
            agentmem_recall,
        ),
        Tool(
            "agentmem_save",
            (
                "Explicitly save an important insight, architectural decision, user preference, "
                "or bug fix pattern into persistent long-term agent memory."
            ),
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The insight or decision to remember"},
                    "memory_type": {
                        "type": "string",
                        "enum": ["pattern", "preference", "architecture", "bug", "workflow", "fact"],
                        "default": "fact",
                    },
                    "concepts": {"type": "string", "description": "Comma-separated key concepts"},
                    "files": {"type": "string", "description": "Comma-separated relevant file paths"},
                    "project": {"type": "string", "description": "Optional canonical project identifier"},
                    "agent_id": {"type": "string", "description": "Optional agent identity to scope memory to"},
                },
                "required": ["content"],
            },
            agentmem_save,
        ),
        Tool(
            "agentmem_file_history",
            (
                "Retrieve past observations, decisions, and modifications regarding specific files."
            ),
            {
                "type": "object",
                "properties": {
                    "files": {"type": "string", "description": "Comma-separated list of file paths to inspect"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["files"],
            },
            agentmem_file_history,
        ),
        Tool(
            "agentmem_smart_search",
            (
                "Execute a hybrid graph + keyword + semantic search over persistent memories."
            ),
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10},
                    "token_budget": {"type": "integer"},
                },
                "required": ["query"],
            },
            agentmem_smart_search,
        ),
        Tool(
            "agentmem_list",
            (
                "List persistent memories stored in agentmemory, filtered optionally by project or agent."
            ),
            {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "default": ""},
                    "agent_id": {"type": "string", "default": ""},
                    "limit": {"type": "integer", "default": 50},
                },
            },
            agentmem_list,
        ),
    ]
