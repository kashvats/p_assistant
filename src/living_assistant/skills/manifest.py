from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


SKILL_ID_REGEX = re.compile(r"^[a-z0-9_.-]{1,64}$")
SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9_.]+)?$")


class SkillPermissionScope(BaseModel):
    filesystem: list[str] = Field(default_factory=list, description="Allowed directory roots or relative paths, e.g. ['./workspace', './downloads']")
    network: bool = Field(default=False, description="Whether network access is permitted")
    network_hosts: list[str] = Field(default_factory=list, description="Allowlist of domain names/hosts if network is True")
    subprocess: bool = Field(default=False, description="Whether external system subprocess execution is permitted")
    destructive: bool = Field(default=False, description="Whether destructive file operations (delete, overwrite) are permitted")
    messaging: bool = Field(default=False, description="Whether messaging or notification emission is permitted")

    def permission_hash(self) -> str:
        """Deterministic hash of permission scopes to detect any permission expansions."""
        data = {
            "filesystem": sorted([p.strip().replace("\\", "/") for p in self.filesystem]),
            "network": bool(self.network),
            "network_hosts": sorted([h.strip().lower() for h in self.network_hosts]),
            "subprocess": bool(self.subprocess),
            "destructive": bool(self.destructive),
            "messaging": bool(self.messaging),
        }
        raw = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class SkillStep(BaseModel):
    id: str = Field(description="Unique step identifier, e.g. 'extract_invoice'")
    tool: str = Field(description="Tool or portable adapter interface, e.g. 'documents.extract'")
    description: str = Field(default="", description="Human-readable step intent")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Argument mapping with parameter interpolation support")
    output_variable: str | None = Field(default=None, description="Variable name to store output into execution context")
    when: str | None = Field(default=None, description="Declarative boolean condition expression")
    condition: str | None = Field(default=None, description="Alias for when condition")
    for_each: str | None = Field(default=None, description="Collection reference to iterate over, e.g. '{list_invoices.items}'")
    max_iterations: int = Field(default=100, ge=1, le=500, description="Upper bound for for_each iterations")
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=1800.0, description="Step execution timeout")
    retries: int = Field(default=0, ge=0, le=5, description="Number of retry attempts on error")
    retry_delay_seconds: float = Field(default=0.5, ge=0.0, le=60.0, description="Delay between retries")
    on_failure: Literal["abort", "continue", "fallback"] = Field(default="abort", description="Policy when step fails")
    fallback_step_id: str | None = Field(default=None, description="Step ID to jump to if on_failure is fallback")
    output_schema: dict[str, Any] | None = Field(default=None, description="Optional schema for output validation")


class SkillLimits(BaseModel):
    timeout_seconds: int = Field(default=120, ge=5, le=3600)
    max_steps: int = Field(default=20, ge=1, le=100)
    max_retries: int = Field(default=2, ge=0, le=5)


class SkillProvenance(BaseModel):
    author: str = Field(default="user")
    source: str = Field(default="local")
    created_at: str = Field(default="")
    signature: str | None = Field(default=None)


class SkillExample(BaseModel):
    title: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str = Field(default="")


class SkillManifest(BaseModel):
    schema_version: str = Field(default="1.0.0")
    id: str = Field(description="Unique stable alphanumeric lowercase identifier")
    name: str = Field(description="Display name")
    description: str = Field(default="", max_length=1000)
    version: str = Field(default="1.0.0")
    type: Literal["declarative_workflow", "instruction"] = Field(default="declarative_workflow")
    triggers: list[str] = Field(default_factory=list, description="Keywords or phrases that activate this skill")
    inputs_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for inputs")
    outputs_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for outputs")
    required_tools: list[str] = Field(default_factory=list, description="List of required application tools or portable interfaces")
    permissions: SkillPermissionScope = Field(default_factory=SkillPermissionScope)
    offline_capable: bool = Field(default=True)
    platforms: list[str] = Field(default_factory=lambda: ["windows", "linux", "darwin"])
    limits: SkillLimits = Field(default_factory=SkillLimits)
    provenance: SkillProvenance = Field(default_factory=SkillProvenance)
    workflow: list[SkillStep] = Field(default_factory=list, description="Declarative sequence of tool calls")
    examples: list[SkillExample] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        s = v.strip().lower()
        if not SKILL_ID_REGEX.match(s):
            raise ValueError(f"Skill id '{v}' must match {SKILL_ID_REGEX.pattern}")
        return s

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        s = v.strip()
        if not SEMVER_REGEX.match(s):
            raise ValueError(f"Version '{v}' must be semantic versioning (e.g. 1.0.0)")
        return s

    def validate_against_tools(self, registered_tools: set[str]) -> list[str]:
        """Verify that all required_tools and workflow steps use existing registered tools and satisfy contract."""
        from living_assistant.skills.evaluator import validate_workflow_contract
        errors = validate_workflow_contract(self.workflow, registered_tools, max_steps=self.limits.max_steps)
        portable_tools = {
            "files.list", "files.read", "files.move", "files.write", "files.preview_write",
            "documents.extract", "notifications.show", "calendar.list", "briefings.get",
            "personal.remember", "personal.recall"
        }
        all_valid = registered_tools | portable_tools
        for tool in self.required_tools:
            if tool not in all_valid:
                errors.append(f"Required tool '{tool}' is not registered in the application.")
        return errors

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, data: str | dict) -> SkillManifest:
        if isinstance(data, str):
            data = json.loads(data)
        return cls.model_validate(data)


def convert_legacy_skill(name: str, legacy_dict: dict) -> tuple[SkillManifest, str]:
    """Convert an existing flat legacy skill entry (from skills.json) into a valid manifest and SKILL.md."""
    clean_id = re.sub(r"[^a-z0-9_-]", "-", name.lower()).strip("-")
    if not clean_id:
        clean_id = "legacy-skill"
    desc = str(legacy_dict.get("description", ""))
    triggers = [str(t).strip().lower() for t in legacy_dict.get("triggers", []) if str(t).strip()]
    instructions = str(legacy_dict.get("instructions", ""))

    manifest = SkillManifest(
        schema_version="1.0.0",
        id=clean_id,
        name=name,
        description=desc,
        version="1.0.0",
        type="instruction",
        triggers=triggers,
        required_tools=[],
        permissions=SkillPermissionScope(
            filesystem=["."],
            network=False,
            subprocess=False,
            destructive=False,
            messaging=False,
        ),
        offline_capable=True,
        provenance=SkillProvenance(
            author="legacy_migration",
            source=legacy_dict.get("source", "legacy_skills_json"),
        ),
    )

    skill_md = f"""# {name}

## Purpose
{desc or "Migrated from legacy prompt skills."}

## Activation Triggers
{', '.join(f'`{t}`' for t in triggers) if triggers else "Explicit invocation."}

## Instructions
{instructions}
"""
    return manifest, skill_md
