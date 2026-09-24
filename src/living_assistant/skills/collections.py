from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from living_assistant.skills.manifest import (
    SkillManifest,
    SkillPermissionScope,
    SkillProvenance,
)
from living_assistant.skills.package import SkillPackage, default_skills_dir
from living_assistant.skills.store import SkillStore


class ExternalSkillCollections:
    """Discovers and selectively imports compatible skills from external-components without auto-activation."""

    COLLECTION_PATHS = {
        "cybersecurity": Path("external-components/Anthropic-Cybersecurity-Skills/skills"),
        "scientific": Path("external-components/scientific-agent-skills/skills"),
        "diagram": Path("external-components/diagram-design/skills"),
    }

    def __init__(self, project_root: Path | None = None, skill_store: SkillStore | None = None):
        self.project_root = project_root or Path.cwd()
        self.skill_store = skill_store

    def scan_collections(self, limit: int = 50) -> dict[str, list[dict[str, Any]]]:
        """Scan available external collections and return brief metadata up to limit entries per collection."""
        results: dict[str, list[dict[str, Any]]] = {}
        for col_name, rel_path in self.COLLECTION_PATHS.items():
            full_path = (self.project_root / rel_path).resolve()
            results[col_name] = []
            if not full_path.exists() or not full_path.is_dir():
                continue
            count = 0
            for entry in sorted(full_path.iterdir(), key=lambda x: x.name):
                if limit and count >= limit:
                    break
                if entry.is_dir():
                    count += 1
                    skill_md = entry / "SKILL.md"
                    has_md = skill_md.exists()
                    title = entry.name.replace("-", " ").capitalize()
                    summary = ""
                    if has_md:
                        try:
                            # Read first 300 chars of SKILL.md
                            content = skill_md.read_text(encoding="utf-8", errors="ignore")
                            summary = content[:200].replace("\n", " ").strip()
                        except Exception:
                            pass
                    results[col_name].append({
                        "id": entry.name,
                        "title": title,
                        "has_skill_md": has_md,
                        "summary": summary,
                        "path": str(entry).replace("\\", "/"),
                    })
        return results

    def import_skill(self, collection_name: str, skill_folder_name: str) -> SkillPackage:
        """Selectively import a single skill from an external collection into local skills directory as a DRAFT."""
        if collection_name not in self.COLLECTION_PATHS:
            raise ValueError(f"Unknown collection '{collection_name}'. Available: {list(self.COLLECTION_PATHS.keys())}")

        src_dir = (self.project_root / self.COLLECTION_PATHS[collection_name] / skill_folder_name).resolve()
        if not src_dir.exists() or not src_dir.is_dir():
            raise FileNotFoundError(f"Skill '{skill_folder_name}' not found in {collection_name}")

        skill_md_path = src_dir / "SKILL.md"
        skill_md_content = ""
        if skill_md_path.exists():
            skill_md_content = skill_md_path.read_text(encoding="utf-8", errors="replace")

        # Synthesize a safe manifest for this external skill
        clean_id = f"ext-{collection_name[:4]}-{skill_folder_name[:24]}".strip("-").lower()
        manifest = SkillManifest(
            schema_version="1.0.0",
            id=clean_id,
            name=skill_folder_name.replace("-", " ").capitalize(),
            description=f"Imported from {collection_name} collection.",
            version="1.0.0",
            type="instruction",
            triggers=[skill_folder_name.replace("-", " ")],
            required_tools=[],
            permissions=SkillPermissionScope(
                filesystem=["."],
                network=False,
                subprocess=False,
                destructive=False,
                messaging=False,
            ),
            offline_capable=True,
            provenance=SkillProvenance(
                author="imported",
                source=f"external-components/{collection_name}",
            ),
        )

        dest_dir = default_skills_dir() / clean_id
        pkg = SkillPackage(root=dest_dir, manifest=manifest, skill_md=skill_md_content)
        pkg.save()

        if self.skill_store:
            # Register in SQLite as untrusted DRAFT
            self.skill_store.register_skill(manifest, skill_md_content, initial_state="DRAFT", snapshot_dir=str(dest_dir))

        return pkg
