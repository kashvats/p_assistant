from __future__ import annotations

from pathlib import Path

from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.evaluation import EvaluationEngine, EvaluationStore
from living_assistant.improvements import ImprovementEngine, ImprovementStore
from living_assistant.learning.repair_loop import AutonomousRepairLoop
from living_assistant.workspace import Workspace


def _build(tmp_path, monkeypatch):
    import living_assistant.evaluation as evaluation_facade

    monkeypatch.setattr(evaluation_facade, "data_dir", lambda: tmp_path / "data")
    project = tmp_path / "project"
    project.mkdir()
    approvals = ApprovalStore(tmp_path / "approvals.sqlite3")
    approval = ApprovalManager(interactive=False, store=approvals)
    improvements = ImprovementEngine(
        Workspace([project]), approval, ImprovementStore(tmp_path / "improvements.sqlite3")
    )
    cfg = {
        "self_improvement": {
            "evaluation": {
                "enabled": True,
                "execution_provider": "host",
                "benchmark_repetitions": 1,
                "command_timeout_seconds": 10,
                "max_commands": 8,
                "copy_max_files": 100,
                "copy_max_mb": 10,
            },
            "repair": {"enabled": True, "max_cycles": 3, "max_cycles_limit": 5},
        }
    }
    evaluations = EvaluationEngine(
        improvements.workspace,
        approval,
        improvements,
        EvaluationStore(tmp_path / "evaluations.sqlite3"),
        cfg,
    )
    return project, approvals, approval, improvements, evaluations, cfg


def _approve(approvals: ApprovalStore, first: dict, retry):
    assert first["approval_required"] is True
    approvals.resolve(first["approval_id"], True)
    return retry()


def _failed_evaluation(project, approvals, improvements, evaluations):
    target = project / "calc.py"
    target.write_text("def value():\n    return 1\n")
    proposal = improvements.propose(
        "calc.py", "def value():\n    return 2\n", "bad candidate", "exercise repair loop"
    )
    command = "python -c \"import calc; assert calc.value() == 3\""
    first = evaluations.evaluate(proposal["id"], project_path=str(project), test_commands=[command])
    failed = _approve(
        approvals,
        first,
        lambda: evaluations.evaluate(proposal["id"], project_path=str(project), test_commands=[command]),
    )
    assert failed["verdict"] == "failed"
    return target, proposal, failed


def test_repair_loop_generates_and_evaluates_without_applying(tmp_path, monkeypatch):
    project, approvals, approval, improvements, evaluations, cfg = _build(tmp_path, monkeypatch)
    target, original, failed = _failed_evaluation(project, approvals, improvements, evaluations)

    def repairer(task: str, context: str):
        assert "Return JSON only" in task
        assert "failed_evaluation" in context
        return {
            "new_content": "def value():\n    return 3\n",
            "title": "repair value",
            "rationale": "Make the isolated test pass.",
        }

    loop = AutonomousRepairLoop(improvements, evaluations, approval, repairer, cfg)
    first = loop.run(failed["id"], max_cycles=2)
    result = _approve(approvals, first, lambda: loop.run(failed["id"], max_cycles=2))

    assert result["ok"] is True and result["repaired"] is True
    assert result["cycles_used"] == 1
    assert result["applied"] is False and result["promoted"] is False
    assert target.read_text() == "def value():\n    return 1\n"
    repaired = improvements.store.get(result["proposal_id"])
    assert repaired and repaired["status"] == "pending"
    evaluated = evaluations.store.get(result["evaluation_id"])
    assert evaluated and evaluated["verdict"] == "passed"
    # The single SELF_REPAIR approval authorizes the bounded loop. No hidden
    # SELF_EVALUATION approval should be created for the generated candidate.
    assert [x for x in approvals.list("pending") if x["kind"] == "SELF_EVALUATION"] == []
    assert improvements.store.get(original["id"])["status"] == "pending"


