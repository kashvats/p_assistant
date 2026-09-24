from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class AwesomeHarnessAdapter:
    """Production boundary around awesome-harness-engineering reference."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        if not self._path or not self._path.is_dir():
            default_candidate = Path("external-components/awesome-harness-engineering").resolve()
            if default_candidate.is_dir():
                self._path = default_candidate

    def read_reference(self) -> dict[str, Any]:
        """Read the awesome-harness-engineering reference content."""
        if not self._path:
            return {"ok": False, "error": "awesome-harness-engineering directory not configured"}

        readme = self._path / "README.md"
        if readme.is_file():
            try:
                return {"ok": True, "content": readme.read_text(encoding="utf-8")}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": False, "error": "README.md not found"}
