import json
from pathlib import Path

import pytest

from living_assistant.companies.engine import CompanyEngine, extract_json, find_cycle, parse_args
from living_assistant.companies.store import CompanyStore, InvalidTransition
from living_assistant.skills.library import SkillLibrary, builtin_root

PLAN = {
    "spec": {"goal": "A greeting script", "requirements": ["prints hello"], "acceptance": ["hello.py prints hello"]},
    "tasks": [
        {"key": "write-script", "title": "Write hello.py", "description": "Create hello.py that prints hello",
         "department": "backend", "depends": [], "acceptance": ["hello.py prints hello"], "deliverables": ["hello.py"]},
        {"key": "write-readme", "title": "Write README", "description": "Explain how to run hello.py",
         "department": "docs", "depends": ["write-script"], "acceptance": ["README.md explains running it"],
         "deliverables": ["README.md"]},
    ],
}


class FakeOrchestrator:
    """Stands in for the model: workers write their deliverables with a (real) file write, verifiers read and pass."""

    tools = {"read_file": None, "write_file": None, "run_command": None, "desktop_analyze_screen": None, "skill_install": None}

    def __init__(self, workers_write=True, verifier_inspects=True):
        self.workers_write = workers_write
        self.verifier_inspects = verifier_inspects
        self.contexts = []

    def run_stream(self, brief, context="", session_id=None, pinned_tools=(), excluded_tools=(), source="text",
                   max_steps=None):
        self.contexts.append((context, tuple(excluded_tools), tuple(pinned_tools), brief.startswith("VERIFY")))
        if brief.startswith("VERIFY"):
            if self.verifier_inspects:
                yield {"type": "tool", "tool": "read_file", "status": "started", "args": '{"path": "x"}'}
                yield {"type": "tool", "tool": "read_file", "status": "completed", "ok": True}
            yield {"type": "final", "text": json.dumps({"verdict": "pass", "criteria": [
                {"criterion": "c", "ok": True, "evidence": "opened the file"}], "problems": []})}
            return
        workspace = brief.split("Work in ", 1)[1].split(". Use the tools", 1)[0]
        for line in brief.splitlines():
            if line.startswith("- ") and line[2:].startswith(workspace) and self.workers_write:
                target = Path(line[2:])
                yield {"type": "tool", "tool": "write_file", "status": "started",
                       "args": json.dumps({"path": str(target), "content": "print('hello')" * 50})[:300]}
                target.write_text("print('hello')\n", encoding="utf-8")
                yield {"type": "tool", "tool": "write_file", "status": "completed", "ok": True}
        yield {"type": "final", "text": "Done: wrote the files."}


def make_engine(tmp_path, orchestrator=None, plan=PLAN):
    store = CompanyStore(tmp_path / "c.sqlite3")
    lib = SkillLibrary(tmp_path / "skills", builtin=builtin_root())
    engine = CompanyEngine(store, workspace_root=tmp_path / "ws", get_orchestrator=lambda: orchestrator,
                           complete=lambda messages, max_tokens=0: json.dumps(plan), skill_library=lib,
                           background_planning=False)
    return engine


def run_until_settled(engine, project_id, rounds=40):
    for _ in range(rounds):
        engine.tick(run_inline=True)
        if engine.store.project(project_id)["status"] in ("delivered", "needs_user_input", "failed"):
            break
    return engine.store.project(project_id)


def test_software_template_builds_full_hierarchy(tmp_path):
    engine = make_engine(tmp_path)
    company = engine.create_from_template("software")
    keys = {d["key"] for d in company["departments"]}
    assert {"product", "design", "architecture", "frontend", "backend", "data", "ai", "integrations", "infra",
            "security", "qa", "verification", "docs"} <= keys
    by_key = {e["key"]: e for e in company["employees"]}
    assert by_key["backend-engineer"]["reports_to"] == by_key["backend-lead"]["id"]
    assert by_key["backend-lead"]["reports_to"] == by_key["engineering-director"]["id"]
    assert all(s["tier"] != "learning" for e in company["employees"] for s in e["skills"])  # every skill is installed