def test_repair_loop_repeats_only_up_to_approved_bound(tmp_path, monkeypatch):
    project, approvals, approval, improvements, evaluations, cfg = _build(tmp_path, monkeypatch)
    _target, _original, failed = _failed_evaluation(project, approvals, improvements, evaluations)
    calls = {"n": 0}

    def repairer(_task: str, _context: str):
        calls["n"] += 1
        value = 4 if calls["n"] == 1 else 3
        return {"new_content": f"def value():\n    return {value}\n", "title": "repair", "rationale": "retry"}

    loop = AutonomousRepairLoop(improvements, evaluations, approval, repairer, cfg)
    first = loop.run(failed["id"], max_cycles=2)
    result = _approve(approvals, first, lambda: loop.run(failed["id"], max_cycles=2))
    assert result["ok"] is True
    assert result["cycles_used"] == 2
    assert len(result["attempts"]) == 2
    assert calls["n"] == 2


def test_repair_loop_revalidates_stored_commands_before_approval(tmp_path, monkeypatch):
    project, approvals, approval, improvements, evaluations, cfg = _build(tmp_path, monkeypatch)
    _target, _proposal, failed = _failed_evaluation(project, approvals, improvements, evaluations)
    config = dict(failed["config"])
    config["test_commands"] = ["rm -rf /"]
    evaluations.store.update(failed["id"], config_json=__import__("json").dumps(config))

    loop = AutonomousRepairLoop(improvements, evaluations, approval, lambda *_: {}, cfg)
    result = loop.run(failed["id"], max_cycles=1)
    assert result["ok"] is False
    assert "no longer valid" in result["error"]
    assert "Unsafe evaluation command" in result["error"]
    assert [x for x in approvals.list("pending") if x["kind"] == "SELF_REPAIR"] == []


def test_invalid_internal_authorization_cannot_bypass_evaluation_approval(tmp_path, monkeypatch):
    project, approvals, _approval, improvements, evaluations, _cfg = _build(tmp_path, monkeypatch)
    (project / "a.txt").write_text("old")
    proposal = improvements.propose("a.txt", "new", "candidate", "test")
    command = "python -c \"print('ok')\""
    result = evaluations.evaluate(
        proposal["id"],
        project_path=str(project),
        test_commands=[command],
        _repair_authorization=object(),
    )
    assert result["ok"] is False
    assert result["internal_authorization_invalid"] is True
    assert approvals.list("pending") == []


def test_repair_authorization_is_bound_to_exact_plan(tmp_path, monkeypatch):
    project, _approvals, _approval, improvements, evaluations, _cfg = _build(tmp_path, monkeypatch)
    (project / "a.txt").write_text("old")
    proposal = improvements.propose("a.txt", "new", "candidate", "test")
    plan = evaluations._resolve_plan(
        proposal,
        None,
        str(project),
        ["python -c \"print('a')\""],
        [],
        [],
        1,
        None,
        None,
    )
    auth = evaluations._create_repair_authorization(plan, max_uses=1, ttl_seconds=600)
    result = evaluations.evaluate(
        proposal["id"],
        project_path=str(project),
        test_commands=["python -c \"print('different')\""],
        _repair_authorization=auth,
    )
    assert result["ok"] is False
    assert result["internal_authorization_invalid"] is True
    assert "does not match" in result["error"]


def test_improvement_tool_exposes_repair_only_when_loop_is_supplied(tmp_path, monkeypatch):
    from living_assistant.tools.improvementtools import build_improvement_tools

    project, _approvals, approval, improvements, evaluations, cfg = _build(tmp_path, monkeypatch)
    loop = AutonomousRepairLoop(improvements, evaluations, approval, lambda *_: {}, cfg)
    without = {tool.name for tool in build_improvement_tools(improvements, evaluations)}
    with_loop = {tool.name for tool in build_improvement_tools(improvements, evaluations, repairs=loop)}
    assert "repair_failed_improvement" not in without
    assert "repair_failed_improvement" in with_loop
