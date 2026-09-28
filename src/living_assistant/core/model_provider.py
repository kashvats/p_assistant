from __future__ import annotations
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import gc
import importlib
import os
import threading
import time
import httpx
from living_assistant.security.security_utils import is_local_model_endpoint, safe_display_url, redact_secrets

class ModelError(RuntimeError):
    pass


def to_openai_messages(messages: list[dict]) -> list[dict]:
    """Normalize internal (Ollama-style) messages to the OpenAI chat schema.

    Converts `images` (base64 strings) into image_url content parts, ensures every
    assistant tool call has an id and string arguments, and links tool results to
    their call via tool_call_id (OpenAI-compatible servers reject unlinked results).
    """
    import json as _json

    out: list[dict] = []
    pending_ids: list[str] = []
    for raw in messages:
        if not isinstance(raw, dict):
            continue
        role = raw.get("role", "user")
        msg: dict[str, Any] = {"role": role}
        content = raw.get("content")
        images = raw.get("images") or []
        if images:
            parts: list[dict] = [{"type": "text", "text": str(content or "")}]
            for img in images:
                url = img if str(img).startswith("data:") else f"data:image/png;base64,{img}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
            msg["content"] = parts
        else:
            msg["content"] = content if isinstance(content, list) else str(content or "")

        if role == "assistant" and raw.get("tool_calls"):
            calls = []
            for i, call in enumerate(raw["tool_calls"]):
                fn = (call or {}).get("function") or {}
                args = fn.get("arguments")
                if not isinstance(args, str):
                    args = _json.dumps(args or {})
                calls.append({
                    "id": call.get("id") or f"call_{len(out)}_{i}",
                    "type": "function",
                    "function": {"name": fn.get("name") or "", "arguments": args},
                })
            msg["tool_calls"] = calls
            pending_ids = [c["id"] for c in calls]
        elif role == "tool":
            call_id = raw.get("tool_call_id")
            if call_id in pending_ids:
                pending_ids.remove(call_id)
            elif not call_id and pending_ids:
                call_id = pending_ids.pop(0)
            if call_id:
                msg["tool_call_id"] = call_id
            name = raw.get("name") or raw.get("tool_name")
            if name:
                msg["name"] = name
        out.append(msg)
    return out


ONLINE_PROVIDER_SPECS = {
    "openai": {
        "name": "OpenAI",
        "prefixes": ("openai:",),
        "credential_env": "OPENAI_API_KEY",
        "credential_label": "OpenAI API key",
    },
    "anthropic": {
        "name": "Anthropic / Claude",
        "prefixes": ("anthropic:", "claude:"),
        "credential_env": "ANTHROPIC_API_KEY",
        "credential_label": "Anthropic API key",
    },
    "google": {
        "name": "Google / Gemini",
        "prefixes": ("google:", "gemini:"),
        "credential_env": "GOOGLE_API_KEY",
        "credential_label": "Google AI API key",
    },
}


def model_provider_info(model: str | None) -> dict:
    """Classify a model identifier without reading or returning its secret."""
    selected = str(model or "").strip()
    if not selected:
        return {
            "id": "unknown",
            "name": "No model selected",
            "mode": "unknown",
            "local": None,
            "credentials_required": None,
            "credentials_configured": None,
            "credential_env": None,
            "credential_label": None,
            "model": None,
            "supported": None,
        }
    lowered = selected.lower()
    for provider_id, spec in ONLINE_PROVIDER_SPECS.items():
        if lowered.startswith(spec["prefixes"]):
            configured = bool(os.environ.get(spec["credential_env"], "").strip())
            return {
                "id": provider_id,
                "name": spec["name"],
                "mode": "online",
                "local": False,
                "credentials_required": True,
                "credentials_configured": configured,
                "credential_env": spec["credential_env"],
                "credential_label": spec["credential_label"],
                "model": selected,
                "supported": False,
            }
    if lowered.startswith("ollama:"):
        return {
            "id": "ollama",
            "name": "Ollama (local)",
            "mode": "local",
            "local": True,
            "credentials_required": False,
            "credentials_configured": False,
            "credential_env": None,
            "credential_label": None,
            "model": selected,
            "supported": True,
        }
    return {
        "id": "llamacpp",
        "name": "llama.cpp (local)",
        "mode": "local",
        "local": True,
        "credentials_required": False,
        "credentials_configured": False,
        "credential_env": None,
        "credential_label": None,
        "model": selected,
        "supported": True,
    }


@dataclass
class ModelCapability:
    """Explicit metadata declaring capabilities of a model.
    
    Never infer critical capabilities solely from the model filename.
    """
    name: str
    provider: str
    supports_text: bool = True
    supports_vision: bool = False
    supports_tools: bool = True
    supports_json: bool = True
    supports_streaming: bool = True
    context_length: int = 4096
    estimated_vram_mb: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "supports_text": self.supports_text,
            "supports_vision": self.supports_vision,
            "supports_tools": self.supports_tools,
            "supports_json": self.supports_json,
            "supports_streaming": self.supports_streaming,
            "context_length": self.context_length,
            "estimated_vram_mb": self.estimated_vram_mb,
        }


class CapabilityRegistry:
    """Registry maintaining verified model capability declarations."""
    def __init__(self):
        self._capabilities: dict[str, ModelCapability] = {}

    def register(self, capability: ModelCapability) -> None:
        self._capabilities[capability.name] = capability

    def get(self, model_name: str) -> ModelCapability | None:
        return self._capabilities.get(model_name)

    def validate_capability(self, model_name: str, requires_vision: bool = False, requires_tools: bool = False) -> tuple[bool, str]:
        cap = self.get(model_name)
        if cap is None:
            if requires_vision:
                return False, f"Model '{model_name}' has no declared vision capability metadata."
            return True, ""
        if requires_vision and not cap.supports_vision:
            return False, f"Model '{model_name}' does not support vision tasks."
        if requires_tools and not cap.supports_tools:
            return False, f"Model '{model_name}' does not support tool calling."
        return True, ""


