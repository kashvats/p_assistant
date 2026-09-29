"""Knowledge that accumulates across projects.

New research recalls related patterns, claims, experiments, failed approaches and
proofs from older projects instead of starting from zero, and patterns with the
same abstract structure in different projects are linked by a ``relationship``
("P and Q may be the same structure") rather than duplicated. Such links are
hypotheses (level HYPOTHESIS) until something tests them.
"""
from __future__ import annotations

import threading

from .store import KnowledgeStore

_MODEL = None
_MODEL_LOCK = threading.Lock()
RECALL_TYPES = ("pattern", "claim", "hypothesis", "finding", "experiment", "interpretation", "verification")


def _embedder(name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            try:
                from sentence_transformers import SentenceTransformer

                _MODEL = SentenceTransformer(name, device="cpu")
            except Exception:
                _MODEL = False
        return _MODEL or None


def recall(store: KnowledgeStore, text: str, exclude_project: str | None = None, limit: int = 12,
           semantic: bool = True) -> list[dict]:
    """Related knowledge from other projects: full-text candidates, re-ranked by meaning when possible."""
    candidates = [o for o in store.search(text, types=RECALL_TYPES, limit=limit * 4) if o["project_id"] != exclude_project]
    model = _embedder() if semantic and candidates else None
    if model is not None:
        vecs = model.encode([text] + [c["title"] for c in candidates], normalize_embeddings=True)
        scores = vecs[1:] @ vecs[0]
        ranked = sorted(zip(scores, candidates), key=lambda s: -s[0])
        candidates = [dict(c, similarity=round(float(s), 3)) for s, c in ranked if s >= 0.35]
    projects = {p["id"]: p["name"] for p in store.list_projects()}
    return [{"id": c["id"], "project": projects.get(c["project_id"]), "type": c["type"], "title": c["title"],
             "status": c["status"], "level": c["level"], **({"similarity": c["similarity"]} if "similarity" in c else {})}
            for c in candidates[:limit]]


def link_structures(store: KnowledgeStore, project_id: str, pattern_ids: list[str] | None = None) -> list[str]:
    """Relate this project's patterns to same-shaped patterns elsewhere (one relationship per pair)."""
    mine = [store.get(p) for p in pattern_ids] if pattern_ids is not None else store.find(project_id, "pattern", limit=5000)
    others = [p for p in store.find(None, "pattern", limit=50_000) if p["project_id"] != project_id]
    made = []
    for p in (x for x in mine if x):
        shape, ptype = p["data"].get("shape"), p["data"].get("pattern_type")
        if not shape or ptype not in ("sequence", "numeric_motif", "co_occurrence") or len(shape.split(">")) < 3:
            continue
        for q in others:
            if q["data"].get("pattern_type") != ptype or q["data"].get("shape") != shape:
                continue
            key = "xproj:" + "|".join(sorted((p["id"], q["id"])))
            if store.find_one(None, "relationship", key):
                continue
            r = store.add(project_id, "relationship", f"{p['id']} and {q['id']} may be the same structure ({shape})", kind=key,
                          status="OPEN", level="HYPOTHESIS",
                          data={"relation": "same_abstract_structure", "shape": shape, "a": p["id"], "b": q["id"],
                                "projects": [p["project_id"], q["project_id"]]},
                          links=[("relates", p["id"]), ("relates", q["id"])])
            store.link(p["id"], "structurally_similar_to", q["id"], relationship=r["id"])
            store.link(q["id"], "structurally_similar_to", p["id"], relationship=r["id"])
            made.append(r["id"])
    return made
