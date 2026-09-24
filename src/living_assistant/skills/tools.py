from __future__ import annotations

from typing import Any
from living_assistant.skills.manager import SkillManager
from living_assistant.tools.base import Tool


def build_skill_tools(manager: SkillManager) -> list[Tool]:
    """Exposes custom skill creation, discovery, and execution tools to the Orchestrator."""

    def create_skill_draft(description: str) -> dict[str, Any]:
        """Convert a user request (e.g. 'Organize my invoices by vendor and month') into a validated draft skill."""
        pkg = manager.create_draft(description)
        m = pkg.manifest
        return {
            "ok": True,
            "skill_id": m.id,
            "name": m.name,
            "version": m.version,
            "state": "DRAFT",
            "required_tools": m.required_tools,
            "permissions": m.permissions.model_dump(),
            "description": m.description,
            "message": f"Draft skill '{m.name}' ({m.id}) created successfully. It is saved in DRAFT state. Review permissions and activate it to run.",
        }

    def execute_skill(skill_id: str, inputs: dict[str, Any] | None = None, dry_run: bool = False) -> dict[str, Any]:
        """Execute an active custom skill or test run in dry-run mode."""
        return manager.execute_skill(skill_id, inputs=inputs or {}, dry_run=dry_run, trigger="orchestrator_tool")

    def list_active_skills() -> list[dict[str, Any]]:
        """List active skills available for invocation with their triggers and descriptions."""
        return manager.list_skills(state="ACTIVE")

    return [
        Tool(
            "create_skill_draft",
            "Create a new custom skill draft from a natural-language description (e.g. 'Organize invoices by vendor and month'). Saves as DRAFT for review.",
            {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural-language goal for the skill",
                    }
                },
                "required": ["description"],
            },
            create_skill_draft,
        ),
        Tool(
            "execute_skill",
            "Execute an active custom skill, or test run a draft in dry_run mode without modifying disk files.",
            {
                "type": "object",
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "description": "Stable ID of the skill to execute (e.g. 'invoice-organizer')",
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Dictionary of input arguments for the skill",
                        "default": {},
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If True, previews all actions without making actual file modifications",
                        "default": False,
                    },
                },
                "required": ["skill_id"],
            },
            execute_skill,
        ),
        Tool(
            "list_active_skills",
            "List all currently active custom and built-in skills with their triggers and descriptions.",
            {"type": "object", "properties": {}},
            list_active_skills,
        ),
    ]
