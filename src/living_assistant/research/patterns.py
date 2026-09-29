"""Generic pattern engine over normalized events.

Detectors are plugins: each reads the project's events and proposes patterns (with
the exact events of every occurrence) and findings (deviations, anomalies, changes).
The engine stores them and links pattern <-> occurrence <-> event <-> evidence, so
no pattern exists apart from the events that produced it. Re-running is
idempotent: known patterns gain new occurrences, known findings are not repeated.

Statistics come from established libraries: scipy (binomial, Poisson, KS,
Mann-Whitney, Spearman), scikit-learn (IsolationForest), ruptures (change points),
stumpy (matrix-profile motifs and discords) and networkx (relationship graphs).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from .epistemics import ALPHA
from .store import KnowledgeStore


@dataclass
class PatternCandidate:
    signature: str
    pattern_type: str
    title: str
    occurrences: list[list[str]]          # event ids per occurrence
    stats: dict = field(default_factory=dict)
    level: str = "OBSERVED"
    shape: str = ""                       # abstract structure, comparable across projects


@dataclass
class FindingCandidate:
    finding_type: str
    title: str
    event_ids: list[str]
    pattern_signature: str | None = None
    expected: Any = None
    actual: Any = None
    stats: dict = field(default_factory=dict)
    level: str = "OBSERVED"


class Context:
    def __init__(self, events: list[dict], params: dict | None = None):
        self.events = events
        self.params = params or {}
        self.streams: dict[str, list[dict]] = defaultdict(list)
        for e in events:
            self.streams[(e.get("data") or {}).get("stream", "default")].append(e)

    @staticmethod
    def time_of(event: dict) -> float | None:
        ts = event.get("ts") or ""
        if not ts or ts.startswith("~"):
            return None
        try:
            return datetime.fromisoformat(ts).timestamp()
        except ValueError:
            return None

    def axis(self, events: list[dict]) -> tuple[np.ndarray, bool]:
        """Event positions: real time when every event has one, else sequence order."""
        times = [self.time_of(e) for e in events]
        if events and all(t is not None for t in times):
            return np.array(times, dtype=float), True
        return np.arange(len(events), dtype=float), False

    def numeric_series(self, min_points: int = 20) -> dict[tuple[str, str], tuple[np.ndarray, list[str]]]:
        """(event type, feature) -> (values in event order, event ids)."""
        series: dict[tuple[str, str], tuple[list, list]] = defaultdict(lambda: ([], []))
        for e in self.events:
            for name, value in ((e.get("data") or {}).get("numeric_features") or {}).items():
                if isinstance(value, (int, float)) and math.isfinite(value):
                    vals, ids = series[(e["kind"], name)]
                    vals.append(float(value))
                    ids.append(e["id"])
        return {k: (np.array(v), ids) for k, (v, ids) in series.items() if len(v) >= min_points}


def shape_of(sequence) -> str:
    """Abstract form of a sequence: ('init','load','init') -> 'A>B>A'."""
    names: dict[Any, str] = {}
    return ">".join(names.setdefault(x, chr(65 + len(names) % 26)) for x in sequence)


class Detector:
    name = "detector"

    def detect(self, ctx: Context) -> list:  # pragma: no cover - interface
        raise NotImplementedError


class SequenceDetector(Detector):
    """Repeated event sequences, and the ways new data departs from them."""
    name = "sequence"

    def __init__(self, max_n: int = 4, min_support: int = 3, min_confidence: float = 0.8, max_patterns: int = 60):
        self.max_n, self.min_support, self.min_confidence, self.max_patterns = max_n, min_support, min_confidence, max_patterns

    def detect(self, ctx: Context) -> list:
        from scipy.stats import binomtest

        out: list = []
        for stream, events in ctx.streams.items():
            kinds = [e["kind"] for e in events]
            ids = [e["id"] for e in events]
            total = len(kinds)
            if total < self.min_support * 2:
                continue
            freq = Counter(kinds)
            deviations: dict[int, FindingCandidate] = {}  # one per deviating event, with the longest context
            for n in range(2, self.max_n + 1):
                grams: dict[tuple, list[int]] = defaultdict(list)
                for i in range(total - n + 1):
                    grams[tuple(kinds[i:i + n])].append(i)
                following: dict[tuple, Counter] = defaultdict(Counter)
                for g, pos in grams.items():
                    following[g[:-1]][g[-1]] += len(pos)
                ranked = sorted((g for g, p in grams.items() if len(p) >= self.min_support),
                                key=lambda g: -len(grams[g]))[: self.max_patterns]
                for g in ranked:
                    if len(set(g)) == 1:
                        continue  # "A A A" is a frequency effect, not an ordering
                    pos = grams[g]
                    prefix_total = sum(following[g[:-1]].values())
                    confidence = len(pos) / prefix_total
                    base = freq[g[-1]] / total
                    p = binomtest(len(pos), prefix_total, base, alternative="greater").pvalue if base < 1 else 1.0
                    if confidence < self.min_confidence and p >= ALPHA:
                        continue
                    sig = f"seq:{stream}:{'>'.join(g)}"
                    stats = {"support": len(pos), "confidence": round(confidence, 3), "p_value": float(p),
                             "base_rate": round(base, 4), "length": n, "stream": stream, "sequence": list(g)}
                    out.append(PatternCandidate(sig, "sequence", " → ".join(g), [ids[i:i + n] for i in pos], stats,
                                                "STATISTICALLY_SUPPORTED" if p < ALPHA else "OBSERVED", shape_of(g)))
                    if confidence < self.min_confidence:
                        continue
                    # A→B→X where A→B→C is the rule: X is rare after this prefix.
                    for actual, count in following[g[:-1]].items():
                        if actual == g[-1] or count >= self.min_support:
                            continue
                        for i in grams[g[:-1] + (actual,)]:
                            deviant = i + n - 1
                            if deviant in deviations and len(deviations[deviant].event_ids) >= n:
                                continue
                            deviations[deviant] = FindingCandidate(
                                "SEQUENCE_DEVIATION", f"{' → '.join(g[:-1])} → {actual}, expected {g[-1]}",
                                ids[i:i + n], sig, expected=g[-1], actual=actual,
                                stats={"pattern_support": len(pos), "pattern_confidence": round(confidence, 3),
                                       "deviation_count": count})
                    reverse = g[::-1]
                    if reverse != g and 0 < len(grams.get(reverse, [])) < self.min_support:
                        for i in grams[reverse]:
                            out.append(FindingCandidate("REVERSED_PATTERN", f"{' → '.join(reverse)} (reverse of {' → '.join(g)})",
                                                        ids[i:i + n], sig, expected=list(g), actual=list(reverse)))
                    # Where in the stream the pattern lives: only early (disappeared) or only late (emerging).
                    if total >= 30 and len(pos) >= self.min_support:
                        early, late = total * 2 / 3, total / 3
                        if max(pos) < early and sum(1 for k in kinds[int(early):] if k == g[0]) >= self.min_support:
                            out.append(FindingCandidate("PATTERN_DISAPPEARED", f"{' → '.join(g)} stopped occurring",
                                                        ids[pos[-1]:pos[-1] + n], sig, expected="continues", actual="absent in last third",
                                                        stats={"last_position": pos[-1], "events": total}))
                        elif min(pos) >= late:
                            out.append(FindingCandidate("PATTERN_EMERGING", f"{' → '.join(g)} appeared recently",
                                                        ids[pos[0]:pos[0] + n], sig, expected="absent", actual="new",
                                                        stats={"first_position": pos[0], "events": total}))
            out.extend(deviations.values())
        return out


class TemporalDetector(Detector):
    """Unusual gaps between events that normally follow each other, and expected events that never came."""
    name = "temporal"

    def __init__(self, min_samples: int = 8, z: float = 5.0, min_confidence: float = 0.9):
        self.min_samples, self.z, self.min_confidence = min_samples, z, min_confidence

    def detect(self, ctx: Context) -> list:
        out: list = []
        for stream, events in ctx.streams.items():
            t, timed = ctx.axis(events)
            if not timed or len(events) < self.min_samples * 2:
                continue
            gaps: dict[tuple, list[tuple[float, int]]] = defaultdict(list)
            after: dict[str, Counter] = defaultdict(Counter)
            for i in range(len(events) - 1):
                pair = (events[i]["kind"], events[i + 1]["kind"])
                gaps[pair].append((t[i + 1] - t[i], i))
                after[pair[0]][pair[1]] += 1
            for (a, b), samples in gaps.items():
                if len(samples) < self.min_samples:
                    continue
                values = np.array([g for g, _ in samples])
                med = float(np.median(values))
                mad = float(np.median(np.abs(values - med))) or (float(np.std(values)) or 1e-9)
                for gap, i in samples:
                    rz = 0.6745 * (gap - med) / mad
                    if abs(rz) > self.z:
                        out.append(FindingCandidate(
                            "UNUSUAL_TIMING", f"{a} → {b} took {gap:.3g}s (typical {med:.3g}s)",
                            [events[i]["id"], events[i + 1]["id"]], f"seq:{stream}:{a}>{b}", expected=med, actual=gap,
                            stats={"robust_z": round(rz, 2), "samples": len(samples)}))
                confidence = after[a][b] / sum(after[a].values())
                if confidence >= self.min_confidence:
                    last_a = max(i for i, e in enumerate(events) if e["kind"] == a)
                    waited = t[-1] - t[last_a]
                    if last_a < len(events) - 1 and events[last_a + 1]["kind"] != b and waited > values.max() * 3:
                        out.append(FindingCandidate(
                            "MISSING_EXPECTED", f"{a} was not followed by {b} (usually {confidence:.0%} of the time)",
                            [events[last_a]["id"]], f"seq:{stream}:{a}>{b}", expected=b, actual=events[last_a + 1]["kind"],
                            stats={"confidence": round(confidence, 3), "waited_s": waited, "max_normal_gap_s": float(values.max())}))
        return out


class FrequencyDetector(Detector):
    """Event types occurring unusually often/rarely in a window, newly appearing, or vanishing."""
    name = "frequency"

    def detect(self, ctx: Context) -> list:
        from scipy.stats import binomtest, poisson

        out: list = []
        events = sorted(ctx.events, key=lambda e: (e.get("ts") or ""))
        if len(events) < 40:
            return out
        t, timed = ctx.axis(events)
        bins = int(min(30, max(6, len(events) // 20)))
        edges = np.linspace(t.min(), t.max() + 1e-9, bins + 1)
        totals, _ = np.histogram(t, bins=edges)
        warmup = max(3, bins // 3)
        cut = ALPHA / bins  # Bonferroni over windows

        def ids_in(b: int, idx: list[int] | None = None) -> list[str]:
            pool = idx if idx is not None else range(len(events))
            return [events[i]["id"] for i in pool if edges[b] <= t[i] < edges[b + 1]][:20]

        # Overall activity: bursts and silences of everything (only meaningful on a real time axis).
        if timed:
            for b in range(warmup, bins):
                mu, c = totals[:b].mean(), int(totals[b])
                if mu > 0 and c >= 3 and poisson.sf(c - 1, mu) < cut:
                    out.append(FindingCandidate("UNUSUAL_FREQUENCY", f"burst: {c} events in one window (normal {mu:.1f})",
                                                ids_in(b), None, expected=round(float(mu), 2), actual=c,
                                                stats={"window": b, "scope": "all events", "direction": "high"}))
                elif mu >= 5 and poisson.cdf(c, mu) < cut:
                    before = [events[i]["id"] for i in range(len(events)) if t[i] < edges[b]][-1:]
                    out.append(FindingCandidate("UNUSUAL_FREQUENCY", f"silence: {c} events in one window (normal {mu:.1f})",
                                                before, None, expected=round(float(mu), 2), actual=c,
                                                stats={"window": b, "scope": "all events", "direction": "low"}))

        # Each event type: its share of the window's events, so a global lull is not blamed on every type.
        by_kind: dict[str, list[int]] = defaultdict(list)
        for i, e in enumerate(events):
            by_kind[e["kind"]].append(i)
        for kind, idx in by_kind.items():
            if len(idx) < 10:
                continue
            counts, _ = np.histogram(t[idx], bins=edges)
            for b in range(warmup, bins):
                n_bin, c = int(totals[b]), int(counts[b])
                base_total = totals[:b].sum()
                if n_bin < 5 or base_total == 0:
                    continue
                share = counts[:b].sum() / base_total
                if share <= 0 or share >= 1:
                    continue
                high = binomtest(c, n_bin, share, alternative="greater").pvalue
                low = binomtest(c, n_bin, share, alternative="less").pvalue
                if high < cut and c >= 3:
                    out.append(FindingCandidate("UNUSUAL_FREQUENCY", f"{kind}: {c} of {n_bin} events in one window (normal share {share:.0%})",
                                                ids_in(b, idx), None, expected=round(float(share * n_bin), 2), actual=c,
                                                stats={"window": b, "direction": "high", "p_value": float(high)}))
                elif low < cut:
                    out.append(FindingCandidate("UNUSUAL_FREQUENCY", f"{kind}: only {c} of {n_bin} events in one window (normal share {share:.0%})",
                                                ids_in(b) or [events[idx[-1]]["id"]], None, expected=round(float(share * n_bin), 2), actual=c,
                                                stats={"window": b, "direction": "low", "p_value": float(low)}))
            third = bins // 3
            if counts[: bins // 2].sum() == 0 and counts[bins // 2:].sum() >= 5:
                out.append(FindingCandidate("EMERGING_EVENT", f"{kind} started occurring", [events[i]["id"] for i in idx[:5]],
                                            None, expected=0, actual=int(counts.sum())))
            if (counts[: bins - third] > 0).mean() >= 0.5 and counts[bins - third:].sum() == 0:
                out.append(FindingCandidate("DISAPPEARING_EVENT", f"{kind} stopped occurring", [events[idx[-1]]["id"]],
                                            None, expected=round(float(counts[: bins - third].mean()), 2), actual=0))
        return out


class CombinationDetector(Detector):
    """Event types that are each common but almost never occur together - and pairs that reliably do."""
    name = "combination"

    def __init__(self, window: int = 10, min_support: int = 3):
        self.window, self.min_support = window, min_support

    def detect(self, ctx: Context) -> list:
        out: list = []
        events = sorted(ctx.events, key=lambda e: (e.get("ts") or ""))
        if len(events) < self.window * 6:
            return out
        windows = [events[i:i + self.window] for i in range(0, len(events), self.window)]
        sets = [set(e["kind"] for e in w) for w in windows]
        W = len(sets)
        present = Counter(k for s in sets for k in s)
        pair_windows: dict[tuple, list[int]] = defaultdict(list)
        for wi, s in enumerate(sets):
            ks = sorted(s)
            for i in range(len(ks)):
                for j in range(i + 1, len(ks)):
                    pair_windows[(ks[i], ks[j])].append(wi)
        common = [k for k, c in present.items() if c / W >= 0.2]
        for i in range(len(common)):
            for j in range(i + 1, len(common)):
                a, b = sorted((common[i], common[j]))
                expected = present[a] / W * present[b] / W * W
                seen = pair_windows.get((a, b), [])
                lift = len(seen) / expected if expected else 0.0
                if expected >= 3 and 0 < len(seen) <= max(1, int(expected * 0.1)):
                    for wi in seen:
                        ids = [e["id"] for e in windows[wi] if e["kind"] in (a, b)]
                        out.append(FindingCandidate("UNUSUAL_COMBINATION", f"{a} together with {b} (each normal, rarely together)",
                                                    ids, None, expected=round(expected, 2), actual=len(seen),
                                                    stats={"lift": round(lift, 3), "windows": W}))
                elif len(seen) >= self.min_support and lift >= 2.0:
                    occ = [[e["id"] for e in windows[wi] if e["kind"] in (a, b)] for wi in seen]
                    out.append(PatternCandidate(f"cooc:{a}|{b}", "co_occurrence", f"{a} with {b}", occ,
                                                {"together": len(seen), "expected": round(expected, 2), "lift": round(lift, 2)},
                                                "CORRELATED", "A+B"))
        return out


class GraphDetector(Detector):
    """Relationships between entities (co-occurring in events), and relationships that appear or vanish."""
    name = "graph"

    def __init__(self, min_weight: int = 3):
        self.min_weight = min_weight

    def detect(self, ctx: Context) -> list:
        import networkx as nx

        out: list = []
        events = sorted(ctx.events, key=lambda e: (e.get("ts") or ""))
        with_entities = [e for e in events if len((e.get("data") or {}).get("entities") or []) >= 2]
        if len(with_entities) < self.min_weight * 2:
            return out
        half = len(with_entities) // 2
        graphs = [nx.Graph(), nx.Graph()]
        edge_events: dict[tuple, list[str]] = defaultdict(list)
        for k, e in enumerate(with_entities):
            ents = sorted(set(e["data"]["entities"]))[:8]
            g = graphs[0 if k < half else 1]
            for i in range(len(ents)):
                for j in range(i + 1, len(ents)):
                    u, v = ents[i], ents[j]
                    g.add_edge(u, v, weight=g.get_edge_data(u, v, {"weight": 0})["weight"] + 1)
                    edge_events[(u, v)].append(e["id"])
        early, late = graphs
        for (u, v), ids in edge_events.items():
            w1 = early.get_edge_data(u, v, {"weight": 0})["weight"]
            w2 = late.get_edge_data(u, v, {"weight": 0})["weight"]
            if w1 + w2 >= self.min_weight:
                out.append(PatternCandidate(f"rel:{u}|{v}", "relationship", f"{u} ↔ {v}", [ids],
                                            {"weight": w1 + w2, "entities": [u, v]}, "CORRELATED", "A-B"))
            if w1 == 0 and w2 >= self.min_weight and early.has_node(u) and early.has_node(v):
                out.append(FindingCandidate("RELATIONSHIP_APPEARED", f"{u} and {v} started appearing together",
                                            ids[:10], f"rel:{u}|{v}", expected=0, actual=w2))
            if w1 >= self.min_weight and w2 == 0 and late.has_node(u) and late.has_node(v):
                out.append(FindingCandidate("RELATIONSHIP_DISAPPEARED", f"{u} and {v} no longer appear together",
                                            ids[-5:], f"rel:{u}|{v}", expected=w1, actual=0))
        return out


class ChangePointDetector(Detector):
    """Points where a numeric feature's level shifts (ruptures PELT, confirmed by Mann-Whitney)."""
    name = "change_point"

    def detect(self, ctx: Context) -> list:
        import ruptures as rpt
        from scipy.stats import mannwhitneyu

        out: list = []
        for (kind, feat), (values, ids) in ctx.numeric_series(30).items():
            std = values.std()
            if std == 0:
                continue
            z = (values - values.mean()) / std
            try:
                points = rpt.Pelt(model="l2", min_size=5).fit(z).predict(pen=3 * math.log(len(z)))[:-1]
            except Exception:
                continue
            for cp in points:
                before, after_ = values[max(0, cp - 50):cp], values[cp:cp + 50]
                if len(before) < 5 or len(after_) < 5:
                    continue
                p = mannwhitneyu(before, after_).pvalue
                if p < ALPHA:
                    out.append(FindingCandidate(
                        "CHANGE_POINT", f"{kind}.{feat} shifted from {before.mean():.4g} to {after_.mean():.4g}",
                        ids[max(0, cp - 2):cp + 2], None, expected=float(before.mean()), actual=float(after_.mean()),
                        stats={"index": int(cp), "p_value": float(p), "feature": feat}, level="STATISTICALLY_SUPPORTED"))
        return out


