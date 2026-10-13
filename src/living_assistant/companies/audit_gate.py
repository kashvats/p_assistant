"""Loads the project-audit skill's script: the one audit implementation in the assistant.

builtin_skills/project-audit/scripts/audit.py is run by employees as a skill, imported by the company
engine as its quality gate, and wrapped by system/project_auditor.py (coding API, CLI, project_audit tool),
so every caller reports the same findings.
"""
from __future__ import annotations

import functools
import importlib.util
from pathlib import Path
from types import ModuleType

from living_assistant.skills.library import builtin_root

# static checks: they read files and never execute project code
STATIC_CHECKS = ("health", "syntax", "lint", "security", "deps", "seo", "checks")


@functools.lru_cache(maxsize=1)
def audit_module() -> ModuleType:
    path = Path(builtin_root()) / "project-audit" / "scripts" / "audit.py"
    spec = importlib.util.spec_from_file_location("project_audit_skill", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # our own bundled file, not project code
    return module
