from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class AwesomeAgentToolsAdapter:
    """Production boundary around awesome-ai-agent-tools reference."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        if not self._path or not self._path.is_dir():
            default_candidate = Path("external-components/awesome-ai-agent-tools").resolve()
            if default_candidate.is_dir():
                self._path = default_candidate

    def read_reference(self) -> dict[str, Any]:
        """Read the awesome-ai-agent-tools readme content."""
        if not self._path:
            return {"ok": False, "error": "awesome-ai-agent-tools directory not configured"}

        # In awesome-ai-agent-tools, the readme is lowercase readme.md
        readme = self._path / "readme.md"
        if not readme.is_file():
            readme = self._path / "README.md"

        if readme.is_file():
            try:
                return {"ok": True, "content": readme.read_text(encoding="utf-8")}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": False, "error": "readme.md not found"}

    def list_categories(self) -> dict[str, Any]:
        """List categories available in the awesome-ai-agent-tools repository."""
        if not self._path:
            return {"ok": False, "error": "awesome-ai-agent-tools directory not configured"}

        categories = []
        for p in self._path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                categories.append(p.name)
        return {"ok": True, "categories": sorted(categories)}
