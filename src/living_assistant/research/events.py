"""Normalized events: the common form every observation takes before pattern analysis.

An event is {event_type, timestamp?, stream, entities, attributes, numeric_features}
stored as an ``event`` object (kind = event_type) and linked to the evidence that
produced it. Adapters turn logs (Drain template mining), time series, symbol
streams and plain records into events; research claims become events in
``evidence.py``.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .store import KnowledgeStore

_SPACE_RE = re.compile(r"[\s\x00-\x1f]+")


def normalize_type(value: Any, lower: bool = True) -> str:
    """Stable event type: whitespace collapsed to "_". Non-ASCII is kept, so symbols such as
    "△" or "ZX-4" survive intact (symbol types are not lowercased)."""
    text = str(value or "event").strip()
    if lower and not text.startswith("symbol:"):
        text = text.lower()
    text = _SPACE_RE.sub("_", text).strip("_")
    return text[:120] or "event"


def normalize_time(value: Any) -> str | None:
    """ISO-8601 UTC string, or None when the value is not a recognizable time."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value  # epoch millis vs seconds
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="milliseconds")
    if isinstance(value, datetime):
        value = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            import pandas as pd

            parsed = pd.Timestamp(text).to_pydatetime()
        except Exception:
            return None
    return normalize_time(parsed)


def add_events(store: KnowledgeStore, project_id: str, events: Iterable[dict], *, evidence_ids: Iterable[str] = (),
               source: str = "user") -> list[dict]:
    """Store events. Each item may use event_type/type, timestamp/ts/time, entities, attributes,
    numeric_features, stream, evidence_ids and related_event_ids."""
    shared_evidence = list(evidence_ids)
    seq = store.count(project_id).get("event", 0)
    stored = []
    for raw in events:
        if not isinstance(raw, dict):
            continue
        seq += 1
        etype = normalize_type(raw.get("event_type") or raw.get("type") or raw.get("kind"))
        numeric = {str(k): float(v) for k, v in (raw.get("numeric_features") or {}).items() if _is_number(v)}
        attributes = dict(raw.get("attributes") or {})
        for key, value in raw.items():  # flat records: extra numeric columns become features, others attributes
            if key in ("event_type", "type", "kind", "timestamp", "ts", "time", "entities", "attributes",
                       "numeric_features", "stream", "evidence_ids", "related_event_ids"):
                continue
            if _is_number(value) and not isinstance(value, bool):
                numeric.setdefault(str(key), float(value))
            else:
                attributes.setdefault(str(key), value)
        entities = [str(e) for e in (raw.get("entities") or []) if str(e).strip()]
        ts = normalize_time(raw.get("timestamp") or raw.get("ts") or raw.get("time"))
        data = {
            "stream": str(raw.get("stream") or "default"),
            "seq": seq,
            "entities": entities,
            "attributes": attributes,
            "numeric_features": numeric,
            "source": source,
        }
        links = [("evidenced_by", e) for e in [*shared_evidence, *(raw.get("evidence_ids") or [])]]
        links += [("related_to", e) for e in raw.get("related_event_ids") or []]
        title = etype + (f" ({', '.join(entities[:3])})" if entities else "")
        stored.append(store.add(project_id, "event", title, kind=etype, ts=ts or f"~{seq:012d}", level="OBSERVED",
                                data=data, links=links, body=f"{etype} {' '.join(entities)} {attributes}"))
    return stored


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return not isinstance(value, str) or bool(re.fullmatch(r"\s*-?\d+(\.\d+)?([eE]-?\d+)?\s*", value))
    except (TypeError, ValueError):
        return False


# ---- adapters ------------------------------------------------------------------------

_LOG_TIME = re.compile(r"^\s*\[?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?\s*")


def events_from_log(lines: Iterable[str], stream: str = "log") -> list[dict]:
    """Log lines -> events whose type is the Drain-mined template (variable parts removed)."""
    from drain3 import TemplateMiner
    from drain3.template_miner_config import TemplateMinerConfig

    config = TemplateMinerConfig()
    config.profiling_enabled = False
    miner = TemplateMiner(config=config)
    out = []
    for line in lines:
        line = str(line).rstrip()
        if not line.strip():
            continue
        m = _LOG_TIME.match(line)
        ts = m.group(1).replace(",", ".") if m else None
        message = line[m.end():] if m else line
        result = miner.add_log_message(message)
        template = result["template_mined"]
        params = miner.extract_parameters(template, message, exact_matching=False) or []
        numeric = {f"p{i}": float(p.value) for i, p in enumerate(params) if _is_number(p.value)}
        out.append({"event_type": "log:" + normalize_type(template)[:100], "timestamp": ts, "stream": stream,
                    "attributes": {"template": template, "line": line[:500]}, "numeric_features": numeric,
                    "entities": [p.value for p in params if not _is_number(p.value)][:5]})
    return out


def events_from_series(values: Iterable[Any], timestamps: Iterable[Any] | None = None, name: str = "value",
                       stream: str = "series") -> list[dict]:
    times = list(timestamps) if timestamps is not None else None
    out = []
    for i, v in enumerate(values):
        if not _is_number(v):
            continue
        out.append({"event_type": f"measurement:{normalize_type(name)}", "timestamp": times[i] if times and i < len(times) else None,
                    "stream": stream, "numeric_features": {name: float(v)}})
    return out


def events_from_symbols(tokens: Iterable[str], stream: str = "symbols", context: int = 3) -> list[dict]:
    tokens = [str(t) for t in tokens if str(t).strip()]
    out = []
    for i, tok in enumerate(tokens):
        out.append({"event_type": f"symbol:{tok}", "stream": stream,
                    "attributes": {"symbol": tok, "left": tokens[max(0, i - context):i], "right": tokens[i + 1:i + 1 + context],
                                   "position": i}})
    return out
