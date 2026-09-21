from __future__ import annotations

from dataclasses import dataclass
import os
import shlex
from pathlib import PurePath

from living_assistant.security.security_policy import Decision, Risk, classify_command


@dataclass(frozen=True)
class CommandExplanation:
    """Deterministic, non-executing explanation of a shell command."""

    summary: str
    risk: str
    risk_level: str
    allowed: bool
    requires_approval: bool
    policy_reason: str
    executable: str | None = None

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "risk": self.risk,
            "risk_level": self.risk_level,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "policy_reason": self.policy_reason,
            "executable": self.executable,
        }


def _first_executable(command: str) -> str | None:
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except (ValueError, TypeError):
        parts = command.strip().split()
    if not parts:
        return None
    token = str(parts[0]).strip('"\'')
    return PurePath(token.replace("\\", "/")).name.lower() or None


def explain_command(
    command: str,
    decision: Decision | None = None,
    *,
    require_execute_approval: bool = True,
) -> CommandExplanation:
    """Explain command intent/risk without executing or echoing its arguments.

    The explanation intentionally describes only the command category/executable. It
    does not repeat arguments because shell arguments frequently contain credentials,
    paths, customer data, or other sensitive values.
    """

    decision = decision or classify_command(command, require_execute_approval)
    executable = _first_executable(command)

    if decision.risk is Risk.DESTRUCTIVE or not decision.allowed:
        level = "blocked"
        summary = "This command matches a destructive or secret-exfiltration safety rule and will not be executed."
    elif decision.risk is Risk.PRIVILEGED:
        level = "high"
        summary = "This command requests elevated/system privileges and may change machine-wide state."
    elif decision.risk is Risk.READ:
        level = "low"
        summary = "This command is a narrowly matched read-only inspection and is not expected to modify workspace or system state."
    else:
        level = "medium"
        category = {
            "git": "Runs a Git operation in the approved workspace; depending on its arguments it may modify repository state.",
            "python": "Runs Python code in the approved workspace and may read or modify files or start subprocesses.",
            "python3": "Runs Python code in the approved workspace and may read or modify files or start subprocesses.",
            "node": "Runs Node.js code in the approved workspace and may read or modify files or start subprocesses.",
            "npm": "Runs an npm command that may execute package scripts or modify project dependencies/files.",
            "npx": "Runs an npm package command and may download or execute project tooling.",
            "pip": "Runs a Python package-manager command that may modify the active environment.",
            "pip3": "Runs a Python package-manager command that may modify the active environment.",
            "curl": "Performs a network command; its arguments determine whether data is downloaded or uploaded.",
            "wget": "Performs a network download command and may write files in the workspace.",
            "powershell": "Runs PowerShell code, which can modify files, processes, network state, or system configuration.",
            "pwsh": "Runs PowerShell code, which can modify files, processes, network state, or system configuration.",
            "cmd": "Runs a Windows command shell operation that may change files or process state.",
            "bash": "Runs a shell script/command that may change files or process state.",
            "sh": "Runs a shell script/command that may change files or process state.",
        }
        summary = category.get(
            executable or "",
            "Runs a local shell command inside the approved workspace; its arguments may modify files or process state.",
        )

    return CommandExplanation(
        summary=summary,
        risk=decision.risk.value,
        risk_level=level,
        allowed=bool(decision.allowed),
        requires_approval=bool(decision.requires_approval),
        policy_reason=decision.reason,
        executable=executable,
    )
