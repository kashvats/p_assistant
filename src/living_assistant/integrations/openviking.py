from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

_UNAVAILABLE = (
    "OpenViking is enabled but the SDK is not installed or available at the configured path. "
    "Install it with: pip install openviking-sdk or clone to external-components/OpenViking"
)


class OpenVikingAdapter:
    """Thin boundary around the openviking-sdk SyncHTTPClient.

    The SDK is imported lazily so the assistant starts without it when the
    integration is disabled. All public methods return plain dicts so no
    third-party types leak into the assistant core. Supports both pip-installed
    openviking-sdk and a pinned local checkout under external-components.
    """

    _import_lock = threading.RLock()

    def __init__(
        self,
        url: str,
        api_key: str = "",
        account: str = "",
        user: str = "",
        actor_peer_id: str = "living-assistant",
        timeout: float = 30.0,
        path: str | Path | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._account = account
        self._user = user
        self._actor_peer_id = actor_peer_id
        self._timeout = timeout
        self._path = Path(path).expanduser().resolve() if path else None
        self._client: Any = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sdk(self):
        with self._import_lock:
            candidates: list[Path] = []
            if self._path:
                candidates.extend([self._path / "sdk" / "python", self._path])
            default_loc = Path("external-components/OpenViking/sdk/python").resolve()
            if default_loc.is_dir():
                candidates.append(default_loc)

            for cand in candidates:
                cand_str = str(cand)
                if cand.is_dir() and cand_str not in sys.path:
                    sys.path.insert(0, cand_str)

            if importlib.util.find_spec("openviking_sdk") is None:
                raise RuntimeError(_UNAVAILABLE)
            from openviking_sdk import SyncHTTPClient  # type: ignore[import]
            return SyncHTTPClient

    def _ensure_client(self) -> Any:
        try:
            self._sdk()
        except Exception:
            pass
        if self._client is not None:
            return self._client
        SyncHTTPClient = self._sdk()
        kwargs: dict[str, Any] = {
            "url": self._url,
            "timeout": self._timeout,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._account:
            kwargs["account"] = self._account
        if self._user:
            kwargs["user"] = self._user
        if self._actor_peer_id:
            kwargs["actor_peer_id"] = self._actor_peer_id
        client = SyncHTTPClient(**kwargs)
        try:
            client.initialize()
        except Exception as exc:
            logger.warning("OpenViking initialize() failed: %s", exc)
        self._client = client
        return client

    def _safe(self, fn, *args, **kwargs) -> dict[str, Any]:
        try:
            result = fn(*args, **kwargs)
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": result}
        except Exception as exc:
            logger.warning("OpenViking call failed: %s", exc)
            return {"ok": False, "error": str(exc)[:800]}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def available(self) -> bool:
        if self._path and (self._path / "sdk" / "python" / "openviking_sdk").is_dir():
            return True
        if Path("external-components/OpenViking/sdk/python/openviking_sdk").is_dir():
            return True
        return importlib.util.find_spec("openviking_sdk") is not None

    def health(self) -> dict[str, Any]:
        try:
            client = self._ensure_client()
            result = client.health()
            return {"ok": True, "health": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:400]}

    def recall(self, query: str, uri: str = "", limit: int = 6) -> dict[str, Any]:
        """Semantic recall — returns the most relevant context chunks."""
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}
        try:
            client = self._ensure_client()
            kwargs: dict[str, Any] = {"query": query.strip()}
            if uri:
                kwargs["uri"] = uri
            results = client.find(**kwargs)
            items = results if isinstance(results, list) else results.get("items", [])
            return {
                "ok": True,
                "query": query,
                "items": [
                    {
                        "uri": getattr(r, "uri", None) or r.get("uri", ""),
                        "content": getattr(r, "content", None) or r.get("content", ""),
                        "score": getattr(r, "score", None) or r.get("score", None),
                    }
                    for r in (items[:limit] if isinstance(items, list) else [])
                ],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:800]}

    def remember(
        self,
        content: str,
        uri: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write a memory into the OpenViking store."""
        if not content or not content.strip():
            return {"ok": False, "error": "content must not be empty"}
        try:
            client = self._ensure_client()
            try:
                from openviking_sdk import TextPart  # type: ignore[import]
                parts = [TextPart(text=content.strip())]
            except Exception:
                parts = [content.strip()]
            kwargs: dict[str, Any] = {"parts": parts}
            if uri:
                kwargs["uri"] = uri
            if tags:
                kwargs["tags"] = tags
            result = client.write(**kwargs)
            return {"ok": True, "uri": uri or "", "result": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:800]}

    def search(self, query: str, uri: str = "") -> dict[str, Any]:
        """Keyword-aware search across a context subtree."""
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}
        try:
            client = self._ensure_client()
            kwargs: dict[str, Any] = {"query": query.strip()}
            if uri:
                kwargs["uri"] = uri
            results = client.search(**kwargs)
            items = results if isinstance(results, list) else results.get("items", [])
            return {
                "ok": True,
                "query": query,
                "items": [
                    {
                        "uri": getattr(r, "uri", None) or r.get("uri", ""),
                        "snippet": getattr(r, "snippet", None) or r.get("snippet", ""),
                    }
                    for r in (items if isinstance(items, list) else [])
                ],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:800]}

    def capture_session(
        self,
        session_id: str,
        messages: list[dict],
        token_budget: int = 4096,
    ) -> dict[str, Any]:
        """Push a conversation session into OpenViking memory for long-term recall."""
        if not session_id:
            return {"ok": False, "error": "session_id required"}
        try:
            client = self._ensure_client()
            try:
                from openviking_sdk import TextPart  # type: ignore[import]
                has_tp = True
            except Exception:
                has_tp = False
            client.create_session(session_id=session_id)
            sc = client.session(session_id=session_id)
            for msg in messages:
                role = str(msg.get("role", "user"))
                text = str(msg.get("content", ""))
                if not text.strip():
                    continue
                if role == "assistant":
                    if has_tp:
                        sc.add_message(role="assistant", parts=[TextPart(text=text)])
                    else:
                        sc.add_message(role="assistant", content=text)
                else:
                    sc.add_message(role="user", content=text)
            ctx = sc.get_session_context(token_budget=token_budget)
            return {"ok": True, "session_id": session_id, "context_length": len(str(ctx))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:800]}
