"""
Incident Recovery & Human-in-the-Loop Action Approval (Milestone 5 / Feature F12).
Living Assistant - Security & Governance Subsystem.

Implements:
1. Action Classification:
   - AUTOMATIC: read files, run tests, analyze code, workspace edits, local checkpoints.
   - APPROVAL_REQUIRED: production deployments, destructive database migrations, force pushes,
     deleting critical project files, modifying security policies.
   - PROHIBITED: git reset --hard, fork bombs, format disk, destructive disk wipes.
2. 8-Stage Incident Containment & Recovery Workflow:
   DETECTED -> DIAGNOSED -> CONTAINED -> ROLLED_BACK -> REPAIRED -> TESTED -> VERIFIED -> RESOLVED.
   If verification tests fail during verify_and_resolve, the incident remains at TESTED
   and does not transition to RESOLVED.
"""

from __future__ import annotations

import datetime as dt
import enum
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from living_assistant.core.approval import ApprovalManager
from living_assistant.core.workspace import Workspace
from living_assistant.system.git_manager import GitChangeManager

logger = logging.getLogger("living_assistant.agents.software_company.incident_recovery")


class ActionClass(str, enum.Enum):
    """Action classification for governance and human-in-the-loop gates."""
    AUTOMATIC = "automatic"
    APPROVAL_REQUIRED = "approval_required"
    PROHIBITED = "prohibited"


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStage(str, enum.Enum):
    DETECTED = "detected"
    DIAGNOSED = "diagnosed"
    CONTAINED = "contained"
    ROLLED_BACK = "rolled_back"
    REPAIRED = "repaired"
    TESTED = "tested"
    VERIFIED = "verified"
    RESOLVED = "resolved"


# Explicit approval-required command / tool patterns per Addendum Section 5 (retained for backward compatibility)
_APPROVAL_REQUIRED_PATTERNS = {
    "git push --force",
    "git push -f",
    "deploy --prod",
    "production deploy",
    "drop database",
    "truncate table",
    "rm -rf",
    "modify_security_policy",
    "delete_critical_data",
}

_PROHIBITED_COMMANDS = {
    "git reset --hard",
    ":(){ :|:& };:",
    "format c:",
}

# Precompiled regex patterns for Prohibited actions (Non-destructive safety policy)
_PROHIBITED_REGEXES: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+reset\b[^\n;&|]*?\s+['\"]?--hard['\"]?\b", re.IGNORECASE),
        "git reset --hard",
    ),
    (
        re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&", re.IGNORECASE),
        "fork bomb",
    ),
    (
        re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*[;\s]*:", re.IGNORECASE),
        "fork bomb",
    ),
    (
        re.compile(r"\bformat(?:\.com)?\b(?:\s+/[a-z0-9:/-]+)*\s+[a-z]:", re.IGNORECASE),
        "format disk",
    ),
    (
        re.compile(r"\bformat(?:\.com)?\b\s+[a-z]:", re.IGNORECASE),
        "format disk",
    ),
    (
        re.compile(r"\bformat\s+disk\b", re.IGNORECASE),
        "format disk",
    ),
    (
        re.compile(r"\bmkfs(?:\.[a-z0-9_-]+)?\b", re.IGNORECASE),
        "mkfs",
    ),
]

# Precompiled regex patterns for Approval-Required actions (Human governance gate)
_APPROVAL_REQUIRED_REGEXES: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\bgit\s+push\b[^\n;&|]*?\s+['\"]?(?:-[a-z]*f[a-z]*|--force(?:-[a-z0-9_-]+)?|\+[a-z0-9_/-]+)['\"]?\b",
            re.IGNORECASE,
        ),
        "git push --force",
    ),
    (
        re.compile(r"\bdeploy\b[^\n;&|]*?\s+--(?:prod|production)\b", re.IGNORECASE),
        "deploy --prod",
    ),
    (
        re.compile(r"\bproduction\s+deploy\b", re.IGNORECASE),
        "production deploy",
    ),
    (
        re.compile(r"\bdeploy\s+(?:to\s+)?production\b", re.IGNORECASE),
        "production deploy",
    ),
    (
        re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
        "drop database",
    ),
    (
        re.compile(r"\btruncate\s+(?:table\s+)?[a-z0-9_\"'`]+", re.IGNORECASE),
        "truncate table",
    ),
    (
        re.compile(
            r"\brm\s+[^\n;&|]*?-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)[a-z]*\b",
            re.IGNORECASE,
        ),
        "rm -rf",
    ),
    (
        re.compile(r"\brm\s+[^\n;&|]*?-r\s+[^\n;&|]*?-f\b", re.IGNORECASE),
        "rm -rf",
    ),
    (
        re.compile(r"\bmodify[_\s]+security[_\s]+policy\b", re.IGNORECASE),
        "modify_security_policy",
    ),
    (
        re.compile(r"\bdelete[_\s]+critical[_\s]+data\b", re.IGNORECASE),
        "delete_critical_data",
    ),
]


