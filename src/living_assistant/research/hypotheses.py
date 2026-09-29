"""Hypotheses with testable predictions, and the verifications that decide them.

A hypothesis stores a statement plus a ``prediction`` the system can check:

    {"type": "sequence",    "after": ["a", "b"], "expect": "c"}
    {"type": "correlation", "event_type": "...", "x": "...", "y": "...", "direction": "positive"|"negative"}
    {"type": "benchmark",   "metric": "...", "better": "higher"|"lower", "candidate": "...", "baseline": "...", "dataset": "..."}
    {"type": "sources"}                                  # decided by independent sources for/against
    {"type": "formal",      "lhs": "...", "rhs": "..."}  # identity checked symbolically (sympy)
    {"type": "experiment",  "experiment_id": "X-3", "metric": "...", "op": ">=", "value": 2.0}

Each check is stored as a Verification (method, passed, statistics, what it used),
and the hypothesis' status/level is recomputed by ``epistemics.assess`` from all of
them. Hypotheses that fail stay in the project as CONTRADICTED knowledge.
"""
from __future__ import annotations

import json
import math
import random
import re
from collections import defaultdict

import numpy as np

from .epistemics import ALPHA, MIN_INDEPENDENT_SOURCES, assess, project_status
from .llm import Complete, ask_json
from .store import KnowledgeStore

PREDICTION_TYPES = ("sequence", "correlation", "benchmark", "sources", "formal", "experiment")


def add_hypothesis(store: KnowledgeStore, project_id: str, statement: str, prediction: dict | None = None, *,
                   core: bool = False, origin: str = "user", links: list[tuple[str, str]] = ()) -> dict:
    prediction = dict(prediction or {})
    if prediction and prediction.get("type") not in PREDICTION_TYPES:
        raise ValueError(f"prediction.type must be one of {PREDICTION_TYPES}")
    key = re.sub(r"\s+", " ", statement.strip().lower())[:300]
    existing = store.find_one(project_id, "hypothesis", key)
    if existing:
        return existing
    seq_now = store.count(project_id).get("event", 0)
    h = store.add(project_id, "hypothesis", statement.strip()[:500], kind=key,
                  status="OPEN" if prediction else "UNRESOLVED", level="HYPOTHESIS",
                  data={"prediction": prediction, "core": bool(core), "origin": origin, "fitted_through_seq": seq_now,
                        "testable": bool(prediction)},
                  links=list(links), body=f"{statement} {json.dumps(prediction)}")
    for rel, dst in links:
        store.link(dst, "suggests", h["id"])
    return h


def generate_from_patterns(store: KnowledgeStore, project_id: str, pattern_ids: list[str], finding_ids: list[str]) -> dict:
    """Mechanical hypotheses from strong patterns, and research questions from findings."""
    made, questions = [], []
    for pid in pattern_ids:
        p = store.get(pid)
        if not p:
            continue
        stats = p["data"].get("stats", {})
        if p["data"].get("pattern_type") == "sequence" and stats.get("confidence", 0) >= 0.8 and stats.get("support", 0) >= 5:
            seq = stats["sequence"]
            h = add_hypothesis(store, project_id, f"After {' → '.join(seq[:-1])}, {seq[-1]} follows",
                               {"type": "sequence", "after": seq[:-1], "expect": seq[-1], "stream": stats.get("stream")},
                               origin="pattern", links=[("derived_from", pid)])
            made.append(h["id"])
        elif p["data"].get("pattern_type") == "correlation":
            et, pair = p["kind"].split(":", 2)[1:]
            x, y = pair.split("|")
            h = add_hypothesis(store, project_id, p["title"],
                               {"type": "correlation", "event_type": et, "x": x, "y": y,
                                "direction": "positive" if stats.get("rho", 0) > 0 else "negative"},
                               origin="pattern", links=[("derived_from", pid)])
            made.append(h["id"])
    templates = {
        "SEQUENCE_DEVIATION": "Why did {actual} occur where {expected} was expected? ({title})",
        "CHANGE_POINT": "What caused this change: {title}?",
        "DISTRIBUTION_DRIFT": "What caused this drift: {title}?",
        "CONTRADICTION": "Which is right, and in what scope? {title}",
        "MISSING_EXPECTED": "Why was the expected event missing? {title}",
        "RELATIONSHIP_APPEARED": "Why did this relationship appear? {title}",
        "RELATIONSHIP_DISAPPEARED": "Why did this relationship disappear? {title}",
        "UNUSUAL_COMBINATION": "Is this combination meaningful? {title}",
    }
    for fid in finding_ids:
        f = store.get(fid)
        if not f:
            continue
        template = templates.get(f["data"].get("finding_type"))
        if template:
            q = add_question(store, project_id, template.format(title=f["title"], actual=f["data"].get("actual"),
                                                                expected=f["data"].get("expected")), origin=fid)
            questions.append(q["id"])
    return {"hypotheses": made, "questions": questions}


