from __future__ import annotations

import json

from living_assistant.security.security_guardian import _now

def _safe_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return None

def _event_time(value) -> str:
    if isinstance(value, str) and value:
        return value
    return _now()

