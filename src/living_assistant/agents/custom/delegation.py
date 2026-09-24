from __future__ import annotations

import threading
from typing import Any

from living_assistant.agents.custom.manifest import AgentManifest


class DelegationViolation(PermissionError):
    pass


class AgentDelegationCoordinator:
    """Coordinates and polices inter-agent delegation."""

    def __init__(self, resource_manager: Any = None):
        self.resource_manager = resource_manager
        # Ensure only 1 resident model inference occurs at a time for 4GB VRAM
        self._inference_lock = threading.Lock()

    def validate_delegation(
        self,
        parent_manifest: AgentManifest,
        child_manifest: AgentManifest,
        current_depth: int,
        current_subagents_count: int,
    ) -> None:
        """Enforce strict delegation boundaries and security inheritance."""
        if not parent_manifest.delegation_policy.can_delegate:
            raise DelegationViolation(
                f"Agent '{parent_manifest.id}' is not authorized to delegate tasks."
            )

        if current_depth >= parent_manifest.limits.max_delegation_depth:
            raise DelegationViolation(
                f"Delegation depth limit ({parent_manifest.limits.max_delegation_depth}) reached for agent '{parent_manifest.id}'."
            )

        if current_subagents_count >= parent_manifest.delegation_policy.max_subagents:
            raise DelegationViolation(
                f"Maximum sub-agent count ({parent_manifest.delegation_policy.max_subagents}) reached for agent '{parent_manifest.id}'."
            )

        allowed = parent_manifest.delegation_policy.allowed_agents
        if allowed and child_manifest.id not in allowed:
            raise DelegationViolation(
                f"Agent '{parent_manifest.id}' is only authorized to delegate to {allowed}, but attempted to delegate to '{child_manifest.id}'."
            )

        # Inherited permission check: child cannot exceed parent's tool or skill scopes
        if parent_manifest.delegation_policy.inherit_permissions:
            parent_tools = set(parent_manifest.allowed_tools)
            child_tools = set(child_manifest.allowed_tools)
            tool_diff = child_tools - parent_tools
            if tool_diff:
                raise DelegationViolation(
                    f"Child agent '{child_manifest.id}' requests tools {sorted(tool_diff)} "
                    f"that exceed parent agent '{parent_manifest.id}' allowed tools."
                )

            parent_skills = set(parent_manifest.allowed_skills)
            child_skills = set(child_manifest.allowed_skills)
            skill_diff = child_skills - parent_skills
            if skill_diff:
                raise DelegationViolation(
                    f"Child agent '{child_manifest.id}' requests skills {sorted(skill_diff)} "
                    f"that exceed parent agent '{parent_manifest.id}' allowed skills."
                )
