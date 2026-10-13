"""Workspace-bounded project audits.

The analysis itself lives in one place, the project-audit skill's script
(builtin_skills/project-audit/scripts/audit.py), so chat tools, the coding API, the CLI, company employees
and the company quality gate all report the same findings. This class keeps the old interface.
"""
from __future__ import annotations

from pathlib import Path

from living_assistant.core.workspace import Workspace


def _audit():
    from living_assistant.companies.audit_gate import audit_module
    return audit_module()


class ProjectAuditor:
    """Bounded, offline-safe static project health auditor."""

    def __init__(self, workspace: Workspace, max_files: int = 1500, max_file_bytes: int = 750_000):
        self.workspace = workspace
        self.max_files = max(50, min(int(max_files), 10_000))
        self.max_file_bytes = max(16_384, min(int(max_file_bytes), 5_000_000))

    def audit(self, path: str | Path = ".") -> dict:
        root = self.workspace.resolve(path)  # raises WorkspaceViolation outside the workspace
        if not root.is_dir():
            return {"ok": False, "error": "Project audit path must be a directory."}
        return _audit().report(root)

    def _python_scan(self, root: Path, files: list[Path]) -> dict:
        """Lint, dead code and security for specific files (the coding API's single-file audit)."""
        audit = _audit()
        issues, defs, refs, security = [], [], set(), []
        for file in files:
            if file.suffix.lower() != ".py" or audit.SENSITIVE.search(file.name):
                continue
            text = audit.read(file)
            if text is None:
                continue
            rel = file.relative_to(root).as_posix()
            scan = audit.python_scan(rel, text)
            issues.extend(scan["lint"])
            defs.extend(scan["defs"])
            refs |= scan["refs"]
            security.extend(audit._file_security(rel, text))
        dead = [{**d, "confidence": "candidate"} for d in defs if d["name"] not in refs]
        syntax_errors = sum(1 for i in issues if i["rule"] == "syntax-error")
        counts: dict[str, int] = {}
        for f in security:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        return {"python_files": sum(1 for f in files if f.suffix.lower() == ".py"),
                "lint": {"score": max(0, 100 - min(100, syntax_errors * 20 + (len(issues) - syntax_errors) * 2)),
                         "issue_count": len(issues), "issues": issues[:200]},
                "dead_code": {"candidate_count": len(dead), "candidates": dead[:200]},
                "security": {"finding_count": len(security), "severity_counts": counts, "findings": security[:200]}}
