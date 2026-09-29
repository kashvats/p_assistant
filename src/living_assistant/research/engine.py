"""The research intelligence loop around GPT Researcher.

    question -> research (GPT Researcher / quick source reading) -> evidence
    -> claims + events -> patterns / symbols -> hypotheses -> verification
    -> follow-up questions -> research again ... -> project knowledge

Each project keeps everything in the knowledge store and mirrors a readable
dossier to ``<workspace>/research_projects/<slug>/``. Runs are persisted and resume
after a restart. Research never starts implementation: that only happens through
the build gate, on the user's explicit request.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable

from .build import BuildGate, readiness
from .crossproject import link_structures, recall
from .epistemics import project_status
from .events import add_events, events_from_log, events_from_series
from .evidence import add_evidence, add_source, extract_claims, relate_claims
from .experiments import ExperimentRunner
from .hypotheses import Verifier, add_question, generate_from_claims, generate_from_patterns
from .llm import Complete, ask_json
from .patterns import PatternEngine
from .store import KnowledgeStore, now
from .symbols import SymbolEngine, ingest_symbols
from .why import explain

AUTO_TESTABLE = ("sequence", "correlation", "benchmark", "formal", "experiment", "sources")


class ResearchEngine:
    def __init__(self, store: KnowledgeStore, *, workspace_root: Path, complete: Complete | None = None,
                 research_run: Callable[..., dict] | None = None, run_command: Callable[..., dict] | None = None,
                 resolve_path: Callable[[str], Path] | None = None, approval=None, goals=None,
                 publish: Callable[..., None] | None = None, max_evidence_per_round: int = 6):
        self.store = store
        self.root = Path(workspace_root) / "research_projects"
        self.complete = complete
        self.research_run = research_run
        self.publish = publish or (lambda *a, **k: None)
        self.max_evidence = max_evidence_per_round
        self.patterns = PatternEngine(store)
        self.symbols = SymbolEngine(store, complete)
        self.verifier = Verifier(store, complete)
        self.experiments = ExperimentRunner(store, run_command, resolve_path) if run_command and resolve_path else None
        self.build = BuildGate(store, approval, start_goal=goals.start, goal_status=goals.store.get,
                               project_folder=self.folder) if goals is not None else None
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ---- projects ------------------------------------------------------------------------

    def folder(self, project: dict) -> Path:
        return self.root / project["slug"]

    def project(self, ref: str, create_kind: str | None = None, description: str = "") -> dict:
        p = self.store.get_project(ref)
        if p is None and create_kind:
            p = self.store.create_project(ref, create_kind, description)
            self.folder(p).mkdir(parents=True, exist_ok=True)
        if p is None:
            raise KeyError(f"No research project named {ref!r}.")
        return p

    # ---- ingestion -----------------------------------------------------------------------

    def ingest_research(self, project_ref: str, result: dict, question_id: str | None = None, extract: bool = True) -> dict:
        """Store what a research run read: sources, evidence passages, claims, events, contradictions."""
        from living_assistant.tools.researchtools import _passages, _terms

        project = self.project(project_ref, create_kind="general")
        pid = project["id"]
        terms = _terms(result.get("question") or "")
        evidence = []
        for page in result.get("pages") or []:
            source = add_source(self.store, pid, page.get("url"), page.get("title") or "", page.get("published"))
            text = str(page.get("raw_content") or page.get("text") or "")
            for passage in (_passages(text, terms, 3000) or [text[:1500]])[:4]:
                evidence.append(add_evidence(self.store, pid, source, passage, question_id=question_id))
        if result.get("report"):
            reports = self.folder(project) / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / f"{time.strftime('%Y%m%d-%H%M%S')}.md").write_text(result["report"], encoding="utf-8")
        claims, contradictions = [], []
        if extract and self.complete is not None:
            fresh = [e for e in evidence if not self.store.links_from(e["id"], "states")]
            for ev in fresh[: self.max_evidence]:
                claims += extract_claims(self.store, pid, ev, self.complete, focus=result.get("question") or "")
            contradictions = relate_claims(self.store, pid, claims, self.complete)
        return {"project": project["name"], "sources": len({e["data"].get("source_id") for e in evidence}),
                "evidence": [e["id"] for e in evidence], "claims": [c["id"] for c in claims], "contradictions": contradictions}

    def ingest_data(self, project_ref: str, kind: str, *, content: str = "", records: list | None = None,
                    values: list | None = None, timestamps: list | None = None, name: str = "value", stream: str = "",
                    symbol_pattern: str | None = None, source_label: str = "user") -> dict:
        """Observations from the user or files: log text, event records, a numeric series, or symbols."""
        project = self.project(project_ref, create_kind="general")
        pid = project["id"]
        source = add_source(self.store, pid, f"input:{source_label}:{now()}", source_label, origin="user")
        ev = add_evidence(self.store, pid, source, (content or json.dumps(records or values or [], default=str))[:6000])
        if kind == "log":
            stored = add_events(self.store, pid, events_from_log(content.splitlines(), stream=stream or "log"),
                                evidence_ids=[ev["id"]], source=source_label)
        elif kind == "events":
            stored = add_events(self.store, pid, [dict(r, stream=r.get("stream") or stream or "input") for r in records or []],
                                evidence_ids=[ev["id"]], source=source_label)
        elif kind == "series":
            stored = add_events(self.store, pid, events_from_series(values or [], timestamps, name=name, stream=stream or "series"),
                                evidence_ids=[ev["id"]], source=source_label)
        elif kind == "symbols":
            return {"ok": True, "evidence": ev["id"], **ingest_symbols(self.store, pid, text=content,
                                                                       tokens=records if records else None,
                                                                       pattern=symbol_pattern, stream=stream or "symbols",
                                                                       evidence_ids=[ev["id"]])}
        else:
            return {"ok": False, "error": "kind must be log, events, series or symbols."}
        return {"ok": True, "evidence": ev["id"], "events_added": len(stored)}

    # ---- analysis ------------------------------------------------------------------------

    def analyze(self, project_ref: str, verify: bool = True) -> dict:
        project = self.project(project_ref)
        pid = project["id"]
        patterns = self.patterns.run(pid)
        symbols = self.symbols.analyze(pid) if any(e["kind"].startswith("symbol:") for e in self.store.find(pid, "event", limit=5000)) else None
        generated = generate_from_patterns(self.store, pid, patterns["new_patterns"], patterns["new_findings"])
        cross = link_structures(self.store, pid, patterns["new_patterns"])
        verified = self.verify_all(pid) if verify else []
        self.export(pid)
        return {"patterns": patterns, "symbols": symbols, "new_hypotheses": generated["hypotheses"],
                "new_questions": generated["questions"], "cross_project_links": cross, "verified": verified,
                "project_status": self.store.get_project(pid)["status"]}

    def verify_all(self, project_id: str) -> list[dict]:
        out = []
        for h in self.store.find(project_id, "hypothesis", limit=10_000):
            ptype = (h["data"].get("prediction") or {}).get("type")
            if ptype in AUTO_TESTABLE and h["status"] not in ("PROVEN",):
                if ptype == "sources" and self.complete is None:
                    continue
                result = self.verifier.verify(h["id"])
                out.append({k: result.get(k) for k in ("hypothesis", "status", "level", "reason")})
        project = self.store.get_project(project_id)
        status = project_status(project["status"], project["kind"], self.store.find(project_id, "hypothesis", limit=10_000))
        if status != project["status"]:
            self.store.update_project(project_id, "hypotheses re-verified", status=status)
        return out

    # ---- the loop ------------------------------------------------------------------------

    def start(self, project_ref: str, question: str = "", *, kind: str = "general", description: str = "", rounds: int = 3,
              depth: str = "quick", background: bool = True) -> dict:
        if self.research_run is None:
            return {"ok": False, "error": "No research backend is configured."}
        project = self.project(project_ref, create_kind=kind, description=description or question)
        pid = project["id"]
        if question:
            add_question(self.store, pid, question, priority=1)
        prior = recall(self.store, question or project["name"], exclude_project=pid, limit=8)
        run = self.store.add(pid, "run", f"Research: {question or project['name']}", status="QUEUED",
                             data={"question": question, "max_rounds": max(1, min(int(rounds), 20)), "rounds_done": 0,
                                   "depth": depth, "log": [], "prior_knowledge": prior})
        if background:
            self._launch(run["id"])
            return {"ok": True, "run": run["id"], "project": project["name"], "status": "RUNNING",
                    "related_knowledge_from_other_projects": prior}
        self._loop(run["id"])
        return {"ok": True, **self.run_status(run["id"])}

    def _launch(self, run_id: str) -> None:
        with self._lock:
            thread = self._threads.get(run_id)
            if thread and thread.is_alive():
                return
            thread = threading.Thread(target=self._loop, args=(run_id,), name=f"research-{run_id}", daemon=True)
            self._threads[run_id] = thread
            thread.start()

    def cancel(self, run_id: str) -> dict:
        run = self.store.get(run_id)
        if run is None:
            return {"ok": False, "error": f"Unknown run {run_id}."}
        self.store.update(run_id, "cancel requested", status="CANCELLING")
        return {"ok": True, "run": run_id, "status": "CANCELLING"}

    def resume_interrupted(self) -> list[str]:
        resumed = []
        for run in self.store.find(None, "run", limit=1000):
            if run["status"] in ("RUNNING", "QUEUED"):
                self._launch(run["id"])
                resumed.append(run["id"])
        return resumed

    def run_status(self, run_id: str) -> dict:
        run = self.store.get(run_id)
        if run is None:
            return {"ok": False, "error": f"Unknown run {run_id}."}
        project = self.store.get_project(run["project_id"])
        return {"run": run_id, "status": run["status"], "project": project["name"], "project_status": project["status"],
                "rounds_done": run["data"].get("rounds_done"), "max_rounds": run["data"].get("max_rounds"),
                "log": run["data"].get("log", [])[-5:], "error": run["data"].get("error")}

    def _loop(self, run_id: str) -> None:
        self.store.update(run_id, "started", status="RUNNING")
        try:
            while True:
                run = self.store.get(run_id)
                if run["status"] == "CANCELLING":
                    self.store.update(run_id, "cancelled", status="CANCELLED")
                    return
                if run["data"]["rounds_done"] >= run["data"]["max_rounds"]:
                    self.store.update(run_id, "all rounds done", status="DONE")
                    return
                entry = self._round(run)
                run = self.store.get(run_id)
                log = run["data"].get("log", []) + [entry]
                self.store.merge_data(run_id, "round finished", rounds_done=run["data"]["rounds_done"] + 1, log=log[-50:])
                self.publish("research.round", run=run_id, **{k: entry.get(k) for k in ("question", "project_status")})
                if entry.get("stop"):
                    self.store.update(run_id, entry["stop"], status="DONE")
                    return
        except Exception as exc:
            self.store.merge_data(run_id, "failed", error=str(exc)[:800])
            self.store.update(run_id, f"failed: {str(exc)[:200]}", status="FAILED")

    def _round(self, run: dict) -> dict:
        pid = run["project_id"]
        project = self.store.get_project(pid)
        questions = sorted(self.store.find(pid, "question", status="OPEN", limit=500),
                           key=lambda q: (q["data"].get("priority", 5), q["created_at"]))
        if not questions:
            return {"at": now(), "stop": "No open questions left.", "project_status": project["status"]}
        q = questions[0]
        self.store.update(q["id"], "being researched", status="RESEARCHING")
        result = self.research_run(q["title"], run["data"].get("depth", "quick"))
        if not result.get("ok") and not result.get("pages"):
            self.store.update(q["id"], f"research failed: {result.get('error')}", status="OPEN")
            self.store.merge_data(q["id"], "research failed", attempts=q["data"].get("attempts", 0) + 1)
            if q["data"].get("attempts", 0) + 1 >= 2:
                self.store.update(q["id"], "no sources found twice", status="UNRESOLVED")
            return {"at": now(), "question": q["title"], "error": result.get("error"), "project_status": project["status"]}
        stored = self.ingest_research(pid, result, question_id=q["id"])
        new_hyps = generate_from_claims(self.store, pid, stored["claims"], self.complete, topic=project["name"]) if self.complete else []
        analysis = self.analyze(pid)
        follow_ups = self._follow_up_questions(pid, q) if self.complete else []
        self.store.update(q["id"], f"researched: {len(stored['evidence'])} evidence, {len(stored['claims'])} claims", status="ANSWERED")
        for ev in stored["evidence"][:50]:
            self.store.link(q["id"], "answered_by", ev)
        return {"at": now(), "question": q["title"], "evidence": len(stored["evidence"]), "claims": len(stored["claims"]),
                "contradictions": len(stored["contradictions"]), "hypotheses": new_hyps + analysis["new_hypotheses"],
                "findings": len(analysis["patterns"]["new_findings"]), "follow_up_questions": follow_ups,
                "project_status": analysis["project_status"]}

    def _follow_up_questions(self, pid: str, answered: dict) -> list[str]:
        open_hyps = [h for h in self.store.find(pid, "hypothesis", limit=200) if h["status"] not in ("VERIFIED", "PROVEN", "CONTRADICTED")]
        contradictions = [f for f in self.store.find(pid, "finding", limit=500) if f["data"].get("finding_type") == "CONTRADICTION"]
        existing = {q["title"].lower() for q in self.store.find(pid, "question", limit=2000)}
        try:
            items = ask_json(self.complete, "You plan the next research steps. Reply with JSON only.", (
                f"Just researched: {answered['title']}\n"
                "Unresolved hypotheses:\n" + "\n".join(f"- {h['title']} ({h['status']}: {h['data'].get('assessment', '')})" for h in open_hyps[:10])
                + "\nOpen contradictions:\n" + "\n".join(f"- {f['title']}" for f in contradictions[-5:])
                + "\n\nWhich 1-2 web research questions would most reduce the uncertainty (find confirming or refuting "
                'evidence, counterexamples, benchmarks)? Reply ["question", ...].'), 400)
        except Exception:
            return []
        made = []
        for text in items if isinstance(items, list) else []:
            if isinstance(text, str) and text.strip() and text.strip().lower() not in existing:
                made.append(add_question(self.store, pid, text, origin=answered["id"], priority=3)["id"])
        return made[:2]

    # ---- views ---------------------------------------------------------------------------

    def status(self, project_ref: str) -> dict:
        project = self.project(project_ref)
        pid = project["id"]
        hyps = self.store.find(pid, "hypothesis", limit=10_000)
        return {
            "project": project["name"], "id": pid, "kind": project["kind"], "status": project["status"],
            "counts": self.store.count(pid),
            "hypotheses": [{"id": h["id"], "status": h["status"], "level": h["level"], "statement": h["title"]} for h in hyps][:30],
            "open_questions": [q["title"] for q in self.store.find(pid, "question", status="OPEN", limit=10)],
            "recent_findings": [{"id": f["id"], "type": f["data"].get("finding_type"), "title": f["title"]}
                                for f in self.store.find(pid, "finding", order="updated", limit=10)],
            "runs": [{"id": r["id"], "status": r["status"], "rounds": f"{r['data'].get('rounds_done')}/{r['data'].get('max_rounds')}"}
                     for r in self.store.find(pid, "run", order="updated", limit=5)],
            "build": readiness(self.store, pid),
            "folder": str(self.folder(project)),
        }

    def why(self, ref: str) -> dict:
        return explain(self.store, ref)

    def export(self, project_ref: str) -> Path:
        project = self.project(project_ref)
        pid = project["id"]
        folder = self.folder(project)
        folder.mkdir(parents=True, exist_ok=True)
        s = self.store
        hyps = s.find(pid, "hypothesis", limit=10_000)

        def section(title, rows):
            return [f"## {title}", *(rows or ["- none"]), ""]

        lines = [f"# {project['name']}", "", f"Kind: {project['kind']} | Status: **{project['status']}** | Updated: {now()}", "",
                 project.get("description") or "", ""]
        lines += section("Verified / proven", [f"- {h['id']} [{h['level']}] {h['title']} - {h['data'].get('assessment', '')}"
                                               for h in hyps if h["status"] in ("VERIFIED", "PROVEN")])
        lines += section("Hypotheses under test", [f"- {h['id']} {h['status']} [{h['level']}] {h['title']}"
                                                   for h in hyps if h["status"] not in ("VERIFIED", "PROVEN", "CONTRADICTED")])
        lines += section("Failed ideas (kept on purpose)", [f"- {h['id']} {h['title']} - {h['data'].get('assessment', '')}"
                                                            for h in hyps if h["status"] == "CONTRADICTED"])
        lines += section("Patterns", [f"- {p['id']} [{p['level']}] {p['title']} (occurrences: {p['data'].get('occurrence_count')})"
                                      for p in s.find(pid, "pattern", limit=50)])
        lines += section("Findings", [f"- {f['id']} {f['data'].get('finding_type')}: {f['title']}" for f in s.find(pid, "finding", order="updated", limit=50)])
        lines += section("Symbols and interpretations", [f"- {i['id']} {i['status']} [{i['level']}] {i['title']}"
                                                         + (f" - meaning: {i['data']['meaning']}" if i["data"].get("meaning") else "")
                                                         for i in s.find(pid, "interpretation", limit=50)])
        lines += section("Experiments", [f"- {x['id']} {x['title']} reproducible={x['data'].get('reproducible')} "
                                         f"metrics={ {k: round(v['mean'], 4) for k, v in (x['data'].get('metrics') or {}).items()} }"
                                         for x in s.find(pid, "experiment", limit=50)])
        lines += section("Open questions", [f"- {q['id']} {q['title']}" for q in s.find(pid, "question", status="OPEN", limit=50)])
        lines += section("Sources", [f"- {src['id']} {src['title']} - {src['data'].get('url')}" for src in s.find(pid, "source", limit=100)])
        lines += ["Every item has a stable id; ask \"why <id>\" for its full evidence chain."]
        (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
        snapshot = {"project": project, "counts": s.count(pid), "hypotheses": hyps,
                    **{t + "s": s.find(pid, t, limit=5000) for t in ("pattern", "finding", "symbol", "interpretation", "experiment",
                                                                    "question", "verification", "implementation", "relationship")}}
        (folder / "knowledge.json").write_text(json.dumps(snapshot, indent=1, default=str), encoding="utf-8")
        return folder