@dataclass
class IncidentReport:
    incident_id: str
    task_id: str
    severity: IncidentSeverity
    summary: str
    detected_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    stage: IncidentStage = IncidentStage.DETECTED
    diagnosis: str = ""
    containment_actions: List[str] = field(default_factory=list)
    rollback_applied: bool = False
    repaired_artifacts: List[str] = field(default_factory=list)
    verification_passed: bool = False
    resolved_at: Optional[str] = None


class ActionGatekeeper:
    """
    Evaluates actions against security governance and human approval requirements.
    Wraps ApprovalManager to enforce human approval for privileged or destructive operations.
    """

    def __init__(
        self,
        approval_manager: Optional[ApprovalManager] = None,
        workspace: Optional[Workspace] = None,
    ) -> None:
        self.approval_manager = approval_manager
        self.workspace = workspace

    def classify_action(self, action_name: str, arguments: Dict[str, Any]) -> Tuple[ActionClass, str]:
        """Classifies an action as AUTOMATIC, APPROVAL_REQUIRED, or PROHIBITED."""
        action_raw = str(action_name or "").strip()
        cmd_raw = str(arguments.get("command") or "").strip()

        # Canonical whitespace collapsing: map \s+ (multiple spaces, tabs, newlines) to single space
        norm_cmd = re.sub(r"\s+", " ", cmd_raw).lower().strip()
        norm_action = re.sub(r"\s+", " ", action_raw).lower().strip()
        targets = [t for t in (norm_cmd, norm_action) if t]

        # 1. Prohibited actions (robust regexes)
        for pattern, desc in _PROHIBITED_REGEXES:
            for target in targets:
                if pattern.search(target):
                    return ActionClass.PROHIBITED, f"Action violates non-destructive safety policy: {desc}"

        # 2. Approval required actions (robust regexes)
        for pattern, desc in _APPROVAL_REQUIRED_REGEXES:
            for target in targets:
                if pattern.search(target):
                    return ActionClass.APPROVAL_REQUIRED, f"Action requires human approval: {desc}"

        # Check explicit tool arguments
        if arguments.get("force_push") or arguments.get("is_production_deploy"):
            return ActionClass.APPROVAL_REQUIRED, "Privileged deployment / remote push requires approval."

        # Check path deletion of critical project files
        critical_files = ["system.graph.yaml", "requirements.graph.yaml", ".git", "pyproject.toml"]
        path = str(arguments.get("path") or arguments.get("target") or "").lower()
        if norm_action in {"delete_file", "rm", "unlink", "delete"}:
            if any(crit in path for crit in critical_files):
                return ActionClass.APPROVAL_REQUIRED, f"Deletion of critical project artifact requires approval: {path}"

        if re.search(r"\b(?:rm|del|unlink|remove)\s+", norm_cmd):
            if any(crit in norm_cmd for crit in critical_files):
                return ActionClass.APPROVAL_REQUIRED, f"Deletion of critical project artifact requires approval: {norm_cmd}"

        # 3. Automatic actions
        return ActionClass.AUTOMATIC, "Permitted automatic workspace/testing action."

    def evaluate_and_request(
        self,
        action_name: str,
        arguments: Dict[str, Any],
        task_id: str = "",
        role: str = "worker",
    ) -> Dict[str, Any]:
        """
        Evaluates action. If APPROVAL_REQUIRED, interacts with ApprovalManager.
        Returns outcome dict with allowed=True/False and approval status.
        Blocks execution if approval is denied or rejected.
        """
        action_class, reason = self.classify_action(action_name, arguments)

        if action_class == ActionClass.PROHIBITED:
            return {
                "allowed": False,
                "status": "PROHIBITED",
                "action_class": action_class.value,
                "reason": reason,
            }

        if action_class == ActionClass.APPROVAL_REQUIRED:
            if self.approval_manager:
                app_res = self.approval_manager.request(
                    action=f"{action_name}:{arguments}",
                    reason=reason,
                    kind="governance_gate",
                )
                is_allowed = bool(app_res.get("allowed", False))
                raw_status = str(app_res.get("status") or "").upper()
                if is_allowed:
                    status = "APPROVED"
                elif raw_status in {"REJECTED", "DENIED"}:
                    status = "REJECTED"
                else:
                    status = "PENDING_APPROVAL"

                return {
                    "allowed": is_allowed,
                    "status": status,
                    "action_class": action_class.value,
                    "approval_id": app_res.get("approval_id", "pending"),
                    "reason": reason,
                }
            # If no approval manager is configured, default to blocking approval-required actions
            return {
                "allowed": False,
                "status": "PENDING_APPROVAL",
                "action_class": action_class.value,
                "reason": f"ApprovalManager not configured. Blocked privileged action: {reason}",
            }

        return {
            "allowed": True,
            "status": "AUTOMATIC",
            "action_class": action_class.value,
            "reason": reason,
        }


