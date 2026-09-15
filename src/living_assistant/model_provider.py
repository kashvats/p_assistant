from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import httpx
from .security_utils import is_local_model_endpoint, safe_display_url, redact_secrets

class ModelError(RuntimeError):
    pass

@dataclass
class OllamaProvider:
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 180.0
    allow_remote: bool = False
    allow_insecure_remote: bool = False

    def __post_init__(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ModelError("Ollama base_url must be an http/https URL with a hostname.")
        if parsed.username or parsed.password:
            raise ModelError("Ollama base_url must not contain embedded credentials.")
        local = is_local_model_endpoint(self.base_url)
        if not local and not self.allow_remote:
            raise ModelError("Remote Ollama endpoints are disabled. Set ollama.allow_remote=true explicitly to permit prompt data to leave this machine.")
        if not local and parsed.scheme != "https" and not self.allow_insecure_remote:
            raise ModelError("Remote Ollama must use HTTPS unless ollama.allow_insecure_remote=true is explicitly set.")

    def _client(self):
        return httpx.Client(base_url=self.base_url.rstrip("/"), timeout=self.timeout_seconds, trust_env=False)

    def available_models(self) -> list[str]:
        try:
            with self._client() as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                data = r.json()
                return [m.get("name","") for m in data.get("models", [])]
        except Exception as e:
            raise ModelError(f"Could not reach Ollama at {safe_display_url(self.base_url)}: {redact_secrets(e, 800)}") from e

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
                raise ModelError(f"Ollama error {r.status_code}: {redact_secrets(r.text, 1200)}")
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
