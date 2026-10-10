"""
Task-Scoped Permissions and Dynamic Model Routing Engine.
Living Assistant - Security & Multi-Agent Execution Subsystem (Milestone 3 / Feature F8).

Enforces:
    ROLE + TASK + ENVIRONMENT + RESOURCE + RISK = ALLOWED ACTIONS

Directives incorporated:
- B1: Depth limit enforcement.
- B2: Frozen test protection & evidence-based validation.
- B3: Token budget & loop bounds.
- B5: Workspace confinement & path isolation.
- B6: VRAM leasing & serial model execution default on <=4GB VRAM.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from pydantic import BaseModel, Field

from living_assistant.core.approval import ApprovalManager
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.security.security_policy import Decision, Risk, classify_command
from living_assistant.security.security_utils import is_sensitive_path
from living_assistant.tools.base import Tool
from living_assistant.tools.registry import ToolRegistry

logger = logging.getLogger("living_assistant.security.permissions")


class PermissionDeniedViolation(PermissionError):
    """Raised when an action is strictly blocked by task-scoped permission policies."""
    pass


class IntegrityMode(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class TaskComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LatencyCostPreference(str, Enum):
    OFFLINE_ONLY = "offline_only"
    LOW_LATENCY = "low_latency"
    BALANCED = "balanced"
    MAX_QUALITY = "max_quality"


class TaskScope(BaseModel):
    """
    Defines the boundaries, allowed paths, frozen tests, and constraints
    for a specific subtask executed by an agent.
    """
    task_id: str
    goal: str = ""
    role: str = ""
    target_paths: List[str] = Field(default_factory=list, description="Whitelisted paths/globs the role may modify")
    frozen_paths: List[str] = Field(default_factory=list, description="Immutable test files or production assets that cannot be altered")
    allowed_tools: Optional[List[str]] = Field(default=None, description="Explicit whitelist of tool names")
    denied_tools: List[str] = Field(default_factory=list, description="Explicit blacklist of tool names")
    read_only: bool = Field(default=False, description="Strict read-only enforcement")
    allow_network: bool = Field(default=False, description="Allow external network tools")
    allow_shell: bool = Field(default=False, description="Allow shell execution")
    allow_git: bool = Field(default=False, description="Allow git operations")
    max_file_size_bytes: int = Field(default=10_000_000, description="Max editable file size")
    timeout_seconds: float = Field(default=300.0, description="Task execution timeout")
    max_depth: int = Field(default=3, description="Directive B1: Max delegation depth")
    budget_tokens: int = Field(default=100_000, description="Directive B3: Token budget")


@dataclass(frozen=True)
class PermissionDecision:
    """Outcome of evaluating a tool action against security policy."""
    allowed: bool
    risk: Risk
    requires_approval: bool
    reason: str
    remediation_hint: Optional[str] = None


# Canonical capability declarations per role
ROLE_CAPABILITY_MATRIX: Dict[str, Dict[str, Any]] = {
    "manager": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "product": {
        "allowed_tools": {"read_file", "list_files", "search_files"},
        "can_write": False,
        "can_execute": False,
    },
    "product_manager": {
        "allowed_tools": {"read_file", "list_files", "search_files"},
        "can_write": False,
        "can_execute": False,
    },
    "architect": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "software_architect": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "ux_designer": {
        "allowed_tools": {"read_file", "list_files", "search_files", "browser_snapshot"},
        "can_write": False,
        "can_execute": False,
    },
    "ui_designer": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "browser_snapshot"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": False,
    },
    "design_system": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "browser_snapshot"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": False,
    },
    "backend_dev": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command", "git_status", "git_diff"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "denied_path_patterns": [".env*", "**/secrets/**", "credentials/**"],
        "can_execute": True,
        "allowed_command_patterns": [r"^(?:pytest|python|uv|pip|poetry)", r"^git\s+(?:status|diff)"],
    },
    "frontend_dev": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command", "browser_snapshot", "git_status", "git_diff"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "denied_path_patterns": [".env*", "src/**/security/**"],
        "can_execute": True,
        "allowed_command_patterns": [r"^(?:npm|pnpm|yarn|node|vitest)", r"^git\s+(?:status|diff)"],
    },
    "database": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": True,
        "allowed_command_patterns": [r"^(?:alembic|python|sqlite3|pytest)"],
    },
    "database_engineer": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": True,
        "allowed_command_patterns": [r"^(?:alembic|python|sqlite3|pytest)"],
    },
    "data_analyst": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
        "allowed_command_patterns": [r"^(?:python|pytest)"],
    },
    "ai_engineer": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "denied_path_patterns": [".env*"],
        "can_execute": True,
    },
    "devops": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command", "git_status"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": True,
    },
    "devops_sre": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command", "git_status"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": True,
    },
    "qa_engineer": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command", "browser_snapshot", "git_status", "git_diff"},
        "can_write": True,
        "writable_path_patterns": ["tests/**", "test/**", "e2e/**"],
        "denied_path_patterns": ["src/**", "server/**", "api/**"],  # QA cannot edit source code directly!
        "can_execute": True,
        "allowed_command_patterns": [r"^(?:pytest|python\s+-m\s+pytest|npm\s+test)", r"^git\s+(?:status|diff)"],
    },
    "performance": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
    },
    "performance_engineer": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
    },
    "accessibility": {
        "allowed_tools": {"read_file", "list_files", "search_files", "browser_snapshot"},
        "can_write": False,
        "can_execute": False,
    },
    "security_lead": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "appsec": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
    },
    "appsec_engineer": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
    },
    "vapt": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
    },
    "vapt_red_team": {
        "allowed_tools": {"read_file", "list_files", "search_files", "run_command"},
        "can_write": False,
        "can_execute": True,
    },
    "security_auditor": {
        "allowed_tools": {"read_file", "list_files", "search_files"},
        "can_write": False,
        "can_execute": False,
    },
    "seo": {
        "allowed_tools": {"read_file", "list_files", "search_files"},
        "can_write": False,
        "can_execute": False,
    },
    "code_reviewer": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "change_manager": {
        "allowed_tools": {"git_status", "git_diff", "git_commit", "read_file", "list_files"},
        "can_write": False,
        "can_execute": False,
    },
    "release_manager": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "verifier": {
        "allowed_tools": {"read_file", "list_files", "search_files", "git_status", "git_diff"},
        "can_write": False,
        "can_execute": False,
    },
    "tool_operator": {
        "allowed_tools": {"read_file", "write_file", "edit_file", "delete_file", "list_files", "search_files", "run_command", "browser_snapshot", "web_search"},
        "can_write": True,
        "writable_path_patterns": ["**", "*"],
        "can_execute": True,
    },
    "github_researcher": {
        "allowed_tools": {"read_file", "list_files", "search_files", "web_search"},
        "can_write": False,
        "can_execute": False,
        "allow_network": True,
    },
    "web_researcher": {
        "allowed_tools": {"read_file", "list_files", "search_files", "web_search"},
        "can_write": False,
        "can_execute": False,
        "allow_network": True,
    },
    "computer_operator": {
        "allowed_tools": {"read_file", "list_files", "search_files", "browser_snapshot"},
        "can_write": False,
        "can_execute": False,
    },
}


class TaskScopedPermissionEngine:
    """
    Evaluates: ROLE + TASK + ENVIRONMENT + RESOURCE + RISK = ALLOWED ACTIONS.
    Enforces task scoping, path confinement, frozen test protection, and approval gates.
    """

    def __init__(
        self,
        workspace: Workspace,
        approval_manager: Optional[ApprovalManager] = None,
        integrity_mode: IntegrityMode = IntegrityMode.DEVELOPMENT,
    ):
        self.workspace = workspace
        self.approval_manager = approval_manager
        self.integrity_mode = integrity_mode

    def evaluate(
        self,
        role: str,
        task_scope: TaskScope,
        tool_name: str,
        arguments: Dict[str, Any],
        environment: Optional[Dict[str, Any]] = None,
        current_depth: int = 0,
        consumed_tokens: int = 0,
    ) -> PermissionDecision:
        env = environment or {}

        # 0. Budget and Depth limits check (Directive B1 & B3)
        if current_depth > task_scope.max_depth:
            return PermissionDecision(
                allowed=False,
                risk=Risk.PRIVILEGED,
                requires_approval=False,
                reason=f"Exceeded maximum delegation depth limit ({current_depth} > {task_scope.max_depth}).",
            )

        if consumed_tokens > task_scope.budget_tokens:
            return PermissionDecision(
                allowed=False,
                risk=Risk.PRIVILEGED,
                requires_approval=False,
                reason=f"Exceeded assigned token execution budget ({consumed_tokens} > {task_scope.budget_tokens}).",
            )

        role_spec = ROLE_CAPABILITY_MATRIX.get(role.lower(), {
            "allowed_tools": {"read_file", "list_files", "search_files"},
            "can_write": False,
            "can_execute": False,
        })

        # 1. ROLE check
        allowed_for_role = role_spec.get("allowed_tools", set())
        if tool_name not in allowed_for_role:
            return PermissionDecision(
                allowed=False,
                risk=Risk.PRIVILEGED,
                requires_approval=False,
                reason=f"Tool '{tool_name}' is not in the granted capability set for role '{role}'.",
            )

        # 2. TASK check
        if task_scope.read_only and tool_name in {"write_file", "edit_file", "delete_file", "git_commit"}:
            return PermissionDecision(
                allowed=False,
                risk=Risk.WRITE_WORKSPACE,
                requires_approval=False,
                reason=f"Task '{task_scope.task_id}' is marked read-only; mutation tool '{tool_name}' is prohibited.",
            )

        if task_scope.allowed_tools and tool_name not in task_scope.allowed_tools:
            return PermissionDecision(
                allowed=False,
                risk=Risk.PRIVILEGED,
                requires_approval=False,
                reason=f"Tool '{tool_name}' is not in task '{task_scope.task_id}' explicit allowed_tools list.",
            )

        if tool_name in task_scope.denied_tools:
            return PermissionDecision(
                allowed=False,
                risk=Risk.PRIVILEGED,
                requires_approval=False,
                reason=f"Tool '{tool_name}' is explicitly denied by task '{task_scope.task_id}'.",
            )

        # 3. RESOURCE check (Filesystem Confinement & Frozen Tests)
        if tool_name in {"read_file", "write_file", "edit_file", "delete_file", "list_files"}:
            path_arg = arguments.get("path") or arguments.get("file_path") or "."
            try:
                resolved_p = self.workspace.resolve(path_arg)
            except WorkspaceViolation as exc:
                return PermissionDecision(
                    allowed=False,
                    risk=Risk.PRIVILEGED,
                    requires_approval=False,
                    reason=f"Path traversal violation: {exc}",
                )

            # Determine relative path within workspace
            rel_path = str(resolved_p)
            for root in self.workspace.roots:
                try:
                    rel_path = str(resolved_p.relative_to(root)).replace("\\", "/")
                    break
                except ValueError:
                    pass

            # Check frozen tests / immutable paths (Directive B2)
            if tool_name in {"write_file", "edit_file", "delete_file"}:
                for frozen in task_scope.frozen_paths:
                    norm_frozen = frozen.replace("\\", "/").rstrip("/*")
                    if fnmatch.fnmatch(rel_path, frozen) or rel_path == norm_frozen or rel_path.startswith(norm_frozen + "/"):
                        return PermissionDecision(
                            allowed=False,
                            risk=Risk.DESTRUCTIVE,
                            requires_approval=False,
                            reason=f"Path '{rel_path}' is a frozen/immutable test suite and cannot be modified by agent.",
                        )

            # Sensitive file protection
            if is_sensitive_path(resolved_p):
                if tool_name in {"write_file", "edit_file", "delete_file"}:
                    return PermissionDecision(
                        allowed=True,
                        risk=Risk.DESTRUCTIVE,
                        requires_approval=True,
                        reason=f"Modifying/deleting sensitive configuration file '{rel_path}' requires explicit user approval.",
                    )
                else:
                    return PermissionDecision(
                        allowed=True,
                        risk=Risk.PRIVILEGED,
                        requires_approval=True,
                        reason=f"Reading sensitive configuration file '{rel_path}' requires explicit user approval.",
                    )

            # Role path restrictions (e.g., QA can only edit tests; Dev cannot edit tests or outside src)
            if tool_name in {"write_file", "edit_file", "delete_file"}:
                writable_patterns = role_spec.get("writable_path_patterns")
                if writable_patterns:
                    matches_writable = any(fnmatch.fnmatch(rel_path, pat) for pat in writable_patterns)
                    if not matches_writable:
                        return PermissionDecision(
                            allowed=False,
                            risk=Risk.WRITE_WORKSPACE,
                            requires_approval=False,
                            reason=f"Role '{role}' is restricted from modifying '{rel_path}'. Allowed patterns: {writable_patterns}",
                        )

                denied_patterns = role_spec.get("denied_path_patterns")
                if denied_patterns and any(fnmatch.fnmatch(rel_path, pat) for pat in denied_patterns):
                    return PermissionDecision(
                        allowed=False,
                        risk=Risk.WRITE_WORKSPACE,
                        requires_approval=False,
                        reason=f"Path '{rel_path}' matches denied pattern for role '{role}'.",
                    )

                # Task-scoped target path check
                if task_scope.target_paths:
                    matches_target = any(
                        fnmatch.fnmatch(rel_path, target) or rel_path == target.rstrip("/*") or rel_path.startswith(target.rstrip("/*") + "/")
                        for target in task_scope.target_paths
                    )
                    if not matches_target:
                        return PermissionDecision(
                            allowed=False,
                            risk=Risk.WRITE_WORKSPACE,
                            requires_approval=False,
                            reason=f"File '{rel_path}' is outside task '{task_scope.task_id}' assigned target paths: {task_scope.target_paths}",
                        )

        # 4. RISK check (Shell command analysis)
        if tool_name == "run_command":
            cmd = arguments.get("command") or arguments.get("cmd") or ""
            decision: Decision = classify_command(cmd)

            if not decision.allowed:
                return PermissionDecision(
                    allowed=False,
                    risk=decision.risk,
                    requires_approval=False,
                    reason=f"Command blocked by safety policy: {decision.reason}",
                )

            # Check role-specific command pattern whitelist
            allowed_cmd_pats = role_spec.get("allowed_command_patterns")
            if allowed_cmd_pats:
                if not any(re.search(pat, cmd.strip(), re.I) for pat in allowed_cmd_pats):
                    return PermissionDecision(
                        allowed=True,
                        risk=Risk.EXECUTE,
                        requires_approval=True,
                        reason=f"Command '{cmd}' does not match standard test/inspection patterns for role '{role}'; requires approval.",
                    )

            if decision.requires_approval:
                return PermissionDecision(
                    allowed=True,
                    risk=decision.risk,
                    requires_approval=True,
                    reason=decision.reason,
                )

        # 5. ENVIRONMENT check
        integrity = env.get("integrity_mode", self.integrity_mode)
        if integrity == IntegrityMode.PRODUCTION:
            if tool_name in {"write_file", "edit_file", "delete_file", "run_command", "git_commit"}:
                return PermissionDecision(
                    allowed=True,
                    risk=Risk.SYSTEM_CHANGE,
                    requires_approval=True,
                    reason="Production integrity mode requires human approval for all mutations and executions.",
                )

        if env.get("network_isolated") and tool_name == "web_search":
            return PermissionDecision(
                allowed=False,
                risk=Risk.NETWORK_FETCH,
                requires_approval=False,
                reason="Web search is disallowed in network-isolated environment.",
            )

        # Permitted automatic action
        return PermissionDecision(
            allowed=True,
            risk=Risk.READ if tool_name in {"read_file", "list_files", "search_files"} else (Risk.DESTRUCTIVE if tool_name == "delete_file" else Risk.WRITE_WORKSPACE),
            requires_approval=False,
            reason="Action conforms to role, task scope, and security policy.",
        )

    def enforce(
        self,
        role: str,
        task_scope: TaskScope,
        tool_name: str,
        arguments: Dict[str, Any],
        environment: Optional[Dict[str, Any]] = None,
        current_depth: int = 0,
        consumed_tokens: int = 0,
    ) -> None:
        """
        Evaluates permissions and raises PermissionDeniedViolation if not allowed.
        """
        decision = self.evaluate(
            role=role,
            task_scope=task_scope,
            tool_name=tool_name,
            arguments=arguments,
            environment=environment,
            current_depth=current_depth,
            consumed_tokens=consumed_tokens,
        )
        if not decision.allowed:
            raise PermissionDeniedViolation(decision.reason)

    def create_scoped_registry(
        self,
        base_registry: ToolRegistry,
        role: str,
        task_scope: TaskScope,
        environment: Optional[Dict[str, Any]] = None,
    ) -> ToolRegistry:
        """
        Constructs an armored ToolRegistry exposing only tools permitted for this role and task,
        with runtime security verification wrapping each handler.
        """
        scoped = ToolRegistry()
        role_spec = ROLE_CAPABILITY_MATRIX.get(role.lower(), {})
        allowed_tools = role_spec.get("allowed_tools", set())

        for tool in base_registry.all():
            if tool.name not in allowed_tools:
                continue
            if task_scope.allowed_tools and tool.name not in task_scope.allowed_tools:
                continue
            if tool.name in task_scope.denied_tools:
                continue
            if task_scope.read_only and tool.name in {"write_file", "edit_file", "git_commit"}:
                continue

            # Create wrapped handler that checks permissions dynamically
            orig_handler = tool.handler
            tool_name_captured = tool.name

            def make_wrapped_handler(orig_fn: Callable, t_name: str):
                def wrapped_handler(**kwargs):
                    decision = self.evaluate(
                        role=role,
                        task_scope=task_scope,
                        tool_name=t_name,
                        arguments=kwargs,
                        environment=environment,
                    )
                    if not decision.allowed:
                        raise PermissionDeniedViolation(decision.reason)
                    if decision.requires_approval and self.approval_manager:
                        app_res = self.approval_manager.request(
                            action=f"{t_name}({kwargs})",
                            reason=decision.reason,
                            kind="security_gate",
                        )
                        if not app_res.get("allowed"):
                            return {
                                "ok": False,
                                "status": "PENDING_APPROVAL",
                                "approval_id": app_res.get("approval_id"),
                                "message": app_res.get("message", "Action requires human approval."),
                            }
                    return orig_fn(**kwargs)
                return wrapped_handler

            wrapped_tool = Tool(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                handler=make_wrapped_handler(orig_handler, tool_name_captured),
            )
            scoped.register(wrapped_tool)

        return scoped


# =============================================================================
# Directive B6: VRAM Lease Manager
# =============================================================================

@dataclass
class VRAMLease:
    lease_id: str
    vram_mb: int
    granted_at: float
    expires_at: float


class VRAMLeaseManager:
    """
    Manages VRAM concurrency leases for local model execution under Directive B6.
    Enforces strictly serial execution default on 4GB VRAM.
    """

    def __init__(self, total_vram_mb: int = 4096):
        self.total_vram_mb = total_vram_mb
        self._lock = threading.Lock()
        self._active_leases: Dict[str, VRAMLease] = {}

    def acquire_lease(self, requested_mb: int = 2048, duration_seconds: float = 60.0) -> Optional[VRAMLease]:
        with self._lock:
            now = time.time()
            # Clean expired leases
            self._active_leases = {
                lid: l for lid, l in self._active_leases.items() if l.expires_at > now
            }
            used_mb = sum(l.vram_mb for l in self._active_leases.values())
            if used_mb + requested_mb > self.total_vram_mb:
                return None  # Insufficient VRAM; must serialize

            lease = VRAMLease(
                lease_id=uuid.uuid4().hex[:8],
                vram_mb=requested_mb,
                granted_at=now,
                expires_at=now + duration_seconds,
            )
            self._active_leases[lease.lease_id] = lease
            return lease

    def release_lease(self, lease_id: str) -> None:
        with self._lock:
            self._active_leases.pop(lease_id, None)


# =============================================================================
# Dynamic Model Router (F8 / Directive B6)
# =============================================================================

@dataclass
class ModelRouteRequest:
    task_description: str
    role: str
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    risk: Risk = Risk.READ
    context_tokens: int = 2048
    preference: LatencyCostPreference = LatencyCostPreference.BALANCED
    force_local: bool = False
    requires_parallel: bool = False


@dataclass
class ModelRouteResult:
    model_name: str
    provider: str
    base_url: Optional[str]
    endpoint_type: str
    tier: str
    rationale: str
    fallback_models: List[str] = field(default_factory=list)
    serial_enforced: bool = True


class DynamicModelRouter:
    """
    Evaluates: TASK + ROLE + COMPLEXITY + RISK + CONTEXT + LATENCY/COST + HARDWARE = SELECTED MODEL.
    Implements Directive B6: Serial execution default on 4GB local VRAM; parallelism only via VRAM lease.
    """

    def __init__(
        self,
        collibri_base_url: str = "http://127.0.0.1:8080/v1",
        collibri_model: str = "openai/collibri",
        primary_coding_model: str = "anthropic:claude-3-5-sonnet",
        frontier_reasoning_model: str = "anthropic:claude-3-7-sonnet",
        resource_manager=None,
        lease_manager: Optional[VRAMLeaseManager] = None,
    ):
        self.collibri_base_url = collibri_base_url
        self.collibri_model = collibri_model
        self.primary_coding_model = primary_coding_model
        self.frontier_reasoning_model = frontier_reasoning_model
        self.resource_manager = resource_manager
        self.lease_manager = lease_manager or VRAMLeaseManager(total_vram_mb=4096)

    def is_collibri_available(self) -> bool:
        """Lightweight health check against the local Collibri llama.cpp endpoint."""
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self.collibri_base_url.rstrip('/')}/models",
                headers={"User-Agent": "LA-Router"},
            )
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def route(self, req: ModelRouteRequest) -> ModelRouteResult:
        is_throttled = False
        if self.resource_manager:
            is_throttled = getattr(self.resource_manager, "is_throttled", False)

        serial_enforced = True
        if req.requires_parallel:
            lease = self.lease_manager.acquire_lease(requested_mb=2048)
            if lease is not None:
                serial_enforced = False
            else:
                serial_enforced = True  # Fall back to serial execution

        collibri_ready = self.is_collibri_available()

        # Offline or forced local preference
        if req.preference == LatencyCostPreference.OFFLINE_ONLY or req.force_local:
            if collibri_ready:
                return ModelRouteResult(
                    model_name=self.collibri_model,
                    provider="ollama",
                    base_url=self.collibri_base_url,
                    endpoint_type="collibri",
                    tier="local_edge",
                    rationale="Strict offline preference routed to local Collibri llama.cpp server under Directive B6 serial execution.",
                    fallback_models=["ollama/llama3.2", "local/cpu"],
                    serial_enforced=serial_enforced,
                )
            return ModelRouteResult(
                model_name="ollama/llama3.2",
                provider="ollama",
                base_url="http://127.0.0.1:11434",
                endpoint_type="ollama",
                tier="local_edge",
                rationale="Offline preference with Collibri endpoint unavailable; falling back to Ollama.",
                fallback_models=[],
                serial_enforced=True,
            )

        # Frontier Reasoning Tier (Manager, Architect, Security Lead, Verifier, Critical Complexity)
        frontier_roles = {"manager", "software_architect", "architect", "security_lead", "verifier", "security_auditor"}
        if (
            req.role.lower() in frontier_roles
            or req.complexity == TaskComplexity.CRITICAL
            or req.risk in {Risk.PRIVILEGED, Risk.SYSTEM_CHANGE, Risk.DESTRUCTIVE}
        ):
            return ModelRouteResult(
                model_name=self.frontier_reasoning_model,
                provider="litellm",
                base_url=None,
                endpoint_type="litellm_cloud",
                tier="frontier_reasoning",
                rationale=f"High-stakes role '{req.role}' and complexity '{req.complexity.value}' routed to frontier reasoning model for architectural integrity.",
                fallback_models=[self.primary_coding_model, self.collibri_model],
                serial_enforced=False,
            )

        # Local Edge Tier (Low complexity, small context, routine parsing, search research)
        if req.complexity == TaskComplexity.LOW and req.context_tokens <= 4096 and req.risk == Risk.READ:
            if collibri_ready and not is_throttled:
                return ModelRouteResult(
                    model_name=self.collibri_model,
                    provider="ollama",
                    base_url=self.collibri_base_url,
                    endpoint_type="collibri",
                    tier="local_edge",
                    rationale="Low-complexity task with minimal context routed to zero-cost local Collibri instance.",
                    fallback_models=[self.primary_coding_model],
                    serial_enforced=serial_enforced,
                )

        # Primary Coding Tier (Backend dev, Frontend dev, QA, DB engineer)
        return ModelRouteResult(
            model_name=self.primary_coding_model,
            provider="litellm",
            base_url=None,
            endpoint_type="litellm_cloud",
            tier="primary_coding",
            rationale=f"Code implementation task for role '{req.role}' routed to primary coding engine.",
            fallback_models=[self.frontier_reasoning_model, self.collibri_model],
            serial_enforced=False,
        )
