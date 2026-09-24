from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import platform
import secrets
from typing import Any

from living_assistant.core.config import data_dir
from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger("living_assistant.security.keyring_vault")

_DEFAULT_SERVICE = "living-assistant"


def _machine_entropy() -> bytes:
    """Collect local host/user entropy to bind the encrypted file vault to this machine."""
    components = [
        platform.node(),
        platform.machine(),
        os.environ.get("USERNAME") or os.environ.get("USER") or "user",
        str(Path.home()),
    ]
    return ":".join(components).encode("utf-8")


class MemoryVault:
    """Ephemeral in-memory vault for testing and headless fallback."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, str]] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get(service, {}).get(username)

    def set_password(self, service: str, username: str, password: str) -> None:
        if service not in self._store:
            self._store[service] = {}
        self._store[service][username] = str(password)

    def delete_password(self, service: str, username: str) -> bool:
        if service in self._store and username in self._store[service]:
            del self._store[service][username]
            return True
        return False

    def list_keys(self, service: str) -> list[str]:
        return sorted(self._store.get(service, {}).keys())


class EncryptedFileVault:
    """Local encrypted credential vault using PBKDF2-HMAC-SHA256 authenticated encryption."""

    def __init__(self, path: Path | None = None, master_key: bytes | None = None) -> None:
        self.path = path or (data_dir() / "credentials.vault")
        self._master_entropy = master_key or _machine_entropy()

    def _derive_keys(self, salt: bytes) -> tuple[bytes, bytes]:
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            self._master_entropy,
            salt,
            iterations=100_000,
            dklen=64,
        )
        return derived[:32], derived[32:]

    def _xor_keystream(self, key: bytes, nonce: bytes, data: bytes) -> bytes:
        out = bytearray(len(data))
        block_size = 32
        blocks_needed = (len(data) + block_size - 1) // block_size
        offset = 0
        for i in range(blocks_needed):
            counter_bytes = i.to_bytes(4, "big")
            block = hashlib.sha256(key + nonce + counter_bytes).digest()
            chunk_len = min(block_size, len(data) - offset)
            for j in range(chunk_len):
                out[offset + j] = data[offset + j] ^ block[j]
            offset += chunk_len
        return bytes(out)

    def _read_vault(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_bytes()
            if len(raw) < 16 + 12 + 32:  # salt(16) + nonce(12) + tag(32)
                return {}
            salt = raw[:16]
            nonce = raw[16:28]
            tag = raw[28:60]
            ciphertext = raw[60:]

            enc_key, auth_key = self._derive_keys(salt)
            computed_tag = hmac.new(auth_key, salt + nonce + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(tag, computed_tag):
                logger.warning("Vault authentication failed (tampering or wrong machine entropy)")
                return {}

            plaintext = self._xor_keystream(enc_key, nonce, ciphertext)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to read encrypted credentials vault: %s", redact_secrets(e))
            return {}

    def _write_vault(self, data: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        enc_key, auth_key = self._derive_keys(salt)

        plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
        ciphertext = self._xor_keystream(enc_key, nonce, plaintext)
        tag = hmac.new(auth_key, salt + nonce + ciphertext, hashlib.sha256).digest()

        payload = salt + nonce + tag + ciphertext
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_bytes(payload)
        if os.name != "nt":
            try:
                tmp_path.chmod(0o600)
            except OSError:
                pass
        tmp_path.replace(self.path)

    def get_password(self, service: str, username: str) -> str | None:
        store = self._read_vault()
        return store.get(service, {}).get(username)

    def set_password(self, service: str, username: str, password: str) -> None:
        store = self._read_vault()
        if service not in store:
            store[service] = {}
        store[service][username] = str(password)
        self._write_vault(store)

    def delete_password(self, service: str, username: str) -> bool:
        store = self._read_vault()
        if service in store and username in store[service]:
            del store[service][username]
            self._write_vault(store)
            return True
        return False

    def list_keys(self, service: str) -> list[str]:
        store = self._read_vault()
        return sorted(store.get(service, {}).keys())


class KeyringVault:
    """Unified secret store managing OS Keyring, encrypted file fallback, and in-memory vault."""

    def __init__(
        self,
        mode: str = "auto",
        vault_file: Path | None = None,
        master_entropy: bytes | None = None,
    ) -> None:
        self.mode = mode.lower()
        self.vault_file = vault_file
        self._file_vault = EncryptedFileVault(path=vault_file, master_key=master_entropy)
        self._memory_vault = MemoryVault()
        self._keyring_mod = self._detect_keyring()

    def _detect_keyring(self) -> Any:
        if self.mode in ("file", "memory"):
            return None
        try:
            import keyring
            backend = keyring.get_keyring()
            # Reject known fail/dummy backends
            backend_name = backend.__class__.__name__.lower()
            if "fail" in backend_name or "dummy" in backend_name:
                return None
            return keyring
        except Exception:
            return None

    @property
    def backend_type(self) -> str:
        if self.mode == "memory":
            return "in_memory"
        if self.mode == "file":
            return "encrypted_file"
        if self._keyring_mod is not None:
            return "os_keyring"
        return "encrypted_file"

    def status(self) -> dict[str, Any]:
        keyring_name = None
        if self._keyring_mod is not None:
            try:
                keyring_name = self._keyring_mod.get_keyring().__class__.__name__
            except Exception:
                pass
        return {
            "mode": self.mode,
            "active_backend": self.backend_type,
            "keyring_available": self._keyring_mod is not None,
            "keyring_backend": keyring_name,
            "vault_file": str(self._file_vault.path) if self.backend_type == "encrypted_file" else None,
        }

    def get_password(self, service: str, username: str) -> str | None:
        """Retrieve a secret by service name and username/key."""
        if self.backend_type == "os_keyring" and self._keyring_mod is not None:
            try:
                val = self._keyring_mod.get_password(service, username)
                if val is not None:
                    return val
            except Exception as e:
                logger.debug("OS keyring get_password failed, falling back: %s", e)
        # Check encrypted file vault fallback
        val = self._file_vault.get_password(service, username)
        if val is not None:
            return val
        return self._memory_vault.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        """Store a secret securely."""
        if self.backend_type == "os_keyring" and self._keyring_mod is not None:
            try:
                self._keyring_mod.set_password(service, username, password)
                return
            except Exception as e:
                logger.warning("OS keyring set_password failed, falling back to encrypted vault: %s", e)

        if self.backend_type != "in_memory":
            try:
                self._file_vault.set_password(service, username, password)
                return
            except Exception as e:
                logger.warning("File vault set_password failed, falling back to memory: %s", e)

        self._memory_vault.set_password(service, username, password)

    def delete_password(self, service: str, username: str) -> bool:
        """Delete a secret across backends."""
        deleted = False
        if self.backend_type == "os_keyring" and self._keyring_mod is not None:
            try:
                self._keyring_mod.delete_password(service, username)
                deleted = True
            except Exception:
                pass
        if self._file_vault.delete_password(service, username):
            deleted = True
        if self._memory_vault.delete_password(service, username):
            deleted = True
        return deleted

    # High-level secret API
    def get_secret(self, key: str, service: str = _DEFAULT_SERVICE) -> str | None:
        return self.get_password(service, key)

    def set_secret(self, key: str, value: str, service: str = _DEFAULT_SERVICE) -> None:
        self.set_password(service, key, value)

    def delete_secret(self, key: str, service: str = _DEFAULT_SERVICE) -> bool:
        return self.delete_password(service, key)

    def list_secrets(self, service: str = _DEFAULT_SERVICE) -> list[str]:
        keys = set(self._memory_vault.list_keys(service))
        keys.update(self._file_vault.list_keys(service))
        return sorted(keys)


_default_vault: KeyringVault | None = None


def get_keyring_vault(mode: str = "auto") -> KeyringVault:
    global _default_vault
    if _default_vault is None or _default_vault.mode != mode:
        _default_vault = KeyringVault(mode=mode)
    return _default_vault
