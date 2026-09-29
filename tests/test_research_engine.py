"""Research intelligence engine: knowledge store, proof rules, patterns, symbols,
hypotheses, evidence chains, experiments, build gate, loop and GPT Researcher capture."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from living_assistant.research.build import BuildGate, readiness
from living_assistant.research.engine import ResearchEngine
from living_assistant.research.epistemics import assess, project_status
from living_assistant.research.events import add_events, events_from_log, normalize_type
from living_assistant.research.evidence import add_evidence, add_source, extract_claims, relate_claims
from living_assistant.research.experiments import ExperimentRunner
from living_assistant.research.hypotheses import Verifier, _parse_math, add_hypothesis
from living_assistant.research.patterns import PatternEngine
from living_assistant.research.store import KnowledgeStore
from living_assistant.research.symbols import SymbolEngine, extract_symbol_stream, ingest_symbols
from living_assistant.research.why import explain


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(tmp_path / "knowledge.sqlite3")


def _sequence_events(n=40, deviate_at=30, t0=None):
    t = t0 or datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        for kind in ("start", "load", "done"):
            t += timedelta(seconds=1)
            out.append({"event_type": "crash" if (i == deviate_at and kind == "done") else kind, "timestamp": t.isoformat()})
    return out, t


# ---- store & epistemics -------------------------------------------------------------------

def test_store_ids_links_history_and_never_deletes(store):
    p = store.create_project("Compression", "software")
    assert store.create_project("compression")["id"] == p["id"]  # same project by name
    h = store.add(p["id"], "hypothesis", "X beats Y", status="OPEN", level="HYPOTHESIS")
    e = store.add(p["id"], "event", "benchmark", kind="benchmark")
    assert h["id"] == "H-1" and e["id"] == "E-1"
    store.link(h["id"], "about", e["id"])
    store.update(h["id"], "benchmarks failed", status="CONTRADICTED", level="CONTRADICTED")
    assert store.get(h["id"])["status"] == "CONTRADICTED"  # kept, not deleted
    assert store.history(h["id"])[0]["reason"] == "benchmarks failed"
    assert store.links_to(e["id"])[0]["src"] == h["id"]
    assert not hasattr(store, "delete")
    assert store.search("beats")[0]["id"] == h["id"]


def test_model_confidence_never_counts_as_proof():
    assert assess([{"method": "llm_judgement", "passed": True}])[0] == "OPEN"
    assert assess([{"method": "statistical_test", "passed": True}])[:2] == ("SUPPORTED", "STATISTICALLY_SUPPORTED")
    assert assess([{"method": "reproducible_experiment", "passed": True}])[:2] == ("VERIFIED", "VERIFIED")
    assert assess([{"method": "formal_proof", "passed": True}])[:2] == ("PROVEN", "FORMALLY_PROVEN")
    assert assess([{"method": "counterexample", "passed": False}])[0] == "CONTRADICTED"
    mixed = assess([{"method": "reproducible_experiment", "passed": True}, {"method": "counterexample", "passed": False}])
    assert mixed[0] == "PARTIALLY_SUPPORTED"
    assert assess([], supporting=5)[:2] == ("PARTIALLY_SUPPORTED", "OBSERVED")  # sources saying so is not verification


def test_project_status_rollup_and_software_gate():
    verified = [{"status": "VERIFIED", "data": {"core": True}}]
    assert project_status("RESEARCHING", "software", verified) == "READY_TO_BUILD"
    assert project_status("RESEARCHING", "general", verified) == "VERIFIED"
    assert project_status("BUILDING", "software", []) == "BUILDING"
    assert project_status("RESEARCHING", "general", [{"status": "CONTRADICTED", "data": {}}]) == "CONTRADICTED"


# ---- events & patterns ------------------------------------------------------------------

def test_event_normalization_keeps_symbols_and_mines_log_templates():
    assert normalize_type("Benchmark Improved") == "benchmark_improved"
    assert normalize_type("symbol:△") == "symbol:△"
    events = events_from_log(["2026-01-01T00:00:01 connected to db 10.0.0.1 in 12 ms",
                              "2026-01-01T00:00:02 connected to db 10.0.0.2 in 15 ms"])
    assert events[0]["event_type"] == events[1]["event_type"]  # same template, variables stripped
    assert events[1]["numeric_features"]


def test_sequence_deviation_is_linked_to_pattern_events_and_is_idempotent(store):
    p = store.create_project("svc", "software")
    events, _ = _sequence_events()
    add_events(store, p["id"], events)
    engine = PatternEngine(store)
    first = engine.run(p["id"])
    assert not first["errors"]
    deviations = [store.get(f) for f in first["new_findings"] if store.get(f)["data"]["finding_type"] == "SEQUENCE_DEVIATION"]
    assert len(deviations) == 1
    dev = deviations[0]
    assert dev["data"]["expected"] == "done" and dev["data"]["actual"] == "crash"
    pattern = store.get(dev["data"]["pattern_id"])
    assert pattern["level"] == "STATISTICALLY_SUPPORTED"
    assert store.links_from(pattern["id"], "has_occurrence")
    assert all(l["rel"] in ("about", "involves") for l in store.links_from(dev["id"]))
    again = engine.run(p["id"])
    assert again["new_patterns"] == [] and again["new_findings"] == []


def test_numeric_detectors_find_level_shift(store):
    random.seed(0)
    p = store.create_project("latency", "general")
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    add_events(store, p["id"], [{"event_type": "request", "timestamp": (t + timedelta(seconds=i)).isoformat(),
                                 "numeric_features": {"ms": random.gauss(100 if i < 60 else 150, 4)}} for i in range(120)])
    found = {store.get(f)["data"]["finding_type"] for f in PatternEngine(store).run(p["id"])["new_findings"]}
    assert {"CHANGE_POINT", "DISTRIBUTION_DRIFT"} <= found


# ---- symbols ----------------------------------------------------------------------------

def test_symbol_decoding_is_hypothesis_testing_with_holdout(store):
    random.seed(2)
    p = store.create_project("decode", "general")
    tokens = []
    for _ in range(80):
        tokens += ["ZX-4", "Q3" if random.random() < 0.95 else "Q7", random.choice(["K1", "K2"])]
    ingest_symbols(store, p["id"], tokens=tokens)
    engine = SymbolEngine(store)
    first = engine.analyze(p["id"])
    rule = next(store.get(i) for i in first["new_interpretations"] if store.get(i)["title"].startswith("ZX-4: is followed by symbol:Q3"))
    assert rule["status"] != "VERIFIED"  # fitted data alone cannot verify
    ingest_symbols(store, p["id"], tokens=["ZX-4", "Q3", "K1"] * 30)
    engine.analyze(p["id"])
    assert store.get(rule["id"])["status"] == "VERIFIED"
    assert extract_symbol_stream("0x17 0x21 ZX-4 → Q3 △ ○") == ["0x17", "0x21", "ZX-4", "Q3", "△", "○"]


# ---- hypotheses & verification --------------------------------------------------------

def test_sequence_hypothesis_verified_only_on_new_data(store):
    p = store.create_project("seq", "general")
    events, t = _sequence_events(deviate_at=-1)
    add_events(store, p["id"], events)
    h = add_hypothesis(store, p["id"], "After start, load follows", {"type": "sequence", "after": ["start"], "expect": "load"})
    first = Verifier(store).verify(h["id"])
    assert first["status"] == "SUPPORTED" and first["level"] == "STATISTICALLY_SUPPORTED"
    more, _ = _sequence_events(n=25, deviate_at=-1, t0=t)
    add_events(store, p["id"], more)
    second = Verifier(store).verify(h["id"])
    assert second["level"] == "PREDICTIVE"


def test_formal_proof_counterexample_and_safe_parsing(store):
    p = store.create_project("math", "general")
    ok = add_hypothesis(store, p["id"], "(a+b)^2 expands", {"type": "formal", "lhs": "(a+b)^2", "rhs": "a^2 + 2*a*b + b^2"})
    bad = add_hypothesis(store, p["id"], "(a+b)^2 = a^2+b^2", {"type": "formal", "lhs": "(a+b)^2", "rhs": "a^2 + b^2"})
    v = Verifier(store)
    assert v.verify(ok["id"])["status"] == "PROVEN"
    assert v.verify(bad["id"])["status"] == "CONTRADICTED"
    for attack in ("__import__('os').system('x')", "x.subs(x, 1)", "().__class__", "open('f')"):
        assert _parse_math(attack) is None


def test_benchmark_needs_reproducible_repeated_runs(store, tmp_path):
    p = store.create_project("compression", "software")

    def fake_run(command, cwd, timeout_seconds):
        ratio = 3.0 if "candidate" in command else 2.0
        return {"ok": True, "returncode": 0, "stdout": json.dumps({"compression_ratio": ratio, "lossless": True})}

    runner = ExperimentRunner(store, fake_run, lambda path: tmp_path)
    h = add_hypothesis(store, p["id"], "Candidate compresses better than baseline",
                       {"type": "benchmark", "metric": "compression_ratio", "better": "higher", "candidate": "candidate", "baseline": "zstd"},
                       core=True)
    for variant in ("candidate", "zstd"):
        res = runner.run(p["id"], f"{variant} run", f"python bench.py {variant}", variant=variant, repeats=4)
        assert res["ok"] and res["reproducible"]
    x = store.find(p["id"], "experiment")[0]
    assert x["data"]["environment"]["python"] and "code_version" in x["data"]
    assert store.find(p["id"], "event", kind="experiment_result")
    result = Verifier(store).verify(h["id"])
    assert result["status"] == "VERIFIED" and result["project_status"] == "READY_TO_BUILD"


# ---- evidence ---------------------------------------------------------------------------

def _fake_complete(messages, max_tokens):
    prompt = messages[-1]["content"]
    if "extract factual claims" in messages[0]["content"]:
        return json.dumps([
            {"claim": "Algorithm X reaches ratio 3.1 on enwik8", "quote": "Algorithm X reaches a ratio of 3.1 on enwik8",
             "subject": "Algorithm X", "entities": ["Algorithm X", "enwik8"], "numbers": {"ratio": 3.1},
             "event": {"type": "benchmark_published", "time": "2026-02-01", "entities": ["Algorithm X"]}},
            {"claim": "Algorithm X is the fastest codec", "quote": "fastest codec ever made", "subject": "speed"},  # not in text
        ])
    if "compare factual claims" in messages[0]["content"]:
        return json.dumps([{"pair": 0, "relation": "contradicts", "why": "different ratios"}])
    return "[]"


def test_claims_must_quote_the_source_verbatim_and_contradictions_are_found(store):
    p = store.create_project("claims", "general")
    src = add_source(store, p["id"], "https://a.example/paper", "Paper A")
    ev = add_evidence(store, p["id"], src, "In our tests Algorithm X reaches a ratio of 3.1 on enwik8 with default settings.")
    claims = extract_claims(store, p["id"], ev, _fake_complete)
    assert [c["title"] for c in claims] == ["Algorithm X reaches ratio 3.1 on enwik8"]  # the unquotable claim is dropped
    assert store.links_from(claims[0]["id"], "describes_event")
    src2 = add_source(store, p["id"], "https://b.example/post", "Post B")
    ev2 = add_evidence(store, p["id"], src2, "Algorithm X reaches a ratio of 3.1 on enwik8 only with a custom dictionary.")
    other = store.add(p["id"], "claim", "Algorithm X reaches ratio 2.4 on enwik8", data={"evidence_id": ev2["id"]})
    findings = relate_claims(store, p["id"], [other], _fake_complete)
    assert findings and store.get(findings[0])["data"]["finding_type"] == "CONTRADICTION"


# ---- build gate -------------------------------------------------------------------------

class _Approval:
    def __init__(self, allow):
        self.allow, self.requests = allow, []

    def request(self, action, reason, kind):
        self.requests.append(kind)
        return {"allowed": self.allow, "approval_id": "a1"} if self.allow else {"allowed": False, "pending": True, "approval_id": "a1"}


class _Goals:
    def __init__(self):
        self.started, self.state = [], {}

    def start(self, goal, check_command="", cwd="."):
        self.started.append(goal)
        self.state["g1"] = {"id": "g1", "status": "running"}
        return {"ok": True, "id": "g1"}


def test_build_gate_requires_software_verification_and_explicit_approval(store, tmp_path):
    goals = _Goals()
    general = store.create_project("History of symbols", "general")
    soft = store.create_project("Compressor", "software")
    gate = lambda allow: BuildGate(store, _Approval(allow), goals.start, lambda gid: goals.state.get(gid), lambda p: tmp_path / p["slug"])
    assert not readiness(store, general["id"])["ready"]
    assert gate(True).request(general["id"])["ok"] is False  # non-software: never built
    assert gate(True).request(soft["id"])["ok"] is False  # not verified yet
    assert goals.started == []
    store.update_project(soft["id"], "test", status="READY_TO_BUILD")
    denied = gate(False).request(soft["id"])
    assert denied["approval_required"] and goals.started == []  # no approval, no build
    built = gate(True).request(soft["id"], instructions="use Rust")
    assert built["ok"] and store.get_project(soft["id"])["status"] == "BUILDING"
    assert "use Rust" in Path(built["brief"]).read_text(encoding="utf-8")
    goals.state["g1"] = {"id": "g1", "status": "completed", "rounds": 3}
    gate(True).sync(soft["id"])
    assert store.get_project(soft["id"])["status"] == "IMPLEMENTED"


# ---- loop, why, capture -----------------------------------------------------------------

def test_research_loop_stores_evidence_answers_questions_and_exports(store, tmp_path):
    def fake_research(question, depth="quick", source_urls=None):
        return {"ok": True, "question": question, "report": "",
                "pages": [{"url": "https://a.example/paper", "title": "Paper A",
                           "raw_content": "Algorithm X reaches a ratio of 3.1 on enwik8 with default settings. " * 3}]}

    engine = ResearchEngine(store, workspace_root=tmp_path, complete=_fake_complete, research_run=fake_research)
    result = engine.start("Compression", "How well does Algorithm X compress enwik8?", kind="software", rounds=2, background=False)
    assert result["status"] == "DONE"
    p = store.get_project("compression")
    assert store.find(p["id"], "evidence") and store.find(p["id"], "claim")
    assert store.find(p["id"], "question", status="ANSWERED")
    assert (tmp_path / "research_projects" / "compression" / "README.md").exists()
    assert p["status"] != "BUILDING"  # research never starts a build by itself


def test_why_explains_a_finding_with_its_pattern_and_events(store):
    p = store.create_project("why", "software")
    events, _ = _sequence_events()
    add_events(store, p["id"], events)
    summary = PatternEngine(store).run(p["id"])
    dev = next(f for f in summary["new_findings"] if store.get(f)["data"]["finding_type"] == "SEQUENCE_DEVIATION")
    answer = explain(store, dev)
    assert answer["expected"] == "done" and answer["actual"] == "crash"
    assert answer["pattern"]["occurrences_total"] >= 3 and answer["events"]
    assert answer["proven"] and answer["uncertain"]
    assert explain(store, p["id"])["project"] == "why"


def test_gpt_researcher_retriever_captures_pages_for_the_knowledge_store():
    from living_assistant.tools import deepresearchtools as d

    search = lambda q, num=5: {"ok": True, "results": [{"link": "https://a.example/x", "title": "A"},
                                                      {"link": "https://b.example/y", "title": "B"}]}
    extract = lambda url: {"ok": True, "url": url, "title": "T", "text": "Relevant findings about compression ratios. " * 20}
    run = d.make_research_runner(search, extract, gate=lambda url, purpose: None, base_url="http://127.0.0.1:1/v1", model="m")
    result = run("compression ratios", depth="quick")
    assert result["ok"] and {p["url"] for p in result["pages"]} == {"https://a.example/x", "https://b.example/y"}
    import gpt_researcher.agent as agent

    assert agent.get_retrievers({}, None)[0].requires_scraping is False  # every researcher uses our retriever
