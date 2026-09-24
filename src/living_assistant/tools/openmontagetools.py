from __future__ import annotations

import json
from typing import Any

from .base import Tool
from living_assistant.integrations.openmontage import OpenMontageAdapter


def build_openmontage_tools(adapter: OpenMontageAdapter) -> list[Tool]:
    """Build tool definitions for OpenMontage media orchestration."""

    def openmontage_list_pipelines() -> dict[str, Any]:
        """List available video production pipelines in OpenMontage."""
        return adapter.list_pipelines()

    def openmontage_get_pipeline(name: str) -> dict[str, Any]:
        """Get the detailed manifest and configuration of a specific OpenMontage pipeline."""
        return adapter.get_pipeline(name=name)

    def openmontage_list_tools(capability: str = "") -> dict[str, Any]:
        """List available media production tools in OpenMontage, optionally filtered by capability."""
        return adapter.list_tools(capability=capability if capability else None)

    def openmontage_execute_tool(tool_name: str, inputs: str) -> dict[str, Any]:
        """Execute an OpenMontage tool with JSON inputs."""
        try:
            parsed_inputs = json.loads(inputs) if isinstance(inputs, str) else inputs
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"Invalid JSON inputs: {e}"}

        return adapter.execute_tool(tool_name=tool_name, inputs=parsed_inputs)

    return [
        Tool(
            "openmontage_list_pipelines",
            "List available video production pipelines in OpenMontage.",
            {
                "type": "object",
                "properties": {},
            },
            openmontage_list_pipelines,
        ),
        Tool(
            "openmontage_get_pipeline",
            "Get the detailed manifest and configuration of a specific OpenMontage pipeline.",
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the pipeline (e.g. 'documentary-montage')",
                    },
                },
                "required": ["name"],
            },
            openmontage_get_pipeline,
        ),
        Tool(
            "openmontage_list_tools",
            "List available media production tools in OpenMontage, optionally filtered by capability.",
            {
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": "Optional capability filter (e.g. 'video_generation', 'audio', 'analysis')",
                    },
                },
            },
            openmontage_list_tools,
        ),
        Tool(
            "openmontage_execute_tool",
            "Execute an OpenMontage media tool.",
            {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The name of the tool to execute",
                    },
                    "inputs": {
                        "type": "string",
                        "description": "JSON string containing the tool inputs",
                    },
                },
                "required": ["tool_name", "inputs"],
            },
            openmontage_execute_tool,
        ),
    ]
