from typing import List, Dict, Any
from pathlib import Path
from .base import Tool
from ..task_graph import TaskGraphManager

def build_planning_tools(db_path: Path | TaskGraphManager) -> List[Tool]:
    graph = db_path if isinstance(db_path, TaskGraphManager) else TaskGraphManager(db_path)

    def add_plan_task(task_id: str, description: str, dependencies: List[str] = None) -> dict:
        """Add a new task node to the long-term planning DAG."""
        node = graph.add_task(task_id, description, dependencies)
        return {"ok": True, "task": node.__dict__}

    def complete_plan_task(task_id: str, result: str) -> dict:
        """Mark a long-term planning task as completed."""
        node = graph.get_task(task_id)
        if not node:
            return {"ok": False, "error": "Task not found."}
        graph.update_task_status(task_id, "completed", result)
        return {"ok": True, "message": f"Task {task_id} completed."}

    def fail_plan_task(task_id: str, error_message: str) -> dict:
        """Mark a long-term planning task as failed."""
        node = graph.get_task(task_id)
        if not node:
            return {"ok": False, "error": "Task not found."}
        graph.update_task_status(task_id, "failed", error_message)
        return {"ok": True, "message": f"Task {task_id} failed."}

    def get_ready_tasks() -> dict:
        """Get all pending tasks that have their dependencies met."""
        ready = graph.get_ready_tasks()
        return {"ok": True, "ready_tasks": [r.__dict__ for r in ready]}

    def clear_plan() -> dict:
        """Clear the entire planning DAG."""
        graph.clear_graph()
        return {"ok": True, "message": "DAG cleared."}

    return [
        Tool(
            "plan_add_task",
            "Add a new task node to the long-term planning DAG. Use dependencies to link tasks sequentially.",
            {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "description": {"type": "string"},
                    "dependencies": {"type": "array", "items": {"type": "string"}, "default": []},
                },
                "required": ["task_id", "description"],
            },
            add_plan_task,
        ),
        Tool(
            "plan_complete_task",
            "Mark a long-term planning task as completed and unlock dependent tasks.",
            {
                "type": "object",
                "properties": {"task_id": {"type": "string"}, "result": {"type": "string"}},
                "required": ["task_id", "result"],
            },
            complete_plan_task,
        ),
        Tool(
            "plan_fail_task",
            "Mark a long-term planning task as failed.",
            {
                "type": "object",
                "properties": {"task_id": {"type": "string"}, "error_message": {"type": "string"}},
                "required": ["task_id", "error_message"],
            },
            fail_plan_task,
        ),
        Tool(
            "plan_get_ready",
            "Get all pending tasks that have their dependencies met.",
            {"type": "object", "properties": {}},
            get_ready_tasks,
        ),
        Tool(
            "plan_clear",
            "Clear the entire planning DAG.",
            {"type": "object", "properties": {}},
            clear_plan,
        ),
    ]
