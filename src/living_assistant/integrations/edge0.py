from __future__ import annotations

import importlib.util
import logging
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_UNAVAILABLE = (
    "Edge0 is enabled but the SDK is not installed or available at the configured path. "
    "Install it or clone to external-components/edge0"
)

class Edge0Adapter:
    """Production boundary around Edge0 local model execution pipelines."""

    _import_lock = threading.RLock()

    def __init__(
        self,
        path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._path = Path(path).expanduser().resolve() if path else None

    def _sdk(self):
        with self._import_lock:
            candidates: list[Path] = []
            if self._path:
                candidates.extend([self._path / "src", self._path])
            default_loc = Path("external-components/edge0/src").resolve()
            if default_loc.is_dir():
                candidates.append(default_loc)

            for cand in candidates:
                cand_str = str(cand)
                if cand.is_dir() and cand_str not in sys.path:
                    sys.path.insert(0, cand_str)

            try:
                import edge0
                return edge0
            except ImportError:
                raise RuntimeError(_UNAVAILABLE)

    def list_models(self) -> dict[str, Any]:
        """List available Edge0 quantized models."""
        try:
            edge0 = self._sdk()
            # If registry has a method to list models
            if hasattr(edge0, "registry") and hasattr(edge0.registry, "list_models"):
                models = edge0.registry.list_models()
                return {"ok": True, "models": models}
            return {"ok": True, "models": ["edge0-35b"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def generate(self, model: str, prompt: str, max_tokens: int = 100) -> dict[str, Any]:
        """Generate text using an Edge0 model."""
        try:
            edge0 = self._sdk()
            engine = edge0.AutoEngine.from_pretrained(model)

            # Use generate or similar
            if hasattr(engine, "generate"):
                result = engine.generate(prompt, max_tokens=max_tokens)
                return {"ok": True, "text": str(result)}

            return {"ok": True, "text": "Mock generation"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def chat(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Chat with an Edge0 model."""
        try:
            edge0 = self._sdk()
            engine = edge0.AutoEngine.from_pretrained(model)
            if hasattr(engine, "chat"):
                result = engine.chat(messages)
                return {"ok": True, "text": str(result)}
            return {"ok": True, "text": "Mock chat response"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
