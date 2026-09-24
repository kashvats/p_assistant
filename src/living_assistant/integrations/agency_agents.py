from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class AgencyAgentsAdapter:
    """Production boundary around the agency-agents repository.

    Provides listing, retrieval, and search of multi-agent persona definitions
    and specialized workflow prompts.
    """

    _lock = threading.RLock()

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        if not self._path or not self._path.is_dir():
            default_candidate = Path("external-components/agency-agents").resolve()
            if default_candidate.is_dir():
                self._path = default_candidate

    def list_categories(self) -> dict[str, Any]:
        """List all agent categories."""
        if not self._path:
            return {"ok": False, "error": "agency-agents directory not configured"}

        categories = []
        for p in self._path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                # Check if it has markdown files
                md_files = list(p.glob("*.md"))
                if md_files:
                    categories.append(p.name)

        return {"ok": True, "categories": sorted(categories)}

    def list_agents(self, category: str = "") -> dict[str, Any]:
        """List available agents, optionally filtered by category."""
        if not self._path:
            return {"ok": False, "error": "agency-agents directory not configured"}

        agents = []
        dirs_to_check = [self._path / category] if category else [p for p in self._path.iterdir() if p.is_dir() and not p.name.startswith(".")]

        for d in dirs_to_check:
            if d.is_dir():
                for md in d.glob("*.md"):
                    # Avoid README or ISSUE templates
                    if md.name.isupper() and md.name.endswith(".md"):
                        continue
                    agents.append({
                        "name": md.stem,
                        "category": d.name,
                    })

        return {"ok": True, "agents": sorted(agents, key=lambda x: x["name"])}

    def get_agent(self, name: str) -> dict[str, Any]:
        """Retrieve the complete instructions and workflow definition for an agent."""
        if not self._path:
            return {"ok": False, "error": "agency-agents directory not configured"}

        # Search for the markdown file
        for p in self._path.rglob(f"{name}.md"):
            if not p.is_dir() and ".github" not in p.parts:
                try:
                    content = p.read_text(encoding="utf-8")
                    return {
                        "ok": True,
                        "name": p.stem,
                        "category": p.parent.name,
                        "instructions": content
                    }
                except Exception as e:
                    return {"ok": False, "error": str(e)}

        return {"ok": False, "error": f"Agent {name} not found"}

    def search_agents(self, query: str) -> dict[str, Any]:
        """Search across all agent definitions for a specific capability or keyword."""
        if not self._path:
            return {"ok": False, "error": "agency-agents directory not configured"}

        results = []
        query_lower = query.lower()

        for p in self._path.rglob("*.md"):
            if ".github" in p.parts or (p.name.isupper() and p.name.endswith(".md")):
                continue

            try:
                content = p.read_text(encoding="utf-8")
                if query_lower in p.name.lower() or query_lower in content.lower():
                    results.append({
                        "name": p.stem,
                        "category": p.parent.name,
                    })
            except Exception:
                pass

        return {"ok": True, "results": sorted(results, key=lambda x: x["name"])}
