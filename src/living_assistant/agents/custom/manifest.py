from __future__ import annotations

import hashlib
import json
from typing import Any
from pydantic import BaseModel, Field


class AgentLimits(BaseModel):
    max_steps: int = 15
    max_tool_calls_per_step: int = 5
    loop_detection_threshold: int = 3
    timeout_seconds: float = 120.0
    max_delegation_depth: int = 2
    aggregate_tool_limit: int = 50


class AgentDelegationPolicy(BaseModel):
    can_delegate: bool = False
    allowed_agents: list[str] = Field(default_factory=list)
    max_subagents: int = 2
    inherit_permissions: bool = True  # Child permissions cannot exceed parent permissions


class AgentMemoryScope(BaseModel):
    isolate_working_memory: bool = True
    readable_namespaces: list[str] = Field(
        default_factory=lambda: ["working", "agent_notes", "project_knowledge"]
    )
    writable_namespaces: list[str] = Field(
        default_factory=lambda: ["working", "agent_notes"]
    )


class AgentModelPreference(BaseModel):
    model_name: str | None = None
    temperature: float = 0.7
    context_tokens: int = 4096


class AgentProvenance(BaseModel):
    created_by: str = "user"
    created_at: str = ""
    prompt_used: str = ""
    base_template: str | None = None


class AgentManifest(BaseModel):
    schema_version: str = "1.0.0"
    id: str
    name: str
    description: str = ""
    role: str = "specialist"
    system_prompt: str = ""
    capabilities: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_skills: list[str] = Field(default_factory=list)
    delegation_policy: AgentDelegationPolicy = Field(default_factory=AgentDelegationPolicy)
    memory_scope: AgentMemoryScope = Field(default_factory=AgentMemoryScope)
    limits: AgentLimits = Field(default_factory=AgentLimits)
    model_preference: AgentModelPreference = Field(default_factory=AgentModelPreference)
    provenance: AgentProvenance = Field(default_factory=AgentProvenance)
    triggers: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    version: str = "1.0.0"

    def permission_hash(self) -> str:
        """Deterministic hash of permission-sensitive boundaries."""
        scope_data = {
            "allowed_tools": sorted(self.allowed_tools),
            "allowed_skills": sorted(self.allowed_skills),
            "delegation": self.delegation_policy.model_dump(),
            "memory": self.memory_scope.model_dump(),
            "limits": self.limits.model_dump(),
        }
        encoded = json.dumps(scope_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate_against_system(
        self,
        available_tools: set[str],
        available_skills: set[str] | None = None,
    ) -> list[str]:
        """Validate that all declared tools and skills exist."""
        errors: list[str] = []
        for t in self.allowed_tools:
            if t not in available_tools:
                errors.append(f"Tool '{t}' is not available in system tool registry.")

        if available_skills is not None:
            for s in self.allowed_skills:
                if s not in available_skills:
                    errors.append(f"Skill '{s}' is not registered in skill manager.")

        if self.limits.max_steps < 1 or self.limits.max_steps > 100:
            errors.append(f"max_steps ({self.limits.max_steps}) must be between 1 and 100.")

        if self.limits.timeout_seconds < 1.0 or self.limits.timeout_seconds > 600.0:
            errors.append(f"timeout_seconds ({self.limits.timeout_seconds}) must be between 1 and 600 seconds.")

        return errors

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> AgentManifest:
        return cls.model_validate(data)
