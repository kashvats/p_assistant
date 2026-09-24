from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import zipfile

from living_assistant.agents.custom.manifest import AgentManifest


class AgentPackageError(Exception):
    pass


class AgentPackage:
    """Encapsulates a custom agent bundle on disk."""

    def __init__(
        self,
        root: Path,
        manifest: AgentManifest,
        agent_md: str = "",
        examples: list[dict[str, Any]] | None = None,
        tests: list[dict[str, Any]] | None = None,
    ):
        self.root = Path(root).expanduser().resolve()
        self.manifest = manifest
        self.agent_md = agent_md
        self.examples = examples or []
        self.tests = tests or []

    def save(self):
        """Persist package contents to disk."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "examples").mkdir(parents=True, exist_ok=True)
        (self.root / "tests").mkdir(parents=True, exist_ok=True)

        manifest_path = self.root / "manifest.json"
        manifest_data = self.manifest.model_dump()
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        agent_md_path = self.root / "AGENT.md"
        agent_md_content = self.agent_md
        if not agent_md_content:
            agent_md_content = f"# {self.manifest.name}\n\n{self.manifest.description}\n"
        agent_md_path.write_text(agent_md_content, encoding="utf-8")

        ex_path = self.root / "examples" / "default.json"
        ex_path.write_text(json.dumps(self.examples, indent=2), encoding="utf-8")

        t_path = self.root / "tests" / "test_cases.json"
        t_path.write_text(json.dumps(self.tests, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, root: Path) -> AgentPackage:
        root = Path(root).expanduser().resolve()
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest.json in agent bundle at {root}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_dict = json.load(f)
        manifest = AgentManifest.from_json(manifest_dict)

        agent_md_path = root / "AGENT.md"
        agent_md = agent_md_path.read_text(encoding="utf-8") if agent_md_path.exists() else ""

        examples: list[dict[str, Any]] = []
        ex_path = root / "examples" / "default.json"
        if ex_path.exists():
            try:
                examples = json.loads(ex_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        tests: list[dict[str, Any]] = []
        t_path = root / "tests" / "test_cases.json"
        if t_path.exists():
            try:
                tests = json.loads(t_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        return cls(root=root, manifest=manifest, agent_md=agent_md, examples=examples, tests=tests)

    def deterministic_hash(self) -> str:
        """Compute SHA-256 hash over bundle files, sorted deterministically, ignoring temporary files."""
        hasher = hashlib.sha256()
        for root, dirs, files in os.walk(self.root):
            dirs[:] = sorted([d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "logs")])
            for filename in sorted(files):
                if filename.startswith(".") or filename.endswith(".pyc"):
                    continue
                file_path = Path(root) / filename
                rel_path = file_path.relative_to(self.root).as_posix()
                hasher.update(rel_path.encode("utf-8"))
                hasher.update(file_path.read_bytes())
        return hasher.hexdigest()

    def create_snapshot(self, snapshots_root: Path) -> Path:
        """Create an immutable versioned snapshot directory under snapshots_root."""
        snapshots_root = Path(snapshots_root).expanduser().resolve()
        snapshots_root.mkdir(parents=True, exist_ok=True)
        h = self.deterministic_hash()[:12]
        snap_dir = snapshots_root / self.manifest.id / f"{self.manifest.version}_{h}"
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
        snap_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.root,
            snap_dir,
            ignore=shutil.ignore_patterns(".*", "__pycache__", "*.pyc", "logs"),
        )
        return snap_dir

    def export_zip(self, target_zip: Path) -> Path:
        """Archive package to zip file."""
        target_zip = Path(target_zip).expanduser().resolve()
        target_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.root):
                dirs[:] = sorted([d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "logs")])
                for file in sorted(files):
                    if file.startswith(".") or file.endswith(".pyc"):
                        continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(self.root)
                    zf.write(full_p, rel_p.as_posix())
        return target_zip

    @classmethod
    def import_zip(cls, zip_path: Path, target_dir: Path) -> AgentPackage:
        """Safely import agent zip with zip-slip prevention and resource limits."""
        zip_path = Path(zip_path).expanduser().resolve()
        target_dir = Path(target_dir).expanduser().resolve()
        if not zip_path.exists():
            raise FileNotFoundError(f"Agent archive not found: {zip_path}")

        MAX_ENTRIES = 100
        MAX_UNCOMPRESSED_SIZE = 10 * 1024 * 1024  # 10 MB limit

        total_size = 0
        total_entries = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            infolist = zf.infolist()
            if len(infolist) > MAX_ENTRIES:
                raise AgentPackageError(f"Agent archive contains too many entries ({len(infolist)} > {MAX_ENTRIES})")

            for info in infolist:
                total_entries += 1
                total_size += info.file_size
                if total_size > MAX_UNCOMPRESSED_SIZE:
                    raise AgentPackageError(f"Agent archive uncompressed size exceeds limit ({MAX_UNCOMPRESSED_SIZE} bytes)")

                # Defense against Zip-Slip
                resolved_target = (target_dir / info.filename).resolve()
                try:
                    resolved_target.relative_to(target_dir)
                except ValueError:
                    raise AgentPackageError(f"Archive entry '{info.filename}' attempts path traversal.")

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                zf.extractall(tmp_path)
                if not (tmp_path / "manifest.json").exists():
                    raise AgentPackageError("Archive does not contain a root manifest.json")

                target_dir.mkdir(parents=True, exist_ok=True)
                for item in tmp_path.iterdir():
                    dest = target_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

        return cls.load(target_dir)
