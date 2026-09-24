from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from typing import Any

from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger(__name__)


class AgentMemoryAdapter:
    """Production boundary around the agentmemory persistent memory system.

    Supports both:
    1. HTTP REST API when agentmemory server is running (default http://127.0.0.1:3111).
    2. CLI / Node fallback through npx, global agentmemory binary, or local checkout.

    All public methods return plain dicts and redact sensitive information.
    """

    _lock = threading.RLock()

    def __init__(
        self,
        url: str = "http://127.0.0.1:3111",
        token: str = "",
        timeout: float = 15.0,
        path: str | Path | None = None,
        command: str | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = float(timeout)
        self._path = Path(path).expanduser().resolve() if path else None
        self._command = command or "agentmemory"
        self._client: Any = None

    # ------------------------------------------------------------------
    # Availability & Health
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Check if agentmemory is available via CLI, local checkout, or running server."""
        if shutil.which(self._command):
            return True
        if shutil.which("node") and self._path and (self._path / "dist" / "cli.mjs").is_file():
            return True
        default_checkout = Path("external-components/agentmemory/package.json").resolve()
        if default_checkout.is_file():
            return True
        return self._ping_server()

    def _ping_server(self) -> bool:
        try:
            import httpx
            with httpx.Client(timeout=1.5, trust_env=False) as client:
                res = client.get(f"{self._url}/agentmemory/health")
                return res.status_code == 200
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        """Query agentmemory server health."""
        try:
            import httpx
            headers = {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            with httpx.Client(timeout=self._timeout, trust_env=False) as client:
                res = client.get(f"{self._url}/agentmemory/health", headers=headers)
                if res.status_code == 200:
                    return {"ok": True, "status": "healthy", "server": res.json()}
                return {"ok": False, "status_code": res.status_code, "error": res.text[:400]}
        except Exception as exc:
            return {"ok": False, "error": redact_secrets(str(exc)[:400])}

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def recall(
        self,
        query: str,
        limit: int = 10,
        format_type: str = "full",
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        """Search past session observations and insights for relevant context."""
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}

        payload: dict[str, Any] = {
            "query": query.strip(),
            "limit": max(1, min(int(limit), 100)),
            "format": format_type,
        }
        if token_budget is not None:
            payload["token_budget"] = int(token_budget)

        return self._call_api("/agentmemory/recall", payload, fallback_fn=self._cli_recall)

    def save(
        self,
        content: str,
        memory_type: str = "fact",
        concepts: str = "",
        files: str = "",
        project: str = "",
        agent_id: str = "",
    ) -> dict[str, Any]:
        """Explicitly save an important insight, decision, or pattern into persistent memory."""
        if not content or not content.strip():
            return {"ok": False, "error": "content must not be empty"}

        payload = {
            "content": content.strip(),
            "type": memory_type,
            "concepts": concepts,
            "files": files,
            "project": project,
            "agentId": agent_id,
        }
        return self._call_api("/agentmemory/save", payload)

    def file_history(self, files: str | list[str], limit: int = 10) -> dict[str, Any]:
        """Retrieve past observations regarding specific file paths."""
        file_list = [f.strip() for f in files.split(",")] if isinstance(files, str) else list(files)
        file_list = [f for f in file_list if f]
        if not file_list:
            return {"ok": False, "error": "files must not be empty"}

        payload = {
            "files": ",".join(file_list),
            "limit": max(1, min(int(limit), 100)),
        }
        return self._call_api("/agentmemory/file-history", payload)

    def smart_search(
        self,
        query: str,
        limit: int = 10,
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        """Hybrid search fusing keyword, semantic, and structural graph memory."""
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}

        payload: dict[str, Any] = {
            "query": query.strip(),
            "limit": max(1, min(int(limit), 100)),
        }
        if token_budget is not None:
            payload["token_budget"] = int(token_budget)

        return self._call_api("/agentmemory/smart-search", payload)

    def list_memories(
        self,
        project: str = "",
        agent_id: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        """List stored memories optionally scoped by project or agent ID."""
        payload: dict[str, Any] = {
            "project": project,
            "agentId": agent_id,
            "limit": max(1, min(int(limit), 200)),
        }
        return self._call_api("/agentmemory/list", payload)

    # ------------------------------------------------------------------
    # Dispatch & Fallback Helpers
    # ------------------------------------------------------------------

    def _call_api(
        self,
        endpoint: str,
        payload: dict[str, Any],
        fallback_fn: Any = None,
    ) -> dict[str, Any]:
        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            with httpx.Client(timeout=self._timeout, trust_env=False) as client:
                res = client.post(f"{self._url}{endpoint}", json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return {"ok": True, **(data if isinstance(data, dict) else {"result": data})}
                if fallback_fn is not None:
                    return fallback_fn(payload)
                return {"ok": False, "status_code": res.status_code, "error": res.text[:800]}
        except Exception as exc:
            if fallback_fn is not None:
                return fallback_fn(payload)
            return {"ok": False, "error": redact_secrets(str(exc)[:800])}

    def _cli_recall(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Fallback to CLI invocation if server is not responding."""
        cmd = self._resolve_cli_command(["recall", payload["query"]])
        if not cmd:
            return {"ok": False, "error": "agentmemory server unreachable and CLI not installed"}
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
                    return {"ok": True, "results": data}
                except Exception:
                    return {"ok": True, "output": proc.stdout[:2000]}
            return {"ok": False, "error": redact_secrets(proc.stderr[:800])}
        except Exception as exc:
            return {"ok": False, "error": redact_secrets(str(exc)[:800])}

    def _resolve_cli_command(self, args: list[str]) -> list[str] | None:
        if shutil.which(self._command):
            return [self._command, *args]
        node = shutil.which("node")
        if node and self._path and (self._path / "dist" / "cli.mjs").is_file():
            return [node, str(self._path / "dist" / "cli.mjs"), *args]
        npx = shutil.which("npx")
        if npx:
            return [npx, "-y", "@agentmemory/agentmemory@latest", *args]
        return None
