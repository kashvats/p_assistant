from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
import zipfile

from living_assistant.security.security_utils import redact_secrets


SECRET_KEY_PATTERNS = [
    re.compile(r"api_key", re.I),
    re.compile(r"token", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"password", re.I),
    re.compile(r"credential", re.I),
]


class BackupManager:
    """Creates and restores application state backups while safeguarding plaintext secrets (Section 96)."""

    def __init__(self, data_root: Path | str):
        self.data_root = Path(data_root).resolve()

    def create_backup(
        self,
        output_zip_path: Path | str,
        include_db: bool = True,
        include_agents: bool = True,
        include_skills: bool = True,
        include_settings: bool = True,
    ) -> dict[str, Any]:
        zip_path = Path(output_zip_path).resolve()
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        manifest = {
            "created_at": dt.datetime.now().isoformat(),
            "version": "1.0.0",
            "files": [],
        }

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. SQLite Database
            if include_db:
                for db_file in self.data_root.glob("*.sqlite3"):
                    arcname = f"database/{db_file.name}"
                    zf.write(db_file, arcname=arcname)
                    manifest["files"].append(arcname)

            # 2. Custom Agents
            if include_agents:
                agents_dir = self.data_root / "agents"
                if agents_dir.exists():
                    for root, _, files in os.walk(agents_dir):
                        for f in files:
                            full = Path(root) / f
                            rel = full.relative_to(agents_dir)
                            arcname = f"agents/{rel.as_posix()}"
                            zf.write(full, arcname=arcname)
                            manifest["files"].append(arcname)

            # 3. Skills
            if include_skills:
                skills_dir = self.data_root / "skills"
                if skills_dir.exists():
                    for root, _, files in os.walk(skills_dir):
                        for f in files:
                            full = Path(root) / f
                            rel = full.relative_to(skills_dir)
                            arcname = f"skills/{rel.as_posix()}"
                            zf.write(full, arcname=arcname)
                            manifest["files"].append(arcname)

            # 4. Settings (Secrets Redacted)
            if include_settings:
                for cfg_file in self.data_root.glob("*.yaml"):
                    try:
                        content = cfg_file.read_text(encoding="utf-8")
                        redacted = self._sanitize_config_text(content)
                        arcname = f"settings/{cfg_file.name}"
                        zf.writestr(arcname, redacted)
                        manifest["files"].append(arcname)
                    except Exception:
                        pass

            # Write backup manifest
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))

        return {
            "ok": True,
            "backup_path": str(zip_path),
            "manifest": manifest,
            "file_count": len(manifest["files"]),
        }

    def restore_backup(
        self,
        backup_zip_path: Path | str,
        target_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        zip_path = Path(backup_zip_path).resolve()
        if not zip_path.exists():
            raise FileNotFoundError(f"Backup archive not found: {zip_path}")

        dest = Path(target_dir or self.data_root).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        restored_files = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Check manifest
            if "backup_manifest.json" not in zf.namelist():
                raise ValueError("Archive is not a valid Living Assistant backup (missing manifest).")

            for member in zf.infolist():
                if member.filename == "backup_manifest.json":
                    continue
                # Zip-slip defense
                target_path = (dest / member.filename).resolve()
                if not str(target_path).startswith(str(dest)):
                    raise ValueError(f"Malicious zip-slip path traversal in backup: {member.filename}")

                target_path.parent.mkdir(parents=True, exist_ok=True)
                if not member.is_dir():
                    with zf.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    restored_files.append(str(target_path))

        return {
            "ok": True,
            "restored_to": str(dest),
            "restored_count": len(restored_files),
            "files": restored_files,
        }

    @staticmethod
    def _sanitize_config_text(text: str) -> str:
        """Strip or mask sensitive credentials so backups never leak secrets in plaintext."""
        lines = []
        for line in text.splitlines():
            is_secret = any(p.search(line) for p in SECRET_KEY_PATTERNS)
            if is_secret and ":" in line:
                k, _ = line.split(":", 1)
                lines.append(f"{k}: '[REDACTED_IN_BACKUP]'")
            else:
                lines.append(line)
        return "\n".join(lines)