def test_task_lifecycle_rules(tmp_path):
    engine = make_engine(tmp_path)
    co = engine.create_from_template("office")
    store = engine.store
    p = store.create_project(name="p", request="do a thing", lead_company=co["id"], companies=[], workspace=str(tmp_path))
    a = store.add_task(p["id"], key="a", title="A", acceptance=["x"])
    b = store.add_task(p["id"], key="b", title="B", depends=["a"], acceptance=["y"])
    with pytest.raises(InvalidTransition):
        store.transition(b["id"], "ready")  # dependency not completed
    with pytest.raises(InvalidTransition):
        store.transition(a["id"], "completed")  # never directly
    emps = store.employees(co["id"])
    store.update_task(a["id"], assignee=emps[0]["id"], evidence={"checks": [{"name": "c", "ok": True}]})
    for s in ("ready", "assigned", "in_progress", "review", "verification"):
        store.transition(a["id"], s)
    with pytest.raises(InvalidTransition):
        store.complete_task(a["id"], verifier=emps[0]["id"], verdict={"verdict": "pass"})  # self-verification
    with pytest.raises(InvalidTransition):
        store.complete_task(a["id"], verifier=emps[1]["id"], verdict={"verdict": "fail"})
    assert store.complete_task(a["id"], verifier=emps[1]["id"], verdict={"verdict": "pass"})["state"] == "completed"
    assert store.transition(b["id"], "ready")["state"] == "ready"


def test_plan_validation_catches_cycles_and_unknowns(tmp_path):
    engine = make_engine(tmp_path)
    co = engine.create_from_template("software")
    p = engine.store.create_project(name="p", request="x" * 10, lead_company=co["id"], companies=[], workspace=str(tmp_path))
    deps = engine._department_map(p)
    bad = {"tasks": [{"key": "a", "title": "A", "department": "backend", "depends": ["b"], "acceptance": ["x"]},
                     {"key": "b", "title": "B", "department": "nowhere", "depends": ["a"], "acceptance": ["x"]},
                     {"key": "c", "title": "C", "department": "qa", "depends": ["zzz"], "acceptance": [],
                      "deliverables": ["../escape.txt"]}]}
    _, problems = engine.validate_plan(bad, deps)
    text = " | ".join(problems)
    assert "circular dependency" in text and "unknown department" in text and "unknown task zzz" in text
    assert "no acceptance criteria" in text and "outside the workspace" in text
    assert find_cycle({"a": ["b"], "b": []}) is None


def test_project_runs_to_verified_delivery(tmp_path):
    fake = FakeOrchestrator()
    engine = make_engine(tmp_path, fake)
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    assert project["status"] == "running"
    final = run_until_settled(engine, project["id"])
    assert final["status"] == "delivered", final.get("error")
    tasks = engine.store.tasks(project["id"])
    assert [t["key"] for t in tasks] == ["write-script", "write-readme", "final-check"]
    for t in tasks:
        assert t["state"] == "completed" and t["assignee"] != t["verifier"]
        assert t["evidence"]["verified_by"] == t["verifier"]
    assert (Path(final["workspace"]) / "DELIVERY_REPORT.md").is_file()
    worker_ctx, excluded, pinned, _ = fake.contexts[0]
    assert "[COMPANY EMPLOYEE:" in worker_ctx and "### Skill:" in worker_ctx
    assert "skill_install" in excluded and "team_ask" in excluded  # learning/delegation never granted to employees
    assert "desktop_analyze_screen" in excluded and set(pinned) == {"read_file", "write_file", "run_command"}
    _, v_excluded, v_pinned, is_verifier = next(c for c in fake.contexts if c[3])
    assert "write_file" in v_excluded and "write_file" not in v_pinned  # verification never alters the work