@dataclass
class LlamaCppProvider:
    base_url: str = "http://127.0.0.1:8080"
    timeout_seconds: float = 180.0
    api_key: str = "dummy"

    def __post_init__(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ModelError("llama.cpp base_url must be an http/https URL with a hostname.")

    def _client(self):
        return httpx.Client(base_url=self.base_url.rstrip("/"), timeout=self.timeout_seconds, trust_env=False)

    @staticmethod
    def _clean_model_name(raw: str) -> str:
        if not raw:
            return "local-model"
        norm = raw.replace("\\", "/").rstrip("/")
        base = norm.split("/")[-1]
        if base.lower().endswith(".gguf"):
            return base[:-5]
        return base or raw

    def available_models(self) -> list[str]:
        return list(self.model_inventory().keys())

    def model_inventory(self) -> dict[str, dict]:
        """Fetch models from the running llama.cpp server (/v1/models or /models)."""
        result: dict[str, dict] = {}
        try:
            with self._client() as c:
                r = None
                for path in ("/v1/models", "/models"):
                    try:
                        resp = c.get(path)
                        if resp.status_code == 200:
                            r = resp
                            break
                    except Exception:
                        pass
                if r is not None and r.status_code == 200:
                    data = r.json()
                    models_list = data.get("models") or data.get("data") or []
                    for item in models_list:
                        raw = str(item.get("name") or item.get("id") or item.get("model") or "")
                        if raw:
                            clean = self._clean_model_name(raw)
                            size_bytes = (
                                item.get("meta", {}).get("size")
                                or item.get("size")
                                or 0
                            )
                            try:
                                size_bytes = int(size_bytes)
                            except (TypeError, ValueError):
                                size_bytes = 0
                            meta = {
                                "name": clean,
                                "model": clean,
                                "raw_name": raw,
                                "provider": "llamacpp",
                                "loaded": True,
                                "size": size_bytes,
                                "size_bytes": size_bytes,
                                "status": "loaded",
                            }
                            result[clean] = meta
        except Exception:
            pass

        if not result:
            result["openai/local-model"] = {
                "name": "openai/local-model",
                "model": "openai/local-model",
                "provider": "llamacpp",
                "loaded": True,
                "size": 0,
                "size_bytes": 0,
                "status": "loaded",
            }
        else:
            first_clean = next(iter(result.keys()))
            result["openai/local-model"] = {
                "name": "openai/local-model",
                "model": first_clean,
                "provider": "llamacpp",
                "loaded": True,
                "size": result[first_clean]["size"],
                "size_bytes": result[first_clean]["size_bytes"],
                "status": "loaded",
            }
        return result

    def model_size_bytes(self, model: str) -> int | None:
        return 0

    def running_models(self) -> list[dict]:
        inv = self.model_inventory()
        specific = [v for k, v in inv.items() if k != "openai/local-model"]
        return specific if specific else list(inv.values())[:1]

    def preload(self, model: str, keep_alive: int | str = 300) -> dict:
        return {"ok": True, "model": model, "provider": "llamacpp"}

    def unload(self, model: str):
        pass

    def pull(self, model: str) -> dict:
        return {"ok": True, "model": model, "status": "llama.cpp models are loaded directly by the server"}

    def delete(self, model: str) -> dict:
        return {"ok": True, "model": model, "status": "deleted"}

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None,
             keep_alive: int | str = 45, options: dict | None = None) -> dict:
        payload: dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        opts = options or {}
        if "temperature" in opts:
            payload["temperature"] = float(opts["temperature"])
        if "num_predict" in opts:
            payload["max_tokens"] = int(opts["num_predict"])

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with self._client() as c:
            r = c.post("/v1/chat/completions", json=payload, headers=headers)
            if r.status_code >= 400:
                raise ModelError(f"llama.cpp error {r.status_code}: {redact_secrets(r.text, 1200)}")
            data = r.json()
            choice = data["choices"][0]
            msg = choice.get("message", {})
            out_msg: dict[str, Any] = {
                "role": msg.get("role", "assistant"),
                "content": msg.get("content") or "",
            }
            if msg.get("tool_calls"):
                out_msg["tool_calls"] = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    out_msg["tool_calls"].append({
                        "type": "function",
                        "function": {
                            "name": fn.get("name"),
                            "arguments": fn.get("arguments"),
                        }
                    })
            return {"model": data.get("model", model), "message": out_msg, "done": True}

    def chat_stream(self, model: str, messages: list[dict], tools: list[dict] | None = None,
                    keep_alive: int | str = 45, options: dict | None = None):
        import json
        payload: dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        opts = options or {}
        if "temperature" in opts:
            payload["temperature"] = float(opts["temperature"])
        if "num_predict" in opts:
            payload["max_tokens"] = int(opts["num_predict"])

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with self._client() as c:
            with c.stream("POST", "/v1/chat/completions", json=payload, headers=headers) as r:
                if r.status_code >= 400:
                    body = r.read().decode("utf-8", errors="replace")
                    raise ModelError(f"llama.cpp error {r.status_code}: {redact_secrets(body, 1200)}")
                tool_call_chunks: dict[int, dict] = {}
                for line in r.iter_lines():
                    if not line:
                        continue
                    line_str = line.strip()
                    if line_str.startswith("data:"):
                        data_part = line_str[5:].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_part)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content") or ""
                        tool_calls = delta.get("tool_calls")
                        if tool_calls:
                            for tc in tool_calls:
                                idx = int(tc.get("index", 0))
                                if idx not in tool_call_chunks:
                                    tool_call_chunks[idx] = {
                                        "id": tc.get("id") or f"call_{idx}",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                if tc.get("id"):
                                    tool_call_chunks[idx]["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    tool_call_chunks[idx]["function"]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    tool_call_chunks[idx]["function"]["arguments"] += fn["arguments"]

                        if content:
                            yield {
                                "model": chunk.get("model", model),
                                "message": {
                                    "role": delta.get("role", "assistant"),
                                    "content": content,
                                },
                                "done": False,
                            }
                if tool_call_chunks:
                    assembled = []
                    for idx in sorted(tool_call_chunks.keys()):
                        item = tool_call_chunks[idx]
                        if item.get("function", {}).get("name"):
                            assembled.append(item)
                    if assembled:
                        yield {
                            "model": model,
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": assembled,
                            },
                            "done": True,
                        }


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

    @staticmethod
    def _validate_model_name(model: str) -> str:
        """Validate a model identifier before sending it to Ollama.

        Ollama model names are identifiers, not URLs or shell fragments.  Keeping
        the accepted character set narrow prevents control characters/whitespace
        from reaching model-management endpoints while still supporting namespaces,
        tags, quantization suffixes, dots and dashes.
        """
        import re

        name = str(model or "").strip()
        if not name or len(name) > 300:
            raise ModelError("Ollama model name must be between 1 and 300 characters.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?", name):
            raise ModelError("Ollama model name contains unsupported characters.")
        if ".." in name.split("/"):
            raise ModelError("Ollama model name contains an invalid path segment.")
        return name

    def available_models(self) -> list[str]:
        return list(self.model_inventory().keys())

    def model_inventory(self) -> dict[str, dict]:
        try:
            with self._client() as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                data = r.json()
                result = {}
                for item in data.get("models", []):
                    name = str(item.get("name") or item.get("model") or "")
                    if name:
                        result[name] = item
                return result
        except Exception as e:
            raise ModelError(f"Could not reach Ollama at {safe_display_url(self.base_url)}: {redact_secrets(e, 800)}") from e

    def model_size_bytes(self, model: str) -> int | None:
        try:
            item = self.model_inventory().get(model)
            if not item and ":" not in model:
                item = self.model_inventory().get(model + ":latest")
            size = item.get("size") if isinstance(item, dict) else None
            return int(size) if size is not None else None
        except Exception:
            return None

    def running_models(self) -> list[dict]:
        """Return Ollama's currently loaded models from `/api/ps`."""
        try:
            with self._client() as c:
                r = c.get("/api/ps")
                r.raise_for_status()
                data = r.json()
                return [x for x in data.get("models", []) if isinstance(x, dict)]
        except Exception as e:
            raise ModelError(f"Could not query running Ollama models at {safe_display_url(self.base_url)}: {redact_secrets(e, 800)}") from e

    def pull(self, model: str) -> dict:
        """Download an Ollama model using the provider's configured endpoint."""
        model = self._validate_model_name(model)
        try:
            with self._client() as c:
                # Pulls can legitimately take much longer than inference requests.
                r = c.post(
                    "/api/pull",
                    json={"model": model, "stream": False},
                    timeout=max(float(self.timeout_seconds), 3600.0),
                )
                if r.status_code >= 400:
                    raise ModelError(f"Ollama pull error {r.status_code}: {redact_secrets(r.text, 1200)}")
                data = r.json()
                return data if isinstance(data, dict) else {"status": "success"}
        except ModelError:
            raise
        except Exception as e:
            raise ModelError(f"Could not pull {model}: {redact_secrets(e, 800)}") from e

    def delete(self, model: str) -> dict:
        """Delete a locally stored Ollama model."""
        model = self._validate_model_name(model)
        try:
            with self._client() as c:
                r = c.request("DELETE", "/api/delete", json={"model": model})
                if r.status_code >= 400:
                    raise ModelError(f"Ollama delete error {r.status_code}: {redact_secrets(r.text, 1200)}")
                if not r.content:
                    return {"status": "success"}
                try:
                    data = r.json()
                except Exception:
                    data = {"status": "success"}
                return data if isinstance(data, dict) else {"status": "success"}
        except ModelError:
            raise
        except Exception as e:
            raise ModelError(f"Could not delete {model}: {redact_secrets(e, 800)}") from e

    def preload(self, model: str, keep_alive: int | str = 300) -> dict:
        """Load a model without generating user-visible text."""
        model = self._validate_model_name(model)
        try:
            with self._client() as c:
                r = c.post("/api/chat", json={"model": model, "messages": [], "stream": False, "keep_alive": keep_alive})
                if r.status_code >= 400:
                    raise ModelError(f"Ollama preload error {r.status_code}: {redact_secrets(r.text, 1200)}")
                return r.json()
        except ModelError:
            raise
        except Exception as e:
            raise ModelError(f"Could not preload {model}: {redact_secrets(e, 800)}") from e

    def chat_stream(self, model: str, messages: list[dict], tools: list[dict] | None = None,
                    keep_alive: int | str = 45, options: dict | None = None):
        """Yield Ollama NDJSON chat chunks as dictionaries."""
        import json
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": keep_alive,
        }
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        with self._client() as c:
            with c.stream("POST", "/api/chat", json=payload) as r:
                if r.status_code >= 400:
                    body = r.read().decode("utf-8", errors="replace")
                    raise ModelError(f"Ollama error {r.status_code}: {redact_secrets(body, 1200)}")
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ModelError("Ollama returned malformed streaming JSON.") from exc
                    if isinstance(item, dict):
                        yield item

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
                c.post("/api/chat", json={"model": model, "messages": [], "stream": False, "keep_alive": 0})
        except Exception:
            pass


