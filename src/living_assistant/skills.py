from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from importlib import resources
import json, time, re
from .config import data_dir
from .storage_utils import atomic_write_json

@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    instructions: str

class SkillRegistry:
    """User-confirmed prompt skills. Skills cannot alter deterministic security policy."""
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "skills.json")
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
        return self._load()

    def match(self, text: str, limit: int = 3) -> list[dict]:
        low = text.lower()
        hits = []
        for name, item in self._load().items():
            score = sum(1 for t in item.get("triggers", []) if t and t in low)
            if score:
                hits.append((score, name, item))
        # User-created skills take precedence over built-ins when trigger scores tie.
        # This keeps shipped defaults helpful without overriding explicit user intent.
        hits.sort(key=lambda x: (-x[0], x[2].get("source") == "builtin", x[1]))
        return [{"name": n, **item} for _, n, item in hits[:limit]]
