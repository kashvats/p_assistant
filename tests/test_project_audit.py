import json
import sys
from pathlib import Path

import pytest

from living_assistant.companies.audit_gate import audit_module
from living_assistant.core.workspace import Workspace
from living_assistant.tools.projects import ProjectRegistry, build_project_tools
from test_companies import FakeOrchestrator, make_engine, run_until_settled

audit = audit_module()


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_static_checks_find_real_problems(tmp_path):
    write(tmp_path, "app.py", "import subprocess\nsubprocess.run(cmd, shell=True)\npassword = 'hunter2hunter2'\n")
    write(tmp_path, "broken.py", "def f(:\n")
    write(tmp_path, "tests/test_x.py", "eval('1')\n")  # tests are not security-scanned
    write(tmp_path, "venv/lib/bad.py", "def (\n")  # dependency folders are skipped
    write(tmp_path, "requirements.txt", "flask\npytest==8.0.0\n")
    write(tmp_path, "templates/index.html", "<html><head></head><body><img src=a.png><h1>a</h1><h1>b</h1></body></html>")
    syn = audit.syntax(tmp_path)
    assert not syn["ok"] and [e["path"] for e in syn["errors"]] == ["broken.py"]
    sec = audit.security(tmp_path)
    rules = {(f["path"], f["rule"]) for f in sec["findings"]}
    assert ("app.py", "subprocess-shell-true") in rules and ("app.py", "hardcoded-credential-assignment") in rules
    assert not any(path.startswith("tests/") for path, _ in rules) and not sec["ok"]
    assert audit.security(tmp_path, files=["broken.py"])["findings"] == []  # scoped to changed files
    dep = audit.deps(tmp_path)
    assert dep["issues"][0]["rule"] == "python-unbounded-dependency" and dep["issues"][0]["dependency"] == "flask"
    codes = {f["code"] for f in audit.seo(tmp_path)["findings"]}
    assert {"SEO-TITLE-MISSING", "SEO-IMG-ALT-MISSING", "SEO-H1-MULTIPLE", "SEO-LANG-MISSING"} <= codes
    health = audit.health(tmp_path)
    assert 0 <= health["score"] < 80 and health["findings"][0]["severity"] == "critical"


def test_checks_are_discovered_and_run_with_the_project_interpreter(tmp_path, monkeypatch):
    write(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")
    write(tmp_path, "tests/test_calc.py", "from calc import add\n\ndef test_add():\n    assert add(2, 2) == 4\n")
    write(tmp_path, "conftest.py", "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\n")
    assert "pytest" in audit.checks(tmp_path)["plan"][0]["args"]
    monkeypatch.setattr(audit, "project_python", lambda root: sys.executable)  # this venv has pytest
    ok = audit.run_checks(tmp_path)
    assert ok["passed"] is True and "1 passed" in ok["results"][0]["summary"]
    write(tmp_path, "tests/test_calc.py", "from calc import add\n\ndef test_add():\n    assert add(2, 2) == 5\n")
    bad = audit.run_checks(tmp_path)
    assert bad["passed"] is False and "1 failed" in bad["results"][0]["summary"]


def test_cli_prints_json(tmp_path, capsys):
    write(tmp_path, "a.py", "x = 1\n")
    assert audit.main(["audit.py", "syntax", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_one_project_audit_tool_backed_by_the_skill_script(tmp_path):
    write(tmp_path, "a.py", "eval(input())\ndef unused():\n    pass\n")
    write(tmp_path, "templates/page.html", "<div>{{ body|safe }}</div>")
    tools = {t.name: t.handler for t in build_project_tools(Workspace([tmp_path]), ProjectRegistry(tmp_path / "p.json"))}
    out = tools["project_audit"](path=".", check="security")
    assert out["ok"] and out["passed"] is False
    assert {f["rule"] for f in out["findings"]} >= {"dangerous-call:eval", "template-safe-filter"}
    full = tools["project_audit"](path=".")  # the coding API / CLI report shape, plus health and SEO
    assert {"lint", "dead_code", "security", "dependencies", "health_score", "dimensions", "seo"} <= set(full)
    assert full["dead_code"]["candidates"][0]["name"] == "unused"
    assert tools["project_audit"](path=".", check="run-checks")["ok"] is False  # running code is not offered here


class WritesCode(FakeOrchestrator):
    """A worker that writes given code into its deliverables (and a failing test if asked)."""

    def __init__(self, code, test=None):
        super().__init__()
        self.code, self.test = code, test

    def run_stream(self, brief, *a, **k):
        if brief.startswith("VERIFY"):
            yield from super().run_stream(brief, *a, **k)
            return
        workspace = Path(brief.split("Work in ", 1)[1].split(". Use the tools", 1)[0])
        for line in brief.splitlines():
            if line.startswith("- ") and line[2:].startswith(str(workspace)):
                Path(line[2:]).write_text(self.code, encoding="utf-8")
        if self.test:
            write(workspace, "tests/test_app.py", self.test)
        yield {"type": "final", "text": "Done."}


@pytest.mark.parametrize("code,reason", [
    ("def broken(:\n", "Python files parse"),
    ("import os\nresult = eval(os.environ['X'])\n", "no critical/high security findings"),
])
def test_quality_gate_rejects_broken_or_unsafe_work(tmp_path, code, reason):
    engine = make_engine(tmp_path, WritesCode(code))
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    run_until_settled(engine, project["id"])
    first = engine.store.tasks(project["id"])[0]
    assert first["state"] == "failed" and reason in first["feedback"]


def test_tests_gate_only_runs_with_permission_and_then_decides(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "project_python", lambda root: sys.executable)
    asked = []
    status = {"value": "pending"}
    engine = make_engine(tmp_path, WritesCode("print('hello')\n", test="def test_x():\n    assert 1 == 2\n"))
    engine.request_approval = lambda action, reason: asked.append(action) or {"allowed": False, "approval_id": "t1"}
    engine.approval_status = lambda approval_id: status["value"]
    co = engine.create_from_template("software")
    project = engine.start_project("Build a hello script with docs", co["id"], background=False)
    assert len(asked) == 1 and "run its automated tests" in asked[0]  # asked once, at plan approval
    assert engine.store.project(project["id"])["checks_approval_id"] == "t1"
    engine.tick(run_inline=True)
    first = engine.store.tasks(project["id"])[0]
    assert first["state"] == "completed"  # failing test not run without permission; static gates passed
    assert first["evidence"]["audit"]["tests"]["ran"] is False and len(asked) == 1  # not asked again
    status["value"] = "approved"
    engine.tick(run_inline=True)
    second = engine.store.tasks(project["id"])[1]
    assert second["state"] != "completed" and "automated tests pass" in (second["feedback"] or "")
    assert engine.store.project(project["id"])["checks_approved"] == 1
