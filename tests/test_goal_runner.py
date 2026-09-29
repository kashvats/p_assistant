from __future__ import annotations

import sys

from living_assistant.core.model_provider import ModelError
from living_assistant.system.goal_runner import GoalRunner, GoalStore


def _runner(tmp_path, replies, approval=None, calls=None):
    """replies: list of strings or exceptions returned by successive rounds."""
    replies = list(replies)
    seen = calls if calls is not None else []

    def run_round(goal, checkpoint, session_id):
        seen.append(checkpoint)
        item = replies.pop(0) if replies else "STATUS: continue - still working"
        if isinstance(item, Exception):
            raise item
        return item

    events = []
    runner = GoalRunner(
        GoalStore(tmp_path / "goals.sqlite3"),
        run_round=run_round,
        resolve_cwd=lambda raw: tmp_path,
        approval=approval,
        publish=lambda event, **data: events.append(event),
        model_retry_seconds=0,
    )
    runner.events = events
    return runner


def _wait(runner, gid):
    runner._threads[gid].join(timeout=30)
    return runner.store.get(gid)


def _check(tmp_path):
    """A check command that passes only once the 'fixed' marker file exists."""
    script = tmp_path / "check.py"
    script.write_text("import pathlib, sys\nsys.exit(0 if pathlib.Path('fixed').exists() else 1)\n", encoding="utf-8")
    return f'"{sys.executable}" "{script}"'


def test_goal_continues_across_rounds_until_check_passes(tmp_path):
    calls = []

    def fix_on_round_two(goal, checkpoint, session_id):
        calls.append(checkpoint)
        if len(calls) == 2:
            (tmp_path / "fixed").write_text("ok")
            return "Patched the bug.\nSTATUS: continue - fixed the import error"
        return "Looked around.\nSTATUS: done - I think it works"  # model claims done; the check disagrees

    runner = _runner(tmp_path, [])
    runner.run_round = fix_on_round_two
    started = runner.start("make the check pass", check_command=_check(tmp_path), check_approved=True)
    record = _wait(runner, started["id"])
    assert record["status"] == "completed"
    assert record["rounds"] == 2
    assert [n["check_passed"] for n in record["notes"]] == [False, True]
    # Round 2 resumed from a checkpoint containing round 1's progress and failing check output.
    assert "round 1: I think it works [check failed]" in calls[1]
    assert "Last check output (exit 1" in calls[1]


def test_goal_without_check_completes_when_model_reports_done(tmp_path):
    runner = _runner(tmp_path, ["STATUS: continue - step one", "STATUS: done - all finished"])
    record = _wait(runner, runner.start("summarize the notes")["id"])
    assert record["status"] == "completed" and record["rounds"] == 2
    assert record["notes"][-1]["summary"] == "all finished"


def test_blocked_goal_pauses_and_resume_continues_where_it_left_off(tmp_path):
    calls = []
    runner = _runner(tmp_path, ["STATUS: blocked - need approval to write config", "STATUS: done - wrote config"], calls=calls)
    gid = runner.start("update the config")["id"]
    record = _wait(runner, gid)
    assert record["status"] == "blocked" and "need approval" in record["last_error"]
    runner.resume(gid)
    record = _wait(runner, gid)
    assert record["status"] == "completed" and record["rounds"] == 2
    assert "round 1: need approval to write config" in calls[1]


def test_round_budget_pauses_and_resume_extends_it(tmp_path):
    runner = _runner(tmp_path, [])
    gid = runner.start("endless task", max_rounds=2)["id"]
    record = _wait(runner, gid)
    assert record["status"] == "paused" and record["rounds"] == 2 and "budget" in record["last_error"]
    runner.resume(gid, extra_rounds=1)
    record = _wait(runner, gid)
    assert record["rounds"] > 2


def test_model_outage_pauses_goal_instead_of_losing_it(tmp_path):
    runner = _runner(tmp_path, [ModelError("server down")] * 3 + ["STATUS: done - ok"])
    gid = runner.start("anything")["id"]
    record = _wait(runner, gid)
    assert record["status"] == "paused" and "Model unavailable" in record["last_error"]
    assert record["rounds"] == 0
    assert _wait(runner, runner.resume(gid)["id"])["status"] == "completed"


def test_interrupted_goals_resume_after_restart(tmp_path):
    first = _runner(tmp_path, [])
    record = first.store.create("resume me", "", str(tmp_path), 5, check_approved=True)
    first.store.update(record["id"], status="running", rounds=1)  # simulate a crash mid-goal
    second = _runner(tmp_path, ["STATUS: done - finished after restart"])
    assert second.resume_interrupted() == [record["id"]]
    done = _wait(second, record["id"])
    assert done["status"] == "completed" and done["rounds"] == 2
    assert any(n["status"] == "resumed" for n in done["notes"])


def test_destructive_check_commands_are_refused(tmp_path):
    runner = _runner(tmp_path, [])
    result = runner.start("clean up", check_command="rm -rf /")
    assert result["ok"] is False and "refused" in result["error"]


def test_model_supplied_check_command_needs_one_time_approval(tmp_path):
    class Approvals:
        def __init__(self):
            self.allowed = False
            self.requests = 0

        def request(self, action, reason, kind):
            self.requests += 1
            return {"allowed": self.allowed, "pending": not self.allowed, "approval_id": "ap1"}

    approvals = Approvals()
    (tmp_path / "fixed").write_text("ok")
    runner = _runner(tmp_path, ["STATUS: continue - checked"], approval=approvals)
    gid = runner.start("verify", check_command=_check(tmp_path))["id"]
    record = _wait(runner, gid)
    assert record["status"] == "blocked" and "ap1" in record["last_error"] and record["rounds"] == 0
    approvals.allowed = True
    record = _wait(runner, runner.resume(gid)["id"])
    assert record["status"] == "completed" and record["check_approved"] is True


def test_cancel_stops_an_active_goal(tmp_path):
    runner = _runner(tmp_path, [])
    gid = runner.start("long job", max_rounds=50)["id"]
    runner.cancel(gid)
    assert _wait(runner, gid)["status"] == "cancelled"


def test_goal_rounds_cannot_start_nested_goals(tmp_path):
    from living_assistant.tools.goaltools import build_goal_tools

    holder = {}
    nested = []

    def run_round(goal, checkpoint, session_id):
        tools = {t.name: t.handler for t in build_goal_tools(lambda: holder["runner"])}
        nested.append(tools["goal_start"]("fix the bug so tests pass"))  # what the model did live
        return "STATUS: done - fixed directly"

    runner = _runner(tmp_path, [])
    runner.run_round = run_round
    holder["runner"] = runner
    record = _wait(runner, runner.start("fix the bug")["id"])
    assert record["status"] == "completed"
    assert nested[0]["ok"] is False and "already working inside" in nested[0]["error"]
    assert len(runner.store.list()) == 1
    assert runner.current_goal() is None
