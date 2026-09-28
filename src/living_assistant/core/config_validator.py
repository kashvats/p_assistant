from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
import re

KNOWN_PROVIDERS = {
    "ollama",
    "litellm",
    "airllm",
    "llamacpp",
    "composite",
    "openai",
    "anthropic",
    "mock",
}


class ConfigValidationError(ValueError):
    """Raised when configuration fails schema or safety validation."""
    pass


class ConfigValidator:
    """Validates configuration parameters prior to runtime consumption (Section 92)."""

    @classmethod
    def validate(cls, config: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(config, dict):
            raise ConfigValidationError("Configuration root must be a dictionary.")

        # 1. Port validation
        server = config.get("server", {})
        if isinstance(server, dict) and "port" in server:
            port = server.get("port")
            if not isinstance(port, int) or port < 1 or port > 65535:
                errors.append(f"Invalid server port '{port}': Port must be an integer between 1 and 65535.")

        # 2. Timeouts validation
        for key in ["timeout", "timeout_seconds", "request_timeout"]:
            if key in config:
                val = config[key]
                if not isinstance(val, (int, float)) or val <= 0:
                    errors.append(f"Invalid {key} '{val}': Timeout must be a positive number.")

        # Check nested timeouts
        if isinstance(server, dict) and "timeout" in server:
            val = server["timeout"]
            if not isinstance(val, (int, float)) or val <= 0:
                errors.append(f"Invalid server.timeout '{val}': Timeout must be a positive number.")

        # 3. Model provider validation
        models = config.get("models", {})
        if isinstance(models, dict):
            provider = models.get("provider")
            if provider and str(provider).lower() not in KNOWN_PROVIDERS:
                errors.append(
                    f"Unknown model provider '{provider}'. Supported providers: {sorted(KNOWN_PROVIDERS)}"
                )

        # 4. URL validation
        for section_name in ["server", "endpoints", "models"]:
            sec = config.get(section_name, {})
            if isinstance(sec, dict):
                for k, v in sec.items():
                    if k.endswith("_url") or k == "url":
                        if isinstance(v, str) and v:
                            try:
                                parsed = urlparse(v)
                                if parsed.scheme not in {"http", "https", "ws", "wss"}:
                                    errors.append(f"Malformed URL '{v}' in {section_name}.{k}: scheme must be http(s) or ws(s).")
                                elif not parsed.netloc:
                                    errors.append(f"Malformed URL '{v}' in {section_name}.{k}: missing host.")
                            except Exception as exc:
                                errors.append(f"Invalid URL format for '{v}' in {section_name}.{k}: {exc}")

        # 5. Missing secret reference validation
        def check_unresolved_env(obj: Any, path: str = ""):
            if isinstance(obj, str):
                if re.search(r"\$\{([A-Z0-9_]+)\}", obj):
                    warnings.append(f"Unresolved environment secret reference in '{path}': {obj}")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    check_unresolved_env(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_unresolved_env(v, f"{path}[{i}]")

        check_unresolved_env(config)

        if errors:
            raise ConfigValidationError("; ".join(errors))

        return {
            "valid": True,
            "errors": errors,
            "warnings": warnings,
        }
