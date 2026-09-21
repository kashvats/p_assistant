from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
import hmac
import ipaddress
import json
import os
import socket
import threading
import time
import uuid

import httpx

from living_assistant.core.config import data_dir
from living_assistant.core.storage_utils import atomic_write_json
from living_assistant.security.security_policy import sanitize_external_observation
from living_assistant.security.security_utils import redact_secrets, resolve_url_target

_SERVICE_TYPE = "_living-assistant._tcp.local."
_ALLOWED_ROLES = {"general", "coder", "researcher", "planner"}


class PeerAgentManager:
    """mDNS peer discovery with explicit trust and HTTPS-only delegation."""

    def __init__(
        self,
        config: dict,
        profile: str,
        hardware: dict[str, Any],
        delegate_callback: Callable[[str, str, str], dict] | None = None,
        *,
        identity_path: Path | None = None,
        client: httpx.Client | None = None,
    ):
        self.config = config
        self.cfg = dict(config.get("peers", {}) or {})
        self.profile = profile
        self.hardware = dict(hardware or {})
        self.delegate_callback = delegate_callback
        self.identity_path = identity_path or (data_dir() / "peer_identity.json")
        self.client = client
        self.peer_id = self._load_identity()
        self._lock = threading.RLock()
        self._peers: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._zeroconf = None
        self._browser = None
        self._service_info = None
        self._started = False
        self._start_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", False))

    def _load_identity(self) -> str:
        try:
            data = json.loads(self.identity_path.read_text(encoding="utf-8"))
            value = str(data.get("peer_id", "")).strip()
            if value:
                return value
        except Exception:
            pass
        value = uuid.uuid4().hex
        atomic_write_json(self.identity_path, {"peer_id": value}, mode=0o600)
        return value

    def _trusted_ids(self) -> set[str]:
        return {str(v).strip() for v in (self.cfg.get("trusted_peer_ids") or []) if str(v).strip()}

    def _token(self) -> str | None:
        env_name = str(self.cfg.get("token_env", "ASSISTANT_PEER_TOKEN") or "ASSISTANT_PEER_TOKEN")
        return os.environ.get(env_name)

    def _allowed_roles(self) -> set[str]:
        configured = {str(v).strip() for v in (self.cfg.get("allowed_roles") or _ALLOWED_ROLES)}
        return configured & _ALLOWED_ROLES

    @staticmethod
    def _decode_properties(properties: dict[Any, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, value in (properties or {}).items():
            k = key.decode("utf-8", "replace") if isinstance(key, bytes) else str(key)
            v = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
            out[k] = v
        return out

    def _record_service(self, zc, service_type: str, name: str) -> None:
        try:
            info = zc.get_service_info(service_type, name, timeout=1500)
            if info is None:
                return
            props = self._decode_properties(info.properties)
            peer_id = props.get("peer_id", "").strip()
            if not peer_id or peer_id == self.peer_id:
                return
            url = props.get("url", "").strip()
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                return
            addresses = tuple(info.parsed_addresses()) if hasattr(info, "parsed_addresses") else ()
            item = {
                "peer_id": peer_id,
                "name": props.get("name") or name.removesuffix("." + service_type),
                "url": url.rstrip("/"),
                "profile": props.get("profile") or "unknown",
                "ram_gb": float(props.get("ram_gb") or 0),
                "vram_gb": float(props.get("vram_gb") or 0),
                "cpu_count": int(float(props.get("cpu_count") or 0)),
                "addresses": list(addresses),
                "trusted": peer_id in self._trusted_ids(),
                "last_seen": time.time(),
                "service_name": name,
            }
            with self._lock:
                is_new = peer_id not in self._peers
                self._peers[peer_id] = item
                if is_new:
                    self._events.append({"kind": "peer_discovered", "peer_id": peer_id, "name": item["name"], "trusted": item["trusted"]})
        except Exception:
            return

    def _remove_service(self, zc, service_type: str, name: str) -> None:
        with self._lock:
            for peer_id, item in list(self._peers.items()):
                if item.get("service_name") == name:
                    self._peers.pop(peer_id, None)
                    self._events.append({"kind": "peer_lost", "peer_id": peer_id})

    def ensure_started(self) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "enabled": False, "error": "Peer discovery is disabled."}
        if self._started:
            return {"ok": True, "started": True, "peer_id": self.peer_id}
        try:
            from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf  # type: ignore
        except ImportError:
            self._start_error = 'Install peer discovery support with: pip install -e ".[peers]"'
            return {"ok": False, "enabled": True, "error": self._start_error}

        manager = self
        class Listener:
            def add_service(self, zc, service_type, name): manager._record_service(zc, service_type, name)
            def update_service(self, zc, service_type, name): manager._record_service(zc, service_type, name)
            def remove_service(self, zc, service_type, name): manager._remove_service(zc, service_type, name)

        try:
            self._zeroconf = Zeroconf()
            if bool(self.cfg.get("advertise", False)):
                url = str(self.cfg.get("advertise_url", "")).strip().rstrip("/")
                scope, reason, ips = resolve_url_target(url)
                parsed = urlparse(url)
                if parsed.scheme != "https" or scope != "private":
                    raise RuntimeError(f"Peer advertise_url must be HTTPS on a private/local address: {reason or scope}")
                port = parsed.port or 443
                address_bytes = []
                for raw in ips:
                    try:
                        ip = ipaddress.ip_address(raw)
                        if ip.version == 4:
                            address_bytes.append(socket.inet_aton(str(ip)))
                    except Exception:
                        continue
                if not address_bytes:
                    raise RuntimeError("Peer advertise_url must resolve to at least one private IPv4 address for mDNS advertisement.")
                props = {
                    b"peer_id": self.peer_id.encode(),
                    b"name": str(self.cfg.get("name") or socket.gethostname()).encode()[:200],
                    b"url": url.encode()[:500],
                    b"profile": str(self.profile).encode()[:50],
                    b"ram_gb": str(self.hardware.get("ram_gb") or 0).encode(),
                    b"vram_gb": str(self.hardware.get("gpu_vram_gb") or 0).encode(),
                    b"cpu_count": str(self.hardware.get("cpu_count_logical") or 0).encode(),
                }
                service_name = f"{self.peer_id}.{_SERVICE_TYPE}"
                self._service_info = ServiceInfo(
                    _SERVICE_TYPE, service_name, addresses=address_bytes, port=port,
                    properties=props, server=f"{socket.gethostname().split('.')[0]}.local.",
                )
                self._zeroconf.register_service(self._service_info)
            self._browser = ServiceBrowser(self._zeroconf, _SERVICE_TYPE, Listener())
            self._started = True
            self._start_error = None
            return {"ok": True, "started": True, "peer_id": self.peer_id}
        except Exception as exc:
            self.stop()
            self._start_error = redact_secrets(exc, 1000)
            return {"ok": False, "enabled": True, "error": self._start_error}

    def stop(self) -> None:
        zc = self._zeroconf
        info = self._service_info
        self._browser = None
        self._service_info = None
        self._zeroconf = None
        self._started = False
        if zc is not None:
            try:
                if info is not None:
                    zc.unregister_service(info)
            except Exception:
                pass
            try:
                zc.close()
            except Exception:
                pass

    def poll_events(self) -> list[dict[str, Any]]:
        self.ensure_started()
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return events

    def list_peers(self) -> dict[str, Any]:
        start = self.ensure_started()
        ttl = max(10, min(int(self.cfg.get("peer_ttl_seconds", 180)), 3600))
        cutoff = time.time() - ttl
        with self._lock:
            self._peers = {k: v for k, v in self._peers.items() if float(v.get("last_seen", 0)) >= cutoff}
            peers = [dict(v) for v in self._peers.values()]
        peers.sort(key=lambda p: (not p.get("trusted", False), -self._score(p), p.get("name", "")))
        return {"ok": bool(start.get("ok")), "status": start, "peer_id": self.peer_id, "peers": peers}

    @staticmethod
    def _score(peer: dict[str, Any]) -> float:
        return float(peer.get("vram_gb") or 0) * 10.0 + float(peer.get("ram_gb") or 0) + float(peer.get("cpu_count") or 0) * 0.25

    def _select_peer(self, peer_id: str | None) -> dict[str, Any]:
        with self._lock:
            if peer_id:
                peer = self._peers.get(str(peer_id))
                if not peer:
                    raise ValueError("Unknown discovered peer.")
                candidates = [peer]
            else:
                candidates = [p for p in self._peers.values() if p.get("trusted")]
        if not candidates:
            raise ValueError("No trusted peer is available.")
        peer = max(candidates, key=self._score)
        if not peer.get("trusted") or peer.get("peer_id") not in self._trusted_ids():
            raise PermissionError("Peer is discovered but not explicitly trusted.")
        return peer

    def delegate(self, task: str, role: str = "general", context: str = "", peer_id: str | None = None) -> dict[str, Any]:
        self.ensure_started()
        role = str(role or "general").strip().lower()
        if role not in self._allowed_roles():
            return {"ok": False, "error": f"Peer role is not allowed: {role}"}
        max_task = max(256, min(int(self.cfg.get("max_task_chars", 12000)), 30000))
        max_context = max(0, min(int(self.cfg.get("max_context_chars", 20000)), 50000))
        task = redact_secrets(str(task or ""), max_task).strip()
        context = redact_secrets(str(context or ""), max_context)
        if not task:
            return {"ok": False, "error": "Peer task is empty."}
        token = self._token()
        if not token:
            return {"ok": False, "error": "Peer token is not configured."}
        try:
            peer = self._select_peer(peer_id)
            base = str(peer["url"]).rstrip("/")
            parsed = urlparse(base)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise RuntimeError("Trusted peer URL is not a valid HTTPS endpoint.")
            payload = {"source_peer_id": self.peer_id, "role": role, "task": task, "context": context}
            own = self.client is None
            client = self.client or httpx.Client(
                timeout=float(self.cfg.get("request_timeout_seconds", 90)),
                trust_env=False,
                follow_redirects=False,
                verify=bool(self.cfg.get("verify_tls", True)),
            )
            try:
                response = client.post(base + "/peer/delegate", headers={"Authorization": f"Bearer {token}"}, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"Peer returned HTTP {response.status_code}.")
                data = response.json()
            finally:
                if own:
                    client.close()
            if not isinstance(data, dict) or data.get("ok") is not True:
                raise RuntimeError("Peer returned an invalid delegation response.")
            answer = sanitize_external_observation(str(data.get("answer") or ""), 60000)
            return {"ok": True, "peer_id": peer["peer_id"], "role": role, "model": data.get("model"), "answer": answer, "untrusted_external": True}
        except Exception as exc:
            return {"ok": False, "error": redact_secrets(exc, 1000)}

    def accept_delegation(self, authorization: str | None, *, role: str, task: str, context: str = "") -> dict[str, Any]:
        if not self.enabled or not bool(self.cfg.get("accept_delegation", False)):
            return {"ok": False, "status_code": 503, "error": "Peer delegation is disabled."}
        token = self._token()
        supplied = str(authorization or "")
        expected = f"Bearer {token}" if token else ""
        if not token or not hmac.compare_digest(supplied.encode(), expected.encode()):
            return {"ok": False, "status_code": 401, "error": "Invalid peer token."}
        role = str(role or "general").strip().lower()
        if role not in self._allowed_roles():
            return {"ok": False, "status_code": 400, "error": "Peer role is not allowed."}
        max_task = max(256, min(int(self.cfg.get("max_task_chars", 12000)), 30000))
        max_context = max(0, min(int(self.cfg.get("max_context_chars", 20000)), 50000))
        task = redact_secrets(str(task or ""), max_task).strip()
        context = redact_secrets(str(context or ""), max_context)
        if not task:
            return {"ok": False, "status_code": 400, "error": "Peer task is empty."}
        if self.delegate_callback is None:
            return {"ok": False, "status_code": 503, "error": "Local specialist router is unavailable."}
        try:
            result = self.delegate_callback(role, task, context)
            if not isinstance(result, dict) or not result.get("ok"):
                return {"ok": False, "status_code": 500, "error": redact_secrets((result or {}).get("error", "Delegation failed."), 1000)}
            return {"ok": True, "role": role, "model": result.get("model"), "answer": redact_secrets(str(result.get("answer") or ""), 60000)}
        except Exception as exc:
            return {"ok": False, "status_code": 500, "error": redact_secrets(exc, 1000)}
