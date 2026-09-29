from __future__ import annotations

from typing import Callable

from .base import Tool


def _brief(record: dict) -> dict:
    notes = record.get("notes") or []
    last_check = record.get("last_check") or {}
    return {
        "id": record["id"],
        "goal": record["goal"],
        "status": record["status"],
        "rounds": f"{record['rounds']}/{record['max_rounds']}",
        "check_command": record.get("check_command"),
        "last_check_passed": last_check.get("passed") if last_check else None,
        "latest_progress": notes[-3:],
        "last_error": record.get("last_error"),
    }


def build_goal_tools(get_runner: Callable) -> list[Tool]:
    def goal_start(goal: str, check_command: str = "", cwd: str = ".", max_rounds: int = 12):
        runner = get_runner()
        active = runner.current_goal()
        if active:
            return {
                "ok": False,
                "error": f"You are already working inside long-running goal {active}. Do the work directly with "
                         "file, shell and search tools instead of starting another goal.",
            }
        result = runner.start(goal, check_command=check_command, cwd=cwd, max_rounds=max_rounds)
        return {"ok": True, "goal": _brief(result)} if result.get("ok") else result

    def goal_status(goal_id: str = ""):
        runner = get_runner()
        if goal_id:
            record = runner.store.get(goal_id)
            return {"ok": True, "goal": _brief(record)} if record else {"ok": False, "error": f"Unknown goal {goal_id}."}
        return {"ok": True, "goals": [_brief(r) for r in runner.store.list(10)]}

    def goal_resume(goal_id: str):
        result = get_runner().resume(goal_id)
        return {"ok": True, "goal": _brief(result)} if result.get("ok") else result

    def goal_cancel(goal_id: str):
        result = get_runner().cancel(goal_id)
        return {"ok": True, "goal": _brief(result)} if result.get("ok") else result

    return [
        Tool(
            "goal_start",
            (
                "Start a long-running background goal that keeps working across many steps and restarts until it is done, "
                "e.g. 'fix the failing tests', 'keep fixing until the project builds'. Give check_command (like "
                "'pytest -q' or 'npm test') to finish only when that command succeeds. Returns immediately with a goal id."
            ),
            {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "What must be achieved, stated as an outcome."},
                    "check_command": {"type": "string", "description": "Optional command whose success proves the goal is met."},
                    "cwd": {"type": "string", "description": "Workspace folder or registered project to work in.", "default": "."},
                    "max_rounds": {"type": "integer", "default": 12},
                },
                "required": ["goal"],
            },
            goal_start,
        ),
        Tool("goal_status", "Show progress of long-running background goals (or one goal by id).",
             {"type": "object", "properties": {"goal_id": {"type": "string"}}}, goal_status),
        Tool("goal_resume", "Resume a paused, blocked or interrupted long-running goal where it left off.",
             {"type": "object", "properties": {"goal_id": {"type": "string"}}, "required": ["goal_id"]}, goal_resume),
        Tool("goal_cancel", "Stop a long-running background goal.",
             {"type": "object", "properties": {"goal_id": {"type": "string"}}, "required": ["goal_id"]}, goal_cancel),
    ]
