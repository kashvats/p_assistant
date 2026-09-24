from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.awesome_harness import AwesomeHarnessAdapter

def build_awesome_harness_tools(adapter: AwesomeHarnessAdapter) -> list[Tool]:
    def harness_read_reference() -> dict[str, Any]:
        """Read the awesome-harness-engineering curated list of evaluation harnesses and test fixtures."""
        return adapter.read_reference()

    return [
        Tool(
            "harness_read_reference",
            "Read the awesome-harness-engineering curated list of evaluation harnesses, stress test fixtures, and safety verification benches.",
            {
                "type": "object",
                "properties": {},
            },
            harness_read_reference,
        )
    ]
