from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any

from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger(__name__)


class CodebaseMemoryAdapter:
    """Production boundary around Codebase Memory MCP.

    Provides AST-level knowledge graph queries, call graphs, architecture overviews,
    and Architecture Decision Records (ADRs) across 160+ languages.

    Communicates via native binary, npx/uvx runner, or stdio MCP protocol,
    returning clean Python dicts and redacting secrets.
    """

    _lock = threading.RLock()

    def __init__(
        self,
        command: str = "codebase-memory-mcp",
        path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._command = str(command or "codebase-memory-mcp")
        self._path = Path(path).expanduser().resolve() if path else None
        self._timeout = float(timeout)
        self._resolved_cmd: list[str] | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Check if codebase-memory-mcp executable, npx runner, or local checkout is present."""
        if shutil.which(self._command):
            return True
        if shutil.which("npx"):
            return True
        if shutil.which("uvx"):
            return True
        default_checkout = Path("external-components/codebase-memory-mcp/server.json").resolve()
        return default_checkout.is_file()

    def _resolve_executable(self) -> list[str]:
        if self._resolved_cmd is not None:
            return self._resolved_cmd

        if shutil.which(self._command):
            self._resolved_cmd = [self._command]
            return self._resolved_cmd

        # Check local checkout scripts or builds
        if self._path:
            for candidate in ("codebase-memory-mcp.exe", "codebase-memory-mcp", "bin/codebase-memory-mcp"):
                p = self._path / candidate
                if p.is_file():
                    self._resolved_cmd = [str(p)]
                    return self._resolved_cmd

        npx = shutil.which("npx")
        if npx:
            self._resolved_cmd = [npx, "-y", "codebase-memory-mcp@latest"]
            return self._resolved_cmd

        uvx = shutil.which("uvx")
        if uvx:
            self._resolved_cmd = [uvx, "codebase-memory-mcp"]
            return self._resolved_cmd

        self._resolved_cmd = [self._command]
        return self._resolved_cmd

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def index_repository(self, project_path: str = ".") -> dict[str, Any]:
        """Index a project directory into the Codebase Memory graph."""
        return self._run_command(["index", str(project_path)])

    def get_architecture(self, project_path: str = ".") -> dict[str, Any]:
        """Get high-level architecture overview: languages, boundaries, entry points, layers."""
        return self._run_command(["architecture", str(project_path)])

    def query_graph(self, cypher_query: str, project_path: str = ".") -> dict[str, Any]:
        """Run a Cypher-like knowledge graph query over the codebase AST."""
        if not cypher_query or not cypher_query.strip():
            return {"ok": False, "error": "query must not be empty"}
        return self._run_command(["query", cypher_query.strip(), "--project", str(project_path)])

    def find_callers(self, symbol: str, project_path: str = ".") -> dict[str, Any]:
        """Find all functions/methods calling the given symbol across packages."""
        if not symbol or not symbol.strip():
            return {"ok": False, "error": "symbol must not be empty"}
        return self._run_command(["callers", symbol.strip(), "--project", str(project_path)])

    def find_callees(self, symbol: str, project_path: str = ".") -> dict[str, Any]:
        """Find all functions/methods called by the given symbol."""
        if not symbol or not symbol.strip():
            return {"ok": False, "error": "symbol must not be empty"}
        return self._run_command(["callees", symbol.strip(), "--project", str(project_path)])

    def manage_adr(
        self,
        action: str = "list",
        title: str = "",
        content: str = "",
        project_path: str = ".",
    ) -> dict[str, Any]:
        """Create, read, or list Architectural Decision Records (ADRs)."""
        args = ["adr", action]
        if title:
            args.extend(["--title", title])
        if content:
            args.extend(["--content", content])
        args.extend(["--project", str(project_path)])
        return self._run_command(args)

    # ------------------------------------------------------------------
    # Execution Engine
    # ------------------------------------------------------------------

    def _run_command(self, sub_args: list[str]) -> dict[str, Any]:
        with self._lock:
            cmd = [*self._resolve_executable(), *sub_args]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    check=False,
                )
                if proc.returncode == 0:
                    try:
                        data = json.loads(proc.stdout)
                        return {"ok": True, **(data if isinstance(data, dict) else {"result": data})}
                    except Exception:
                        return {"ok": True, "output": proc.stdout.strip()}
                return {
                    "ok": False,
                    "returncode": proc.returncode,
                    "error": redact_secrets((proc.stderr or proc.stdout)[:800]),
                }
            except Exception as exc:
                return {"ok": False, "error": redact_secrets(str(exc)[:800])}
