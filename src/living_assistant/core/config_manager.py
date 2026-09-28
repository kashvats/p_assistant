from __future__ import annotations

import copy
import logging
from typing import Any, Callable

from living_assistant.core.config_validator import ConfigValidator
from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger("living_assistant.core.config_manager")

RESTART_REQUIRED_KEYS = {
    "server.port",
    "server.host",
    "database.path",
    "storage.root",
}

HOT_RELOADABLE_KEYS = {
    "models.provider",
    "models.api_key",
    "models.default_model",
    "workspace.download_folder",
    "voice.voice_id",
    "voice.enabled",
}


class ConfigManager:
    """Manages runtime configuration, atomic hot-reloading, and secret rotation (Sections 93 & 94)."""

    def __init__(self, initial_config: dict[str, Any]):
        ConfigValidator.validate(initial_config)
        self._config: dict[str, Any] = copy.deepcopy(initial_config)
        self._listeners: list[Callable[[str, Any, Any], None]] = []
        self._secrets: dict[str, str] = {}

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def get_all(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)

    def add_listener(self, listener: Callable[[str, Any, Any], None]) -> None:
        self._listeners.append(listener)

    def reload(self, new_config: dict[str, Any]) -> dict[str, Any]:
        """Atomically reload configuration.

        Ensures full validation before applying; if validation fails, the system
        remains on the old config without partial mutation.
        """
        # 1. Validate new config
        ConfigValidator.validate(new_config)

        # 2. Compute differences
        diffs = self._diff_configs(self._config, new_config)
        restart_keys = [k for k in diffs if k in RESTART_REQUIRED_KEYS]

        # 3. Apply atomic change
        old_config = self._config
        self._config = copy.deepcopy(new_config)

        # 4. Notify listeners of changed hot-reloadable keys
        for key_path, (old_val, new_val) in diffs.items():
            for listener in self._listeners:
                try:
                    listener(key_path, old_val, new_val)
                except Exception as exc:
                    logger.warning("Config listener error for '%s': %s", key_path, redact_secrets(exc))

        return {
            "ok": True,
            "changed_keys": list(diffs.keys()),
            "restart_required": len(restart_keys) > 0,
            "restart_keys": restart_keys,
        }

    def rotate_secret(self, secret_name: str, new_secret_value: str) -> dict[str, Any]:
        """Rotate credentials in-memory and notify components while never exposing secrets in logs."""
        if not new_secret_value or not str(new_secret_value).strip():
            raise ValueError(f"New secret value for '{secret_name}' cannot be empty.")

        old_secret = self._secrets.get(secret_name)
        self._secrets[secret_name] = new_secret_value

        # Update nested config if applicable (e.g. models.api_key)
        if secret_name in self._config:
            self._config[secret_name] = new_secret_value
        elif secret_name == "api_key" and "models" in self._config:
            self._config["models"]["api_key"] = new_secret_value

        logger.info("Secret '%s' successfully rotated (length=%d).", secret_name, len(new_secret_value))

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(f"secret.{secret_name}", "[REDACTED]", "[REDACTED]")
            except Exception:
                pass

        return {
            "ok": True,
            "secret_name": secret_name,
            "rotated": True,
        }

    @staticmethod
    def _diff_configs(old: dict[str, Any], new: dict[str, Any], prefix: str = "") -> dict[str, tuple[Any, Any]]:
        diffs = {}
        all_keys = set(old.keys()) | set(new.keys())
        for k in all_keys:
            full_key = f"{prefix}.{k}" if prefix else k
            if k not in old:
                diffs[full_key] = (None, new[k])
            elif k not in new:
                diffs[full_key] = (old[k], None)
            elif isinstance(old[k], dict) and isinstance(new[k], dict):
                nested = ConfigManager._diff_configs(old[k], new[k], full_key)
                diffs.update(nested)
            elif old[k] != new[k]:
                diffs[full_key] = (old[k], new[k])
        return diffs
