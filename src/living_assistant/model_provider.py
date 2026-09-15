from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import httpx

class ModelError(RuntimeError):
    pass

@dataclass
class OllamaProvider:
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 180.0

    def _client(self):
        return httpx.Client(base_url=self.base_url.rstrip("/"), timeout=self.timeout_seconds)

    def available_models(self) -> list[str]:
        try:
            with self._client() as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                data = r.json()
                return [m.get("name","") for m in data.get("models", [])]
        except Exception as e:
            raise ModelError(f"Could not reach Ollama at {self.base_url}: {e}") from e

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None,
             keep_alive: int | str = 45, options: dict | None = None) -> dict:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
        }
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        with self._client() as c:
            r = c.post("/api/chat", json=payload)
            if r.status_code >= 400:
                raise ModelError(f"Ollama error {r.status_code}: {r.text[:1200]}")
            return r.json()

    def unload(self, model: str):
        try:
            with self._client() as c:
                c.post("/api/generate", json={"model": model, "prompt": "", "keep_alive": 0})
        except Exception:
            pass

class ModelManager:
    def __init__(self, provider: OllamaProvider):
        self.provider = provider
        self.active_model: str | None = None

    def activate(self, model: str):
        if self.active_model and self.active_model != model:
            self.provider.unload(self.active_model)
        self.active_model = model

    def sleep(self):
        if self.active_model:
            self.provider.unload(self.active_model)
            self.active_model = None
