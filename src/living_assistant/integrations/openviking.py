from __future__ import annotations

import importlib.util
import json
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

    def _build_preamble(self) -> str:
        return f"""
import sys
import json
path = {repr(self._path)}
if path:
    sys.path.insert(0, path + '/sdk/python')
    sys.path.insert(0, path)
sys.path.insert(0, 'external-components/OpenViking/sdk/python')

try:
    from openviking_sdk import SyncHTTPClient, TextPart
    has_tp = True
except ImportError:
    try:
        from openviking_sdk import SyncHTTPClient
        has_tp = False
    except ImportError:
        print(json.dumps({{"ok": False, "error": "OpenViking SDK not found"}}))
        sys.exit(0)

kwargs = {{
    "url": {repr(self._url)},
    "timeout": {repr(self._timeout)},
}}
if {repr(self._api_key)}: kwargs["api_key"] = {repr(self._api_key)}
if {repr(self._account)}: kwargs["account"] = {repr(self._account)}
if {repr(self._user)}: kwargs["user"] = {repr(self._user)}
if {repr(self._actor_peer_id)}: kwargs["actor_peer_id"] = {repr(self._actor_peer_id)}

client = SyncHTTPClient(**kwargs)
try:
    client.initialize()
except Exception:
    pass
"""

    def available(self) -> bool:
        if self._path and (Path(self._path) / "sdk" / "python" / "openviking_sdk").is_dir():
            return True
        if Path("external-components/OpenViking/sdk/python/openviking_sdk").is_dir():
            return True
        import importlib.util
        return importlib.util.find_spec("openviking_sdk") is not None

    def health(self) -> dict[str, Any]:
        if self._client is not None:
            try:
                return {"ok": True, "health": self._client.health()}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:400]}
        from living_assistant.core.isolated_executor import run_isolated_tool
        script = self._build_preamble() + """
try:
    print(json.dumps({"ok": True, "health": client.health()}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)[:400]}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def recall(self, query: str, uri: str = "", limit: int = 6) -> dict[str, Any]:
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}
        if self._client is not None:
            try:
                kwargs: dict[str, Any] = {"query": query.strip()}
                if uri:
                    kwargs["uri"] = uri
                results = self._client.find(**kwargs)
                items = results if isinstance(results, list) else results.get("items", [])
                return {
                    "ok": True,
                    "query": query,
                    "items": [
                        {
                            "uri": getattr(r, "uri", None) or (r.get("uri", "") if isinstance(r, dict) else ""),
                            "content": getattr(r, "content", None) or (r.get("content", "") if isinstance(r, dict) else ""),
                            "score": getattr(r, "score", None) or (r.get("score", None) if isinstance(r, dict) else None),
                        }
                        for r in (items[:limit] if isinstance(items, list) else [])
                    ],
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:800]}
        from living_assistant.core.isolated_executor import run_isolated_tool
        script = self._build_preamble() + f"""
try:
    kwargs = {{"query": {repr(query.strip())}}}
    if {repr(uri)}: kwargs["uri"] = {repr(uri)}
    results = client.find(**kwargs)
    items = results if isinstance(results, list) else results.get("items", [])
    out_items = [
        {{
            "uri": getattr(r, "uri", None) or (r.get("uri", "") if isinstance(r, dict) else ""),
            "content": getattr(r, "content", None) or (r.get("content", "") if isinstance(r, dict) else ""),
            "score": getattr(r, "score", None) or (r.get("score", None) if isinstance(r, dict) else None),
        }}
        for r in (items[:{limit}] if isinstance(items, list) else [])
    ]
    print(json.dumps({{"ok": True, "query": {repr(query)}, "items": out_items}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": str(exc)[:800]}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def remember(self, content: str, uri: str = "", tags: list[str] | None = None) -> dict[str, Any]:
        if not content or not content.strip():
            return {"ok": False, "error": "content must not be empty"}
        if self._client is not None:
            try:
                kwargs: dict[str, Any] = {"parts": [content.strip()]}
                if uri:
                    kwargs["uri"] = uri
                if tags:
                    kwargs["tags"] = tags
                res = self._client.write(**kwargs)
                return {"ok": True, "uri": uri or "", "result": res}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:800]}
        from living_assistant.core.isolated_executor import run_isolated_tool
        script = self._build_preamble() + f"""
try:
    if has_tp:
        parts = [TextPart(text={repr(content.strip())})]
    else:
        parts = [{repr(content.strip())}]
    kwargs = {{"parts": parts}}
    if {repr(uri)}: kwargs["uri"] = {repr(uri)}
    if {repr(tags)}: kwargs["tags"] = {repr(tags)}
    result = client.write(**kwargs)
    print(json.dumps({{"ok": True, "uri": {repr(uri or "")}, "result": result}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": str(exc)[:800]}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def search(self, query: str, uri: str = "") -> dict[str, Any]:
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}
        if self._client is not None:
            try:
                kwargs: dict[str, Any] = {"query": query.strip()}
                if uri:
                    kwargs["uri"] = uri
                results = self._client.search(**kwargs)
                items = results if isinstance(results, list) else results.get("items", [])
                return {
                    "ok": True,
                    "query": query,
                    "items": [
                        {
                            "uri": getattr(r, "uri", None) or (r.get("uri", "") if isinstance(r, dict) else ""),
                            "snippet": getattr(r, "snippet", None) or (r.get("snippet", "") if isinstance(r, dict) else ""),
                        }
                        for r in (items if isinstance(items, list) else [])
                    ],
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:800]}
        from living_assistant.core.isolated_executor import run_isolated_tool
        if not query or not query.strip():
            return {"ok": False, "error": "query must not be empty"}
        script = self._build_preamble() + f"""
try:
    kwargs = {{"query": {repr(query.strip())}}}
    if {repr(uri)}: kwargs["uri"] = {repr(uri)}
    results = client.search(**kwargs)
    items = results if isinstance(results, list) else results.get("items", [])
    out_items = [
        {{
            "uri": getattr(r, "uri", None) or (r.get("uri", "") if isinstance(r, dict) else ""),
            "snippet": getattr(r, "snippet", None) or (r.get("snippet", "") if isinstance(r, dict) else ""),
        }}
        for r in (items if isinstance(items, list) else [])
    ]
    print(json.dumps({{"ok": True, "query": {repr(query)}, "items": out_items}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": str(exc)[:800]}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def capture_session(self, session_id: str, messages: list[dict], token_budget: int = 4096) -> dict[str, Any]:
        if not session_id:
            return {"ok": False, "error": "session_id required"}
        if self._client is not None:
            try:
                self._client.create_session(session_id=session_id)
                sc = self._client.session(session_id=session_id)
                for msg in messages:
                    role = str(msg.get("role", "user"))
                    text = str(msg.get("content", ""))
                    if not text.strip():
                        continue
                    sc.add_message(role=role, content=text)
                ctx = sc.get_session_context(token_budget=token_budget)
                return {"ok": True, "session_id": session_id, "context_length": len(str(ctx))}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:800]}
        from living_assistant.core.isolated_executor import run_isolated_tool
        script = self._build_preamble() + f"""
try:
    client.create_session(session_id={repr(session_id)})
    sc = client.session(session_id={repr(session_id)})
    messages = {json.dumps(messages)}
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
    ctx = sc.get_session_context(token_budget={token_budget})
    print(json.dumps({{"ok": True, "session_id": {repr(session_id)}, "context_length": len(str(ctx))}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": str(exc)[:800]}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)
