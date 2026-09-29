"""Symbol recognition and decoding as hypothesis testing.

Unknown symbols (glyphs, hex codes, labels like ZX-4, repeated structural tokens)
are found in text or symbol streams and stored as ``symbol`` events, so the
pattern engine sees them like any other event. For each recurring symbol this
module measures frequency, surrounding context, spacing and what events follow or
precede it, and turns those statistics into *testable* interpretations:

    precedes:<B>     S is (almost) always followed by B       ("S marks the start of B")
    follows:<A>      S is (almost) always preceded by A
    delimiter        S recurs at regular intervals
    alternates:<T>   S and T alternate (S T S T)
    variant_of:<T>   S appears in the same contexts as T

A meaning proposed by a model ("S means initialization") is only stored attached
to one of these predicates, and its status comes from counting supporting cases
and counterexamples - first on the data it was derived from, then on occurrences
that arrive later. Only the later test can make it VERIFIED.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Callable, Iterable

import numpy as np

from .epistemics import ALPHA
from .events import add_events, events_from_symbols
from .store import KnowledgeStore

# Tokens that look like codes rather than words: glyphs, hex, labels with digits, ALLCAPS ids, bracketed markers.
_SYMBOL_PATTERNS = [
    r"0x[0-9A-Fa-f]{2,}",
    r"\b[A-Z]{1,5}-?\d+[A-Za-z]?\b",
    r"\b[A-Z]{2,6}\b",
    r"[\[<{][A-Z0-9_:#-]{1,12}[\]>}]",
    r"[^\w\s.,;:!?'\"()\[\]{}<>/\\@#$%^&*+=|~`\-‐-―←-⇿⟵-⟿]",  # glyphs; arrows/dashes are separators
]
_SYMBOL_RE = re.compile("|".join(f"(?:{p})" for p in _SYMBOL_PATTERNS))
MIN_OCCURRENCES = 5


def extract_symbol_stream(text: str, pattern: str | None = None) -> list[str]:
    """The sequence of symbol-like tokens in ``text`` (or matches of a custom regex)."""
    rx = re.compile(pattern) if pattern else _SYMBOL_RE
    return [m.group(0) for m in rx.finditer(text or "")]


def ingest_symbols(store: KnowledgeStore, project_id: str, *, tokens: Iterable[str] | None = None, text: str = "",
                   pattern: str | None = None, stream: str = "symbols", evidence_ids: Iterable[str] = ()) -> dict:
    seq = list(tokens) if tokens is not None else extract_symbol_stream(text, pattern)
    stored = add_events(store, project_id, events_from_symbols(seq, stream=stream), evidence_ids=evidence_ids, source="symbols")
    return {"symbols_ingested": len(stored), "distinct": len(set(seq)), "stream": stream}


def _binom_p(k: int, n: int, p0: float) -> float:
    from scipy.stats import binomtest

    if n == 0 or p0 >= 1:
        return 1.0
    return float(binomtest(k, n, max(p0, 1e-9), alternative="greater").pvalue)


def _status(support: int, n: int, p_value: float) -> tuple[str, str]:
    if n == 0:
        return "UNRESOLVED", "HYPOTHESIS"
    rate = support / n
    if rate >= 0.9 and p_value < ALPHA and n >= 10:
        return "SUPPORTED", "STATISTICALLY_SUPPORTED"
    if rate >= 0.6:
        return "PARTIALLY_SUPPORTED", "CORRELATED" if p_value < ALPHA else "OBSERVED"
    if n >= 10 and rate < 0.4:
        return "CONTRADICTED", "CONTRADICTED"
    return "UNRESOLVED", "HYPOTHESIS"


class SymbolEngine:
    def __init__(self, store: KnowledgeStore, complete: Callable[[list[dict], int], str] | None = None):
        self.store = store
        self.complete = complete

    # ---- statistics ----------------------------------------------------------------------

    def _streams(self, project_id: str) -> dict[str, list[dict]]:
        streams: dict[str, list[dict]] = defaultdict(list)
        for e in self.store.find(project_id, "event", order="ts", limit=200_000):
            streams[(e.get("data") or {}).get("stream", "default")].append(e)
        return streams

    @staticmethod
    def _symbol_of(event: dict) -> str | None:
        return event["kind"][7:] if event["kind"].startswith("symbol:") else None

    def evaluate(self, predicate: str, symbol: str, streams: dict[str, list[dict]], after_seq: int = 0) -> dict:
        """Count occurrences of ``symbol`` (after event seq ``after_seq``) that satisfy / violate ``predicate``."""
        kind, _, target = predicate.partition(":")
        support = counter = 0
        counterexamples: list[str] = []
        base_hits = base_total = 0
        spacing: list[int] = []
        for events in streams.values():
            last_pos = None
            for i, e in enumerate(events):
                if kind in ("precedes", "follows", "alternates"):
                    base_total += 1
                    if e["kind"] == target:
                        base_hits += 1
                if self._symbol_of(e) != symbol:
                    continue
                if (e.get("data") or {}).get("seq", 0) <= after_seq:
                    last_pos = i
                    continue
                if kind == "precedes":
                    ok = i + 1 < len(events) and events[i + 1]["kind"] == target
                elif kind == "follows":
                    ok = i > 0 and events[i - 1]["kind"] == target
                elif kind == "alternates":
                    ok = (i + 1 < len(events) and events[i + 1]["kind"] == target) or (i > 0 and events[i - 1]["kind"] == target)
                elif kind == "delimiter":
                    ok = None
                    if last_pos is not None:
                        spacing.append(i - last_pos)
                else:
                    ok = None
                last_pos = i
                if ok is True:
                    support += 1
                elif ok is False:
                    counter += 1
                    if len(counterexamples) < 10:
                        counterexamples.append(e["id"])
        if kind == "delimiter":
            n = len(spacing)
            if n < 3:
                return {"n": n, "support": 0, "counterexamples": 0, "p_value": 1.0}
            median = float(np.median(spacing))
            regular = sum(1 for s in spacing if abs(s - median) <= max(1, 0.2 * median))
            # Chance of that regularity under random placement ~ geometric spacing
            p0 = min(0.9, (2 * max(1, 0.2 * median) + 1) / max(2.0, 2 * median))
            return {"n": n, "support": regular, "counterexamples": n - regular, "p_value": _binom_p(regular, n, p0),
                    "median_spacing": median}
        n = support + counter
        base = base_hits / base_total if base_total else 0.0
        return {"n": n, "support": support, "counterexamples": counter, "counterexample_ids": counterexamples,
                "p_value": _binom_p(support, n, base), "base_rate": round(base, 4)}

    def analyze(self, project_id: str, min_occurrences: int = MIN_OCCURRENCES) -> dict:
        """Update every recurring symbol's statistics and (re)test its interpretations."""
        streams = self._streams(project_id)
        occurrences: dict[str, list[tuple[str, int, list[dict]]]] = defaultdict(list)
        for stream, events in streams.items():
            for i, e in enumerate(events):
                sym = self._symbol_of(e)
                if sym is not None:
                    occurrences[sym].append((stream, i, events))
        total_events = sum(len(v) for v in streams.values()) or 1
        context_vectors: dict[str, Counter] = {}
        report = {"symbols": 0, "new_interpretations": [], "updated_interpretations": []}
        for sym, occ in occurrences.items():
            if len(occ) < min_occurrences:
                continue
            report["symbols"] += 1
            nxt, prev, ctx = Counter(), Counter(), Counter()
            for _stream, i, events in occ:
                if i + 1 < len(events):
                    nxt[events[i + 1]["kind"]] += 1
                    ctx["R:" + events[i + 1]["kind"]] += 1
                if i > 0:
                    prev[events[i - 1]["kind"]] += 1
                    ctx["L:" + events[i - 1]["kind"]] += 1
            context_vectors[sym] = ctx  # positional: what sits immediately left / right
            symbol_obj = self._symbol_object(project_id, sym, len(occ), total_events, nxt, prev, occ)
            # Interpretations derived from statistics, each a testable predicate.
            candidates = []
            if nxt:
                target, _ = nxt.most_common(1)[0]
                candidates.append(f"precedes:{target}")
            if prev:
                target, _ = prev.most_common(1)[0]
                candidates.append(f"follows:{target}")
            candidates.append("delimiter")
            for other, c in nxt.items():
                if other.startswith("symbol:") and other[7:] != sym and prev.get(other, 0) >= 0.5 * len(occ) and c >= 0.5 * len(occ):
                    candidates.append(f"alternates:{other}")
            for predicate in candidates:
                self._test(project_id, symbol_obj, sym, predicate, streams, report)
        self._variants(project_id, context_vectors, report)
        return report

    def _symbol_object(self, project_id, sym, count, total_events, nxt, prev, occ) -> dict:
        contexts = [{"left": [e["kind"] for e in events[max(0, i - 2):i]], "right": [e["kind"] for e in events[i + 1:i + 3]]}
                    for _s, i, events in occ[:5]]
        data = {"symbol": sym, "count": count, "frequency": round(count / total_events, 5),
                "next": dict(nxt.most_common(5)), "previous": dict(prev.most_common(5)), "example_contexts": contexts,
                "event_ids": [events[i]["id"] for _s, i, events in occ[:50]]}
        existing = self.store.find_one(project_id, "symbol", sym)
        if existing:
            return self.store.update(existing["id"], "symbol statistics refreshed", data={**existing["data"], **data})
        obj = self.store.add(project_id, "symbol", f"Symbol {sym}", kind=sym, level="OBSERVED", status="OPEN", data=data,
                             body=f"symbol {sym} next {list(nxt)} previous {list(prev)}")
        for _s, i, events in occ[:200]:
            self.store.link(events[i]["id"], "instance_of_symbol", obj["id"])
        return obj

    def _test(self, project_id, symbol_obj, sym, predicate, streams, report) -> None:
        key = f"{sym}|{predicate}"
        existing = self.store.find_one(project_id, "interpretation", key)
        if existing is None:
            result = self.evaluate(predicate, sym, streams)
            status, level = _status(result["support"], result["n"], result["p_value"])
            if status in ("UNRESOLVED", "CONTRADICTED") and result["n"] < 10:
                return  # not worth recording a hypothesis the data barely touches
            max_seq = max((e["data"].get("seq", 0) for evs in streams.values() for e in evs), default=0)
            obj = self.store.add(project_id, "interpretation", f"{sym}: {self._describe(predicate)}", kind=key,
                                 status=status, level=level,
                                 data={"symbol": sym, "predicate": predicate, "meaning": None, "fit": result,
                                       "fitted_through_seq": max_seq, "holdout": None},
                                 links=[("interprets", symbol_obj["id"])])
            self.store.link(symbol_obj["id"], "has_interpretation", obj["id"])
            self._record_verification(project_id, obj, "statistical_test", result, status in ("SUPPORTED",))
            report["new_interpretations"].append(obj["id"])
            return
        # Hold-out test: only occurrences that arrived after the interpretation was fitted.
        data = existing["data"]
        holdout = self.evaluate(predicate, sym, streams, after_seq=int(data.get("fitted_through_seq", 0)))
        if holdout["n"] == 0:
            return
        rate = holdout["support"] / holdout["n"]
        fit_status, _ = _status(data["fit"].get("support", 0), data["fit"].get("n", 0), data["fit"].get("p_value", 1.0))
        if holdout["n"] >= 20 and rate >= 0.9 and holdout["p_value"] < ALPHA / 10 and fit_status == "CONTRADICTED":
            # Holds now but was contradicted on the older data: the behaviour changed; do not call it verified.
            status, level, passed = "PARTIALLY_SUPPORTED", "STATISTICALLY_SUPPORTED", True
            data = {**data, "note": "Contradicted on the data it was fitted to, but holds on newer occurrences: behaviour changed."}
        elif holdout["n"] >= 20 and rate >= 0.9 and holdout["p_value"] < ALPHA / 10:
            status, level, passed = "VERIFIED", "VERIFIED", True
        elif holdout["n"] >= 10 and rate < 0.6:
            status, level, passed = "CONTRADICTED", "CONTRADICTED", False
        else:
            status, level, passed = ("PARTIALLY_SUPPORTED" if rate >= 0.6 else existing["status"]), existing["level"], None
        self.store.update(existing["id"], f"hold-out test on {holdout['n']} new occurrences", status=status, level=level,
                          data={**data, "holdout": holdout})
        if passed is not None:
            self._record_verification(project_id, existing, "prediction_holdout", holdout, passed)
        report["updated_interpretations"].append(existing["id"])

    def _variants(self, project_id, vectors: dict[str, Counter], report) -> None:
        names = sorted(vectors)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = vectors[names[i]], vectors[names[j]]
                keys = set(a) | set(b)
                va = np.array([a.get(k, 0) for k in keys], float)
                vb = np.array([b.get(k, 0) for k in keys], float)
                denom = np.linalg.norm(va) * np.linalg.norm(vb)
                sim = float(va @ vb / denom) if denom else 0.0
                # Variants fill the same slot; symbols that sit next to each other are partners, not variants.
                adjacent = a.get(f"L:symbol:{names[j]}", 0) + a.get(f"R:symbol:{names[j]}", 0)
                if sim >= 0.9 and adjacent == 0:
                    key = f"{names[i]}|variant_of:symbol:{names[j]}"
                    if self.store.find_one(project_id, "interpretation", key):
                        continue
                    sym_obj = self.store.find_one(project_id, "symbol", names[i])
                    obj = self.store.add(project_id, "interpretation", f"{names[i]} and {names[j]} occur in the same contexts",
                                         kind=key, status="PARTIALLY_SUPPORTED", level="CORRELATED",
                                         data={"symbol": names[i], "predicate": f"variant_of:symbol:{names[j]}",
                                               "fit": {"context_cosine": round(sim, 3)}, "meaning": None},
                                         links=[("interprets", sym_obj["id"])] if sym_obj else [])
                    report["new_interpretations"].append(obj["id"])

    def _record_verification(self, project_id, interp, method, result, passed) -> None:
        v = self.store.add(project_id, "verification", f"{method}: {interp['title']}", kind=method, level=None,
                           status="PASSED" if passed else "FAILED",
                           data={"method": method, "passed": bool(passed), "stats": result, "target": interp["id"]},
                           links=[("tests", interp["id"])] + [("counterexample", c) for c in result.get("counterexample_ids", [])])
        self.store.link(interp["id"], "tested_by", v["id"])

    @staticmethod
    def _describe(predicate: str) -> str:
        kind, _, target = predicate.partition(":")
        return {"precedes": f"is followed by {target}", "follows": f"comes right after {target}",
                "delimiter": "recurs at regular intervals (delimiter / period marker)",
                "alternates": f"alternates with {target}"}.get(kind, predicate)

    # ---- meanings ------------------------------------------------------------------------

    def propose_meanings(self, project_id: str, symbol: str) -> list[dict]:
        """Ask the model for human-readable meanings, each bound to an already-tested predicate.

        The meaning inherits the predicate's test status; the model's confidence is not recorded as evidence.
        """
        sym = self.store.find_one(project_id, "symbol", symbol)
        if sym is None or self.complete is None:
            return []
        interps = [i for i in self.store.find(project_id, "interpretation") if i["data"].get("symbol") == symbol]
        if not interps:
            return []
        import json

        from .llm import parse_json as _parse_json

        listing = [{"id": i["id"], "relation": i["title"], "status": i["status"], "fit": i["data"].get("fit")} for i in interps]
        reply = self.complete([
            {"role": "system", "content": "You label statistically tested relations with plausible meanings. Reply with JSON only."},
            {"role": "user", "content": (
                f"Symbol {symbol!r}. Statistics: {json.dumps(sym['data'], default=str)[:2500]}\n"
                f"Tested relations: {json.dumps(listing, default=str)[:2500]}\n"
                'For relations whose status is SUPPORTED, PARTIALLY_SUPPORTED or VERIFIED, propose what the symbol may mean. '
                'Reply [{"id": "<relation id>", "meaning": "<short meaning>", "rationale": "<which statistic suggests it>"}]. '
                "Only use the given ids.")},
        ], 600)
        try:
            items = _parse_json(reply)
        except Exception:
            return []
        updated = []
        valid = {i["id"]: i for i in interps}
        for item in items if isinstance(items, list) else []:
            target = valid.get(str(item.get("id")))
            if target and item.get("meaning"):
                meanings = target["data"].get("meanings") or []
                meanings.append({"meaning": str(item["meaning"])[:200], "rationale": str(item.get("rationale", ""))[:400],
                                 "source": "model proposal - inherits the relation's test status"})
                updated.append(self.store.merge_data(target["id"], "meaning proposed", meanings=meanings, meaning=meanings[0]["meaning"]))
        return updated