def test_claimed_but_missing_work_is_never_completed(tmp_path):
    engine = make_engine(tmp_path, FakeOrchestrator(workers_write=False))
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    final = run_until_settled(engine, project["id"])
    first = engine.store.tasks(project["id"])[0]
    assert first["state"] == "failed" and "deliverable exists: hello.py" in first["feedback"]
    assert first["attempts"] == 2  # balanced mode retries once
    assert final["status"] == "needs_user_input"


def test_verifier_that_inspected_nothing_cannot_pass(tmp_path):
    engine = make_engine(tmp_path, FakeOrchestrator(verifier_inspects=False))
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    run_until_settled(engine, project["id"])
    first = engine.store.tasks(project["id"])[0]
    assert first["state"] != "completed" and "without opening or running anything" in (first["feedback"] or "")


def test_supervised_mode_waits_for_plan_approval(tmp_path):
    engine = make_engine(tmp_path, FakeOrchestrator())
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], mode="supervised", background=False)
    assert project["status"] == "awaiting_plan_approval"
    engine.tick(run_inline=True)
    assert all(t["state"] == "draft" for t in engine.store.tasks(project["id"]))
    engine.approve_plan(project["id"])
    assert run_until_settled(engine, project["id"])["status"] == "delivered"


def test_restart_recovers_interrupted_tasks(tmp_path):
    engine = make_engine(tmp_path)
    co = engine.create_from_template("office")
    p = engine.store.create_project(name="p", request="x" * 10, lead_company=co["id"], companies=[], workspace=str(tmp_path))
    t = engine.store.add_task(p["id"], key="a", title="A", acceptance=["x"])
    for s in ("ready", "assigned", "in_progress"):
        engine.store.transition(t["id"], s)
    reopened = CompanyStore(tmp_path / "c.sqlite3")
    assert reopened.recover_interrupted() == [t["id"]]
    assert reopened.task(t["id"])["state"] == "ready"


def test_company_isolation(tmp_path):
    engine = make_engine(tmp_path)
    a = engine.create_from_template("office")
    b = engine.create_from_template("research")
    p = engine.store.create_project(name="p", request="x" * 10, lead_company=a["id"], companies=[], workspace=str(tmp_path))
    with pytest.raises(ValueError):
        engine.store.add_task(p["id"], key="t", title="T", company_id=b["id"])
    emp = engine.store.employees(a["id"])[0]
    portfolio = {s["name"] for s in engine.skill_portfolio(emp)}
    assert "research-synthesis" not in portfolio  # the other company's library is not visible
    with pytest.raises(ValueError):
        engine.store.add_employee(a["id"], name="X", title="Y", reports_to=engine.store.employees(b["id"])[0]["id"])


def test_improvised_company_always_has_planner_and_verifier(tmp_path):
    design = {"name": "Bakery Ops", "departments": [{"name": "Kitchen", "employees": [
        {"name": "Ana", "title": "Recipe Writer", "level": "lead", "skills": ["content-writing", "made-up-skill"]}]}]}
    engine = make_engine(tmp_path, plan=design)
    company = engine.create_from_description("run my bakery's paperwork")
    keys = {e["key"] for e in company["employees"]}
    assert "project-director" in keys and "verifier" in keys
    ana = next(e for e in company["employees"] if e["name"] == "Ana")
    assert {"name": "made-up-skill", "tier": "learning"} in ana["skills"]  # visible gap, not a loadable skill


def test_context_compaction_keeps_the_current_request():
    from living_assistant.agents.orchestrator import Orchestrator
    payload = "Working context:\n" + "skill text " * 3000 + "\n\n[CURRENT REQUEST]\nWrite word_count.py now."
    out = Orchestrator.compact_context([{"role": "system", "content": "s"}, {"role": "user", "content": payload}], max_tokens=4096)
    assert out[1]["content"].endswith("[CURRENT REQUEST]\nWrite word_count.py now.")
    assert len(out[1]["content"]) <= 7168


