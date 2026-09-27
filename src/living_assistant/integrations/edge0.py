from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any

from living_assistant.core.isolated_executor import run_isolated_tool

logger = logging.getLogger(__name__)

_UNAVAILABLE = (
    "Edge0 is enabled but the SDK is not installed or available at the configured path. "
    "Install it or clone to external-components/edge0"
)

class Edge0Adapter:
    """Production boundary around Edge0 local model execution pipelines.
    Uses subprocess isolation to prevent sys.path and global state corruption.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._path = str(Path(path).expanduser().resolve()) if path else ""

    def _build_preamble(self) -> str:
        """Sets up sys.path exclusively inside the subprocess."""
        return f"""
import sys
import json
path = {repr(self._path)}
if path:
    sys.path.insert(0, path + '/src')
    sys.path.insert(0, path)
sys.path.insert(0, 'external-components/edge0/src')
sys.path.insert(0, 'external-components/edge0')
"""

    def list_models(self) -> dict[str, Any]:
        """List available Edge0 quantized models."""
        script = self._build_preamble() + """
try:
    import edge0
    models = ["edge0-35b"]
    if hasattr(edge0, "registry") and hasattr(edge0.registry, "list_models"):
        models = edge0.registry.list_models()
    print(json.dumps({"ok": True, "models": models}))
except ImportError:
    print(json.dumps({"ok": False, "error": "Edge0 SDK not found."}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def generate(self, model: str, prompt: str, max_tokens: int = 100) -> dict[str, Any]:
        """Generate text using an Edge0 model."""
        script = self._build_preamble() + f"""
try:
    import edge0
    engine = edge0.AutoEngine.from_pretrained({repr(model)})
    if not hasattr(engine, "generate"):
        print(json.dumps({{"ok": False, "error": "Edge0 engine does not expose generate()"}}))
    else:
        result = engine.generate({repr(prompt)}, max_tokens={max_tokens})
        print(json.dumps({{"ok": True, "text": str(result)}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def chat(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Chat with an Edge0 model."""
        script = self._build_preamble() + f"""
try:
    import edge0
    engine = edge0.AutoEngine.from_pretrained({repr(model)})
    if not hasattr(engine, "chat"):
        print(json.dumps({{"ok": False, "error": "Edge0 engine does not expose chat()"}}))
    else:
        result = engine.chat({json.dumps(messages)})
        print(json.dumps({{"ok": True, "text": str(result)}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)
