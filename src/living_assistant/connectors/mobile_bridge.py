from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import time

from living_assistant.core.config import data_dir
from living_assistant.core.storage_utils import atomic_write_json
from living_assistant.security.security_utils import redact_secrets


class MobileBridge:
    """Encrypted phone bridge using an existing Telegram connector.

    Telegram long polling is outbound HTTPS, so the local daemon does not need a
    public listening port or inbound tunnel.  Only explicitly allowlisted private
    chats/users are accepted.  Connector credentials remain in the existing
    credential store; this class persists only the Telegram update offset.
    """

    def __init__(self, config: dict, connector_manager, orchestrator, *, state_path: Path | None = None):
        self.config = config
        self.cfg = dict(config.get("mobile_bridge", {}) or {})
        self.connector_manager = connector_manager
        self.orchestrator = orchestrator
        self.state_path = state_path or (data_dir() / "mobile_bridge_state.json")
        self._last_poll = 0.0
        self._recent_by_chat: dict[str, list[float]] = {}
        self._state = self._load_state()

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", False))

    def _load_state(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def _save_state(self) -> None:
        atomic_write_json(self.state_path, {"offset": int(self._state.get("offset", 0) or 0)})

    def _connector(self) -> dict[str, Any]:
        name = str(self.cfg.get("connector", "")).strip()
        if not name:
            raise RuntimeError("mobile_bridge.connector is not configured.")
        connector = self.connector_manager.registry.get(name)
        if not connector:
            raise RuntimeError(f"Mobile bridge connector {name!r} does not exist.")
        if connector.get("provider") != "telegram":
            raise RuntimeError("Mobile bridge currently requires a Telegram connector.")
        if not connector.get("enabled", True):
            raise RuntimeError("Mobile bridge connector is disabled.")
        capabilities = set(connector.get("capabilities") or [])
        missing = {"messages.read", "messages.send"} - capabilities
        if missing:
            raise RuntimeError(f"Mobile bridge connector is missing capabilities: {sorted(missing)}")
        return connector

    def _allowed(self, message: dict[str, Any]) -> tuple[bool, str]:
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = str(chat.get("id", ""))
        user_id = str(sender.get("id", ""))
        if bool(sender.get("is_bot", False)):
            return False, "bot_sender"
        if bool(self.cfg.get("private_only", True)) and str(chat.get("type", "private")) != "private":
            return False, "non_private_chat"

        allowed_chats = {str(v) for v in (self.cfg.get("allowed_chat_ids") or [])}
        allowed_users = {str(v) for v in (self.cfg.get("allowed_user_ids") or [])}
        if not allowed_chats and not allowed_users:
            return False, "allowlist_empty"
        if allowed_chats and chat_id not in allowed_chats:
            return False, "chat_not_allowed"
        if allowed_users and user_id not in allowed_users:
            return False, "user_not_allowed"
        return True, "allowed"

    def _rate_allowed(self, chat_id: str) -> bool:
        limit = max(1, min(int(self.cfg.get("max_messages_per_minute", 10)), 120))
        now = time.monotonic()
        recent = [ts for ts in self._recent_by_chat.get(chat_id, []) if now - ts < 60.0]
        if len(recent) >= limit:
            self._recent_by_chat[chat_id] = recent
            return False
        recent.append(now)
        self._recent_by_chat[chat_id] = recent
        return True

    @staticmethod
    def _telegram_updates(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise RuntimeError("Telegram returned an invalid updates response.")
        result = payload.get("result")
        if not isinstance(result, list):
            raise RuntimeError("Telegram updates response is missing result list.")
        return [item for item in result if isinstance(item, dict)]

    def _send_text(self, connector: dict[str, Any], chat_id: str, text: str) -> None:
        max_chars = max(256, min(int(self.cfg.get("max_response_chars", 3900)), 4000))
        safe = redact_secrets(str(text or ""), 20000).strip() or "(No text response.)"
        chunks = [safe[i:i + max_chars] for i in range(0, len(safe), max_chars)] or ["(No text response.)"]
        for chunk in chunks:
            response = self.connector_manager._dispatch(
                connector,
                "messages.send",
                {"chat_id": chat_id, "text": chunk},
            )
            if isinstance(response, dict) and response.get("ok") is False:
                raise RuntimeError("Telegram rejected the mobile bridge reply.")

    def poll_once(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        interval = max(1.0, min(float(self.cfg.get("poll_interval_seconds", 3)), 300.0))
        now = time.monotonic()
        if now - self._last_poll < interval:
            return []
        self._last_poll = now

        events: list[dict[str, Any]] = []
        try:
            connector = self._connector()
            limit = max(1, min(int(self.cfg.get("max_messages_per_poll", 10)), 100))
            offset = int(self._state.get("offset", 0) or 0)
            payload = self.connector_manager._dispatch(
                connector,
                "messages.updates",
                {"offset": offset or None, "limit": limit},
            )
            updates = self._telegram_updates(payload)
        except Exception as exc:
            return [{"kind": "mobile_bridge_error", "error": redact_secrets(exc, 1000)}]

        max_message_chars = max(128, min(int(self.cfg.get("max_message_chars", 8000)), 20000))
        for update in updates:
            update_id = update.get("update_id")
            if not isinstance(update_id, int):
                continue
            # Acknowledge before executing the command.  This intentionally
            # prefers at-most-once execution over duplicate side effects after
            # a daemon crash/restart.
            self._state["offset"] = max(int(self._state.get("offset", 0) or 0), update_id + 1)
            try:
                self._save_state()
            except Exception as exc:
                events.append({"kind": "mobile_bridge_error", "error": redact_secrets(exc, 1000)})
                break

            message = update.get("message") or update.get("edited_message")
            if not isinstance(message, dict):
                continue
            allowed, reason = self._allowed(message)
            chat_id = str((message.get("chat") or {}).get("id", ""))
            user_id = str((message.get("from") or {}).get("id", ""))
            if not allowed:
                events.append({
                    "kind": "mobile_bridge_rejected",
                    "reason": reason,
                    "chat_id": chat_id[:64],
                    "user_id": user_id[:64],
                })
                continue
            if not self._rate_allowed(chat_id):
                events.append({"kind": "mobile_bridge_rate_limited", "chat_id": chat_id[:64]})
                continue

            text = message.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            text = text.strip()
            if len(text) > max_message_chars:
                try:
                    self._send_text(connector, chat_id, f"Message is too long. Maximum is {max_message_chars} characters.")
                except Exception as exc:
                    events.append({"kind": "mobile_bridge_error", "error": redact_secrets(exc, 1000)})
                continue

            session_id = f"mobile:telegram:{chat_id}"
            events.append({"kind": "mobile_bridge_command", "chat_id": chat_id[:64], "user_id": user_id[:64]})
            try:
                answer = self.orchestrator.run(text, context="Mobile bridge: authenticated Telegram user.", session_id=session_id)
                self._send_text(connector, chat_id, answer)
                events.append({"kind": "mobile_bridge_replied", "chat_id": chat_id[:64]})
            except Exception as exc:
                events.append({"kind": "mobile_bridge_error", "chat_id": chat_id[:64], "error": redact_secrets(exc, 1000)})
        return events
