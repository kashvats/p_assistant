"""
Hierarchical DAG manager supporting parent/child relationships, max depth constraints,
dependency resolution, execution budget tracking, and task cancellation kill-switch.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from living_assistant.agents.software_company.models import TaskNode, ExecutionBudget
from living_assistant.core.sqlite_utils import ThreadLocalSQLite


class TaskGraphError(Exception):
    """Base exception for hierarchical task graph errors."""
    pass


class MaxDepthExceededError(TaskGraphError):
    """Raised when task hierarchy depth exceeds the maximum allowed limit."""
    pass


class BudgetExceededError(TaskGraphError):
    """Raised when execution budget (steps, tokens, retries, timeout) is exceeded."""
    pass


class DependencyError(TaskGraphError):
    """Raised when dependency resolution fails or invalid dependencies are detected."""
    pass


class HierarchicalTaskGraph:
    """
    Manages recursive hierarchical task DAGs with tree depth <= 3 enforcement,
    child-before-parent dependency resolution, budget tracking, and cancellation.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        max_depth: int = 3,
        budget: ExecutionBudget | None = None,
    ) -> None:
        capped_depth = min(int(max_depth), 3)
        self.max_depth = capped_depth
        self.budget = budget or ExecutionBudget(max_depth=capped_depth)
        if self.budget.max_depth > 3:
            self.budget.max_depth = 3
        self._lock = threading.RLock()

        if db_path is None or str(db_path) == ":memory:":
            self._is_memory = True
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        else:
            self._is_memory = False
            self.conn = ThreadLocalSQLite(Path(db_path), timeout=30.0)

        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS hierarchical_task_nodes (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    role TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    dependencies TEXT NOT NULL,
                    status TEXT NOT NULL,
                    contract TEXT,
                    assigned_worker TEXT,
                    input_context TEXT,
                    output_result TEXT,
                    artifact_ids TEXT,
                    step_count INTEGER NOT NULL DEFAULT 0,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_parent_id ON hierarchical_task_nodes(parent_id)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON hierarchical_task_nodes(status)
            """)
            self.conn.commit()

    def _row_to_node(self, row: sqlite3.Row | tuple) -> TaskNode:
        if isinstance(row, sqlite3.Row):
            d = dict(row)
        else:
            # Fallback for plain tuple
            cols = [
                "id", "parent_id", "title", "description", "role", "depth",
                "dependencies", "status", "contract", "assigned_worker",
                "input_context", "output_result", "artifact_ids",
                "step_count", "tokens_used", "created_at", "updated_at"
            ]
            d = dict(zip(cols, row))

        return TaskNode(
            id=d["id"],
            parent_id=d["parent_id"],
            title=d["title"],
            description=d["description"],
            role=d["role"],
            depth=d["depth"],
            dependencies=json.loads(d["dependencies"]) if d["dependencies"] else [],
            status=d["status"],
            contract=json.loads(d["contract"]) if d["contract"] else None,
            assigned_worker=d["assigned_worker"],
            input_context=json.loads(d["input_context"]) if d["input_context"] else {},
            output_result=json.loads(d["output_result"]) if d["output_result"] else None,
            artifact_ids=json.loads(d["artifact_ids"]) if d["artifact_ids"] else [],
            step_count=d["step_count"],
            tokens_used=d["tokens_used"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def add_node(
        self,
        node_id: str,
        title: str,
        role: str,
        description: str = "",
        parent_id: Optional[str] = None,
        dependencies: list[str] | None = None,
        contract: dict[str, Any] | None = None,
        input_context: dict[str, Any] | None = None,
        assigned_worker: str | None = None,
    ) -> TaskNode:
        """
        Add a task node to the hierarchical DAG.
        Enforces maximum tree depth <= self.max_depth.
        """
        deps = dependencies or []
        ctx = input_context or {}
        now = time.time()

        with self._lock:
            # Check depth calculation
            if parent_id is not None:
                parent = self.get_node(parent_id)
                if not parent:
                    raise TaskGraphError(f"Parent node '{parent_id}' does not exist.")
                depth = parent.depth + 1
            else:
                depth = 0

            if depth > self.max_depth:
                raise MaxDepthExceededError(
                    f"Node '{node_id}' depth {depth} exceeds maximum tree depth {self.max_depth}."
                )

            node = TaskNode(
                id=node_id,
                parent_id=parent_id,
                title=title,
                description=description,
                role=role,
                depth=depth,
                dependencies=deps,
                status="pending",
                contract=contract,
                assigned_worker=assigned_worker,
                input_context=ctx,
                output_result=None,
                artifact_ids=[],
                step_count=0,
                tokens_used=0,
                created_at=now,
                updated_at=now,
            )

            self.conn.execute(
                """
                INSERT OR REPLACE INTO hierarchical_task_nodes (
                    id, parent_id, title, description, role, depth,
                    dependencies, status, contract, assigned_worker,
                    input_context, output_result, artifact_ids,
                    step_count, tokens_used, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.parent_id,
                    node.title,
                    node.description,
                    node.role,
                    node.depth,
                    json.dumps(node.dependencies),
                    node.status,
                    json.dumps(node.contract) if node.contract is not None else None,
                    node.assigned_worker,
                    json.dumps(node.input_context),
                    json.dumps(node.output_result, default=str) if node.output_result is not None else None,
                    json.dumps(node.artifact_ids, default=str),
                    node.step_count,
                    node.tokens_used,
                    node.created_at,
                    node.updated_at,
                ),
            )
            self.conn.commit()
            return node

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """Fetch a node by ID."""
        with self._lock:
            cur = self.conn.execute(
                "SELECT * FROM hierarchical_task_nodes WHERE id = ?", (node_id,)
            )
            row = cur.fetchone()
            if row:
                return self._row_to_node(row)
            return None

    def get_all_nodes(self) -> list[TaskNode]:
        """Fetch all nodes in the DAG."""
        with self._lock:
            cur = self.conn.execute("SELECT * FROM hierarchical_task_nodes ORDER BY depth ASC, created_at ASC")
            rows = cur.fetchall()
            return [self._row_to_node(r) for r in rows]

    def get_children(self, parent_id: str) -> list[TaskNode]:
        """Fetch all immediate children of a parent node."""
        with self._lock:
            cur = self.conn.execute(
                "SELECT * FROM hierarchical_task_nodes WHERE parent_id = ? ORDER BY created_at ASC",
                (parent_id,),
            )
            rows = cur.fetchall()
            return [self._row_to_node(r) for r in rows]

    def get_descendants(self, root_id: str) -> list[TaskNode]:
        """Recursively fetch all descendants of a node."""
        descendants: list[TaskNode] = []
        queue = [root_id]
        while queue:
            curr = queue.pop(0)
            children = self.get_children(curr)
            for c in children:
                descendants.append(c)
                queue.append(c.id)
        return descendants

    def update_node_status(
        self,
        node_id: str,
        status: str,
        output_result: Optional[dict[str, Any]] = None,
        artifact_ids: Optional[list[str]] = None,
    ) -> None:
        """Update node status, result, and produced artifacts."""
        with self._lock:
            node = self.get_node(node_id)
            if not node:
                raise TaskGraphError(f"Node '{node_id}' not found.")

            res_json = json.dumps(output_result, default=str) if output_result is not None else json.dumps(node.output_result, default=str)
            art_json = json.dumps(artifact_ids, default=str) if artifact_ids is not None else json.dumps(node.artifact_ids, default=str)

            self.conn.execute(
                """
                UPDATE hierarchical_task_nodes
                SET status = ?, output_result = ?, artifact_ids = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, res_json, art_json, time.time(), node_id),
            )
            self.conn.commit()

    def record_step(self, node_id: str, tokens: int = 0, delta_time: float = 0.0) -> None:
        """
        Record step and token usage for a node, updating the global ExecutionBudget.
        Raises BudgetExceededError if budget is violated.
        """
        with self._lock:
            node = self.get_node(node_id)
            if not node:
                raise TaskGraphError(f"Node '{node_id}' not found.")

            self.budget.record_step(tokens=tokens, delta_time=delta_time)

            if not self.budget.can_proceed():
                raise BudgetExceededError(
                    f"Execution budget exceeded: steps={self.budget.current_steps}/{self.budget.max_steps}, "
                    f"tokens={self.budget.tokens_used}/{self.budget.token_cap}, "
                    f"elapsed={self.budget.elapsed_time:.1f}/{self.budget.wall_clock_timeout}s."
                )

            new_step_count = node.step_count + 1
            new_tokens_used = node.tokens_used + tokens

            self.conn.execute(
                """
                UPDATE hierarchical_task_nodes
                SET step_count = ?, tokens_used = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_step_count, new_tokens_used, time.time(), node_id),
            )
            self.conn.commit()

    def get_ready_nodes(self) -> list[TaskNode]:
        """
        Return pending nodes that are ready for execution.
        Requirements:
        1. Explicit prerequisite IDs in `dependencies` must all be 'completed'.
        2. If node has child nodes (e.g., integration node), ALL child nodes must be 'completed'
           before parent integration tasks run.
        """
        with self._lock:
            all_nodes = {n.id: n for n in self.get_all_nodes()}
            ready: list[TaskNode] = []

            for node in all_nodes.values():
                if node.status != "pending":
                    continue

                # 1. Check explicit dependencies
                deps_met = True
                for dep_id in node.dependencies:
                    dep_node = all_nodes.get(dep_id)
                    if not dep_node or dep_node.status != "completed":
                        deps_met = False
                        break

                if not deps_met:
                    continue

                # 2. Check child node completion: child nodes must complete before parent integration tasks run
                children = [n for n in all_nodes.values() if n.parent_id == node.id]
                if children:
                    children_met = all(c.status == "completed" for c in children)
                    if not children_met:
                        continue

                ready.append(node)

            return ready

    def cancel_task(self, node_id: str, reason: str = "") -> list[str]:
        """
        Task kill-switch / cancellation.
        Cancels the target node and cascades cancellation downward to all descendants.
        Returns list of all cancelled node IDs.
        """
        with self._lock:
            node = self.get_node(node_id)
            if not node:
                raise TaskGraphError(f"Node '{node_id}' not found.")

            to_cancel = [node] + self.get_descendants(node_id)
            cancelled_ids = []
            now = time.time()

            for n in to_cancel:
                if n.status != "completed":
                    out = n.output_result or {}
                    out["cancellation_reason"] = reason or "Cancelled via task kill-switch."
                    self.conn.execute(
                        """
                        UPDATE hierarchical_task_nodes
                        SET status = 'cancelled', output_result = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (json.dumps(out), now, n.id),
                    )
                    cancelled_ids.append(n.id)

            self.conn.commit()
            return cancelled_ids

    def is_cancelled(self, node_id: str) -> bool:
        """Check if a node has been cancelled."""
        node = self.get_node(node_id)
        return node is not None and node.status == "cancelled"

    def is_all_completed(self) -> bool:
        """Check if all nodes in the graph are completed."""
        with self._lock:
            nodes = self.get_all_nodes()
            if not nodes:
                return False
            return all(n.status == "completed" for n in nodes)

    def get_max_depth(self) -> int:
        """Return the maximum depth present among nodes in the graph."""
        with self._lock:
            cur = self.conn.execute("SELECT MAX(depth) FROM hierarchical_task_nodes")
            row = cur.fetchone()
            return row[0] if (row and row[0] is not None) else 0

    def clear(self) -> None:
        """Clear all nodes from the graph."""
        with self._lock:
            self.conn.execute("DELETE FROM hierarchical_task_nodes")
            self.conn.commit()
