"""Tools for the persistent research intelligence engine (living_assistant.research)."""
from __future__ import annotations

from typing import Callable

from .base import Tool
from living_assistant.security.security_utils import redact_secrets


def build_research_engine_tools(get_engine: Callable, read_text: Callable[[str], str]) -> list[Tool]:
    def safe(fn):
        def wrapper(**kwargs):
            try:
                return fn(**kwargs)
            except KeyError as exc:
                return {"ok": False, "error": str(exc).strip("'\"")}
            except Exception as exc:
                return {"ok": False, "error": redact_secrets(exc, 600)}
        return wrapper

    @safe
    def research_project(action: str = "list", name: str = "", kind: str = "general", description: str = ""):
        eng = get_engine()
        if action == "list":
            return {"ok": True, "projects": [{"name": p["name"], "id": p["id"], "kind": p["kind"], "status": p["status"],
                                              "updated": p["updated_at"]} for p in eng.store.list_projects()]}
        if not name:
            return {"ok": False, "error": "name is required."}
        if action == "create":
            p = eng.project(name, create_kind=kind if kind in ("software", "general") else "general", description=description)
            return {"ok": True, "project": p["name"], "id": p["id"], "kind": p["kind"], "status": p["status"],
                    "folder": str(eng.folder(p))}
        if action == "status":
            return {"ok": True, **eng.status(name)}
        if action == "export":
            return {"ok": True, "folder": str(eng.export(name))}
        return {"ok": False, "error": "action must be list, create, status or export."}

    @safe
    def research_start(project: str, question: str = "", kind: str = "general", rounds: int = 3, depth: str = "quick",
                       background: bool = True):
        return get_engine().start(project, question, kind=kind, rounds=rounds, depth=depth, background=background)

    @safe
    def research_run(run_id: str, action: str = "status"):
        eng = get_engine()
        return eng.cancel(run_id) if action == "cancel" else {"ok": True, **eng.run_status(run_id)}

    @safe
    def research_ingest(project: str, kind: str, content: str = "", path: str = "", records: list | None = None,
                        values: list | None = None, timestamps: list | None = None, name: str = "value", stream: str = "",
                        symbol_pattern: str = ""):
        if path and not content:
            content = read_text(path)
        return get_engine().ingest_data(project, kind, content=content, records=records, values=values, timestamps=timestamps,
                                        name=name, stream=stream, symbol_pattern=symbol_pattern or None,
                                        source_label=path or "user input")

    @safe
    def research_analyze(project: str, propose_meanings_for: str = ""):
        eng = get_engine()
        result = eng.analyze(project)
        summary = {"ok": True, "project_status": result["project_status"], "events": result["patterns"]["events"],
                   "new_patterns": result["patterns"]["new_patterns"][:30], "new_findings": result["patterns"]["new_findings"][:30],
                   "new_hypotheses": result["new_hypotheses"], "new_questions": result["new_questions"],
                   "cross_project_links": result["cross_project_links"], "verified": result["verified"][:20],
                   "detector_errors": result["patterns"]["errors"]}
        if result["symbols"]:
            summary["symbols"] = result["symbols"]
        if propose_meanings_for:
            proj = eng.project(project)
            summary["meanings"] = [{"id": i["id"], "relation": i["title"], "status": i["status"], "meaning": i["data"].get("meaning")}
                                   for i in eng.symbols.propose_meanings(proj["id"], propose_meanings_for)]
        return summary

    @safe
    def research_hypothesis(project: str = "", action: str = "add", statement: str = "", prediction: dict | None = None,
                            core: bool = False, hypothesis_id: str = ""):
        eng = get_engine()
        if action == "verify":
            return eng.verifier.verify(hypothesis_id)
        from living_assistant.research.hypotheses import add_hypothesis

        p = eng.project(project)
        h = add_hypothesis(eng.store, p["id"], statement, prediction or {}, core=core, origin="user")
        result = eng.verifier.verify(h["id"]) if prediction else {"status": h["status"]}
        return {"ok": True, "hypothesis": h["id"], **{k: v for k, v in result.items() if k != "ok"}}

    @safe
    def research_experiment(project: str, name: str, command: str, cwd: str = ".", variant: str = "", dataset: str = "",
                            repeats: int = 3, hypothesis_id: str = "", params: dict | None = None):
        eng = get_engine()
        if eng.experiments is None:
            return {"ok": False, "error": "Experiments need the shell tool, which is unavailable."}
        p = eng.project(project)
        result = eng.experiments.run(p["id"], name, command, cwd=cwd, variant=variant, dataset=dataset, repeats=repeats,
                                     hypothesis_id=hypothesis_id or None, params=params)
        if result.get("ok") and hypothesis_id:
            result["verification"] = eng.verifier.verify(hypothesis_id)
        return result

    @safe
    def research_why(id: str):
        return get_engine().why(id)

    @safe
    def research_recall(query: str, project: str = ""):
        from living_assistant.research.crossproject import recall

        eng = get_engine()
        exclude = eng.project(project)["id"] if project else None
        return {"ok": True, "related": recall(eng.store, query, exclude_project=exclude)}

    @safe
    def research_build(project: str, action: str = "check", instructions: str = "", check_command: str = "", cwd: str = ""):
        eng = get_engine()
        from living_assistant.research.build import readiness

        if action == "check":
            return {"ok": True, **readiness(eng.store, project)}
        if eng.build is None:
            return {"ok": False, "error": "The build runner is unavailable."}
        if action == "sync":
            return eng.build.sync(project)
        if action == "build":
            return eng.build.request(project, instructions=instructions, check_command=check_command, cwd=cwd)
        return {"ok": False, "error": "action must be check, build or sync."}

    obj = {"type": "object"}
    return [
        Tool("research_project",
             "Manage persistent research projects (each topic keeps its questions, evidence, claims, events, patterns, symbols, "
             "hypotheses, experiments and verified findings). action: list | create | status | export. kind: software | general.",
             {**obj, "properties": {"action": {"type": "string", "enum": ["list", "create", "status", "export"], "default": "list"},
                                    "name": {"type": "string"}, "kind": {"type": "string", "enum": ["software", "general"]},
                                    "description": {"type": "string"}}}, research_project),
        Tool("research_start",
             "Start (or continue) researching a question inside a research project: rounds of research -> evidence -> claims "
             "-> patterns -> hypotheses -> verification -> follow-up questions, in the background. Never builds anything.",
             {**obj, "properties": {"project": {"type": "string"}, "question": {"type": "string"},
                                    "kind": {"type": "string", "enum": ["software", "general"], "default": "general"},
                                    "rounds": {"type": "integer", "default": 3},
                                    "depth": {"type": "string", "enum": ["quick", "standard", "detailed", "deep"], "default": "quick"},
                                    "background": {"type": "boolean", "default": True}}, "required": ["project"]}, research_start),
        Tool("research_run", "Status of a research run, or cancel it. action: status | cancel.",
             {**obj, "properties": {"run_id": {"type": "string"}, "action": {"type": "string", "enum": ["status", "cancel"]}},
              "required": ["run_id"]}, research_run),
        Tool("research_ingest",
             "Add observations to a research project as normalized events: kind=log (log text/file, templated with Drain), "
             "events (records with event_type, timestamp, entities, numeric fields), series (numeric values), symbols "
             "(unknown tokens/codes/glyphs in text, or a token list in records).",
             {**obj, "properties": {"project": {"type": "string"}, "kind": {"type": "string", "enum": ["log", "events", "series", "symbols"]},
                                    "content": {"type": "string"}, "path": {"type": "string", "description": "Workspace file to read instead of content."},
                                    "records": {"type": "array"}, "values": {"type": "array"}, "timestamps": {"type": "array"},
                                    "name": {"type": "string"}, "stream": {"type": "string"}, "symbol_pattern": {"type": "string"}},
              "required": ["project", "kind"]}, research_ingest),
        Tool("research_analyze",
             "Run pattern discovery (sequences, deviations, timing, frequency, combinations, relationships, change points, drift, "
             "anomalies, motifs, correlations) and symbol decoding on a project's events, derive hypotheses and questions, and "
             "re-verify hypotheses. Optionally propose meanings for one symbol (bound to its tested relations).",
             {**obj, "properties": {"project": {"type": "string"}, "propose_meanings_for": {"type": "string"}}, "required": ["project"]},
             research_analyze),
        Tool("research_hypothesis",
             "Add a hypothesis with a testable prediction and test it, or re-verify one (action=verify). prediction.type: "
             "sequence {after, expect} | correlation {event_type, x, y, direction} | benchmark {metric, better, candidate, baseline, dataset} "
             "| sources {} | formal {lhs, rhs} | experiment {experiment_id, metric, op, value}. Model confidence never counts as proof.",
             {**obj, "properties": {"project": {"type": "string"}, "action": {"type": "string", "enum": ["add", "verify"], "default": "add"},
                                    "statement": {"type": "string"}, "prediction": {"type": "object"}, "core": {"type": "boolean"},
                                    "hypothesis_id": {"type": "string"}}}, research_hypothesis),
        Tool("research_experiment",
             "Run a reproducible experiment (command repeated N times; records code version, dataset hash, environment, metrics "
             "from the last JSON line of output, logs) and optionally test a hypothesis with it.",
             {**obj, "properties": {"project": {"type": "string"}, "name": {"type": "string"}, "command": {"type": "string"},
                                    "cwd": {"type": "string"}, "variant": {"type": "string"}, "dataset": {"type": "string"},
                                    "repeats": {"type": "integer", "default": 3}, "hypothesis_id": {"type": "string"},
                                    "params": {"type": "object"}}, "required": ["project", "name", "command"]}, research_experiment),
        Tool("research_why",
             "Explain why for any research id (finding, pattern, hypothesis, claim, symbol interpretation) or a project: what "
             "happened, the pattern and its events, how often, expected vs actual, supporting and contradicting evidence, "
             "experiments, remaining hypotheses, what is proven and what is uncertain.",
             {**obj, "properties": {"id": {"type": "string"}}, "required": ["id"]}, research_why),
        Tool("research_recall", "Find related knowledge (patterns, claims, experiments, failed ideas, proofs) from other research projects.",
             {**obj, "properties": {"query": {"type": "string"}, "project": {"type": "string"}}, "required": ["query"]}, research_recall),
        Tool("research_build",
             "Build gate for software research projects. action=check (is it ready?), build (only when the user explicitly asks "
             "to build it; needs READY_TO_BUILD and the user's approval), sync (update build progress).",
             {**obj, "properties": {"project": {"type": "string"}, "action": {"type": "string", "enum": ["check", "build", "sync"], "default": "check"},
                                    "instructions": {"type": "string"}, "check_command": {"type": "string"}, "cwd": {"type": "string"}},
              "required": ["project"]}, research_build),
    ]
