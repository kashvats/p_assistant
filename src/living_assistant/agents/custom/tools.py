from __future__ import annotations

from typing import Any
from living_assistant.agents.custom.manager import AgentManager
from living_assistant.tools.base import Tool


def build_agent_tools(manager: AgentManager) -> list[Tool]:
    """Expose custom agent capabilities as tools to the living assistant runtime."""

    def handle_agent_list(state: str | None = None) -> list[dict[str, Any]]:
        agents = manager.list_agents(state=state)
        return [
            {
                "agent_id": a.get("agent_id"),
                "name": a.get("name"),
                "role": a.get("role"),
                "state": a.get("state"),
                "description": a.get("description", ""),
                "capabilities": a.get("manifest", {}).get("capabilities", []),
            }
            for a in agents
        ]

    def handle_agent_info(agent_id: str) -> dict[str, Any]:
        info = manager.get_agent(agent_id)
        if not info:
            return {"ok": False, "error": f"Agent '{agent_id}' not found."}
        return {"ok": True, "agent": info}

    def handle_agent_draft(prompt: str) -> dict[str, Any]:
        pkg = manager.create_draft(prompt)
        return {
            "ok": True,
            "agent_id": pkg.manifest.id,
            "name": pkg.manifest.name,
            "role": pkg.manifest.role,
            "state": "DRAFT",
            "allowed_tools": pkg.manifest.allowed_tools,
            "allowed_skills": pkg.manifest.allowed_skills,
        }

    def handle_agent_activate(agent_id: str) -> dict[str, Any]:
        return manager.activate_agent(agent_id)

    def handle_agent_execute(
        agent_id: str,
        task: str,
        context: str = "",
        inputs: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return manager.execute_agent(
            agent_id=agent_id,
            task=task,
            context=context,
            inputs=inputs or {},
            dry_run=dry_run,
        )

    return [
        Tool(
            "agent_list",
            "List registered custom agents and their current states (ACTIVE, DRAFT, DISABLED).",
            {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["ACTIVE", "DRAFT", "DISABLED", "ARCHIVED"]},
                },
            },
            handle_agent_list,
        ),
        Tool(
            "agent_get_info",
            "Get detailed specifications, capabilities, and execution history for a custom agent.",
            {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Unique agent identifier"},
                },
                "required": ["agent_id"],
            },
            handle_agent_info,
        ),
        Tool(
            "agent_create_draft",
            "Create a new custom agent draft from a natural-language description.",
            {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Description of what the agent should do"},
                },
                "required": ["prompt"],
            },
            handle_agent_draft,
        ),
        Tool(
            "agent_activate",
            "Activate and approve an agent after review, generating an immutable snapshot.",
            {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier to activate"},
                },
                "required": ["agent_id"],
            },
            handle_agent_activate,
        ),
        Tool(
            "agent_execute",
            "Execute a task using a custom agent.",
            {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "task": {"type": "string", "description": "Specific task for the agent to execute"},
                    "context": {"type": "string", "description": "Background context or data"},
                    "inputs": {"type": "object", "description": "Optional structured inputs"},
                    "dry_run": {"type": "boolean", "description": "Simulate actions without real mutations"},
                },
                "required": ["agent_id", "task"],
            },
            handle_agent_execute,
        ),
    ]
