from __future__ import annotations
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import threading
import time
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

    def preload(self, model: str, keep_alive: int | str = 300) -> dict:
        """Load a model without generating user-visible text."""
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


class ModelManager:
    """Adaptive model residency and generation-concurrency controller.

    Ollama remains responsible for the actual inference allocation. This controller
    adds assistant-level policy: low-memory systems retain one model; capable systems
    may keep several specialists warm; idle models are evicted LRU-style; and the
    number of simultaneous generations is bounded separately from residency.
    """
    def __init__(self, provider: OllamaProvider, resource_manager=None, event_bus=None):
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
        return result
