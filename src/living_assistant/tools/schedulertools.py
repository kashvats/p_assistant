from __future__ import annotations

from typing import Any
from .base import Tool


def build_scheduler_tools(scheduler: Any) -> list[Tool]:
    """Exposes structured persistent scheduling capabilities to the Orchestrator."""

    def schedule_reminder(title: str, due_at: str, message: str = "", misfire_policy: str = "fire_immediately"):
        try:
            task = scheduler.schedule_reminder(
                title=title,
                due_at=due_at,
                message=message or title,
                misfire_policy=misfire_policy,
            )
            return {"ok": True, "task": task}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def schedule_cron_task(name: str, cron_expression: str, message: str):
        try:
            task = scheduler.schedule_cron(
                name=name,
                cron_expr=cron_expression,
                action_type="notify",
                action_payload={"title": name, "message": message},
            )
            return {"ok": True, "task": task}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_scheduled_tasks(category: str | None = None, status: str | None = None):
        try:
            tasks = scheduler.list_tasks(category=category, status=status)
            return {"ok": True, "tasks": tasks, "count": len(tasks)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def cancel_scheduled_task(task_id: str):
        try:
            ok = scheduler.cancel_task(task_id)
            return {"ok": ok, "task_id": task_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def recover_missed_reminders():
        try:
            recovered = scheduler.recover_missed_tasks()
            return {"ok": True, "recovered": recovered, "count": len(recovered)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return [
        Tool(
            "schedule_reminder",
            "Schedule a persistent one-shot reminder at a specific ISO timestamp (e.g. 2026-09-25T14:30:00). Survives reboots.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the reminder"},
                    "due_at": {"type": "string", "description": "ISO format date/time string"},
                    "message": {"type": "string", "description": "Optional reminder message detail"},
                    "misfire_policy": {
                        "type": "string",
                        "enum": ["fire_immediately", "ignore"],
                        "default": "fire_immediately",
                        "description": "Action to take if system was asleep/offline at due time",
                    },
                },
                "required": ["title", "due_at"],
            },
            schedule_reminder,
        ),
        Tool(
            "schedule_cron_task",
            "Schedule a recurring reminder or task using standard 5-part cron syntax (minute hour dom month dow).",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of recurring job"},
                    "cron_expression": {"type": "string", "description": "Standard 5-part cron string e.g. '0 9 * * 1-5'"},
                    "message": {"type": "string", "description": "Notification message to deliver on schedule"},
                },
                "required": ["name", "cron_expression", "message"],
            },
            schedule_cron_task,
        ),
        Tool(
            "list_scheduled_tasks",
            "List scheduled reminders and recurring cron tasks.",
            {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["reminder", "cron", "briefing", "indexing"]},
                    "status": {"type": "string", "enum": ["active", "completed", "paused"]},
                },
            },
            list_scheduled_tasks,
        ),
        Tool(
            "cancel_scheduled_task",
            "Cancel and delete a scheduled task or reminder by ID.",
            {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of task to cancel"},
                },
                "required": ["task_id"],
            },
            cancel_scheduled_task,
        ),
        Tool(
            "recover_missed_reminders",
            "Check for and immediately trigger any reminders missed during system sleep or downtime.",
            {"type": "object", "properties": {}},
            recover_missed_reminders,
        ),
    ]