class IncidentRecoveryManager:
    """
    Coordinates the 8-stage Incident & Recovery Workflow:
    DETECTED -> DIAGNOSED -> CONTAINED -> ROLLED_BACK -> REPAIRED -> TESTED -> VERIFIED -> RESOLVED.
    """

    def __init__(
        self,
        workspace: Workspace,
        change_manager: GitChangeManager,
        gatekeeper: Optional[ActionGatekeeper] = None,
    ) -> None:
        self.workspace = workspace
        self.change_manager = change_manager
        self.gatekeeper = gatekeeper or ActionGatekeeper(workspace=workspace)
        self.incidents: Dict[str, IncidentReport] = {}

    def detect_incident(
        self,
        task_id: str,
        error_context: str,
        severity: IncidentSeverity = IncidentSeverity.HIGH,
    ) -> IncidentReport:
        """Stage 1: Detect incident and log report."""
        inc_id = f"inc_{task_id}_{len(self.incidents) + 1}"
        report = IncidentReport(
            incident_id=inc_id,
            task_id=task_id,
            severity=severity,
            summary=error_context[:250],
        )
        self.incidents[inc_id] = report
        logger.warning("Incident detected (%s): %s", inc_id, report.summary)
        return report

    def diagnose_incident(self, incident_id: str, analysis: str) -> IncidentReport:
        """Stage 2: Record diagnostic root cause analysis."""
        report = self.incidents[incident_id]
        report.diagnosis = analysis
        report.stage = IncidentStage.DIAGNOSED
        return report

    def contain_incident(self, incident_id: str, action: str) -> IncidentReport:
        """Stage 3: Contain damage (e.g., kill rogue process, isolate branch)."""
        report = self.incidents[incident_id]
        report.containment_actions.append(action)
        report.stage = IncidentStage.CONTAINED
        return report

    def rollback_incident(self, incident_id: str, checkpoint_id: Optional[str] = None) -> IncidentReport:
        """Stage 4: Safely roll back workspace to clean checkpoint or task baseline."""
        report = self.incidents[incident_id]
        if checkpoint_id:
            res = self.change_manager.rollback_to_checkpoint(checkpoint_id)
        else:
            res = self.change_manager.rollback_to_baseline(report.task_id)

        report.rollback_applied = bool(res.get("ok", False))
        if report.rollback_applied:
            report.stage = IncidentStage.ROLLED_BACK
        logger.info(
            "Incident %s rolled back (ok=%s, method=%s, stage=%s)",
            incident_id,
            report.rollback_applied,
            res.get("method"),
            report.stage.value,
        )
        return report

    def record_repair(self, incident_id: str, repaired_artifacts: List[str]) -> IncidentReport:
        """Stage 5: Apply repaired code / configuration."""
        report = self.incidents[incident_id]
        report.repaired_artifacts = repaired_artifacts
        report.stage = IncidentStage.REPAIRED
        return report

    def verify_and_resolve(
        self,
        incident_id: str,
        tests_passed: bool,
    ) -> IncidentReport:
        """
        Stages 6, 7 & 8: Test -> Verify -> Document (Resolve).
        If verification tests fail, the incident remains at TESTED and does NOT transition to RESOLVED.
        """
        report = self.incidents[incident_id]
        report.verification_passed = tests_passed
        if tests_passed:
            report.stage = IncidentStage.RESOLVED
            report.resolved_at = dt.datetime.now(dt.timezone.utc).isoformat()
            logger.info("Incident %s fully resolved.", incident_id)
        else:
            report.stage = IncidentStage.TESTED
            logger.warning("Incident %s verification failed.", incident_id)
        return report
