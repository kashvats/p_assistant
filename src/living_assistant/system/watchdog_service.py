from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("living_assistant.system.watchdog_service")

# Common directories and patterns to ignore to avoid thrashing and noise
DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    ".venv", "venv", "env", "node_modules", "bower_components",
    "dist", "build", "target", ".cache", ".next", ".nuxt", "coverage",
}

DEFAULT_IGNORE_SUFFIXES = {
    ".tmp", ".temp", ".swp", ".swo", "~", ".bak", ".part", ".crdownload"
}


class DebouncedEventHandler:
    """Debounces native filesystem events to eliminate burst chatter and redundant notifications.

    When editors save files or build tools emit artifacts, dozens of OS events fire within
    milliseconds. This handler accumulates events per path and flushes only stable,
    coalesced changes after a configurable quiet period.
    """

    def __init__(
        self,
        watch_name: str,
        root: Path,
        extensions: set[str] | None = None,
        debounce_seconds: float = 0.3,
        ignore_dirs: set[str] | None = None,
        ignore_suffixes: set[str] | None = None,
    ) -> None:
        self.watch_name = watch_name
        self.root = root.resolve()
        self.extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions} if extensions else set()
        self.debounce_seconds = max(0.05, float(debounce_seconds))
        self.ignore_dirs = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
        self.ignore_suffixes = ignore_suffixes if ignore_suffixes is not None else DEFAULT_IGNORE_SUFFIXES
        self._lock = threading.Lock()
        # Map: normalized path str -> (event_kind, first_seen_ts, last_seen_ts)
        self._pending: dict[str, tuple[str, float, float]] = {}

    def _should_ignore(self, path_str: str, is_dir: bool = False) -> bool:
        if is_dir:
            return True
        try:
            p = Path(path_str)
            for part in p.parts:
                if part in self.ignore_dirs:
                    return True
            if p.suffix.lower() in self.ignore_suffixes or p.name.startswith("."):
                return True
            if self.extensions and p.suffix.lower() not in self.extensions:
                return True
            return False
        except Exception:
            return True

    def _record_event(self, kind: str, src_path: str) -> None:
        now = time.time()
        norm_path = str(Path(src_path).resolve())
        with self._lock:
            existing = self._pending.get(norm_path)
            if existing is None:
                self._pending[norm_path] = (kind, now, now)
            else:
                prev_kind, first_ts, _ = existing
                # State transition coalescing:
                # added + changed -> added
                # added + removed -> cancelled (ephemeral scratch file)
                # changed + changed -> changed
                # changed + removed -> removed
                # removed + added -> changed
                if prev_kind == "file_added" and kind == "file_removed":
                    del self._pending[norm_path]
                elif prev_kind == "file_added" and kind == "file_changed":
                    self._pending[norm_path] = ("file_added", first_ts, now)
                elif prev_kind == "file_changed" and kind == "file_removed":
                    self._pending[norm_path] = ("file_removed", first_ts, now)
                elif prev_kind == "file_removed" and kind == "file_added":
                    self._pending[norm_path] = ("file_changed", first_ts, now)
                else:
                    self._pending[norm_path] = (kind, first_ts, now)

    def on_created(self, event: Any) -> None:
        if not getattr(event, "is_directory", False) and not self._should_ignore(event.src_path):
            self._record_event("file_added", event.src_path)

    def on_modified(self, event: Any) -> None:
        if not getattr(event, "is_directory", False) and not self._should_ignore(event.src_path):
            self._record_event("file_changed", event.src_path)

    def on_deleted(self, event: Any) -> None:
        if not getattr(event, "is_directory", False) and not self._should_ignore(event.src_path):
            self._record_event("file_removed", event.src_path)

    def on_moved(self, event: Any) -> None:
        if not getattr(event, "is_directory", False):
            if not self._should_ignore(event.src_path):
                self._record_event("file_removed", event.src_path)
            dest = getattr(event, "dest_path", None)
            if dest and not self._should_ignore(dest):
                self._record_event("file_added", dest)

    def collect_ready_events(self, max_events: int = 50, force: bool = False) -> list[dict]:
        now = time.time()
        to_emit: dict[str, str] = {}
        with self._lock:
            for path_str, (kind, first_ts, last_ts) in list(self._pending.items()):
                if force or (now - last_ts >= self.debounce_seconds):
                    to_emit[path_str] = kind
                    del self._pending[path_str]

        if not to_emit:
            return []

        added = {p for p, k in to_emit.items() if k == "file_added"}
        changed = {p for p, k in to_emit.items() if k == "file_changed"}
        removed = {p for p, k in to_emit.items() if k == "file_removed"}
        total_changes = len(added) + len(changed) + len(removed)
        threshold = max(1, int(max_events))

        if total_changes > threshold:
            sample_limit = min(200, max(100, threshold))
            return [{
                "kind": "file_changes_batched",
                "watch": self.watch_name,
                "root": str(self.root),
                "total_changes": total_changes,
                "counts": {
                    "file_added": len(added),
                    "file_changed": len(changed),
                    "file_removed": len(removed),
                },
                "paths": {
                    "file_added": sorted(added)[:sample_limit],
                    "file_changed": sorted(changed)[:sample_limit],
                    "file_removed": sorted(removed)[:sample_limit],
                },
                "sample_truncated": any(len(items) > sample_limit for items in (added, changed, removed)),
            }]

        events = []
        for p in sorted(added):
            events.append({"kind": "file_added", "watch": self.watch_name, "path": p})
        for p in sorted(changed):
            events.append({"kind": "file_changed", "watch": self.watch_name, "path": p})
        for p in sorted(removed):
            events.append({"kind": "file_removed", "watch": self.watch_name, "path": p})
        return events

    def clear(self) -> int:
        with self._lock:
            count = len(self._pending)
            self._pending.clear()
            return count

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)


