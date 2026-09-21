from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import copy
import hashlib

from living_assistant.core.config import load_config
from living_assistant.security.security_utils import redact_secrets


_DYNAMIC_TOP_LEVEL = {
    "notifications",
    "mobile_bridge",
    "peers",
    "routines",
    "briefings",
    "security_guardian",
}
_DYNAMIC_NESTED = {
    "daemon": {
        "poll_seconds",
        "high_memory_percent",
        "high_cpu_percent",
        "alert_on_new_listening_port",
        "watch_files",
        "max_watch_events_per_tick",
        "notification_flush_per_tick",
        "crash_backoff_seconds",
    },
    "connectors": {
        "refresh_interval_seconds",
        "refresh_window_seconds",
    },
}


class ConfigReloader:
    """Validate and hot-apply only settings with safe live semantics.

    Structural/runtime-construction changes are detected and reported as
    restart-required instead of being half-applied to already-built components.
    """

    def __init__(
        self,
        config: dict[str, Any],
        path: Path | None,
        on_apply: Callable[[list[str]], None] | None = None,
    ):
        self.config = config
        self.path = Path(path).expanduser().resolve() if path else None
        self.on_apply = on_apply
        self._last_hash = self._hash_file()

    def _hash_file(self) -> str | None:
        if self.path is None or not self.path.is_file():
            return None
        try:
            return hashlib.sha256(self.path.read_bytes()).hexdigest()
        except OSError:
            return None

    @staticmethod
    def _set_mapping_in_place(target: dict[str, Any], key: str, new_value: Any) -> None:
        current = target.get(key)
        if isinstance(current, dict) and isinstance(new_value, dict):
            current.clear()
            current.update(copy.deepcopy(new_value))
        else:
            target[key] = copy.deepcopy(new_value)

    def _apply(self, new_config: dict[str, Any]) -> tuple[list[str], list[str]]:
        applied: list[str] = []
        restart_required: list[str] = []
        all_keys = set(self.config) | set(new_config)

        for key in sorted(all_keys):
            old_value = self.config.get(key)
            new_value = new_config.get(key)
            if old_value == new_value:
                continue
            if key in _DYNAMIC_TOP_LEVEL:
                self._set_mapping_in_place(self.config, key, new_value if new_value is not None else {})
                applied.append(key)
                continue
            if key in _DYNAMIC_NESTED and isinstance(old_value, dict) and isinstance(new_value, dict):
                allowed = _DYNAMIC_NESTED[key]
                changed_unsupported = []
                for subkey in sorted(set(old_value) | set(new_value)):
                    if old_value.get(subkey) == new_value.get(subkey):
                        continue
                    path = f"{key}.{subkey}"
                    if subkey in allowed:
                        if subkey in new_value:
                            old_value[subkey] = copy.deepcopy(new_value[subkey])
                        else:
                            old_value.pop(subkey, None)
                        applied.append(path)
                    else:
                        changed_unsupported.append(path)
                restart_required.extend(changed_unsupported)
                continue
            restart_required.append(key)

        return applied, restart_required

    def poll(self) -> list[dict[str, Any]]:
        if self.path is None or not self.path.is_file():
            return []
        digest = self._hash_file()
        if digest is None or digest == self._last_hash:
            return []
        # Record the observed revision even if validation fails so one malformed
        # edit creates one event instead of a notification storm every daemon tick.
        self._last_hash = digest
        try:
            new_config = load_config(self.path)
            if not isinstance(new_config, dict):
                raise ValueError("Assistant configuration must be a YAML mapping.")
            applied, restart_required = self._apply(new_config)
            if applied and self.on_apply is not None:
                self.on_apply(applied)
            events: list[dict[str, Any]] = []
            if applied:
                events.append({
                    "kind": "config_reloaded",
                    "path": str(self.path),
                    "applied": applied,
                })
            if restart_required:
                events.append({
                    "kind": "config_restart_required",
                    "path": str(self.path),
                    "settings": sorted(set(restart_required)),
                })
            return events
        except Exception as exc:
            return [{
                "kind": "config_reload_failed",
                "path": str(self.path),
                "error": redact_secrets(exc, 1000),
            }]
