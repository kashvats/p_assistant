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
    """Resolve connector secrets from environment, the OS keyring, or encrypted vault fallback.

    Secrets are never persisted in Living Assistant plain JSON/SQLite state.
    """
    use_keyring: bool = True
    vault: Any = None

    def __post_init__(self) -> None:
        if self.vault is None:
            from living_assistant.security.keyring_vault import KeyringVault
            self.vault = KeyringVault(mode="auto" if self.use_keyring else "memory")

    def prefix_for(self, connector: dict) -> str:
        return _norm(connector.get('env_prefix') or connector.get('name') or connector.get('provider') or 'CONNECTOR')

    def env(self, connector: dict, key: str) -> str | None:
        prefix = self.prefix_for(connector)
        return os.environ.get(f'{prefix}_{_norm(key)}')

    def _keyring(self):
        if not self.use_keyring:
            return None
        return getattr(self.vault, "_keyring_mod", None)

    def load_bundle(self, connector: dict) -> dict[str, Any]:
        try:
            raw = self.vault.get_password(_SERVICE, f"connector:{connector['name']}")
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_bundle(self, connector: dict, data: dict[str, Any]) -> None:
        allowed = {'access_token','refresh_token','expires_at','token_type','scope','provider','created_at'}
        payload = {k:v for k,v in data.items() if k in allowed and v is not None}
        self.vault.set_password(_SERVICE, f"connector:{connector['name']}", json.dumps(payload, separators=(',',':')))

    def delete_bundle(self, connector: dict) -> None:
        try:
            self.vault.delete_password(_SERVICE, f"connector:{connector['name']}")
        except Exception:
            pass

    def secret(self, connector: dict, *keys: str) -> str | None:
        for key in keys:
            value = self.env(connector, key)
            if value:
                return value
        bundle = self.load_bundle(connector)
        for key in keys:
            value = bundle.get(key) or bundle.get(key.lower()) or bundle.get(key.upper())
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
            'keyring_available': self.vault.backend_type == "os_keyring" if self.use_keyring else False,
            'vault_backend': self.vault.backend_type,
        }

    @staticmethod
    def safe_error(exc: Exception) -> str:
        return redact_secrets(exc, 1200)