class WatchdogObserverManager:
    """Manages real-time filesystem observation with background thread lifecycle,

    debouncing, and event subscription hooks.
    """

    def __init__(self, debounce_seconds: float = 0.3) -> None:
        self.debounce_seconds = debounce_seconds
        self._observer: Any = None
        self._handlers: dict[str, tuple[DebouncedEventHandler, Any]] = {}
        self._listeners: list[Callable[[list[dict]], None]] = []
        self._lock = threading.RLock()
        self._running = False
        self._available = False
        self._check_watchdog_available()

    def _check_watchdog_available(self) -> bool:
        try:
            import watchdog.observers
            import watchdog.events
            self._available = True
            return True
        except ImportError:
            self._available = False
            return False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running and (self._observer is not None and self._observer.is_alive())

    def start(self) -> bool:
        if not self._available:
            return False
        with self._lock:
            if self._running and self._observer and self._observer.is_alive():
                return True
            try:
                from watchdog.observers import Observer
                self._observer = Observer()
                self._observer.daemon = True
                self._observer.start()
                self._running = True
                logger.info("WatchdogObserverManager started successfully.")
                return True
            except Exception as e:
                logger.warning("Failed to start watchdog observer: %s", e)
                self._running = False
                return False

    def stop(self, timeout: float = 2.0) -> bool:
        with self._lock:
            if not self._running or self._observer is None:
                return True
            try:
                self._observer.stop()
                self._observer.join(timeout=timeout)
                self._running = False
                self._observer = None
                logger.info("WatchdogObserverManager stopped.")
                return True
            except Exception as e:
                logger.warning("Error stopping watchdog observer: %s", e)
                return False

    def add_watch(
        self,
        name: str,
        path: str | Path,
        recursive: bool = True,
        extensions: list[str] | None = None,
        debounce_seconds: float | None = None,
    ) -> bool:
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"Watch path is not a directory: {resolved}")

        debounce = debounce_seconds if debounce_seconds is not None else self.debounce_seconds
        handler = DebouncedEventHandler(
            watch_name=name,
            root=resolved,
            extensions=set(extensions) if extensions else None,
            debounce_seconds=debounce,
        )

        with self._lock:
            if not self.running:
                self.start()

            # If replacing an existing watch, unschedule old one
            if name in self._handlers:
                self.remove_watch(name)

            if self._observer is not None and self.running:
                try:
                    # Bridge watchdog's handler interface
                    from watchdog.events import FileSystemEventHandler

                    class _Bridge(FileSystemEventHandler):
                        def on_created(self, event): handler.on_created(event)
                        def on_modified(self, event): handler.on_modified(event)
                        def on_deleted(self, event): handler.on_deleted(event)
                        def on_moved(self, event): handler.on_moved(event)

                    watch_handle = self._observer.schedule(
                        _Bridge(),
                        str(resolved),
                        recursive=bool(recursive),
                    )
                    self._handlers[name] = (handler, watch_handle)
                    return True
                except Exception as e:
                    logger.warning("Failed to schedule watch '%s' for path %s: %s", name, resolved, e)
                    self._handlers[name] = (handler, None)
                    return False
            else:
                self._handlers[name] = (handler, None)
                return False

    def remove_watch(self, name: str) -> bool:
        with self._lock:
            entry = self._handlers.pop(name, None)
            if entry is None:
                return False
            handler, watch_handle = entry
            handler.clear()
            if watch_handle is not None and self._observer is not None and self.running:
                try:
                    self._observer.unschedule(watch_handle)
                except Exception:
                    pass
            return True

    def add_listener(self, callback: Callable[[list[dict]], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[list[dict]], None]) -> bool:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)
                return True
            return False

    def poll(self, max_events_per_watch: int = 50, force: bool = False) -> list[dict]:
        all_events: list[dict] = []
        with self._lock:
            for name, (handler, _) in list(self._handlers.items()):
                events = handler.collect_ready_events(max_events=max_events_per_watch, force=force)
                if events:
                    all_events.extend(events)

        if all_events and self._listeners:
            for listener in list(self._listeners):
                try:
                    listener(all_events)
                except Exception as exc:
                    logger.warning("Error in watchdog listener callback: %s", exc)

        return all_events

    def rebaseline(self) -> dict:
        cleared = 0
        with self._lock:
            for _, (handler, _) in self._handlers.items():
                cleared += handler.clear()
        return {"cleared_pending": cleared, "watches": len(self._handlers)}

    def stats(self) -> dict:
        with self._lock:
            return {
                "available": self._available,
                "running": self.running,
                "watches_count": len(self._handlers),
                "watches": {
                    name: {
                        "root": str(h.root),
                        "pending_events": h.pending_count,
                        "extensions": sorted(list(h.extensions)),
                    }
                    for name, (h, _) in self._handlers.items()
                },
                "listeners_count": len(self._listeners),
            }


_GLOBAL_WATCHDOG: WatchdogObserverManager | None = None
_GLOBAL_LOCK = threading.Lock()


def get_watchdog_manager(debounce_seconds: float = 0.3) -> WatchdogObserverManager:
    """Singleton provider for shared WatchdogObserverManager."""
    global _GLOBAL_WATCHDOG
    with _GLOBAL_LOCK:
        if _GLOBAL_WATCHDOG is None:
            _GLOBAL_WATCHDOG = WatchdogObserverManager(debounce_seconds=debounce_seconds)
        return _GLOBAL_WATCHDOG
