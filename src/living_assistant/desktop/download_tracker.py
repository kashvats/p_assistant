from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from living_assistant.security.quarantine import QuarantineVault


DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".scr", ".msi", ".dll", ".pif", ".hta"
}

INCOMPLETE_EXTENSIONS = {
    ".crdownload", ".part", ".tmp", ".download", ".partial"
}


class BrowserDownloadTracker:
    """Normalizes and safely ingests downloads initiated by web browsers.

    Prevents downloaded files in arbitrary browser default directories from escaping
    workspace confinement, enforces completion checks, and checks executable safety.
    """

    def __init__(self, workspace_root: Path | str, vault: QuarantineVault | None = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.vault = vault or QuarantineVault(self.workspace_root / "quarantine")

    def track_and_normalize(
        self,
        landing_path: Path | str,
        target_subfolder: str = "downloads",
    ) -> dict[str, Any]:
        source = Path(landing_path).resolve()
        if not source.exists():
            return {
                "ok": False,
                "error": f"Downloaded file does not exist at landing path: {source}",
                "landing_path": str(source),
                "completed": False,
                "safe": False,
            }

        suffix = source.suffix.lower()

        # 1. Completion check
        if suffix in INCOMPLETE_EXTENSIONS:
            return {
                "ok": True,
                "completed": False,
                "status": "in_progress",
                "landing_path": str(source),
                "safe": True,
                "message": "Download is still in progress (incomplete temp file).",
            }

        # 2. Path Traversal & Destination Normalization
        clean_filename = Path(source.name).name  # Strips any directory traversal
        destination_dir = self.workspace_root / target_subfolder
        destination_dir.mkdir(parents=True, exist_ok=True)
        final_path = (destination_dir / clean_filename).resolve()

        if not str(final_path).startswith(str(self.workspace_root)):
            return {
                "ok": False,
                "error": "Security boundary violation: target path escapes workspace root.",
                "completed": True,
                "safe": False,
            }

        # 3. Executable / Safety check
        is_safe = True
        warnings = []
        if suffix in DANGEROUS_EXTENSIONS:
            is_safe = False
            warnings.append(f"Executable/script extension '{suffix}' detected. File requires review or quarantine.")

        # Move/copy file to normalized workspace location if outside
        if source != final_path:
            shutil.copy2(source, final_path)

        file_size = final_path.stat().st_size

        return {
            "ok": True,
            "completed": True,
            "safe": is_safe,
            "normalized_path": str(final_path),
            "size_bytes": file_size,
            "warnings": warnings,
        }
