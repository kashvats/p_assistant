from __future__ import annotations

import functools
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable

from living_assistant.core.config import cache_dir
from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger("living_assistant.system.disk_cache")


class MemoryCacheFallback:
    """In-memory cache fallback when diskcache is unavailable or disabled."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}
        self.hits: int = 0
        self.misses: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return default
        val, exp = entry
        if exp is not None and time.time() > exp:
            del self._store[key]
            self.misses += 1
            return default
        self.hits += 1
        return val

    def set(self, key: str, value: Any, expire: float | None = None) -> bool:
        exp_time = (time.time() + expire) if expire is not None else None
        self._store[key] = (value, exp_time)
        return True

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        return count

    @property
    def volume(self) -> int:
        return 0

    def __len__(self) -> int:
        return len(self._store)


class DiskCacheManager:
    """Structured disk-backed caching layer using python-diskcache with automatic namespace partitioning."""

    DEFAULT_EXPIRY = {
        "web_queries": 3600.0,       # 1 hour for web search and external fetches
        "doc_parsing": 14 * 86400.0,  # 14 days for parsed invoices / documents
        "embeddings": 30 * 86400.0,   # 30 days for vector features and embeddings
        "tool_results": 300.0,        # 5 minutes for read-only tools
    }

    def __init__(self, root: Path | None = None, size_limit_bytes: int = 1_073_741_824) -> None:
        self.root = root or (cache_dir() / "diskcache")
        self.size_limit = size_limit_bytes
        self._cache: Any = None
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            from diskcache import Cache
            self.root.mkdir(parents=True, exist_ok=True)
            self._cache = Cache(str(self.root), size_limit=self.size_limit)
            self._backend_name = "diskcache"
        except Exception as e:
            logger.info("DiskCache library unavailable, using in-memory fallback: %s", redact_secrets(e))
            self._cache = MemoryCacheFallback()
            self._backend_name = "memory_fallback"

    @property
    def backend(self) -> str:
        return self._backend_name

    def _format_key(self, namespace: str, key: str) -> str:
        clean_ns = namespace.strip().lower()
        return f"{clean_ns}:{key}"

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        composite_key = self._format_key(namespace, key)
        try:
            val = self._cache.get(composite_key, default=default)
            return val
        except Exception as e:
            logger.warning("Cache get error: %s", redact_secrets(e))
            return default

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        expire: float | None = None,
        tag: str | None = None,
    ) -> bool:
        composite_key = self._format_key(namespace, key)
        ttl = expire if expire is not None else self.DEFAULT_EXPIRY.get(namespace.lower())
        try:
            if self._backend_name == "diskcache":
                return bool(self._cache.set(composite_key, value, expire=ttl, tag=tag))
            return bool(self._cache.set(composite_key, value, expire=ttl))
        except Exception as e:
            logger.warning("Cache set error: %s", redact_secrets(e))
            return False

    def delete(self, namespace: str, key: str) -> bool:
        composite_key = self._format_key(namespace, key)
        try:
            return bool(self._cache.delete(composite_key))
        except Exception as e:
            logger.warning("Cache delete error: %s", redact_secrets(e))
            return False

    def clear(self, namespace: str | None = None) -> int:
        if namespace is None:
            try:
                count = len(self._cache)
                self._cache.clear()
                return count
            except Exception:
                return 0

        prefix = f"{namespace.strip().lower()}:"
        deleted = 0
        try:
            if self._backend_name == "diskcache":
                keys_to_del = [k for k in self._cache if isinstance(k, str) and k.startswith(prefix)]
                for k in keys_to_del:
                    if self._cache.delete(k):
                        deleted += 1
            else:
                keys_to_del = [k for k in self._cache._store if k.startswith(prefix)]
                for k in keys_to_del:
                    del self._cache._store[k]
                    deleted += 1
        except Exception as e:
            logger.warning("Cache clear error: %s", redact_secrets(e))
        return deleted

    def stats(self) -> dict[str, Any]:
        count = len(self._cache)
        raw_volume = getattr(self._cache, "volume", 0)
        size = raw_volume() if callable(raw_volume) else int(raw_volume)
        return {
            "backend": self.backend,
            "root": str(self.root),
            "items_count": count,
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "size_limit_mb": round(self.size_limit / (1024 * 1024), 2),
        }

    def cached(
        self,
        namespace: str,
        expire: float | None = None,
        key_fn: Callable[..., str] | None = None,
    ) -> Callable:
        """Decorator to cache function outputs keyed by namespace and arguments."""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if key_fn is not None:
                    k = key_fn(*args, **kwargs)
                else:
                    raw_args = json.dumps({"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}}, sort_keys=True)
                    k = hashlib.sha256(raw_args.encode("utf-8")).hexdigest()[:24]

                cached_val = self.get(namespace, k)
                if cached_val is not None:
                    return cached_val

                res = func(*args, **kwargs)
                if res is not None:
                    self.set(namespace, k, res, expire=expire)
                return res
            return wrapper
        return decorator


_default_disk_cache: DiskCacheManager | None = None


def get_disk_cache() -> DiskCacheManager:
    global _default_disk_cache
    if _default_disk_cache is None:
        _default_disk_cache = DiskCacheManager()
    return _default_disk_cache
