from __future__ import annotations

from typing import Any, Optional
from living_assistant.skills.learning import SkillLearningEngine, CapabilityGap
from living_assistant.skills.manifest import SkillStep, SkillPermissionScope
from living_assistant.skills.manager import SkillManager
from living_assistant.tools.base import Tool


def build_skill_tools(manager: SkillManager) -> list[Tool]:
    """Exposes custom skill creation, discovery, execution, and persistent learning tools to the Orchestrator."""
    learning_engine = SkillLearningEngine(
        store=manager.store,
        tool_registry=manager.tool_registry,
        skills_dir=manager.skills_dir,
    )

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
        """Execute an active or verified custom skill, or test run in dry-run mode."""
        return manager.execute_skill(skill_id, inputs=inputs or {}, dry_run=dry_run, trigger="orchestrator_tool")

    def list_active_skills() -> list[dict[str, Any]]:
        """List active skills available for invocation with their triggers and descriptions."""
        return manager.list_skills(state="ACTIVE")

    def detect_capability_gap(task_description: str) -> dict[str, Any]:
        """Detect whether a task lacks required tool procedures and constitutes a capability gap."""
        gap = learning_engine.detect_gap(task_description)
        if gap:
            return {
                "has_gap": True,
                "gap": gap.__dict__,
                "recommendation": f"Acquire skill '{gap.missing_capability}' from {', '.join(gap.candidate_sources)}.",
            }
        return {
            "has_gap": False,
            "message": "No capability gap detected. Current tools, skills, or clarification protocols can fulfill the task.",
        }

    def acquire_and_verify_skill(
        capability_name: str,
        source_type: str = "documentation",
        source_reference: str = "Technical specification",
        steps: list[dict[str, Any]] | None = None,
        test_inputs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Autonomously learn, synthesize, test in isolation, and verify a new reusable skill."""
        gap = CapabilityGap(
            task_id=f"gap_{capability_name}",
            task_description=f"Acquire {capability_name}",
            missing_capability=capability_name,
            category="missing_procedure",
            severity="blocking",
            candidate_sources=[source_type],
            resolution_strategy="acquire_new_skill",
        )
        prop = learning_engine.propose_skill(gap)
        skill_id = prop["skill_id"]

        skill_steps = []
        raw_steps = steps or [
            {
                "id": "step_1",
                "tool": "files.read",
                "description": f"Read input for {capability_name}",
                "arguments": {"path": "{inputs.path}"},
            }
        ]
        for s in raw_steps:
            skill_steps.append(
                SkillStep(
                    id=s.get("id", "step_1"),
                    tool=s.get("tool", "files.read"),
                    description=s.get("description", ""),
                    arguments=s.get("arguments", {}),
                )
            )

        pkg = learning_engine.learn_from_source(
            skill_id=skill_id,
            source_type=source_type,
            source_reference=source_reference,
            workflow_steps=skill_steps,
        )

        test_data = test_inputs or [{"path": "./workspace/test.txt"}]
        val_res = learning_engine.test_and_validate(skill_id, test_inputs=test_data)
        return val_res

    def list_learned_skills(status: str | None = None) -> list[dict[str, Any]]:
        """List skills in the persistent learning catalog filtered by lifecycle status."""
        return learning_engine.list_learned_skills(state=status)

    return [
        Tool(
            "create_skill_draft",
            "Create a new custom user automation/skill draft from a natural-language description (e.g. 'Organize my invoices by vendor and month'). DO NOT call this tool for software development, coding requests, writing applications, backend APIs, or building software projects in the workspace. For building software/apps, write or generate code files in the workspace instead.",
            {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural-language goal for the automation skill (NOT for coding projects or apps)",
                    }
                },
                "required": ["description"],
            },
            create_skill_draft,
        ),
        Tool(
            "execute_skill",
            "Execute an active or verified custom skill, or test run a draft in dry_run mode without modifying disk files.",
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
        Tool(
            "detect_capability_gap",
            "Detect whether a requested task lacks necessary tool capabilities or procedures, distinguishing genuine gaps from underspecified user requirements.",
            {
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task to evaluate for capability gaps.",
                    }
                },
                "required": ["task_description"],
            },
            detect_capability_gap,
        ),
        Tool(
            "acquire_and_verify_skill",
            "Acquire a new skill through multi-stage learning (gap -> research -> synthesize -> isolated test -> verification) and publish into persistent catalog.",
            {
                "type": "object",
                "properties": {
                    "capability_name": {
                        "type": "string",
                        "description": "Name of the missing capability to acquire (e.g. markdown_frontmatter_parser).",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Source of knowledge: documentation, repository, tools, or user_demonstration.",
                        "default": "documentation",
                    },
                    "source_reference": {
                        "type": "string",
                        "description": "Citation or description of the knowledge source.",
                        "default": "Technical specification",
                    },
                    "steps": {
                        "type": "array",
                        "description": "Procedural workflow steps for the skill.",
                    },
                    "test_inputs": {
                        "type": "array",
                        "description": "Sample test inputs to execute in isolated validation.",
                    },
                },
                "required": ["capability_name"],
            },
            acquire_and_verify_skill,
        ),
        Tool(
            "list_learned_skills",
            "List learned skills in the persistent catalog with their 6-stage lifecycle state (PROPOSED, LEARNING, TESTING, VERIFIED, DEPRECATED, FAILED).",
            {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional lifecycle status filter (e.g. 'VERIFIED', 'PROPOSED', 'TESTING').",
                    }
                },
            },
            list_learned_skills,
        ),
    ]
