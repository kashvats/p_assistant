from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from importlib import resources
import json, time, re
from typing import TYPE_CHECKING
from living_assistant.core.config import data_dir
from living_assistant.core.storage_utils import atomic_write_json

if TYPE_CHECKING:
    from living_assistant.skills.manager import SkillManager

@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    instructions: str

class SkillRegistry:
    """User-confirmed prompt skills. Skills cannot alter deterministic security policy.

    Seamlessly integrates with the Custom Skill Package System (FEAT-19) while
    preserving legacy backward-compatibility.
    """
    def __init__(self, path: Path | None = None, manager: SkillManager | None = None):
        self.path = path or (data_dir() / "skills.json")
        self.manager = manager
        if not self.path.exists():
            defaults = {}
            try:
                raw = resources.files("living_assistant").joinpath("default_skills.json").read_text(encoding="utf-8")
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    defaults = loaded
            except Exception:
                # A damaged optional defaults resource must not prevent the assistant
                # from starting; the user registry remains a valid empty mapping.
                defaults = {}
            atomic_write_json(self.path, defaults)

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict):
        atomic_write_json(self.path, data)

    def add(self, name: str, description: str, triggers: list[str], instructions: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
            raise ValueError("Skill name may contain letters, numbers, dot, underscore and hyphen only.")
        data = self._load()
        data[name] = {
            "description": description[:500],
            "triggers": [t.strip().lower() for t in triggers if t.strip()][:20],
            "instructions": instructions[:8000],
            "created_at": time.time(),
        }
        self._save(data)
        return data[name]

    def remove(self, name: str) -> bool:
        data = self._load(); existed = name in data; data.pop(name, None); self._save(data); return existed

    def list(self) -> dict:
        data = self._load()
        # If manager is attached, include active custom skills in listing
        if self.manager:
            try:
                for custom in self.manager.list_skills(state="ACTIVE"):
                    cid = custom.get("skill_id", "")
                    if cid and cid not in data:
                        data[cid] = {
                            "description": custom.get("description", ""),
                            "triggers": custom.get("triggers", []),
                            "instructions": f"Custom package skill {cid}. Version: {custom.get('current_version')}",
                            "source": "custom_package",
                        }
            except Exception:
                pass
        return data

    def match(self, text: str, limit: int = 3) -> list[dict]:
        low = text.lower()
        hits = []
        for name, item in self._load().items():
            score = sum(1 for t in item.get("triggers", []) if t and t in low)
            if score:
                hits.append((score, name, item))

        # If manager is attached, match custom active package skills
        if self.manager:
            try:
                for c_item in self.manager.match_active_skills(text, limit=limit):
                    cid = c_item.get("skill_id", "")
                    if not any(h[1] == cid for h in hits):
                        triggers = c_item.get("triggers", [])
                        score = sum(1 for t in triggers if t and t.lower() in low)
                        hits.append((score or 1, cid, {
                            "description": c_item.get("description", ""),
                            "triggers": triggers,
                            "instructions": f"Custom package skill {cid}.",
                            "source": "custom_package",
                        }))
            except Exception:
                pass

        # User-created skills take precedence over built-ins when trigger scores tie.
        # This keeps shipped defaults helpful without overriding explicit user intent.
        hits.sort(key=lambda x: (-x[0], x[2].get("source") == "builtin", x[1]))
        return [{"name": n, **item} for _, n, item in hits[:limit]]
