"""Answer "Why?" for any stored object by walking its evidence chain.

Source -> Evidence -> Claim -> Experiment/Analysis -> Pattern -> Finding ->
Verification -> Conclusion. Every answer names the stable ids involved so each
step can be inspected on its own.
"""
from __future__ import annotations

from .store import KnowledgeStore

STRONG = {"VERIFIED", "FORMALLY_PROVEN", "PREDICTIVE"}


def _brief(store: KnowledgeStore, oid: str) -> dict | None:
    o = store.get(oid)
    if o is None:
        return None
    out = {"id": o["id"], "type": o["type"], "title": o["title"], "status": o["status"], "level": o["level"]}
    if o["ts"] and not str(o["ts"]).startswith("~"):
        out["time"] = o["ts"]
    if o["type"] == "evidence":
        out.update(quote=o["data"].get("text", "")[:400], url=o["data"].get("url"), published=o["data"].get("published"))
    elif o["type"] == "claim":
        out.update(quote=o["data"].get("quote"), url=o["data"].get("url"))
    return out


def _evidence_for(store: KnowledgeStore, ids: list[str]) -> list[dict]:
    seen, out = set(), []
    for oid in ids:
        for rel in ("supported_by", "evidenced_by"):
            for l in store.links_from(oid, rel):
                if l["dst"] not in seen:
                    seen.add(l["dst"])
                    b = _brief(store, l["dst"])
                    if b:
                        out.append(b)
    return out


def _verifications(store: KnowledgeStore, oid: str) -> list[dict]:
    out = []
    for l in store.links_from(oid, "tested_by"):
        v = store.get(l["dst"])
        if v:
            out.append({"id": v["id"], "method": v["data"].get("method"), "passed": v["data"].get("passed"),
                        "stats": v["data"].get("stats"), "used": [u["dst"] for u in store.links_from(v["id"], "used")][:20],
                        "counterexamples": [c["dst"] for c in store.links_from(v["id"], "counterexample")][:20]})
    return out


def explain(store: KnowledgeStore, ref: str) -> dict:
    project = store.get_project(ref)
    if project:
        return explain_project(store, project)
    o = store.get(ref)
    if o is None:
        return {"ok": False, "error": f"Nothing stored with id {ref}."}
    d = o["data"]
    pattern = store.get(d["pattern_id"]) if d.get("pattern_id") else (o if o["type"] == "pattern" else None)
    if pattern is None:
        about = [l["dst"] for l in store.links_from(o["id"], "about") + store.links_from(o["id"], "derived_from")]
        pattern = next((store.get(x) for x in about if (store.get(x) or {}).get("type") == "pattern"), None)
    event_ids = d.get("event_ids") or [l["dst"] for l in store.links_from(o["id"], "involves")]
    pattern_block = None
    if pattern:
        occ_links = store.links_from(pattern["id"], "has_occurrence")
        occurrences = []
        for l in occ_links[:10]:
            occ = store.get(l["dst"])
            if occ:
                occurrences.append({"occurrence": occ["id"], "events": occ["data"].get("event_ids")})
        pattern_block = {"id": pattern["id"], "pattern": pattern["title"], "type": pattern["data"].get("pattern_type"),
                         "level": pattern["level"], "stats": pattern["data"].get("stats"),
                         "occurrences_total": len(occ_links), "occurrences": occurrences}
        if o["type"] == "pattern":
            event_ids = [e for occ in occurrences for e in (occ["events"] or [])][:30]
    hypotheses = []
    for rel in ("suggests", "has_hypothesis"):
        hypotheses += [l["dst"] for l in store.links_from(o["id"], rel)]
    if pattern:
        hypotheses += [l["dst"] for l in store.links_from(pattern["id"], "suggests")]
    hypotheses += [l["src"] for l in store.links_to(o["id"], "derived_from") + store.links_to(o["id"], "based_on")]
    hyp_blocks = []
    for hid in dict.fromkeys(hypotheses):
        h = store.get(hid)
        if h and h["type"] == "hypothesis":
            hyp_blocks.append({"id": h["id"], "hypothesis": h["title"], "status": h["status"], "level": h["level"],
                               "assessment": h["data"].get("assessment"), "verifications": _verifications(store, h["id"])})
    verifications = _verifications(store, o["id"])
    contradicting = [_brief(store, l["dst"]) for l in store.links_from(o["id"], "contradicts") + store.links_from(o["id"], "contradicted_by")]
    for v in verifications + [v for h in hyp_blocks for v in h["verifications"]]:
        contradicting += [{"counterexample": c} for c in v["counterexamples"][:5]]
    experiments = sorted({u for v in verifications + [v for h in hyp_blocks for v in h["verifications"]] for u in v["used"]
                          if u.startswith("X-")})
    experiments += [l["dst"] for l in store.links_from(o["id"], "tested_in")]
    proven = [f"{v['method']} passed ({v['id']})" for v in verifications if v["passed"]]
    proven += [f"{h['id']} {h['status']} ({h['level']})" for h in hyp_blocks if h["level"] in STRONG]
    uncertain = [f"{h['id']} {h['status']}: {h['hypothesis']}" for h in hyp_blocks if h["level"] not in STRONG]
    if o["level"] not in STRONG | {"CONTRADICTED"}:
        uncertain.append(f"{o['id']} itself is {o['level']} - not verified.")
    questions = [_brief(store, l["src"]) for l in store.links_to(o["id"], "raised_by")]
    return {
        "ok": True,
        "id": o["id"],
        "what_happened": o["title"],
        "type": d.get("finding_type") or o["type"],
        "status": o["status"],
        "level": o["level"],
        "expected": d.get("expected"),
        "actual": d.get("actual"),
        "what_changed": {"expected": d.get("expected"), "actual": d.get("actual")} if d.get("expected") is not None else None,
        "pattern": pattern_block,
        "how_often": pattern_block["occurrences_total"] if pattern_block else None,
        "events": [b for b in (_brief(store, e) for e in event_ids[:30]) if b],
        "supporting_evidence": _evidence_for(store, [o["id"], *event_ids[:30]]),
        "contradicting_evidence": [c for c in contradicting if c],
        "experiments": [b for b in (_brief(store, x) for x in dict.fromkeys(experiments)) if b],
        "verifications": verifications,
        "hypotheses": hyp_blocks,
        "open_questions": [q for q in questions if q],
        "proven": proven or ["Nothing about this has been verified yet."],
        "uncertain": uncertain,
        "history": store.history(o["id"]),
    }


def explain_project(store: KnowledgeStore, project: dict) -> dict:
    pid = project["id"]
    hyps = store.find(pid, "hypothesis", limit=10_000)
    return {
        "ok": True,
        "project": project["name"],
        "id": pid,
        "kind": project["kind"],
        "status": project["status"],
        "why_this_status": [f"{h['id']} {h['status']} ({h['level']}): {h['title']} - {h['data'].get('assessment', '')}"
                            for h in hyps if (h["data"].get("core") or len(hyps) <= 12)][:20],
        "verified_or_proven": [f"{h['id']}: {h['title']}" for h in hyps if h["status"] in ("VERIFIED", "PROVEN")],
        "failed_ideas": [f"{h['id']}: {h['title']}" for h in hyps if h["status"] == "CONTRADICTED"],
        "open_questions": [q["title"] for q in store.find(pid, "question", status="OPEN", limit=20)],
        "contradictions": [f["title"] for f in store.find(pid, "finding", limit=10_000) if f["data"].get("finding_type") == "CONTRADICTION"][:10],
        "counts": store.count(pid),
        "status_history": store.history(pid),
    }