def add_question(store: KnowledgeStore, project_id: str, text: str, origin: str | None = None, priority: int = 5) -> dict:
    key = re.sub(r"\s+", " ", text.strip().lower())[:300]
    existing = store.find_one(project_id, "question", key)
    if existing:
        return existing
    links = [("raised_by", origin)] if origin else []
    return store.add(project_id, "question", text.strip()[:500], kind=key, status="OPEN",
                     data={"origin": origin, "priority": priority}, links=links)


def generate_from_claims(store: KnowledgeStore, project_id: str, claim_ids: list[str], complete: Complete,
                         topic: str = "") -> list[str]:
    """Model-proposed hypotheses, accepted only in a testable form (or kept as UNRESOLVED ideas)."""
    claims = [store.get(c) for c in claim_ids[:20]]
    claims = [c for c in claims if c]
    if not claims:
        return []
    try:
        items = ask_json(complete, "You propose testable research hypotheses. Reply with JSON only.", (
            f"Project topic: {topic}\nClaims found so far:\n"
            + "\n".join(f"- [{c['id']}] {c['title']}" for c in claims)
            + "\n\nPropose up to 3 hypotheses that would advance the research. Each must be checkable by one of:\n"
            '  {"type": "sources"} (independent sources can confirm or refute it)\n'
            '  {"type": "benchmark", "metric": "...", "better": "higher|lower", "candidate": "...", "baseline": "...", "dataset": "..."}\n'
            '  {"type": "formal", "lhs": "<sympy expression>", "rhs": "<sympy expression>"}\n'
            'Reply [{"statement": "...", "prediction": {...}, "based_on": ["<claim id>"]}].'), 1200)
    except Exception:
        return []
    made = []
    valid = {c["id"] for c in claims}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not item.get("statement"):
            continue
        prediction = item.get("prediction") if isinstance(item.get("prediction"), dict) else {}
        if prediction.get("type") not in ("sources", "benchmark", "formal"):
            prediction = {}
        h = add_hypothesis(store, project_id, str(item["statement"]), prediction, origin="model",
                           links=[("based_on", c) for c in item.get("based_on") or [] if c in valid])
        made.append(h["id"])
    return made


# ---- verification -----------------------------------------------------------------------

