from __future__ import annotations

from .base import Tool
from living_assistant.integrations.openviking import OpenVikingAdapter


def build_viking_tools(adapter: OpenVikingAdapter) -> list[Tool]:
    def viking_recall(query: str, uri: str = "", limit: int = 6) -> dict:
        """Retrieve semantically relevant context from OpenViking memory."""
        return adapter.recall(query, uri=uri, limit=limit)

    def viking_remember(content: str, uri: str = "", tags: list[str] | None = None) -> dict:
        """Write a memory or note into the OpenViking context store."""
        return adapter.remember(content, uri=uri, tags=tags)

    def viking_search(query: str, uri: str = "") -> dict:
        """Keyword-aware search across OpenViking context. Scope with a viking:// URI."""
        return adapter.search(query, uri=uri)

    def viking_capture_session(session_id: str, messages: list[dict], token_budget: int = 4096) -> dict:
        """Archive a conversation into OpenViking for cross-session memory. Each message needs role and content keys."""
        return adapter.capture_session(session_id, messages, token_budget)

    return [
        Tool(
            "viking_recall",
            (
                "Semantically retrieve the most relevant memories, documents, or skills "
                "from OpenViking. Use this before answering questions that may benefit "
                "from past context. Scope retrieval with a viking:// URI when you know "
                "the subtree (e.g. viking://user/{user}/memories/)."
            ),
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language recall query"},
                    "uri": {
                        "type": "string",
                        "default": "",
                        "description": "Optional viking:// URI to scope the search to a subtree",
                    },
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["query"],
            },
            viking_recall,
        ),
        Tool(
            "viking_remember",
            (
                "Store a fact, preference, lesson, or note into OpenViking for long-term "
                "cross-session recall. Use a viking:// URI to place it in the right subtree "
                "(e.g. viking://user/{user}/memories/preferences/)."
            ),
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Text content to store"},
                    "uri": {
                        "type": "string",
                        "default": "",
                        "description": "Destination viking:// URI (directory or resource path)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional metadata tags",
                    },
                },
                "required": ["content"],
            },
            viking_remember,
        ),
        Tool(
            "viking_search",
            (
                "Keyword-aware search across a OpenViking context subtree. "
                "Prefer viking_recall for semantic questions; use this for "
                "exact-term or structured searches."
            ),
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "uri": {"type": "string", "default": "", "description": "Optional viking:// URI to scope"},
                },
                "required": ["query"],
            },
            viking_search,
        ),
        Tool(
            "viking_capture_session",
            (
                "Archive a completed conversation into OpenViking so its memories are "
                "available in future sessions. Pass the session_id and a list of "
                "{role, content} message dicts. Call this at the end of important tasks."
            ),
            {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string", "enum": ["user", "assistant"]},
                                "content": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                    },
                    "token_budget": {"type": "integer", "default": 4096},
                },
                "required": ["session_id", "messages"],
            },
            viking_capture_session,
        ),
    ]
