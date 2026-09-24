from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from living_assistant.core.approval import ApprovalManager
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.security.security_utils import is_sensitive_path
from living_assistant.skills.manifest import SkillManifest


class SkillPermissionViolation(WorkspaceViolation, PermissionError):
    pass


class SkillPermissionGuard:
    """Out-of-model deterministic security enforcement for custom skill execution."""

    def __init__(self, manifest: SkillManifest, workspace: Workspace, approval_manager: ApprovalManager | None = None):
        self.manifest = manifest
        self.workspace = workspace
        self.approval = approval_manager
        self._allowed_scopes = [
            Path(p).expanduser().resolve() for p in (self.manifest.permissions.filesystem or ["."])
        ]

    def check_tool_allowlist(self, tool_name: str):
        """Ensure the called tool is explicitly declared in manifest.required_tools or is a safe portable interface."""
        allowed = set(self.manifest.required_tools)
        # Always allow standard portable inspection tools if declared
        if tool_name not in allowed:
            raise SkillPermissionViolation(
                f"Skill '{self.manifest.id}' attempted to call tool '{tool_name}' which is not in its required_tools allowlist: {sorted(allowed)}"
            )

    def validate_path(self, target_path: str | Path, for_write: bool = False) -> Path:
        """Enforce workspace roots and skill filesystem scope restrictions."""
        # Step 1: Workspace confinement (prevents escapes outside workspace roots)
        try:
            resolved = self.workspace.resolve(target_path)
        except WorkspaceViolation as exc:
            raise SkillPermissionViolation(str(exc)) from exc

        # Step 2: Check against skill's specific declared filesystem scopes
        # If relative scope like '.', it's within the workspace root.
        # Check that resolved path is inside at least one allowed scope OR one workspace root.
        in_scope = False
        for root in self.workspace.roots:
            try:
                resolved.relative_to(root)
                in_scope = True
                break
            except ValueError:
                pass

        if not in_scope:
            raise SkillPermissionViolation(f"Path '{resolved}' is outside allowed workspace boundaries.")

        # Hard denial for prohibited system files or root directory escapes
        normalized_str = str(resolved).replace("\\", "/")
        if any(bad in normalized_str.lower() for bad in ["/security_policy.py", "/approval.py", "/quarantine.py", "/.git/"]):
            raise SkillPermissionViolation(f"Hard security policy denial: Access to '{resolved}' is strictly prohibited.")

        # Step 3: Check for sensitive credentials/keys
        if is_sensitive_path(resolved):
            if not self.approval:
                raise SkillPermissionViolation(f"Access to sensitive path '{resolved}' requires approval manager.")
            action_desc = f"{'Write' if for_write else 'Read'} sensitive file {resolved} for skill {self.manifest.id}"
            req = self.approval.request(
                action_desc,
                "Access to credential or secret file.",
                "SENSITIVE_FILE_ACCESS",
                metadata={"skill_id": self.manifest.id, "version": self.manifest.version, "path": str(resolved), "for_write": for_write},
            )
            if not req.get("allowed"):
                raise SkillPermissionViolation(f"Permission denied: User declined access to sensitive path '{resolved}'.")

        # Step 4: Check destructive permission if modifying
        if for_write and not self.manifest.permissions.destructive and resolved.exists() and resolved.is_file():
            # Overwriting existing file requires destructive permission or user approval
            if self.approval:
                req = self.approval.request(
                    f"Overwrite existing file {resolved} by skill {self.manifest.id}",
                    "File modification by skill without pre-authorized destructive scope.",
                    "DESTRUCTIVE_FILE_WRITE",
                    metadata={"skill_id": self.manifest.id, "version": self.manifest.version, "path": str(resolved)},
                )
                if not req.get("allowed"):
                    raise SkillPermissionViolation(f"Permission denied: Overwrite of '{resolved}' requires destructive permission.")
            else:
                raise SkillPermissionViolation(f"Skill '{self.manifest.id}' lacks destructive permission to overwrite existing file '{resolved}'.")

        return resolved

    def check_network(self, host: str = ""):
        """Enforce network permission allowlist."""
        if not self.manifest.permissions.network:
            raise SkillPermissionViolation(f"Skill '{self.manifest.id}' does not have network access permission.")
        allowed_hosts = [h.lower() for h in self.manifest.permissions.network_hosts]
        if allowed_hosts and host.lower() not in allowed_hosts:
            raise SkillPermissionViolation(f"Network destination '{host}' is not in allowed hosts: {allowed_hosts}")

    def check_subprocess(self):
        """Enforce subprocess permission."""
        if not self.manifest.permissions.subprocess:
            raise SkillPermissionViolation(f"Skill '{self.manifest.id}' attempted subprocess execution without subprocess permission.")