class Verifier:
    def __init__(self, store: KnowledgeStore, complete: Complete | None = None):
        self.store = store
        self.complete = complete

    def verify(self, hypothesis_id: str) -> dict:
        h = self.store.get(hypothesis_id)
        if h is None or h["type"] != "hypothesis":
            return {"ok": False, "error": f"{hypothesis_id} is not a hypothesis."}
        prediction = h["data"].get("prediction") or {}
        kind = prediction.get("type")
        if not kind:
            return {"ok": False, "hypothesis": hypothesis_id, "error": "No testable prediction; it stays UNRESOLVED."}
        handler = getattr(self, f"_verify_{kind}", None)
        result = handler(h, prediction) if handler else None
        if result is not None:
            self._record(h, result)
        return {"ok": True, **self.reassess(hypothesis_id), "verification": result}

    def reassess(self, hypothesis_id: str) -> dict:
        h = self.store.get(hypothesis_id)
        verifications = [self.store.get(l["dst"]) for l in self.store.links_from(hypothesis_id, "tested_by")]
        records = [{"method": v["data"]["method"], "passed": v["data"]["passed"]} for v in verifications if v]
        supporting = len(self.store.links_from(hypothesis_id, "supported_by"))
        contradicting = len(self.store.links_from(hypothesis_id, "contradicted_by"))
        status, level, reason = assess(records, supporting, contradicting)
        self.store.update(hypothesis_id, reason, status=status, level=level)
        self.store.merge_data(hypothesis_id, "assessment", assessment=reason)
        project = self.store.get_project(h["project_id"])
        hyps = self.store.find(h["project_id"], "hypothesis", limit=10_000)
        new_status = project_status(project["status"], project["kind"], hyps)
        if new_status != project["status"]:
            self.store.update_project(project["id"], f"after assessing {hypothesis_id}", status=new_status)
        return {"hypothesis": hypothesis_id, "status": status, "level": level, "reason": reason, "project_status": new_status}

    def _record(self, h: dict, result: dict) -> dict:
        v = self.store.add(h["project_id"], "verification", f"{result['method']}: {h['title'][:150]}", kind=result["method"],
                           status="PASSED" if result["passed"] else "FAILED" if result["passed"] is False else "INCONCLUSIVE",
                           data={**result, "target": h["id"]},
                           links=[("tests", h["id"])] + [("used", u) for u in result.get("used", [])[:200]]
                           + [("counterexample", c) for c in result.get("counterexample_ids", [])[:50]])
        self.store.link(h["id"], "tested_by", v["id"])
        return v

    # sequence: does `expect` follow `after`? Held-out events first; all events if too few are new.
    def _verify_sequence(self, h: dict, pred: dict) -> dict:
        from scipy.stats import binomtest

        after, expect = [str(x) for x in pred.get("after") or []], str(pred.get("expect"))
        cutoff = int(h["data"].get("fitted_through_seq", 0))
        streams = defaultdict(list)
        for e in self.store.find(h["project_id"], "event", order="ts", limit=200_000):
            if pred.get("stream") in (None, e["data"].get("stream")):
                streams[e["data"].get("stream", "default")].append(e)

        def count(new_only: bool):
            hits = total = 0
            misses, used = [], []
            base: dict[str, int] = defaultdict(int)
            n_events = 0
            for events in streams.values():
                kinds = [e["kind"] for e in events]
                n_events += len(kinds)
                for k in kinds:
                    base[k] += 1
                for i in range(len(kinds) - len(after)):
                    if kinds[i:i + len(after)] != after:
                        continue
                    nxt = events[i + len(after)]
                    if new_only and nxt["data"].get("seq", 0) <= cutoff:
                        continue
                    total += 1
                    used.append(nxt["id"])
                    if nxt["kind"] == expect:
                        hits += 1
                    else:
                        misses.append(nxt["id"])
            p0 = base.get(expect, 0) / n_events if n_events else 0
            p = binomtest(hits, total, max(p0, 1e-9), alternative="greater").pvalue if total else 1.0
            return hits, total, misses, used, float(p)

        hits, total, misses, used, p = count(new_only=True)
        if total >= 20:
            rate = hits / total
            passed = True if rate >= 0.9 and p < ALPHA else False if rate < 0.6 else None
            return {"method": "prediction_holdout", "passed": passed, "stats": {"hits": hits, "n": total, "rate": round(rate, 3), "p_value": p},
                    "used": used, "counterexample_ids": misses}
        hits, total, misses, used, p = count(new_only=False)
        rate = hits / total if total else 0.0
        return {"method": "statistical_test", "passed": (rate >= 0.8 and p < ALPHA) if total >= 10 else None,
                "stats": {"hits": hits, "n": total, "rate": round(rate, 3), "p_value": p, "note": "fitted data, not held out"},
                "used": used, "counterexample_ids": misses}

    def _verify_correlation(self, h: dict, pred: dict) -> dict:
        from scipy.stats import spearmanr

        cutoff = int(h["data"].get("fitted_through_seq", 0))
        rows_new, rows_all = [], []
        for e in self.store.find(h["project_id"], "event", kind=pred.get("event_type"), limit=200_000):
            f = e["data"].get("numeric_features") or {}
            if pred.get("x") in f and pred.get("y") in f:
                rows_all.append((f[pred["x"]], f[pred["y"]], e["id"]))
                if e["data"].get("seq", 0) > cutoff:
                    rows_new.append(rows_all[-1])
        rows, method = (rows_new, "prediction_holdout") if len(rows_new) >= 20 else (rows_all, "correlation_test")
        if len(rows) < 10:
            return {"method": method, "passed": None, "stats": {"n": len(rows), "note": "not enough data"}}
        x, y, ids = zip(*rows)
        rho, p = spearmanr(x, y)
        want = 1 if pred.get("direction", "positive") == "positive" else -1
        passed = bool(p < ALPHA and np.sign(rho) == want) if p < ALPHA else (False if method == "prediction_holdout" else None)
        return {"method": method, "passed": passed, "stats": {"rho": float(rho), "p_value": float(p), "n": len(rows)}, "used": list(ids)[:200]}

    # benchmark: repeated experiment runs of candidate vs baseline on the same dataset.
    def _verify_benchmark(self, h: dict, pred: dict) -> dict:
        from scipy.stats import mannwhitneyu

        metric = pred.get("metric")
        key = _metric_key(metric)  # "compression ratio" matches an experiment's "compression_ratio"
        groups: dict[str, list[float]] = defaultdict(list)
        used, reproducible = [], True
        for x in self.store.find(h["project_id"], "experiment", limit=10_000):
            d = x["data"]
            if pred.get("dataset") and d.get("dataset_label") not in (pred.get("dataset"), None) and d.get("dataset") != pred.get("dataset"):
                continue
            if d.get("variant") in (pred.get("candidate"), pred.get("baseline")):
                values = [v for r in d.get("runs", []) if r.get("ok")
                          for name, v in (r.get("metrics") or {}).items() if _metric_key(name) == key]
                groups[d["variant"]].extend(values)
                used.append(x["id"])
                reproducible = reproducible and bool(d.get("reproducible"))
        cand, base = groups.get(pred.get("candidate"), []), groups.get(pred.get("baseline"), [])
        if len(cand) < 3 or len(base) < 3:
            return {"method": "reproducible_experiment", "passed": None, "used": used,
                    "stats": {"candidate_runs": len(cand), "baseline_runs": len(base), "note": "need at least 3 runs of each"}}
        alt = "greater" if pred.get("better", "higher") == "higher" else "less"
        p_better = mannwhitneyu(cand, base, alternative=alt).pvalue
        p_worse = mannwhitneyu(cand, base, alternative="less" if alt == "greater" else "greater").pvalue
        stats = {"candidate_mean": float(np.mean(cand)), "baseline_mean": float(np.mean(base)), "p_better": float(p_better),
                 "p_worse": float(p_worse), "runs": [len(cand), len(base)], "reproducible": reproducible,
                 "scope": {"dataset": pred.get("dataset"), "metric": metric}}
        if p_better < ALPHA and reproducible:
            return {"method": "reproducible_experiment", "passed": True, "stats": stats, "used": used}
        if p_worse < ALPHA:
            return {"method": "reproducible_experiment", "passed": False, "stats": stats, "used": used}
        return {"method": "statistical_test", "passed": False if p_better >= 0.5 else None,
                "stats": {**stats, "note": "no significant difference" if reproducible else "runs not reproducible"}, "used": used}

    # sources: independent primary sources for vs against (claims linked to the hypothesis).
    def _verify_sources(self, h: dict, pred: dict) -> dict:
        if self.complete is not None:
            self.map_claims(h)
        pro = [self.store.get(l["dst"]) for l in self.store.links_from(h["id"], "supported_by")]
        con = [self.store.get(l["dst"]) for l in self.store.links_from(h["id"], "contradicted_by")]
        pro_domains = {c["data"].get("domain") for c in pro if c and c["type"] == "claim" and c["data"].get("domain")}
        con_domains = {c["data"].get("domain") for c in con if c and c["type"] == "claim" and c["data"].get("domain")}
        stats = {"supporting_domains": sorted(pro_domains), "contradicting_domains": sorted(con_domains)}
        used = [c["id"] for c in pro + con if c]
        if len(pro_domains) >= MIN_INDEPENDENT_SOURCES and not con_domains:
            return {"method": "independent_sources", "passed": True, "stats": stats, "used": used}
        if con_domains and len(con_domains) >= len(pro_domains):
            return {"method": "independent_sources", "passed": False, "stats": stats, "used": used,
                    "counterexample_ids": [c["id"] for c in con if c]}
        return {"method": "independent_sources", "passed": None, "stats": {**stats, "note": "not enough independent sources yet"}, "used": used}

    def map_claims(self, h: dict, limit: int = 15) -> None:
        """Ask the model which stored claims bear on the hypothesis (mapping only; it proves nothing)."""
        linked = {l["dst"] for l in self.store.links_from(h["id"])}
        claims = [c for c in self.store.search(h["title"], project_id=h["project_id"], types=["claim"], limit=limit)
                  if c["id"] not in linked]
        if not claims:
            return
        try:
            verdicts = ask_json(self.complete, "You judge whether claims bear on a hypothesis. Reply with JSON only.", (
                f"Hypothesis: {h['title']}\nClaims:\n" + "\n".join(f"- [{c['id']}] {c['title']}" for c in claims)
                + '\nReply [{"id": "<claim id>", "relation": "supports" | "contradicts" | "irrelevant"}].'), 800)
        except Exception:
            return
        ids = {c["id"] for c in claims}
        for v in verdicts if isinstance(verdicts, list) else []:
            cid, rel = v.get("id"), v.get("relation")
            if cid in ids and rel == "supports":
                self.store.link(h["id"], "supported_by", cid, mapped_by="model")
            elif cid in ids and rel == "contradicts":
                self.store.link(h["id"], "contradicted_by", cid, mapped_by="model")

    # formal: symbolic proof of lhs == rhs, or a numeric counterexample.
    def _verify_formal(self, h: dict, pred: dict) -> dict:
        lhs, rhs = _parse_math(pred.get("lhs")), _parse_math(pred.get("rhs"))
        if lhs is None or rhs is None:
            return {"method": "formal_proof", "passed": None, "stats": {"note": "expressions could not be parsed safely"}}
        import sympy

        diff = sympy.simplify(lhs - rhs)
        if diff == 0:
            return {"method": "formal_proof", "passed": True, "stats": {"proof": f"simplify(({lhs}) - ({rhs})) = 0"}}
        symbols = sorted(diff.free_symbols, key=str)
        rng = random.Random(0)
        for _ in range(50):
            point = {s: rng.uniform(-5, 5) for s in symbols}
            try:
                value = complex(diff.evalf(subs=point))
            except Exception:
                continue
            if math.isfinite(value.real) and abs(value) > 1e-9:
                return {"method": "counterexample", "passed": False,
                        "stats": {"at": {str(k): round(v, 6) for k, v in point.items()}, "difference": str(value), "residual": str(diff)}}
        return {"method": "formal_proof", "passed": None, "stats": {"note": "not simplified to zero and no counterexample found", "residual": str(diff)}}

    def _verify_experiment(self, h: dict, pred: dict) -> dict:
        x = self.store.get(str(pred.get("experiment_id")))
        if x is None:
            return {"method": "reproducible_experiment", "passed": None, "stats": {"note": "experiment not found"}}
        metric, op, target = pred.get("metric"), pred.get("op", ">="), float(pred.get("value", 0))
        values = [r["metrics"][metric] for r in x["data"].get("runs", []) if r.get("ok") and metric in (r.get("metrics") or {})]
        if len(values) < 2:
            return {"method": "reproducible_experiment", "passed": None, "used": [x["id"]], "stats": {"note": "need at least 2 successful runs"}}
        ops = {">=": lambda a: a >= target, ">": lambda a: a > target, "<=": lambda a: a <= target, "<": lambda a: a < target,
               "==": lambda a: abs(a - target) <= 1e-9 * max(1, abs(target))}
        check = ops.get(op)
        if check is None:
            return {"method": "reproducible_experiment", "passed": None, "stats": {"note": f"unknown op {op}"}}
        holds = [check(v) for v in values]
        passed = True if all(holds) and x["data"].get("reproducible") else False if not any(holds) else None
        return {"method": "reproducible_experiment", "passed": passed, "used": [x["id"]],
                "stats": {"values": values, "condition": f"{metric} {op} {target}", "reproducible": x["data"].get("reproducible")}}


def _metric_key(name) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


_MATH_OK = re.compile(r"^[\w\s+\-*/^().,]*$")
_MATH_FUNCS = {"sin", "cos", "tan", "exp", "log", "sqrt", "pi", "E", "Abs", "factorial", "binomial", "Sum", "oo", "I"}


def _parse_math(text):
    """Parse an arithmetic expression without executing arbitrary code."""
    import sympy

    text = str(text or "").strip()
    if not text or len(text) > 400 or "__" in text or not _MATH_OK.match(text) or re.search(r"\.\s*[A-Za-z_]", text):
        return None  # plain arithmetic only: no attribute access
    names = set(re.findall(r"[A-Za-z_]\w*", text))
    local = {n: getattr(sympy, n) for n in names & _MATH_FUNCS}
    local.update({n: sympy.Symbol(n) for n in names - _MATH_FUNCS})
    try:
        return sympy.sympify(text.replace("^", "**"), locals=local, evaluate=True)
    except Exception:
        return None
