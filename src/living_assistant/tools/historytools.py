from __future__ import annotations

from .base import Tool
from living_assistant.learning.run_history import RunHistoryStore


def build_run_history_tools(history: RunHistoryStore) -> list[Tool]:
    return [
        Tool(
            "query_run_history",
            "Query the persistent redacted audit trail of agent/tool actions by project, run, or time period such as 'last Tuesday'.",
            {
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "when": {"type": "string"},
                    "run_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 200, "minimum": 1, "maximum": 1000},
                },
            },
            history.query,
        )
    ]
