from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from living_assistant.security.security_utils import redact_secrets

_SERVICE = 'living-assistant'


def _norm(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_').upper()


@dataclass
class CredentialStore:
    """Resolve connector secrets from environment or the OS keyring.

    Secrets are never persisted in Living Assistant JSON/SQLite state.
    """
    use_keyring: bool = True

    def prefix_for(self, connector: dict) -> str:
        return _norm(connector.get('env_prefix') or connector.get('name') or connector.get('provider') or 'CONNECTOR')

    def env(self, connector: dict, key: str) -> str | None:
        prefix = self.prefix_for(connector)
        return os.environ.get(f'{prefix}_{_norm(key)}')

    def _keyring(self):
        if not self.use_keyring:
            return None
        try:
            import keyring  # type: ignore
            return keyring
        except Exception:
            return None

    def load_bundle(self, connector: dict) -> dict[str, Any]:
        kr = self._keyring()
        if kr is None:
            return {}
        try:
            raw = kr.get_password(_SERVICE, f"connector:{connector['name']}")
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_bundle(self, connector: dict, data: dict[str, Any]) -> None:
        kr = self._keyring()
        if kr is None:
            raise RuntimeError('OS keyring support is unavailable. Install the connectors extra or provide tokens through environment variables.')
        # Keep only token/auth fields. Never store arbitrary provider payloads.
        allowed = {'access_token','refresh_token','expires_at','token_type','scope','provider','created_at'}
        payload = {k:v for k,v in data.items() if k in allowed and v is not None}
        kr.set_password(_SERVICE, f"connector:{connector['name']}", json.dumps(payload, separators=(',',':')))

    def delete_bundle(self, connector: dict) -> None:
        kr = self._keyring()
        if kr is None:
            return
        try:
            kr.delete_password(_SERVICE, f"connector:{connector['name']}")
        except Exception:
            pass

    def secret(self, connector: dict, *keys: str) -> str | None:
        for key in keys:
            value = self.env(connector, key)
            if value:
                return value
        bundle = self.load_bundle(connector)
        for key in keys:
            value = bundle.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def status(self, connector: dict) -> dict:
        prefix = self.prefix_for(connector)
        bundle = self.load_bundle(connector)
        configured = []
        for key in ('ACCESS_TOKEN','REFRESH_TOKEN','TOKEN','BOT_TOKEN','CLIENT_ID','CLIENT_SECRET'):
            if os.environ.get(f'{prefix}_{key}'):
                configured.append(key.lower())
        if bundle.get('access_token'): configured.append('keyring_access_token')
        if bundle.get('refresh_token'): configured.append('keyring_refresh_token')
        return {
            'env_prefix': prefix,
            'configured': sorted(set(configured)),
            'keyring_available': self._keyring() is not None,
        }

    @staticmethod
    def safe_error(exc: Exception) -> str:
        return redact_secrets(exc, 1200)
