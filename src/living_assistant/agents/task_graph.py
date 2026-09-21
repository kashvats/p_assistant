import sqlite3
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class TaskNode:
    id: str
    description: str
    status: str  # pending, running, completed, failed
    dependencies: List[str]  # list of node IDs that must complete first
    result: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0

class TaskGraphManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS task_nodes (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dependencies TEXT NOT NULL,
                    result TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            ''')
            conn.commit()

    def add_task(self, task_id: str, description: str, dependencies: List[str] = None) -> TaskNode:
        deps = dependencies or []
        now = time.time()
        node = TaskNode(
            id=task_id, 
            description=description, 
            status="pending", 
            dependencies=deps,
            created_at=now,
            updated_at=now
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO task_nodes (id, description, status, dependencies, result, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (node.id, node.description, node.status, json.dumps(node.dependencies), node.result, node.created_at, node.updated_at)
            )
            conn.commit()
        return node

    def get_task(self, task_id: str) -> Optional[TaskNode]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM task_nodes WHERE id = ?", (task_id,)).fetchone()
            if row:
                return TaskNode(
                    id=row[0],
                    description=row[1],
                    status=row[2],
                    dependencies=json.loads(row[3]),
                    result=row[4],
                    created_at=row[5],
                    updated_at=row[6]
                )
        return None

    def update_task_status(self, task_id: str, status: str, result: str = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE task_nodes SET status = ?, result = ?, updated_at = ? WHERE id = ?",
                (status, result, time.time(), task_id)
            )
            conn.commit()

    def get_ready_tasks(self) -> List[TaskNode]:
        """Returns pending tasks whose dependencies are all completed."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM task_nodes").fetchall()
            
        all_nodes = {}
        for r in rows:
            all_nodes[r[0]] = TaskNode(id=r[0], description=r[1], status=r[2], dependencies=json.loads(r[3]), result=r[4], created_at=r[5], updated_at=r[6])
            
        ready = []
        for node in all_nodes.values():
            if node.status == "pending":
                deps_met = all(all_nodes.get(d) and all_nodes[d].status == "completed" for d in node.dependencies)
                if deps_met:
                    ready.append(node)
        return ready

    def clear_graph(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM task_nodes")
            conn.commit()
