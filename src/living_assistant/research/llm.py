"""Small helpers for asking the local model for structured output."""
from __future__ import annotations

import json
import re
from typing import Any, Callable

Complete = Callable[[list[dict], int], str]  # messages, max_tokens -> reply text


def parse_json(text: str) -> Any:
    """Parse a model reply that should be JSON, tolerating code fences, prose around it and small syntax slips."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.I)
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if starts:
        text = text[min(starts):]
    try:
        return json.loads(text)
    except ValueError:
        from json_repair import repair_json

        return json.loads(repair_json(text))


def ask_json(complete: Complete, system: str, user: str, max_tokens: int = 1500) -> Any:
    return parse_json(complete([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens))