def test_excluded_tools_are_blocked_even_when_called_by_name():
    from unittest.mock import MagicMock
    from living_assistant.agents.orchestrator import Orchestrator
    from living_assistant.core.model_provider import ModelManager
    from living_assistant.tools.base import Tool
    ran = []
    mm = MagicMock(spec=ModelManager)
    mm.provider = MagicMock()
    orc = Orchestrator(mm, "m", [Tool("write_file", "write", {"type": "object"}, lambda **k: ran.append(k) or {"ok": True})],
                       MagicMock())
    mm.provider.chat_stream.return_value = [{"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "x"}}}]}}]
    orc.max_steps = 1
    events = list(orc.run_stream("verify", "", excluded_tools=("write_file",)))
    done = next(e for e in events if e.get("type") == "tool" and e.get("status") == "completed")
    assert done["ok"] is False and "not available" in done["error"] and ran == []


def test_chat_tools_create_and_run_a_company_project(tmp_path):
    from living_assistant.companies.tools import build_company_tools
    engine = make_engine(tmp_path, FakeOrchestrator())
    tools = {t.name: t.handler for t in build_company_tools(lambda: engine)}
    made = tools["company_create"](template="software", name="Acme Software")
    assert made["ok"] and len(made["company"]["employees"]) == 22
    assert tools["company_create"]()["ok"] is False
    started = tools["project_start"](request="Build a hello script with docs", company="acme")  # by partial name
    assert started["ok"], started
    run_until_settled(engine, started["project_id"])
    status = tools["project_status"](project=started["project_id"])
    assert status["status"] == "delivered" and all(t["state"] == "completed" for t in status["tasks"])
    assert tools["project_control"](project=started["project_id"], action="explode")["ok"] is False


def test_file_writes_outside_the_project_fail_the_evidence(tmp_path):
    engine = make_engine(tmp_path)
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    task = engine.store.tasks(project["id"])[0]
    outside = str(tmp_path / "ws" / "elsewhere.txt")
    turn = {"answer": "done", "error": None, "approval_id": None,
            "calls": [{"tool": "write_file", "ok": True, "args": {"path": "a.txt"}, "error": ""},  # relative: in project
                      {"tool": "write_file", "ok": True, "args": {"path": outside}, "error": ""}]}
    checks = {c["name"]: c for c in engine.collect_evidence(project, task, turn)["checks"]}
    scope = checks["all file changes stayed inside the project workspace"]
    assert not scope["ok"] and "elsewhere.txt" in scope["detail"] and "a.txt" not in scope["detail"]


def test_project_scope_confines_workspace_paths(tmp_path):
    from living_assistant.core.scope import project_scope
    from living_assistant.core.workspace import Workspace, WorkspaceViolation
    ws = Workspace([tmp_path / "ws"])
    proj = tmp_path / "ws" / "company_projects" / "p1"
    proj.mkdir(parents=True)
    assert ws.resolve("a.txt") == (tmp_path / "ws" / "a.txt").resolve()  # normal chat: workspace root
    with project_scope(proj):
        assert ws.resolve("a.txt") == (proj / "a.txt").resolve()
        assert ws.resolve(".") == proj.resolve()
        with pytest.raises(WorkspaceViolation):
            ws.resolve(str(tmp_path / "ws" / "other.txt"))
        with pytest.raises(WorkspaceViolation):
            ws.resolve("../../secret.txt")
    assert ws.resolve("a.txt") == (tmp_path / "ws" / "a.txt").resolve()  # scope ends with the turn


def test_trusted_project_runs_build_commands_without_asking(tmp_path):
    from living_assistant.core.scope import project_scope
    from living_assistant.core.workspace import Workspace
    from living_assistant.tools.shell import ProcessRegistry, build_shell_tools

    class Approvals:
        def __init__(self):
            self.asked = []

        def request(self, action, reason, kind="execute", **_):
            self.asked.append(action)
            return {"allowed": False, "approval_id": "a1"}

    ws = Workspace([tmp_path / "ws"])
    proj = tmp_path / "ws" / "p"
    proj.mkdir(parents=True)
    approvals = Approvals()
    tools = build_shell_tools(ws, approvals, {}, ProcessRegistry(tmp_path / "procs.json"))
    run = {t.name: t.handler for t in tools}["run_command"]
    with project_scope(proj):  # not trusted: asks
        assert run(command="python -c \"print(1)\"")["approval_required"]
    with project_scope(proj, trust_commands=True):
        out = run(command="python -c \"print(41+1)\"")
        assert out.get("ok") and "42" in str(out.get("stdout"))
    assert len(approvals.asked) == 1
    run(command="python -c \"print(1)\"")  # outside any project scope: still asks
    assert len(approvals.asked) == 2


def test_existing_folder_project_and_blueprint_planning(tmp_path):
    seen = []
    plan = {"spec": {"goal": "shop"}, "tasks": [{"key": "a", "title": "Add a cart", "description": "cart",
                                                  "department": "backend", "acceptance": ["cart works"]}]}
    engine = make_engine(tmp_path, FakeOrchestrator(), plan=plan)
    engine.complete = lambda messages, max_tokens=0: seen.append(messages[0]["content"]) or json.dumps(plan)
    existing = tmp_path / "ws" / "my-shop"
    existing.mkdir(parents=True)
    (existing / "app.py").write_text("print('old')", encoding="utf-8")
    (existing / "node_modules").mkdir()
    (existing / "node_modules" / "junk.js").write_text("x", encoding="utf-8")
    engine.resolve_folder = lambda raw: tmp_path / "ws" / raw
    co = engine.create_from_template("software")
    project = engine.start_project("Improve my online shop: add a shopping cart to the store", co["id"],
                                   folder="my-shop", background=False)
    assert project["workspace"] == str(existing.resolve()) and project["existing_folder"]
    assert "PRODUCT BLUEPRINT (blueprint-ecommerce)" in seen[0] and "app.py" in seen[0] and "junk.js" not in seen[0]
    final = run_until_settled(engine, project["id"])
    assert final["status"] == "delivered" and not (existing / "DELIVERY_REPORT.md").exists()
    assert (existing / "app.py").read_text(encoding="utf-8") == "print('old')"  # untouched by the fake worker
    with pytest.raises(ValueError):
        engine.start_project("Improve a missing folder please", co["id"], folder="nope", background=False)


def test_approval_granted_during_the_turn_reruns_without_using_an_attempt(tmp_path):
    class AsksOnce(FakeOrchestrator):
        asked = False

        def run_stream(self, brief, *a, **k):
            if not brief.startswith("VERIFY") and not AsksOnce.asked:
                AsksOnce.asked = True
                yield {"type": "tool", "tool": "run_command", "status": "started", "args": '{"command": "python -m venv venv"}'}
                yield {"type": "tool", "tool": "run_command", "status": "completed", "ok": False, "approval_id": "ap1"}
                yield {"type": "final", "text": "Please approve ap1."}
                return
            yield from super().run_stream(brief, *a, **k)

    engine = make_engine(tmp_path, AsksOnce())
    engine.approval_status = lambda approval_id: "approved"  # the user approved before the turn was graded
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    assert run_until_settled(engine, project["id"])["status"] == "delivered"
    first = engine.store.tasks(project["id"])[0]
    assert first["attempts"] == 1


def test_failures_become_company_lessons_and_employees_know_the_os(tmp_path):
    engine = make_engine(tmp_path, FakeOrchestrator(workers_write=False))
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    run_until_settled(engine, project["id"])
    lessons = engine.store.lessons(co["id"])
    assert lessons and "deliverable exists: hello.py" in lessons[0]
    assert len(lessons) == 1  # the same lesson is stored once
    context = engine.employee_context(engine.store.employees(co["id"])[-1], engine.store.project(project["id"]))
    assert "Lessons from earlier work" in context and "This machine:" in context


def test_parsers():
    assert extract_json("<think>{no}</think> sure: ```json\n{\"a\": 1}\n```") == {"a": 1}
    assert extract_json('text {"b": {"c": "}"}} more') == {"b": {"c": "}"}}
    assert parse_args('{"path": "C:\\\\w\\\\a.py", "content": "very long tex')["path"] == "C:\\w\\a.py"