class LiteLLMProvider:
    """Universal provider for llama.cpp servers, OpenAI, Claude, Groq, etc. via LiteLLM."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    def available_models(self) -> list[str]:
        # Represents standard unified namespaces that LiteLLM can parse
        return ["openai/gpt-4o", "anthropic/claude-3-5-sonnet-20240620", "openai/local-model", "ollama/llama3"]

    def model_inventory(self) -> dict[str, dict]:
        return {m: {"size_bytes": 0, "status": "api"} for m in self.available_models()}

    def model_size_bytes(self, model: str) -> int | None:
        return 0

    def running_models(self) -> list[dict]:
        return []

    def preload(self, model: str, keep_alive: int | str = 300) -> dict:
        return {"ok": True, "model": model, "status": "ready"}
        
    def unload(self, model: str):
        pass

    def _kwargs(self, options: dict | None) -> dict:
        kwargs: dict[str, Any] = {}
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.api_key:
            kwargs["api_key"] = self.api_key
        opts = options or {}
        if "temperature" in opts:
            kwargs["temperature"] = float(opts["temperature"])
        if "num_predict" in opts:
            kwargs["max_tokens"] = int(opts["num_predict"])
        return kwargs

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None,
             keep_alive: int | str = 45, options: dict | None = None) -> dict:
        import litellm
        litellm.drop_params = True
        try:
            res = litellm.completion(
                model=model,
                messages=to_openai_messages(messages),
                tools=tools or None,
                **self._kwargs(options),
            )
        except Exception as e:
            raise self._friendly_error(e) from e
        msg = res.choices[0].message
        out_msg: dict[str, Any] = {"role": msg.role or "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            out_msg["tool_calls"] = [
                {
                    "id": tc.id or f"call_{i}",
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for i, tc in enumerate(msg.tool_calls)
            ]
        return {"model": model, "message": out_msg, "done": True}

    def chat_stream(self, model: str, messages: list[dict], tools: list[dict] | None = None,
                    keep_alive: int | str = 45, options: dict | None = None):
        import litellm
        litellm.drop_params = True
        try:
            res = litellm.completion(
                model=model,
                messages=to_openai_messages(messages),
                tools=tools or None,
                stream=True,
                **self._kwargs(options),
            )
            calls: dict[int, dict] = {}
            for chunk in res:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = int(getattr(tc, "index", 0) or 0)
                    slot = calls.setdefault(
                        idx,
                        {"id": f"call_{idx}", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if getattr(tc, "id", None):
                        slot["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if fn.name:
                            slot["function"]["name"] += fn.name
                        if fn.arguments:
                            slot["function"]["arguments"] += fn.arguments
                if delta.content:
                    yield {
                        "model": model,
                        "message": {"role": "assistant", "content": delta.content},
                        "done": False,
                    }
            assembled = [calls[i] for i in sorted(calls) if calls[i]["function"]["name"]]
            if assembled:
                yield {
                    "model": model,
                    "message": {"role": "assistant", "content": "", "tool_calls": assembled},
                    "done": True,
                }
        except ModelError:
            raise
        except Exception as e:
            raise self._friendly_error(e) from e

    def _friendly_error(self, exc: Exception) -> ModelError:
        text = str(exc)
        if any(marker in text for marker in ("10061", "Connection refused", "ConnectError", "Cannot connect", "APIConnectionError")):
            return ModelError(
                f"The local model server at {safe_display_url(self.base_url or '')} is not reachable. "
                "Start llama.cpp/Collibri (llama-server) and try again."
            )
        return ModelError(redact_secrets(text, 2000))

class AirLLMProvider:
    """Lazy local AirLLM provider for models that are larger than GPU VRAM.

    AirLLM performs its own layer-wise disk/GPU streaming.  The dependency is
    optional and imported only when an AirLLM model is actually loaded, so a
    normal Ollama-only installation has no torch/transformers/AirLLM startup
    cost.

    This adapter intentionally exposes *text generation only*.  There is no
    model-family-independent, verified tool-call parser in AirLLM itself, so
    passing tool schemas fails closed rather than silently degrading the
    Orchestrator into unstructured text.
    """

    PREFIX = "airllm:"

    def __init__(self, *, configured_models: list[str] | None = None,
                 compression: str | None = None,
                 layer_shards_saving_path: str | None = None,
                 hf_token_env: str = "HF_TOKEN",
                 prefetching: bool = True,
                 delete_original: bool = False,
                 max_input_tokens: int = 4096,
                 max_new_tokens: int = 512):
        compression = str(compression or "").strip().lower() or None
        if compression not in {None, "4bit", "8bit"}:
            raise ModelError("AirLLM compression must be '4bit', '8bit', or empty.")
        self.compression = compression
        self.layer_shards_saving_path = str(layer_shards_saving_path or "").strip() or None
        self.hf_token_env = str(hf_token_env or "HF_TOKEN").strip() or "HF_TOKEN"
        self.prefetching = bool(prefetching)
        self.delete_original = bool(delete_original)
        self.max_input_tokens = max(128, int(max_input_tokens))
        self.max_new_tokens = max(1, int(max_new_tokens))
        self._configured_models = {
            self.normalize_model(x) for x in (configured_models or []) if str(x or "").strip()
        }
        self._models: dict[str, Any] = {}
        self._load_lock = threading.RLock()
        # Layer streaming is extremely GPU/disk intensive and upstream model
        # objects are not documented as thread-safe.  Serialize AirLLM
        # generations even when the general runtime permits model concurrency.
        self._generation_lock = threading.Lock()

    @classmethod
    def is_airllm_model(cls, model: str) -> bool:
        return str(model or "").strip().lower().startswith(cls.PREFIX)

    @classmethod
    def normalize_model(cls, model: str) -> str:
        value = str(model or "").strip()
        if value.lower().startswith(cls.PREFIX):
            value = value[len(cls.PREFIX):].strip()
        if not value:
            raise ModelError("AirLLM model id/path cannot be empty.")
        return value

    @classmethod
    def external_name(cls, model: str) -> str:
        return cls.PREFIX + cls.normalize_model(model)

    def _airllm_module(self):
        try:
            return importlib.import_module("airllm")
        except ImportError as exc:
            raise ModelError(
                'AirLLM is optional. Install it with: pip install -e ".[airllm]"'
            ) from exc

    def _load_model(self, model: str):
        model_id = self.normalize_model(model)
        with self._load_lock:
            cached = self._models.get(model_id)
            if cached is not None:
                return cached
            module = self._airllm_module()
            auto_model = getattr(module, "AutoModel", None)
            if auto_model is None or not callable(getattr(auto_model, "from_pretrained", None)):
                raise ModelError("Installed AirLLM does not expose AutoModel.from_pretrained().")

            kwargs: dict[str, Any] = {
                "prefetching": self.prefetching,
                "delete_original": self.delete_original,
            }
            if self.compression:
                kwargs["compression"] = self.compression
            if self.layer_shards_saving_path:
                kwargs["layer_shards_saving_path"] = self.layer_shards_saving_path
            token = os.environ.get(self.hf_token_env)
            if token:
                kwargs["hf_token"] = token
            try:
                loaded = auto_model.from_pretrained(model_id, **kwargs)
            except Exception as exc:
                raise ModelError(
                    f"Could not load AirLLM model {model_id}: {redact_secrets(exc, 1000)}"
                ) from exc
            tokenizer = getattr(loaded, "tokenizer", None)
            if tokenizer is None or not callable(tokenizer):
                raise ModelError(f"AirLLM model {model_id} did not expose a callable tokenizer.")
            if not callable(getattr(loaded, "generate", None)):
                raise ModelError(f"AirLLM model {model_id} did not expose generate().")
            self._models[model_id] = loaded
            self._configured_models.add(model_id)
            return loaded

    def _prompt(self, tokenizer, messages: list[dict]) -> str:
        clean_messages: list[dict[str, str]] = []
        for item in messages or []:
            if not isinstance(item, dict):
                continue
            if item.get("images"):
                raise ModelError(
                    "AirLLMProvider currently supports text-only messages; use a compatible local vision provider for images."
                )
            role = str(item.get("role") or "user")
            content = item.get("content", "")
            if not isinstance(content, str):
                raise ModelError("AirLLMProvider requires string message content.")
            clean_messages.append({"role": role, "content": content})

        template = getattr(tokenizer, "apply_chat_template", None)
        if callable(template):
            try:
                rendered = template(clean_messages, tokenize=False, add_generation_prompt=True)
                if isinstance(rendered, str) and rendered:
                    return rendered
            except Exception:
                # Not every tokenizer ships a usable chat template. Fall back to
                # a deterministic role transcript rather than failing a plain
                # text model that otherwise works.
                pass
        parts = []
        for item in clean_messages:
            parts.append(f"{item['role'].upper()}: {item['content']}")
        parts.append("ASSISTANT:")
        return "\n\n".join(parts)

    @staticmethod
    def _sequence_length(value) -> int:
        shape = getattr(value, "shape", None)
        if shape is not None:
            try:
                return int(shape[-1])
            except Exception:
                pass
        try:
            return len(value)
        except Exception:
            return 0

    def available_models(self) -> list[str]:
        names = set(self._configured_models) | set(self._models)
        return sorted(self.external_name(x) for x in names)

    def model_inventory(self) -> dict[str, dict]:
        return {
            self.external_name(model): {
                "name": self.external_name(model),
                "model": self.external_name(model),
                "provider": "airllm",
                "loaded": model in self._models,
            }
            for model in sorted(set(self._configured_models) | set(self._models))
        }

    def model_size_bytes(self, model: str) -> int | None:
        # Total checkpoint size is deliberately *not* returned as a VRAM
        # estimate. AirLLM streams layer shards and a 70B checkpoint size would
        # cause ResourceManager to reject the exact low-VRAM use case this
        # provider is for.
        self.normalize_model(model)
        return None

    def running_models(self) -> list[dict]:
        with self._load_lock:
            return [
                {"name": self.external_name(model), "model": self.external_name(model), "provider": "airllm"}
                for model in sorted(self._models)
            ]

    def preload(self, model: str, keep_alive: int | str = 300) -> dict:
        model_id = self.normalize_model(model)
        self._load_model(model_id)
        return {"done": True, "model": self.external_name(model_id), "provider": "airllm"}

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None,
             keep_alive: int | str = 45, options: dict | None = None) -> dict:
        if tools:
            raise ModelError(
                "AirLLMProvider does not expose verified structured tool calling. "
                "Keep the orchestrator on Ollama and use airllm: models for text specialists."
            )
        model_id = self.normalize_model(model)
        loaded = self._load_model(model_id)
        tokenizer = loaded.tokenizer
        prompt = self._prompt(tokenizer, messages)
        opts = options or {}
        max_input = min(self.max_input_tokens, max(128, int(opts.get("num_ctx") or self.max_input_tokens)))
        max_new = min(self.max_new_tokens, max(1, int(opts.get("num_predict") or self.max_new_tokens)))
        try:
            encoded = tokenizer(
                [prompt], return_tensors="pt", return_attention_mask=False,
                truncation=True, max_length=max_input, padding=False,
            )
            input_ids = encoded["input_ids"]
        except Exception as exc:
            raise ModelError(f"AirLLM tokenization failed: {redact_secrets(exc, 800)}") from exc
        cuda = getattr(input_ids, "cuda", None)
        if not callable(cuda):
            raise ModelError("AirLLM input tensor does not support CUDA transfer.")
        try:
            input_ids = cuda()
        except Exception as exc:
            raise ModelError(
                "AirLLM CUDA transfer failed. A working CUDA-capable PyTorch/GPU setup is required: "
                + redact_secrets(exc, 500)
            ) from exc
        prompt_tokens = self._sequence_length(input_ids)
        try:
            with self._generation_lock:
                generated = loaded.generate(
                    input_ids, max_new_tokens=max_new, use_cache=True,
                    return_dict_in_generate=True,
                )
            sequences = getattr(generated, "sequences", None)
            if sequences is None:
                raise ModelError("AirLLM generation did not return sequences.")
            sequence = sequences[0]
            new_tokens = sequence[prompt_tokens:]
            completion_tokens = self._sequence_length(new_tokens)
            try:
                text = tokenizer.decode(new_tokens, skip_special_tokens=True)
            except TypeError:
                text = tokenizer.decode(new_tokens)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(f"AirLLM generation failed: {redact_secrets(exc, 1000)}") from exc
        return {
            "message": {"role": "assistant", "content": str(text)},
            "done": True,
            "model": self.external_name(model_id),
            "provider": "airllm",
            "prompt_eval_count": prompt_tokens,
            "eval_count": completion_tokens,
        }

    def chat_stream(self, model: str, messages: list[dict], tools: list[dict] | None = None,
                    keep_alive: int | str = 45, options: dict | None = None):
        # AirLLM streams *model layers* from disk; upstream does not currently
        # document a model-family-independent token streaming API. Yield the
        # completed response as one valid chat chunk instead of faking tokens.
        yield self.chat(model, messages, tools=tools, keep_alive=keep_alive, options=options)

    def unload(self, model: str):
        model_id = self.normalize_model(model)
        with self._load_lock:
            self._models.pop(model_id, None)
        gc.collect()
        try:
            torch = importlib.import_module("torch")
            cuda = getattr(torch, "cuda", None)
            if cuda is not None and callable(getattr(cuda, "empty_cache", None)):
                cuda.empty_cache()
        except Exception:
            pass


class CompositeModelProvider:
    """Route normal model names to llama.cpp (primary), airllm: to AirLLM, litellm/ to LiteLLM, and ollama: to Ollama."""

    def __init__(
        self,
        ollama: OllamaProvider | None = None,
        airllm: AirLLMProvider | None = None,
        litellm_provider: LiteLLMProvider | None = None,
        llamacpp: LlamaCppProvider | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ):
        self.llamacpp = llamacpp
        self.ollama = ollama or OllamaProvider()
        self.airllm = airllm or AirLLMProvider()
        self.litellm_enabled = litellm_provider is not None
        self.litellm_provider = litellm_provider or LiteLLMProvider(base_url="http://127.0.0.1:8080/v1", api_key="dummy")
        self.capability_registry = capability_registry or CapabilityRegistry()
        if self.llamacpp is not None:
            self.base_url = self.llamacpp.base_url
        elif ollama is not None and hasattr(ollama, "base_url"):
            self.base_url = ollama.base_url
        else:
            self.llamacpp = LlamaCppProvider()
            self.base_url = self.llamacpp.base_url

    def _route(self, model: str):
        if self.airllm.is_airllm_model(model):
            return self.airllm, self.airllm.normalize_model(model)
        if model.startswith("ollama:"):
            return self.ollama, model[7:]
        if model.startswith(("anthropic/", "huggingface/", "groq/", "openrouter/")):
            return self.litellm_provider, model
        # Collibri / llama.cpp are addressed through LiteLLM's OpenAI-compatible alias.
        if self.litellm_enabled and model.startswith("openai/"):
            return self.litellm_provider, model
        if self.llamacpp is not None:
            return self.llamacpp, model
        return self.ollama, model

    def available_models(self) -> list[str]:
        llamacpp_models = []
        if self.llamacpp is not None:
            try:
                llamacpp_models = self.llamacpp.available_models()
            except Exception:
                pass
        air = self.airllm.available_models()
        lite = self.litellm_provider.available_models()
        try:
            ollama = self.ollama.available_models()
        except Exception:
            ollama = []
        return list(dict.fromkeys([*llamacpp_models, *lite, *air, *ollama]))

    def model_inventory(self) -> dict[str, dict]:
        result = {}
        if self.llamacpp is not None:
            try:
                result.update(self.llamacpp.model_inventory())
            except Exception:
                pass
        try:
            result.update(self.airllm.model_inventory())
        except Exception:
            pass
        try:
            result.update(self.litellm_provider.model_inventory())
        except Exception:
            pass
        try:
            result.update(self.ollama.model_inventory())
        except Exception:
            pass
        return result

    def model_size_bytes(self, model: str) -> int | None:
        provider, routed = self._route(model)
        return provider.model_size_bytes(routed)

    def running_models(self) -> list[dict]:
        if self.llamacpp is not None:
            try:
                running = self.llamacpp.running_models()
                if running:
                    return running
            except Exception:
                pass
        air = self.airllm.running_models()
        try:
            ollama = self.ollama.running_models()
        except Exception:
            ollama = []
        return [*ollama, *air]

    def preload(self, model: str, keep_alive: int | str = 300) -> dict:
        provider, routed = self._route(model)
        return provider.preload(routed, keep_alive=keep_alive)

    def chat_stream(self, model: str, messages: list[dict], tools: list[dict] | None = None,
                    keep_alive: int | str = 45, options: dict | None = None):
        provider, routed = self._route(model)
        yield from provider.chat_stream(
            routed, messages, tools=tools, keep_alive=keep_alive, options=options
        )

    def _failover_candidates(self, current_provider: Any, requires_vision: bool = False) -> list[tuple[Any, str]]:
        candidates = []
        pool = [
            (self.ollama, "ollama:default"),
            (self.litellm_provider, "openai/gpt-4o"),
            (self.llamacpp, "local-model"),
        ]
        for prov, mname in pool:
            if prov is not current_provider and prov is not None:
                cap = self.capability_registry.get(mname)
                if requires_vision and (cap is None or not cap.supports_vision):
                    continue
                candidates.append((prov, mname))
        return candidates

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None,
             keep_alive: int | str = 45, options: dict | None = None) -> dict:
        requires_vision = any(isinstance(m, dict) and ("images" in m or "image_url" in m) for m in messages)
        valid, err = self.capability_registry.validate_capability(model, requires_vision=requires_vision, requires_tools=bool(tools))
        if not valid:
            raise ModelError(err)

        provider, routed = self._route(model)
        try:
            return provider.chat(routed, messages, tools=tools, keep_alive=keep_alive, options=options)
        except (httpx.ConnectError, httpx.TimeoutException, ModelError) as exc:
            for fallback_provider, fallback_model in self._failover_candidates(provider, requires_vision=requires_vision):
                try:
                    res = fallback_provider.chat(fallback_model, messages, tools=tools, keep_alive=keep_alive, options=options)
                    if isinstance(res, dict):
                        res["failover"] = True
                        res["original_model"] = model
                        res["active_provider"] = getattr(fallback_provider, "__class__", type(fallback_provider)).__name__
                    return res
                except Exception:
                    continue
            raise

    def unload(self, model: str):
        provider, routed = self._route(model)
        return provider.unload(routed)


class ModelManager:
    """Adaptive model residency and generation-concurrency controller.

    The configured provider remains responsible for actual inference allocation. This controller
    adds assistant-level policy: low-memory systems retain one model; capable systems
    may keep several specialists warm; idle models are evicted LRU-style; and the
    number of simultaneous generations is bounded separately from residency.
    """
    def __init__(self, provider: Any, resource_manager=None, event_bus=None):
        self.provider = provider
        self.resources = resource_manager
        self.event_bus = event_bus
        policy = getattr(resource_manager, "model_policy", None)
        self.max_resident_models = int(getattr(policy, "max_resident_models", 1))
        self.max_concurrent_generations = int(getattr(policy, "max_concurrent_generations", 1))
        self.max_parallel_per_model = int(getattr(policy, "max_parallel_per_model", 1))
        self.resident_keep_alive_seconds = int(getattr(policy, "resident_keep_alive_seconds", 45))
        self.admission_timeout_seconds = float(getattr(policy, "admission_timeout_seconds", 120))
        self.active_model: str | None = None
        self._resident: OrderedDict[str, dict] = OrderedDict()
        self._in_use: dict[str, int] = {}
        self._condition = threading.Condition(threading.RLock())
        self._global_slots = threading.BoundedSemaphore(max(1, self.max_concurrent_generations))
        self._model_slots: dict[str, threading.BoundedSemaphore] = {}

    def _publish(self, event_type: str, **data):
        if self.event_bus:
            try:
                self.event_bus.publish(event_type, **data)
            except Exception:
                pass

    def _model_sem(self, model: str) -> threading.BoundedSemaphore:
        with self._condition:
            sem = self._model_slots.get(model)
            if sem is None:
                sem = threading.BoundedSemaphore(max(1, self.max_parallel_per_model))
                self._model_slots[model] = sem
            return sem

    def _touch_locked(self, model: str, priority: int | None = None):
        now = datetime.now(timezone.utc).isoformat()
        item = self._resident.pop(model, {})
        if priority is not None:
            # Priority is sticky upward for the lifetime of a resident model. A
            # lower-priority background use of the same model must not demote a
            # foreground model that the Orchestrator is relying on.
            item["priority"] = max(int(item.get("priority", 0) or 0), int(priority))
        else:
            item.setdefault("priority", 50)
        item.update({"model": model, "last_used": now})
        self._resident[model] = item
        self.active_model = model

    def _evict_one_locked(self, exclude: set[str] | None = None, incoming_priority: int = 50) -> str | None:
        exclude = exclude or set()
        candidates = []
        for lru_index, candidate in enumerate(self._resident.keys()):
            if candidate in exclude or self._in_use.get(candidate, 0) > 0:
                continue
            priority = int(self._resident[candidate].get("priority", 50) or 50)
            # A background/lower-priority request is never allowed to evict a
            # higher-priority idle foreground model. Among eligible models, evict
            # the lowest priority first and preserve LRU ordering as the tie-breaker.
            if priority > int(incoming_priority):
                continue
            candidates.append((priority, lru_index, candidate))
        if not candidates:
            return None
        priority, _index, candidate = min(candidates)
        self.provider.unload(candidate)
        self._resident.pop(candidate, None)
        self._publish("model.evicted", model=candidate, reason="priority_lru", priority=priority, incoming_priority=int(incoming_priority))
        if self.active_model == candidate:
            self.active_model = next(reversed(self._resident), None) if self._resident else None
        return candidate

    def _prepare_locked(self, model: str, priority: int = 50):
        if model in self._resident:
            self._touch_locked(model, priority)
            return

        deadline = time.monotonic() + self.admission_timeout_seconds
        while True:
            # Respect the residency count first.
            if len(self._resident) >= self.max_resident_models:
                if self._evict_one_locked(exclude={model}, incoming_priority=priority) is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ModelError("Timed out waiting for an idle model slot.")
                    self._condition.wait(timeout=min(remaining, 0.25))
                    continue

            size = None
            try:
                size = self.provider.model_size_bytes(model)
            except Exception:
                pass
            if self.resources:
                resident_size = sum(int(meta.get('estimated_size_bytes') or 0) for meta in self._resident.values())
                try:
                    ok, reason = self.resources.can_admit_model(size, resident_count=len(self._resident), resident_size_bytes=resident_size)
                except TypeError:
                    # Compatibility with custom ResourceManager implementations using
                    # the pre-v0.13 two-argument admission hook.
                    ok, reason = self.resources.can_admit_model(size, resident_count=len(self._resident))
                if not ok and self._resident:
                    if self._evict_one_locked(exclude={model}, incoming_priority=priority) is not None:
                        continue
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ModelError(reason)
                    self._condition.wait(timeout=min(remaining, 0.25))
                    continue
                if not ok and not self._resident:
                    # One model is allowed to use Ollama's normal partial-offload path
                    # as long as basic system RAM remains healthy.
                    try:
                        basic_ok, basic_reason = self.resources.can_start_model(size)
                    except TypeError:
                        # Backwards compatibility for external/custom resource
                        # managers implementing the older zero-argument hook.
                        basic_ok, basic_reason = self.resources.can_start_model()
                    if not basic_ok:
                        raise ModelError(basic_reason)
            self._touch_locked(model, priority)
            if size is not None:
                self._resident[model]["estimated_size_bytes"] = int(size)
            self._publish("model.resident", model=model, resident_count=len(self._resident), max_resident=self.max_resident_models)
            return

    def activate(self, model: str, priority: int = 50):
        """Backwards-compatible activation without starting a generation lease."""
        with self._condition:
            self._prepare_locked(model, priority=priority)

    def effective_keep_alive(self, requested: int | str | None = None) -> int | str:
        if self.max_resident_models > 1:
            return self.resident_keep_alive_seconds
        return 45 if requested is None else requested

    def _wait_for_thermal_slot(self, deadline: float):
        check = getattr(self.resources, 'thermal_pressure', None) if self.resources else None
        if not callable(check):
            return
        announced = False
        while True:
            with self._condition:
                active = sum(self._in_use.values())
            if active <= 0:
                return
            try:
                hot, reason = check()
            except Exception:
                return
            if not hot:
                return
            if not announced:
                self._publish('model.concurrency_throttled', reason=reason, active_generations=active)
                announced = True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ModelError(f"Timed out waiting for thermal pressure to fall: {reason}")
            with self._condition:
                self._condition.wait(timeout=min(remaining, 0.25))

    @contextmanager
    def lease(self, model: str, timeout: float | None = None, priority: int = 50):
        timeout = self.admission_timeout_seconds if timeout is None else max(0.1, float(timeout))
        model_slot = self._model_sem(model)
        started = time.monotonic()
        if not model_slot.acquire(timeout=timeout):
            raise ModelError(f"Timed out waiting for model concurrency slot: {model}")
        remaining = max(0.1, timeout - (time.monotonic() - started))
        if not self._global_slots.acquire(timeout=remaining):
            model_slot.release()
            raise ModelError("Timed out waiting for a global model generation slot.")
        deadline = started + timeout
        try:
            self._wait_for_thermal_slot(deadline)
            with self._condition:
                self._prepare_locked(model, priority=priority)
                self._in_use[model] = self._in_use.get(model, 0) + 1
                self._touch_locked(model, priority)
                self._publish("model.generation_started", model=model, in_use=self._in_use[model])
            yield self.effective_keep_alive()
        finally:
            with self._condition:
                if self._in_use.get(model, 0) > 1:
                    self._in_use[model] -= 1
                else:
                    self._in_use.pop(model, None)
                if model in self._resident:
                    self._touch_locked(model)
                self._publish("model.generation_completed", model=model, in_use=self._in_use.get(model, 0))
                self._condition.notify_all()
            self._global_slots.release()
            model_slot.release()

    def _local_provider(self):
        """Return the configured local model provider (llama.cpp or Ollama)."""
        candidate = getattr(self.provider, "llamacpp", None)
        if candidate is not None:
            return candidate
        candidate = getattr(self.provider, "ollama", self.provider)
        return candidate

    def _ollama_provider(self):
        """Compatibility accessor for local model provider."""
        return self._local_provider()

    def resolve_local_model(self, requested: str | None) -> str | None:
        """Resolve a requested model name to an installed/running model."""
        if not requested or AirLLMProvider.is_airllm_model(str(requested)):
            return requested
        try:
            inv = self._local_provider().model_inventory()
            names = sorted(inv.keys())
        except Exception:
            return requested
        if not names:
            return requested
        if requested in names:
            return requested
        prefix_matches = [
            name for name in names
            if name.startswith(f"{requested}-") or name.startswith(f"{requested}:")
        ]
        return prefix_matches[0] if prefix_matches else requested

    def local_model_catalog(self) -> dict:
        """Return installed Ollama models with disk and VRAM information.

        `size_vram` reported by `/api/ps` is an actual current residency value. For
        unloaded models we expose the same conservative size * 1.15 estimate used
        by the resource-admission policy and label it explicitly as an estimate.
        """
        provider = self._ollama_provider()
        try:
            inventory = provider.model_inventory()
        except Exception:
            inventory = {}
            
        try:
            running = provider.running_models()
        except Exception:
            running = []

        running_by_name: dict[str, dict] = {}
        for item in running:
            name = str(item.get("name") or item.get("model") or "")
            if name:
                running_by_name[name] = item

        with self._condition:
            in_use = dict(self._in_use)

        models = []
        total_disk = 0
        for name, raw in sorted(inventory.items(), key=lambda item: item[0].lower()):
            item = raw if isinstance(raw, dict) else {}
            disk_size = max(0, int(item.get("size") or 0))
            total_disk += disk_size
            live = running_by_name.get(name)
            if live is None and name.endswith(":latest"):
                live = running_by_name.get(name[:-7])
            has_actual_vram = bool(live) and (live or {}).get("size_vram") is not None
            actual_vram = max(0, int((live or {}).get("size_vram") or 0)) if has_actual_vram else None
            estimated_vram = int(disk_size * 1.15) if disk_size else 0
            if has_actual_vram:
                vram_bytes = int(actual_vram or 0)
                vram_kind = "actual_loaded"
            else:
                vram_bytes = estimated_vram
                vram_kind = "estimated_from_disk"
            models.append({
                "name": name,
                "digest": str(item.get("digest") or ""),
                "modified_at": item.get("modified_at"),
                "details": item.get("details") if isinstance(item.get("details"), dict) else {},
                "disk_size_bytes": disk_size,
                "loaded": bool(live),
                "in_use": int(in_use.get(name, 0)),
                "vram_bytes": vram_bytes,
                "vram_kind": vram_kind,
                "actual_vram_bytes": actual_vram,
                "estimated_vram_bytes": estimated_vram,
            })

        hardware = getattr(self.resources, "hardware", None)
        gpu_total = getattr(hardware, "gpu_vram_gb", None)
        gpu_free = getattr(hardware, "gpu_vram_free_gb", None)
        if self.resources:
            try:
                gpu_free = self.resources.snapshot().get("gpu_free_vram_gb", gpu_free)
            except Exception:
                pass
        return {
            "ok": True,
            "models": models,
            "count": len(models),
            "total_disk_bytes": total_disk,
            "gpu": {
                "name": getattr(hardware, "gpu_name", None),
                "total_vram_gb": gpu_total,
                "free_vram_gb": gpu_free,
                "unified_memory": bool(getattr(hardware, "unified_memory", False)),
            },
        }

    def pull_local_model(self, model: str) -> dict:
        provider = self._ollama_provider()
        model = provider._validate_model_name(model)
        data = provider.pull(model)
        self._publish("model.pulled", model=model)
        return {"ok": True, "model": model, "provider": data}

    def delete_local_model(self, model: str, *, confirmed: bool = False) -> dict:
        provider = self._ollama_provider()
        model = provider._validate_model_name(model)
        if not confirmed:
            return {"ok": False, "error": "Model deletion requires explicit confirmation.", "model": model}
        with self._condition:
            if self._in_use.get(model, 0):
                return {"ok": False, "error": "Model is currently in use.", "model": model}
            if model in self._resident:
                provider.unload(model)
                self._resident.pop(model, None)
                if self.active_model == model:
                    self.active_model = next(reversed(self._resident), None) if self._resident else None
                self._condition.notify_all()
        data = provider.delete(model)
        self._publish("model.deleted", model=model)
        return {"ok": True, "model": model, "provider": data}

    def preload(self, model: str) -> dict:
        """Preload a model and retain it according to the residency policy."""
        with self.lease(model, priority=10) as keep_alive:
            data = self.provider.preload(model, keep_alive=keep_alive)
        return {"ok": True, "model": model, "provider": data, "runtime": self.status(refresh=False)}

    def unload(self, model: str, force: bool = False) -> dict:
        with self._condition:
            if self._in_use.get(model, 0) and not force:
                return {"ok": False, "error": "Model is currently in use.", "model": model}
            self.provider.unload(model)
            self._resident.pop(model, None)
            self._in_use.pop(model, None)
            if self.active_model == model:
                self.active_model = next(reversed(self._resident), None) if self._resident else None
            self._condition.notify_all()
        self._publish("model.unloaded", model=model, forced=bool(force))
        return {"ok": True, "model": model}

    def sleep(self):
        """Unload all idle resident models.

        In-use models are not force-killed; they will become eligible after their
        generation lease completes.
        """
        with self._condition:
            for model in list(self._resident.keys()):
                if self._in_use.get(model, 0):
                    continue
                self.provider.unload(model)
                self._resident.pop(model, None)
            self.active_model = next(reversed(self._resident), None) if self._resident else None
            self._condition.notify_all()

    def sync_running_models(self) -> list[dict]:
        running = self.provider.running_models()
        names = []
        with self._condition:
            for item in running:
                name = str(item.get("name") or item.get("model") or "")
                if not name:
                    continue
                names.append(name)
                meta = self._resident.pop(name, {})
                meta.update({
                    "model": name,
                    "size_bytes": item.get("size"),
                    "size_vram_bytes": item.get("size_vram"),
                    "expires_at": item.get("expires_at"),
                    "last_used": meta.get("last_used") or datetime.now(timezone.utc).isoformat(),
                })
                self._resident[name] = meta
            # Do not delete local in-use entries merely because `/api/ps` raced with
            # a load; prune only idle entries known not to be reported.
            for name in list(self._resident.keys()):
                if name not in names and not self._in_use.get(name, 0):
                    self._resident.pop(name, None)
            if self.active_model not in self._resident:
                self.active_model = next(reversed(self._resident), None) if self._resident else None
        return running

    def status(self, refresh: bool = False) -> dict:
        provider_running = None
        provider_error = None
        if refresh:
            try:
                provider_running = self.sync_running_models()
            except Exception as exc:
                provider_error = redact_secrets(exc, 500)
        with self._condition:
            policy = getattr(getattr(self.resources, "model_policy", None), "to_dict", lambda: {
                "mode": "single",
                "max_resident_models": self.max_resident_models,
                "max_concurrent_generations": self.max_concurrent_generations,
                "max_parallel_per_model": self.max_parallel_per_model,
                "resident_keep_alive_seconds": self.resident_keep_alive_seconds,
            })()
            result = {
                "active_model": self.active_model,
                "resident_models": [dict(v, in_use=self._in_use.get(k, 0)) for k, v in self._resident.items()],
                "resident_count": len(self._resident),
                "in_use": dict(self._in_use),
                "policy": policy,
            }
        if provider_running is not None:
            result["provider_running"] = provider_running
        if provider_error:
            result["provider_error"] = provider_error
        result["model_provider"] = self.provider_info(self.active_model)
        return result

    def provider_info(self, model: str | None = None) -> dict:
        """Describe the inference provider without exposing provider credentials."""
        selected = str(model or self.active_model or "")
        provider = self.provider
        inferred = model_provider_info(selected)
        if inferred["mode"] == "online":
            return inferred
        if isinstance(provider, CompositeModelProvider):
            if provider.airllm.is_airllm_model(selected):
                return {
                    "id": "airllm",
                    "name": "AirLLM (local)",
                    "mode": "local",
                    "local": True,
                    "credentials_required": False,
                    "credentials_configured": False,
                    "credential_env": None,
                    "credential_label": None,
                    "model": selected,
                    "supported": True,
                }
            if selected.startswith("ollama:"):
                return {
                    "id": "ollama",
                    "name": "Ollama (local)",
                    "mode": "local",
                    "local": True,
                    "credentials_required": False,
                    "credentials_configured": False,
                    "credential_env": None,
                    "credential_label": None,
                    "model": selected,
                    "supported": True,
                }
            return {
                "id": "llamacpp",
                "name": "llama.cpp (local)",
                "mode": "local",
                "local": True,
                "credentials_required": False,
                "credentials_configured": False,
                "credential_env": None,
                "credential_label": None,
                "model": selected,
                "supported": True,
            }
        if isinstance(provider, LlamaCppProvider):
            return {
                "id": "llamacpp",
                "name": "llama.cpp (local)",
                "mode": "local",
                "local": True,
                "credentials_required": False,
                "credentials_configured": False,
                "credential_env": None,
                "credential_label": None,
                "model": selected,
                "supported": True,
            }
        if isinstance(provider, AirLLMProvider):
            return {
                "id": "airllm",
                "name": "AirLLM (local)",
                "mode": "local",
                "local": True,
                "credentials_required": False,
                "credentials_configured": False,
                "credential_env": None,
                "credential_label": None,
                "model": selected,
                "supported": True,
            }
        if isinstance(provider, OllamaProvider):
            return inferred
        name = type(provider).__name__
        return {
            "id": name.lower().removesuffix("provider"),
            "name": name,
            "mode": "online",
            "local": False,
            "credentials_required": True,
            "credentials_configured": False,
            "credential_env": None,
            "credential_label": "Provider credentials",
            "model": selected,
            "supported": False,
        }

    def validate_model_selection(self, model: str) -> dict:
        info = self.provider_info(model)
        if info["mode"] == "local":
            return {"ok": True, "provider": info}
        if not info["credentials_configured"]:
            return {
                "ok": False,
                "provider": info,
                "error": (
                    f"{info['name']} is an online provider and requires "
                    f"{info['credential_label']} in {info['credential_env']}. "
                    "Local models never require provider credentials."
                ),
            }
        return {
            "ok": False,
            "provider": info,
            "error": (
                f"{info['name']} online inference is not configured in this "
                "installation. Select an Ollama or AirLLM model for local use."
            ),
        }

    def handle_oom(self, failed_model: str, error_message: str = "") -> dict:
        """Section 52: Detect GPU/system OOM, release failed model, clear caches, and select smaller fallback."""
        lowered_err = (error_message or "").lower()
        is_oom = any(
            marker in lowered_err
            for marker in ("out of memory", "cuda oom", "not enough memory", "oom", "resource exhausted", "allocation failed")
        ) or not error_message

        # 1. Release failed model from residency and unload provider
        try:
            self.provider.unload(failed_model)
        except Exception:
            pass
        with self._condition:
            self._resident.pop(failed_model, None)
            if self.active_model == failed_model:
                self.active_model = None

        # 2. Clear recoverable cache via resource manager if available
        cleared_caches = {}
        if self.resources and hasattr(self.resources, "metabolize"):
            try:
                cleared_caches = self.resources.metabolize()
            except Exception:
                pass

        # 3. Track failed model to avoid infinite fallback loops
        if not hasattr(self, "_oom_failed_models"):
            self._oom_failed_models: set[str] = set()
        self._oom_failed_models.add(failed_model)

        # 4. Select smaller model from available models
        smaller_model = None
        candidates = []
        try:
            inventory = self.status(refresh=False).get("models", [])
            failed_size = None
            for item in inventory:
                if item["name"] == failed_model:
                    failed_size = item.get("disk_size_bytes") or item.get("vram_bytes") or 0
                    break

            for item in inventory:
                c_name = item["name"]
                if c_name == failed_model or c_name in self._oom_failed_models:
                    continue
                c_size = item.get("disk_size_bytes") or item.get("vram_bytes") or 0
                if failed_size is None or c_size < failed_size or failed_size == 0:
                    candidates.append((c_size, c_name))
            if candidates:
                candidates.sort()
                smaller_model = candidates[0][1]
        except Exception:
            pass

        # If no smaller model found in current inventory, check lightweight fallbacks
        if not smaller_model:
            for fallback in ("llama3.2:1b", "gemma:2b", "qwen2.5:1.5b", "phi3:mini"):
                if fallback != failed_model and fallback not in self._oom_failed_models:
                    try:
                        resolved = self.resolve_local_model(fallback)
                        if resolved and resolved != fallback and resolved not in self._oom_failed_models:
                            smaller_model = resolved
                            break
                    except Exception:
                        pass

        retry_allowed = bool(smaller_model and smaller_model not in self._oom_failed_models)
        self._publish(
            "model.oom_recovery",
            failed_model=failed_model,
            smaller_model=smaller_model,
            retry_allowed=retry_allowed,
        )

        return {
            "ok": True,
            "detected_oom": is_oom,
            "released_model": failed_model,
            "cleared_caches": cleared_caches,
            "smaller_model": smaller_model,
            "retry_allowed": retry_allowed,
            "error_detail": error_message,
        }
