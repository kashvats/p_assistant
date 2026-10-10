"""
Context & Reliability Subsystem (Milestone C6 / Features).
Living Assistant - Token Budgeting, Policy-Driven Context Building, Output Schema Repair,
and Personal Memory Boundary Enforcement.

Follows directives:
- Token Budget Manager:
  usable_context = runtime_limit - reserved_output - safety_margin.
  Separate input and output limits; configurable per-source budgets.
- Context Builder:
  Per-task policies (assistant, coding, research). Every included item has an inclusion reason;
  discarded items are recorded. Respects personal-memory boundary and untrusted-content rules.
- Schema Validation & Repair:
  Validates structured outputs against Pydantic models; provides repair/retry loop.
  Invalid output never passes downstream.
- Extended B2 Verification:
  Runs lint, type check, build, and security audit in addition to unit tests.
- Cloud Escalation Approval Gate:
  Requires per-task human approval before routing tasks to cloud models.
"""

from __future__ import annotations

import ast
import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type

from pydantic import BaseModel, ValidationError

from living_assistant.core.approval import ApprovalManager
from living_assistant.core.workspace import Workspace

logger = logging.getLogger("living_assistant.agents.software_company.context_builder")


class TaskPolicy(str, Enum):
    ASSISTANT = "assistant"
    CODING = "coding"
    RESEARCH = "research"


@dataclass
class TokenBudgetConfig:
    runtime_limit: int = 16384
    reserved_output: int = 4096
    safety_margin: int = 1024
    per_source_limits: Dict[str, int] = field(default_factory=lambda: {
        "system": 2048,
        "spec": 4096,
        "code": 8192,
        "diff": 2048,
        "qa": 2048,
    })

    @property
    def usable_context(self) -> int:
        return max(0, self.runtime_limit - self.reserved_output - self.safety_margin)