class DriftDetector(Detector):
    """Distribution shift between the older and the most recent values (two-sample KS test)."""
    name = "drift"

    def detect(self, ctx: Context) -> list:
        from scipy.stats import ks_2samp

        out: list = []
        for (kind, feat), (values, ids) in ctx.numeric_series(40).items():
            ref, recent = values[: len(values) // 2], values[-len(values) // 4:]
            result = ks_2samp(ref, recent)
            if result.pvalue < ALPHA:
                out.append(FindingCandidate(
                    "DISTRIBUTION_DRIFT", f"{kind}.{feat} distribution drifted (KS={result.statistic:.2f})",
                    ids[-len(values) // 4:][:10], None, expected=float(np.median(ref)), actual=float(np.median(recent)),
                    stats={"ks": float(result.statistic), "p_value": float(result.pvalue), "feature": feat},
                    level="STATISTICALLY_SUPPORTED"))
        return out


class AnomalyDetector(Detector):
    """Events whose numeric features are jointly unusual (IsolationForest) and extreme on some feature."""
    name = "anomaly"

    def detect(self, ctx: Context) -> list:
        from sklearn.ensemble import IsolationForest

        out: list = []
        by_kind: dict[str, list[dict]] = defaultdict(list)
        for e in ctx.events:
            if (e.get("data") or {}).get("numeric_features"):
                by_kind[e["kind"]].append(e)
        for kind, events in by_kind.items():
            if len(events) < 30:
                continue
            feats = Counter(f for e in events for f in e["data"]["numeric_features"])
            names = [f for f, c in feats.items() if c >= 0.8 * len(events)]
            if not names:
                continue
            X = np.array([[e["data"]["numeric_features"].get(f, np.nan) for f in names] for e in events], dtype=float)
            X = np.where(np.isnan(X), np.nanmedian(X, axis=0), X)
            scores = IsolationForest(random_state=0, contamination="auto").fit(X).score_samples(X)
            med = np.median(X, axis=0)
            mad = np.median(np.abs(X - med), axis=0)
            mad[mad == 0] = X.std(axis=0)[mad == 0] + 1e-9
            rz = 0.6745 * (X - med) / mad
            cutoff = np.quantile(scores, 0.01)
            for i in np.where(scores <= cutoff)[0]:
                j = int(np.argmax(np.abs(rz[i])))
                if abs(rz[i, j]) > 3.5:
                    out.append(FindingCandidate(
                        "POINT_ANOMALY", f"{kind}: unusual {names[j]}={X[i, j]:.4g} (typical {med[j]:.4g})",
                        [events[i]["id"]], None, expected=float(med[j]), actual=float(X[i, j]),
                        stats={"feature": names[j], "robust_z": round(float(rz[i, j]), 2), "isolation_score": float(scores[i])}))
        return out


class MotifDetector(Detector):
    """Repeated shapes (motifs) and one-off shapes (discords) in numeric series (stumpy matrix profile)."""
    name = "motif"

    def detect(self, ctx: Context) -> list:
        import stumpy

        out: list = []
        for (kind, feat), (values, ids) in ctx.numeric_series(48).items():
            if values.std() == 0:
                continue
            m = int(max(4, min(32, len(values) // 8)))
            try:
                mp = stumpy.stump(values, m)
            except Exception:
                continue
            profile = mp[:, 0].astype(float)
            try:
                _dist, idx = stumpy.motifs(values, profile, max_motifs=2, max_matches=10)
            except Exception:
                idx = []
            for k, group in enumerate(idx):
                starts = sorted(int(s) for s in group if s >= 0)
                if len(starts) >= 2:
                    out.append(PatternCandidate(
                        f"motif:{kind}.{feat}:{m}:{starts[0]}", "numeric_motif", f"{kind}.{feat}: shape of length {m} repeats {len(starts)}x",
                        [ids[s:s + m] for s in starts], {"window": m, "starts": starts, "feature": feat}, "OBSERVED", f"motif{m}"))
            finite = profile[np.isfinite(profile)]
            if finite.size and finite.std() > 0:
                d = int(np.nanargmax(profile))
                zscore = (profile[d] - finite.mean()) / finite.std()
                if zscore > 3:
                    out.append(FindingCandidate("DISCORD", f"{kind}.{feat}: a shape seen nowhere else", ids[d:d + m], None,
                                                stats={"window": m, "start": d, "z": round(float(zscore), 2), "feature": feat}))
        return out


class CorrelationDetector(Detector):
    """Numeric features that move together within an event type (Spearman, significance-tested)."""
    name = "correlation"

    def detect(self, ctx: Context) -> list:
        from scipy.stats import spearmanr

        out: list = []
        by_kind: dict[str, list[dict]] = defaultdict(list)
        for e in ctx.events:
            if len((e.get("data") or {}).get("numeric_features") or {}) >= 2:
                by_kind[e["kind"]].append(e)
        for kind, events in by_kind.items():
            if len(events) < 20:
                continue
            names = sorted({f for e in events for f in e["data"]["numeric_features"]})
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    rows = [(e["data"]["numeric_features"][names[i]], e["data"]["numeric_features"][names[j]], e["id"])
                            for e in events if names[i] in e["data"]["numeric_features"] and names[j] in e["data"]["numeric_features"]]
                    if len(rows) < 20:
                        continue
                    a, b, ids = zip(*rows)
                    if np.std(a) == 0 or np.std(b) == 0:
                        continue
                    rho, p = spearmanr(a, b)
                    if p < ALPHA and abs(rho) >= 0.5:
                        out.append(PatternCandidate(
                            f"corr:{kind}:{names[i]}|{names[j]}", "correlation",
                            f"{kind}: {names[i]} {'rises' if rho > 0 else 'falls'} with {names[j]} (rho={rho:.2f})",
                            [list(ids)], {"rho": float(rho), "p_value": float(p), "n": len(rows)}, "CORRELATED", "corr"))
        return out


DEFAULT_DETECTORS = (SequenceDetector, TemporalDetector, FrequencyDetector, CombinationDetector, GraphDetector,
                     ChangePointDetector, DriftDetector, AnomalyDetector, MotifDetector, CorrelationDetector)


class PatternEngine:
    def __init__(self, store: KnowledgeStore, detectors: list[Detector] | None = None):
        self.store = store
        self.detectors = detectors if detectors is not None else [cls() for cls in DEFAULT_DETECTORS]

    def register(self, detector: Detector) -> None:
        self.detectors.append(detector)

    def run(self, project_id: str, only: list[str] | None = None) -> dict:
        events = self.store.find(project_id, "event", order="ts", limit=200_000)
        ctx = Context(events)
        summary = {"events": len(events), "new_patterns": [], "updated_patterns": [], "new_findings": [], "errors": {}}
        candidates: list = []
        for det in self.detectors:
            if only and det.name not in only:
                continue
            try:
                candidates.extend(det.detect(ctx))
            except Exception as exc:  # one broken detector must not stop the others
                summary["errors"][det.name] = str(exc)[:300]
        pattern_ids: dict[str, str] = {}
        for c in candidates:
            if isinstance(c, PatternCandidate):
                pid, created = self._store_pattern(project_id, c)
                pattern_ids[c.signature] = pid
                summary["new_patterns" if created else "updated_patterns"].append(pid)
        for c in candidates:
            if isinstance(c, FindingCandidate):
                fid = self._store_finding(project_id, c, pattern_ids)
                if fid:
                    summary["new_findings"].append(fid)
        summary["updated_patterns"] = sorted(set(summary["updated_patterns"]) - set(summary["new_patterns"]))
        return summary

    def _store_pattern(self, project_id: str, c: PatternCandidate) -> tuple[str, bool]:
        s = self.store
        existing = s.find_one(project_id, "pattern", c.signature)
        data = {"pattern_type": c.pattern_type, "stats": c.stats, "shape": c.shape, "occurrence_count": len(c.occurrences)}
        if existing:
            s.update(existing["id"], "detector re-run", level=c.level, data={**existing["data"], **data})
            pid, created = existing["id"], False
        else:
            pid = s.add(project_id, "pattern", c.title, kind=c.signature, level=c.level, status="ACTIVE", data=data,
                        body=f"{c.pattern_type} {c.title} {c.shape}")["id"]
            created = True
        for occ in c.occurrences:
            if not occ:
                continue
            key = f"{c.signature}@{occ[0]}"
            if s.find_one(project_id, "occurrence", key):
                continue
            o = s.add(project_id, "occurrence", f"{c.title} @ {occ[0]}", kind=key, data={"event_ids": occ},
                      links=[("instance_of", pid)] + [("includes", e) for e in occ])
            s.link(pid, "has_occurrence", o["id"])
            for e in occ:
                s.link(e, "part_of", pid)
        return pid, created

    def _store_finding(self, project_id: str, c: FindingCandidate, pattern_ids: dict[str, str]) -> str | None:
        s = self.store
        key = f"{c.finding_type}:{','.join(c.event_ids[:12])}"
        if s.find_one(project_id, "finding", key):
            return None
        evidence = sorted({l["dst"] for e in c.event_ids for l in s.links_from(e, "evidenced_by")})
        pattern_id = pattern_ids.get(c.pattern_signature or "") or (
            (s.find_one(project_id, "pattern", c.pattern_signature) or {}).get("id") if c.pattern_signature else None)
        links = [("involves", e) for e in c.event_ids] + [("supported_by", ev) for ev in evidence]
        if pattern_id:
            links.append(("about", pattern_id))
        f = s.add(project_id, "finding", c.title, kind=key, status="OPEN", level=c.level,
                  data={"finding_type": c.finding_type, "expected": c.expected, "actual": c.actual, "stats": c.stats,
                        "pattern_id": pattern_id, "event_ids": c.event_ids, "evidence_ids": evidence}, links=links)
        if pattern_id:
            s.link(pattern_id, "has_finding", f["id"])
        return f["id"]
