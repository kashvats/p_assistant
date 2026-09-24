from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import zipfile
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.skills.manifest import SkillManifest


def default_skills_dir() -> Path:
    """User skills directory outside application installation folder."""
    p = data_dir() / "skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


class SkillPackage:
    """Represents a versioned skill directory containing manifest.json, SKILL.md, and test/example artifacts."""

    def __init__(self, root: Path, manifest: SkillManifest, skill_md: str):
        self.root = root
        self.manifest = manifest
        self.skill_md = skill_md

    @property
    def skill_id(self) -> str:
        return self.manifest.id

    @property
    def version(self) -> str:
        return self.manifest.version

    @classmethod
    def load(cls, skill_dir: Path) -> SkillPackage:
        manifest_path = skill_dir / "manifest.json"
        skill_md_path = skill_dir / "SKILL.md"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest.json in skill directory: {skill_dir}")

        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = SkillManifest.from_json(manifest_data)

        skill_md = ""
        if skill_md_path.exists():
            skill_md = skill_md_path.read_text(encoding="utf-8")

        return cls(root=skill_dir, manifest=manifest, skill_md=skill_md)

    def save(self, target_dir: Path | None = None) -> Path:
        dest = target_dir or self.root
        dest.mkdir(parents=True, exist_ok=True)

        manifest_path = dest / "manifest.json"
        manifest_path.write_text(self.manifest.to_json(indent=2), encoding="utf-8")

        skill_md_path = dest / "SKILL.md"
        skill_md_path.write_text(self.skill_md, encoding="utf-8")

        # Create standard package subdirectories
        (dest / "examples").mkdir(exist_ok=True)
        (dest / "tests").mkdir(exist_ok=True)

        # Write examples if present
        for i, eg in enumerate(self.manifest.examples):
            eg_path = dest / "examples" / f"example_{i+1}.json"
            eg_path.write_text(json.dumps(eg.model_dump(), indent=2), encoding="utf-8")

        self.root = dest
        return dest

    def deterministic_hash(self) -> str:
        """Deterministic sha256 hash of all execution-relevant package files, excluding mutable logs and caches."""
        import hashlib
        hasher = hashlib.sha256()
        relevant_files: list[Path] = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            suffix = p.suffix.lower()
            if suffix in {".log", ".tmp", ".pyc", ".swp"} or "__pycache__" in p.parts or ".pytest_cache" in p.parts:
                continue
            relevant_files.append(p)

        for p in sorted(relevant_files, key=lambda x: str(x.relative_to(self.root)).replace("\\", "/")):
            rel_name = str(p.relative_to(self.root)).replace("\\", "/")
            hasher.update(rel_name.encode("utf-8"))
            hasher.update(p.read_bytes())
        return hasher.hexdigest()

    def create_snapshot(self, snapshots_root: Path) -> Path:
        """Create an immutable snapshot directory of this approved version for execution."""
        pkg_hash = self.deterministic_hash()
        snap_dir = snapshots_root / f"{self.skill_id}_{self.version}_{pkg_hash[:12]}"
        if snap_dir.exists():
            return snap_dir
        snap_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.root, snap_dir, ignore=shutil.ignore_patterns("*.log", "*.tmp", "__pycache__", ".pytest_cache"))
        return snap_dir

    def export_zip(self) -> bytes:
        """Export skill package as a zip archive."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in self.root.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(self.root)
                    zf.write(item, arcname=str(rel).replace("\\", "/"))
        return buf.getvalue()

    @classmethod
    def import_zip(cls, archive_bytes: bytes, target_parent_dir: Path) -> SkillPackage:
        """Securely import and extract a skill zip archive with strict zip-slip and symlink defenses."""
        MAX_ZIP_ENTRIES = 100
        MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024  # 10 MB

        buf = io.BytesIO(archive_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            infolist = zf.infolist()
            if len(infolist) > MAX_ZIP_ENTRIES:
                raise ValueError(f"Security error: Archive contains {len(infolist)} entries, exceeding limit of {MAX_ZIP_ENTRIES}.")

            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise ValueError(f"Security error: Archive decompressed size {total_uncompressed} exceeds limit of {MAX_UNCOMPRESSED_BYTES} bytes.")

            # First pass: validate all entries for path traversal and dangerous paths
            for name in zf.namelist():
                # Prevent absolute paths or UNC paths
                if os.path.isabs(name) or name.startswith("/") or name.startswith("\\"):
                    raise ValueError(f"Security error: Archive contains absolute path: {name}")
                # Prevent directory traversal
                parts = Path(name).parts
                if ".." in parts:
                    raise ValueError(f"Security error: Archive contains directory traversal: {name}")

            # Check that manifest.json exists
            names = set(zf.namelist())
            if "manifest.json" not in names:
                # Check if wrapped in a single root folder, e.g. skill-name/manifest.json
                root_candidates = {p.split("/")[0] for p in names if "/" in p}
                if len(root_candidates) == 1:
                    prefix = f"{list(root_candidates)[0]}/"
                    if f"{prefix}manifest.json" not in names:
                        raise ValueError("Invalid skill archive: manifest.json not found.")
                else:
                    raise ValueError("Invalid skill archive: manifest.json not found.")

            # Extract to temporary staging folder
            staging = target_parent_dir / "_import_staging"
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True, exist_ok=True)

            try:
                for member in zf.infolist():
                    target_path = (staging / member.filename).resolve()
                    if not str(target_path).startswith(str(staging.resolve())):
                        raise ValueError(f"Security error: Extraction target escaped root: {member.filename}")
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)

                # Locate the manifest folder inside staging
                extracted_root = staging
                if not (extracted_root / "manifest.json").exists():
                    subdirs = [d for d in staging.iterdir() if d.is_dir()]
                    if subdirs and (subdirs[0] / "manifest.json").exists():
                        extracted_root = subdirs[0]
                    else:
                        raise ValueError("Cannot locate manifest.json in extracted archive.")

                pkg = cls.load(extracted_root)

                # Move into official skill directory: target_parent_dir / pkg.skill_id
                final_dir = target_parent_dir / pkg.skill_id
                if final_dir.exists():
                    shutil.rmtree(final_dir)
                shutil.copytree(extracted_root, final_dir)
                pkg.root = final_dir
                return pkg
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