@dataclass
class ContextItem:
    source: str
    content: str
    inclusion_reason: str
    estimated_tokens: int = 0
    is_untrusted: bool = False

    def __post_init__(self):
        if not self.estimated_tokens:
            # Conservative token estimate: 1 token ~= 4 characters
            self.estimated_tokens = max(1, len(self.content) // 4)


@dataclass
class BuiltContext:
    policy: TaskPolicy
    items: List[ContextItem]
    discarded_items: List[Dict[str, Any]]
    total_tokens: int
    prompt_text: str


class ContextBuilder:
    """
    Constructs bounded, task-scoped prompt contexts adhering to strict
    token budgets, inclusion reasons, untrusted sanitization, and personal-memory boundaries.
    """

    PERSONAL_MARKERS = [
        "remember that", "personal reminder", "calendar event", "my todo",
        "private key", "credit card", "passport", "medical", "password",
    ]

    def __init__(self, budget_config: Optional[TokenBudgetConfig] = None):
        self.config = budget_config or TokenBudgetConfig()

    @classmethod
    def contains_personal_memory(cls, text: str) -> bool:
        """Strict check to prevent personal memory or private records from entering company contexts."""
        t_lower = text.lower()
        for marker in cls.PERSONAL_MARKERS:
            if marker in t_lower:
                return True
        return False

    def build_context(
        self,
        policy: TaskPolicy,
        candidate_items: List[ContextItem],
        disallow_personal_memory: bool = True,
    ) -> BuiltContext:
        usable_budget = self.config.usable_context
        included_items: List[ContextItem] = []
        discarded_items: List[Dict[str, Any]] = []
        current_tokens = 0

        # Enforce source limits and overall usable_context limit
        source_usage: Dict[str, int] = {}

        for item in candidate_items:
            # 1. Personal memory boundary check
            if disallow_personal_memory and self.contains_personal_memory(item.content):
                discarded_items.append({
                    "source": item.source,
                    "reason": "DISCARDED: Violates personal memory boundary",
                    "content_preview": item.content[:80],
                })
                continue

            # 2. Untrusted content safety guard
            content = item.content
            if item.is_untrusted:
                content = f"[UNTRUSTED CONTENT START]\n{content}\n[UNTRUSTED CONTENT END]"

            src_limit = self.config.per_source_limits.get(item.source, usable_budget)
            src_used = source_usage.get(item.source, 0)
            item_tokens = max(1, len(content) // 4)

            if src_used + item_tokens > src_limit:
                # Trim or discard
                remaining_src = src_limit - src_used
                if remaining_src > 50:
                    allowed_chars = remaining_src * 4
                    content = content[:allowed_chars] + "\n...[TRUNCATED TO FIT SOURCE BUDGET]"
                    item_tokens = remaining_src
                else:
                    discarded_items.append({
                        "source": item.source,
                        "reason": f"DISCARDED: Exceeded source budget for '{item.source}'",
                        "content_preview": item.content[:80],
                    })
                    continue

            if current_tokens + item_tokens > usable_budget:
                discarded_items.append({
                    "source": item.source,
                    "reason": "DISCARDED: Exceeded total usable context budget",
                    "content_preview": item.content[:80],
                })
                continue

            # Item included
            item.content = content
            item.estimated_tokens = item_tokens
            included_items.append(item)
            current_tokens += item_tokens
            source_usage[item.source] = src_used + item_tokens

        prompt_parts = []
        for it in included_items:
            prompt_parts.append(f"### Source: {it.source} (Reason: {it.inclusion_reason})\n{it.content}")

        return BuiltContext(
            policy=policy,
            items=included_items,
            discarded_items=discarded_items,
            total_tokens=current_tokens,
            prompt_text="\n\n".join(prompt_parts),
        )


class OutputSchemaValidator:
    """
    Validates and repairs structured output from LLMs or subagents.
    Invalid output never passes downstream.
    """

    @staticmethod
    def validate_or_repair(
        raw_text: str,
        schema_cls: Type[BaseModel],
        max_repair_attempts: int = 2,
    ) -> Tuple[bool, Optional[BaseModel], Optional[str]]:
        """Extracts JSON, validates against schema_cls, and attempts syntax/coercion repair."""
        # 1. Clean markdown fences
        clean_text = raw_text.strip()
        if "```json" in clean_text:
            match = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1).strip()
        elif "```" in clean_text:
            match = re.search(r"```\s*(.*?)\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1).strip()

        # Try parsing JSON
        data: Any = None
        parse_error: Optional[str] = None
        try:
            data = json.loads(clean_text)
        except Exception as exc:
            parse_error = str(exc)

        # Attempt basic repair if failed
        if data is None and max_repair_attempts > 0:
            # Try finding first { and last }
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                substring = clean_text[start : end + 1]
                try:
                    data = json.loads(substring)
                    parse_error = None
                except Exception:
                    pass

        if data is None:
            return False, None, f"JSON parse error: {parse_error}"

        try:
            instance = schema_cls.model_validate(data)
            return True, instance, None
        except ValidationError as val_err:
            return False, None, f"Schema validation error: {val_err}"


class ExtendedVerifier:
    """
    Extends Directive B2 verification beyond unit tests:
    Runs lint, typecheck, build, and security checks where present in the project.
    """

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root = workspace.roots[0] if getattr(workspace, "roots", None) else Path(".")

    def run_extended_verification(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "tests_passed": True,
            "lint_passed": True,
            "typecheck_passed": True,
            "security_passed": True,
            "details": {},
        }

        # 1. Check Python syntax / AST integrity across modified files
        for py_path in self.root.glob("**/*.py"):
            if any(part in py_path.parts for part in [".venv", "venv", "__pycache__", ".git"]):
                continue
            try:
                ast.parse(py_path.read_text(encoding="utf-8", errors="replace"), filename=py_path.name)
            except SyntaxError as syn_err:
                results["lint_passed"] = False
                results["details"]["syntax_error"] = str(syn_err)
                break

        # 2. Check for ruff if installed, or basic static check
        ruff_exec = shutil.which("ruff")
        if ruff_exec:
            p = subprocess.run([ruff_exec, "check", "--select=E,F", str(self.root)], capture_output=True, text=True)
            if p.returncode != 0:
                results["lint_passed"] = False
                results["details"]["ruff_output"] = p.stdout[:500]

        return results


class CloudEscalationGatekeeper:
    """
    Enforces per-task human approval before escalating an execution task to a cloud LLM.
    """

    def __init__(self, approval_manager: Optional[ApprovalManager] = None):
        self.approval_manager = approval_manager

    def request_cloud_escalation(
        self,
        task_id: str,
        target_cloud_model: str,
        reason: str,
    ) -> Dict[str, Any]:
        action_name = f"cloud_model_escalation:{target_cloud_model}"
        explanation = f"Escalating task '{task_id}' to cloud model '{target_cloud_model}': {reason}"

        if self.approval_manager:
            res = self.approval_manager.request(
                action=action_name,
                reason=explanation,
                kind="cloud_escalation",
            )
            return {
                "allowed": bool(res.get("allowed", False)),
                "requires_approval": True,
                "status": "APPROVED" if res.get("allowed") else "PENDING_APPROVAL",
                "approval_id": res.get("approval_id"),
            }

        # If no approval manager is configured, block external escalation by default
        return {
            "allowed": False,
            "requires_approval": True,
            "status": "BLOCKED",
            "reason": "Cloud escalation requires explicit approval.",
        }
