from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import time
import yaml

from living_assistant.core.config import load_config, user_config_path
from living_assistant.core.storage_utils import atomic_write_text
from living_assistant.connectors.connectors import ConnectorRegistry, PROVIDER_ACTIONS

_MODEL_RE = re.compile(r'^[A-Za-z0-9._:/-]{1,200}$')


class OnboardingManager:
    """First-launch configuration over the existing config/connector stores."""

    def __init__(self, connector_registry: ConnectorRegistry | None = None, config_path: Path | None = None):
        self.config_path = config_path or user_config_path()
        self.connectors = connector_registry or ConnectorRegistry()

    def status(self) -> dict[str, Any]:
        cfg = load_config(self.config_path) if self.config_path.exists() else load_config()
        state = cfg.get('onboarding') or {}
        return {
            'complete': bool(state.get('completed', False)),
            'completed_at': state.get('completed_at'),
            'config_path': str(self.config_path),
            'workspace_roots': list(cfg.get('workspace_roots') or []),
            'voice_enabled': bool((cfg.get('voice') or {}).get('enabled', False)),
        }

    @staticmethod
    def allowed_connector_capabilities(provider: str) -> list[str]:
        provider = str(provider or '').lower().strip()
        return sorted({spec['cap'] for spec in PROVIDER_ACTIONS.get(provider, {}).values()})

    def complete(
        self,
        *,
        workspace_root: str,
        profile: str,
        model: str,
        voice_enabled: bool,
        connector: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace = Path(workspace_root).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        if not workspace.is_dir():
            raise ValueError('Workspace root must be a directory.')

        profile = str(profile or '').strip()
        model = str(model or '').strip()
        if not _MODEL_RE.fullmatch(model):
            raise ValueError('Model name contains unsupported characters.')

        cfg = load_config(self.config_path) if self.config_path.exists() else load_config()
        profiles = cfg.get('profiles') or {}
        if profile not in profiles or not isinstance(profiles[profile], dict):
            raise ValueError(f'Unknown profile: {profile}')
        models = profiles[profile].get('models') or {}
        if not isinstance(models, dict) or not models:
            raise ValueError(f'Profile {profile} has no model roles configured.')

        cfg['workspace_roots'] = [str(workspace)]
        for role in list(models):
            models[role] = model
        profiles[profile]['models'] = models
        cfg.setdefault('voice', {})['enabled'] = bool(voice_enabled)
        cfg['onboarding'] = {
            'completed': True,
            'completed_at': int(time.time()),
            'profile': profile,
        }

        connector_result = None
        if connector:
            provider = str(connector.get('provider') or '').lower().strip()
            name = str(connector.get('name') or '').strip()
            kind = str(connector.get('kind') or 'custom').strip()
            allowed = set(self.allowed_connector_capabilities(provider))
            capabilities = sorted(set(connector.get('capabilities') or []))
            if provider not in PROVIDER_ACTIONS:
                raise ValueError(f'Unsupported onboarding connector provider: {provider}')
            if not name:
                raise ValueError('Connector name is required.')
            if not capabilities or set(capabilities) - allowed:
                raise ValueError(f'Connector capabilities must be a non-empty subset of {sorted(allowed)}')
            connector_result = self.connectors.add(
                name,
                kind,
                provider,
                capabilities,
                env_prefix=connector.get('env_prefix') or None,
                settings=connector.get('settings') or {},
                enabled=True,
            )

        rendered = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
        atomic_write_text(self.config_path, rendered, mode=0o600)
        return {
            'ok': True,
            'config_path': str(self.config_path),
            'workspace_root': str(workspace),
            'profile': profile,
            'model': model,
            'voice_enabled': bool(voice_enabled),
            'connector': connector_result,
        }
