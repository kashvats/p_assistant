from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any
import yaml

logger = logging.getLogger(__name__)

class ScientificSkillsAdapter:
    """Production boundary around the scientific-agent-skills repository.

    Provides indexed search and retrieval across scientific computing,
    data synthesis, and analytical method skills.
    """

    _lock = threading.RLock()

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        if not self._path or not self._path.is_dir():
            default_candidate = Path("external-components/scientific-agent-skills").resolve()
            if default_candidate.is_dir():
                self._path = default_candidate

        self._index: dict[str, Any] | None = None
        self._skills_list: list[dict[str, Any]] = []

    def _ensure_index(self) -> None:
        if self._skills_list or not self._path:
            return

        with self._lock:
            if self._skills_list:
                return

            skills_dir = self._path / "skills"
            if not skills_dir.is_dir():
                return

            for md_file in skills_dir.glob("*/SKILL.md"):
                skill_name = md_file.parent.name
                metadata = {}
                try:
                    # Parse frontmatter if present
                    content = md_file.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            parsed = yaml.safe_load(parts[1])
                            if isinstance(parsed, dict):
                                metadata = parsed
                except Exception:
                    pass

                self._skills_list.append({
                    "name": skill_name,
                    "description": metadata.get("description", ""),
                    "domain": metadata.get("domain", ""),
                    "tags": metadata.get("tags", []),
                    "path": str(md_file.relative_to(self._path)),
                })

    def search_skills(self, query: str = "", domain: str = "", limit: int = 10) -> dict[str, Any]:
        """Search the scientific skills library."""
        if not self._path:
            return {"ok": False, "error": "scientific-agent-skills directory not configured"}

        self._ensure_index()
        results = []
        q = query.lower()

        for s in self._skills_list:
            if domain and domain.lower() != str(s.get("domain", "")).lower():
                continue

            score = 0
            if q:
                if q in s["name"].lower():
                    score += 10
                if q in s["description"].lower():
                    score += 5
                if any(q in t.lower() for t in s["tags"]):
                    score += 3
            else:
                score = 1

            if score > 0:
                results.append((score, s))

        results.sort(key=lambda x: x[0], reverse=True)
        top_results = [r[1] for r in results[:limit]]

        return {
            "ok": True,
            "count": len(top_results),
            "total_matches": len(results),
            "results": top_results,
        }

    def get_skill(self, name_or_path: str) -> dict[str, Any]:
        """Retrieve full details, frontmatter metadata, and instructions for a skill."""
        if not self._path:
            return {"ok": False, "error": "scientific-agent-skills directory not configured"}

        clean_name = name_or_path.strip().replace("skills/", "")
        skill_dir = self._path / "skills" / clean_name
        skill_file = skill_dir / "SKILL.md"

        if not skill_file.is_file():
            candidates = list((self._path / "skills").glob(f"*{clean_name}*"))
            if candidates and candidates[0].is_dir() and (candidates[0] / "SKILL.md").is_file():
                skill_dir = candidates[0]
                skill_file = skill_dir / "SKILL.md"
            else:
                return {"ok": False, "error": f"Skill not found: {name_or_path}"}

        try:
            content = skill_file.read_text(encoding="utf-8")
            parts = content.split("---", 2)
            metadata: dict[str, Any] = {}

            if content.startswith("---") and len(parts) >= 3:
                parsed = yaml.safe_load(parts[1])
                if isinstance(parsed, dict):
                    metadata = parsed
                instructions = parts[2].strip()
            else:
                instructions = content.strip()

            return {
                "ok": True,
                "name": skill_dir.name,
                "metadata": metadata,
                "instructions": instructions,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
