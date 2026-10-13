"""Persistent companies, departments, employees, projects, tasks, records and audit events (SQLite).

Everything the company platform shows or decides on lives here, so a restart loses nothing and every
state change leaves an audit event.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Iterable

COMPANY_STATES = ("draft", "active", "paused", "archived")
PROJECT_STATES = ("planning", "awaiting_plan_approval", "running", "paused", "needs_user_input", "delivered",
                  "failed", "cancelled")
TASK_STATES = ("draft", "ready", "assigned", "in_progress", "review", "verification", "completed",
               "blocked", "failed", "needs_user_input", "cancelled")
LEVELS = ("director", "lead", "specialist")
SKILL_TIERS = ("core", "specialist", "supporting", "learning")
MODES = ("supervised", "balanced", "autonomous")

# Allowed task state changes. "completed" is only reachable from verification, so nothing is marked done
# without an independent verification step (see CompanyStore.complete_task).
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "blocked", "cancelled"},
    "ready": {"assigned", "blocked", "cancelled"},
    "assigned": {"in_progress", "ready", "blocked", "cancelled"},
    "in_progress": {"review", "failed", "blocked", "needs_user_input", "ready", "cancelled"},
    "review": {"verification", "in_progress", "failed", "needs_user_input", "ready", "cancelled"},
    "verification": {"completed", "in_progress", "failed", "needs_user_input", "review", "cancelled"},
    "blocked": {"ready", "cancelled"},
    "needs_user_input": {"ready", "in_progress", "cancelled", "failed"},
    "failed": {"ready", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
ACTIVE_TASK_STATES = ("assigned", "in_progress", "review", "verification")
TERMINAL_TASK_STATES = ("completed", "cancelled")


class InvalidTransition(ValueError):
    pass


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def slug(text: str, limit: int = 40) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return (out[:limit].strip("-") or "item")


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY, name TEXT NOT NULL, template TEXT, description TEXT,
  status TEXT NOT NULL, mission TEXT, skills TEXT NOT NULL DEFAULT '[]', config TEXT NOT NULL DEFAULT '{}',
  version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, company_id TEXT NOT NULL, key TEXT NOT NULL,
  name TEXT NOT NULL, mission TEXT, head TEXT, skills TEXT NOT NULL DEFAULT '[]', position INTEGER DEFAULT 0,
  UNIQUE(company_id, key));
CREATE TABLE IF NOT EXISTS employees(id TEXT PRIMARY KEY, company_id TEXT NOT NULL, department_id TEXT,
  key TEXT NOT NULL, name TEXT NOT NULL, title TEXT, level TEXT NOT NULL, reports_to TEXT, responsibilities TEXT,
  instructions TEXT, mbti TEXT, skills TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT, UNIQUE(company_id, key));
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, request TEXT NOT NULL,
  lead_company TEXT NOT NULL, companies TEXT NOT NULL, workspace TEXT NOT NULL, mode TEXT NOT NULL,
  status TEXT NOT NULL, spec TEXT NOT NULL DEFAULT '{}', report TEXT, error TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, parent_id TEXT, key TEXT NOT NULL,
  title TEXT NOT NULL, description TEXT, company_id TEXT, department_id TEXT, assignee TEXT, verifier TEXT,
  state TEXT NOT NULL, depends TEXT NOT NULL DEFAULT '[]', acceptance TEXT NOT NULL DEFAULT '[]',
  deliverables TEXT NOT NULL DEFAULT '[]', evidence TEXT NOT NULL DEFAULT '{}', result TEXT, feedback TEXT,
  approval_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, position INTEGER DEFAULT 0, created_at TEXT,
  updated_at TEXT, UNIQUE(project_id, key));
CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
  title TEXT, body TEXT, author TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, company_id TEXT,
  task_id TEXT, type TEXT NOT NULL, actor TEXT, data TEXT NOT NULL DEFAULT '{}', created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS ix_events_project ON events(project_id, id);
"""

_JSON_COLS = {"skills", "config", "companies", "spec", "depends", "acceptance", "deliverables", "evidence", "data"}


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for key in _JSON_COLS & out.keys():
        try:
            out[key] = json.loads(out[key] or "null")
        except (TypeError, ValueError):
            out[key] = None
    return out


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class CompanyStore:
    def __init__(self, path: Path, *, publish=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        for ddl in ("ALTER TABLE projects ADD COLUMN trust_commands INTEGER NOT NULL DEFAULT 0",
                    "ALTER TABLE projects ADD COLUMN existing_folder INTEGER NOT NULL DEFAULT 0",
                    "ALTER TABLE projects ADD COLUMN checks_approved INTEGER NOT NULL DEFAULT 0",
                    "ALTER TABLE projects ADD COLUMN checks_approval_id TEXT"):
            try:  # columns added after the first release
                self.conn.execute(ddl)
            except sqlite3.OperationalError:
                pass
        self.conn.commit()
        self._lock = threading.RLock()
        self._publish = publish

    # ---- low level -----------------------------------------------------------------------

    def _one(self, sql: str, args: Iterable = ()) -> dict | None:
        with self._lock:
            return _row(self.conn.execute(sql, tuple(args)).fetchone())

    def _all(self, sql: str, args: Iterable = ()) -> list[dict]:
        with self._lock:
            return [_row(r) for r in self.conn.execute(sql, tuple(args)).fetchall()]

    def _exec(self, sql: str, args: Iterable = ()) -> None:
        with self._lock:
            self.conn.execute(sql, tuple(args))
            self.conn.commit()

    def event(self, type: str, *, project_id: str | None = None, company_id: str | None = None,
              task_id: str | None = None, actor: str = "system", **data) -> None:
        """Append an audit event and publish it live (``company.<type>``) for the control centers."""
        self._exec("INSERT INTO events(project_id, company_id, task_id, type, actor, data, created_at) VALUES(?,?,?,?,?,?,?)",
                   (project_id, company_id, task_id, type, actor, _dump(data), now()))
        if self._publish:
            try:
                self._publish(f"company.{type}", project_id=project_id, company_id=company_id, task_id=task_id,
                              actor=actor, **data)
            except Exception:
                pass  # a broken event subscriber must not stop the work

    def events(self, *, project_id: str | None = None, company_id: str | None = None, after: int = 0,
               limit: int = 200) -> list[dict]:
        where, args = ["id > ?"], [after]
        if project_id:
            where.append("project_id = ?"); args.append(project_id)
        if company_id:
            where.append("company_id = ?"); args.append(company_id)
        rows = self._all(f"SELECT * FROM events WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?", [*args, limit])
        return list(reversed(rows))

    # ---- companies -----------------------------------------------------------------------

    def companies(self, include_archived: bool = False) -> list[dict]:
        rows = self._all("SELECT * FROM companies ORDER BY created_at")
        out = []
        for c in rows:
            if c["status"] == "archived" and not include_archived:
                continue
            counts = self._one("SELECT (SELECT COUNT(*) FROM departments WHERE company_id=?) d, "
                               "(SELECT COUNT(*) FROM employees WHERE company_id=? AND status='active') e",
                               (c["id"], c["id"]))
            out.append({**c, "departments": counts["d"], "employees": counts["e"]})
        return out

    def company(self, company_id: str) -> dict:
        row = self._one("SELECT * FROM companies WHERE id=?", (company_id,))
        if not row:
            raise KeyError(f"No company {company_id!r}")
        return row

    def company_full(self, company_id: str) -> dict:
        company = self.company(company_id)
        return {**company, "departments": self.departments(company_id), "employees": self.employees(company_id)}

    def create_company(self, name: str, *, template: str = "", description: str = "", mission: str = "",
                       skills: list[str] | None = None, config: dict | None = None, status: str = "active") -> dict:
        name = str(name or "").strip()
        if not name:
            raise ValueError("A company needs a name.")
        if status not in COMPANY_STATES:
            raise ValueError(f"Unknown company status {status!r}")
        cid = new_id("co")
        self._exec("INSERT INTO companies(id, name, template, description, status, mission, skills, config, created_at, "
                   "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (cid, name[:80], template, description[:1000], status, mission[:1000], _dump(skills or []),
                    _dump(config or {}), now(), now()))
        self.event("company_created", company_id=cid, name=name, template=template)
        return self.company(cid)

    def update_company(self, company_id: str, **fields) -> dict:
        company = self.company(company_id)
        allowed = {"name", "description", "mission", "status", "skills", "config"}
        changes = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "status" in changes and changes["status"] not in COMPANY_STATES:
            raise ValueError(f"Unknown company status {changes['status']!r}")
        if not changes:
            return company
        cols = ", ".join(f"{k}=?" for k in changes)
        vals = [_dump(v) if k in _JSON_COLS else v for k, v in changes.items()]
        self._exec(f"UPDATE companies SET {cols}, version=version+1, updated_at=? WHERE id=?", [*vals, now(), company_id])
        self.event("company_updated", company_id=company_id, fields=sorted(changes))
        return self.company(company_id)

    def delete_company(self, company_id: str) -> dict:
        self.company(company_id)
        busy = self._one("SELECT COUNT(*) n FROM projects WHERE status IN ('planning','running','awaiting_plan_approval',"
                         "'needs_user_input') AND (lead_company=? OR companies LIKE ?)", (company_id, f'%"{company_id}"%'))
        if busy["n"]:
            raise ValueError("This company is working on an open project; cancel or finish it first, or archive the company.")
        with self._lock:
            for table in ("employees", "departments"):
                self.conn.execute(f"DELETE FROM {table} WHERE company_id=?", (company_id,))
            self.conn.execute("DELETE FROM companies WHERE id=?", (company_id,))
            self.conn.commit()
        self.event("company_deleted", company_id=company_id)
        return {"ok": True, "deleted": company_id}

    # ---- departments and employees -------------------------------------------------------

    def departments(self, company_id: str) -> list[dict]:
        return self._all("SELECT * FROM departments WHERE company_id=? ORDER BY position, name", (company_id,))

    def department(self, department_id: str) -> dict:
        row = self._one("SELECT * FROM departments WHERE id=?", (department_id,))
        if not row:
            raise KeyError(f"No department {department_id!r}")
        return row

    def add_department(self, company_id: str, name: str, *, key: str = "", mission: str = "",
                       skills: list[str] | None = None, position: int | None = None) -> dict:
        self.company(company_id)
        key = slug(key or name, 30)
        if self._one("SELECT id FROM departments WHERE company_id=? AND key=?", (company_id, key)):
            raise ValueError(f"The company already has a department {key!r}")
        if position is None:
            position = (self._one("SELECT COALESCE(MAX(position), -1) + 1 p FROM departments WHERE company_id=?",
                                  (company_id,)) or {"p": 0})["p"]
        did = new_id("dep")
        self._exec("INSERT INTO departments(id, company_id, key, name, mission, skills, position) VALUES(?,?,?,?,?,?,?)",
                   (did, company_id, key, str(name)[:80], str(mission)[:1000], _dump(skills or []), position))
        self.event("department_added", company_id=company_id, department=key)
        return self.department(did)

    def update_department(self, department_id: str, **fields) -> dict:
        dep = self.department(department_id)
        changes = {k: v for k, v in fields.items() if k in {"name", "mission", "skills", "head"} and v is not None}
        if changes:
            cols = ", ".join(f"{k}=?" for k in changes)
            self._exec(f"UPDATE departments SET {cols} WHERE id=?",
                       [*[_dump(v) if k in _JSON_COLS else v for k, v in changes.items()], department_id])
            self.event("department_updated", company_id=dep["company_id"], department=dep["key"], fields=sorted(changes))
        return self.department(department_id)

    def employees(self, company_id: str, include_inactive: bool = False) -> list[dict]:
        rows = self._all("SELECT * FROM employees WHERE company_id=? ORDER BY CASE level WHEN 'director' THEN 0 "
                         "WHEN 'lead' THEN 1 ELSE 2 END, name", (company_id,))
        return [r for r in rows if include_inactive or r["status"] == "active"]

    def employee(self, employee_id: str) -> dict:
        row = self._one("SELECT * FROM employees WHERE id=?", (employee_id,))
        if not row:
            raise KeyError(f"No employee {employee_id!r}")
        return row

    def add_employee(self, company_id: str, *, name: str, title: str, level: str = "specialist",
                     department_id: str | None = None, key: str = "", reports_to: str | None = None,
                     responsibilities: str = "", instructions: str = "", mbti: str = "",
                     skills: list[dict] | None = None) -> dict:
        self.company(company_id)
        if level not in LEVELS:
            raise ValueError(f"level must be one of {', '.join(LEVELS)}")
        if department_id:
            dep = self.department(department_id)
            if dep["company_id"] != company_id:
                raise ValueError("The department belongs to another company.")
        if reports_to and self.employee(reports_to)["company_id"] != company_id:
            raise ValueError("An employee can only report to someone in the same company.")
        key = slug(key or title or name, 40)
        base, n = key, 2
        while self._one("SELECT id FROM employees WHERE company_id=? AND key=?", (company_id, key)):
            key, n = f"{base}-{n}", n + 1
        eid = new_id("emp")
        self._exec("INSERT INTO employees(id, company_id, department_id, key, name, title, level, reports_to, "
                   "responsibilities, instructions, mbti, skills, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (eid, company_id, department_id, key, str(name)[:80], str(title)[:120], level, reports_to,
                    str(responsibilities)[:2000], str(instructions)[:6000], str(mbti or "")[:8],
                    _dump(normalize_skills(skills)), now()))
        self.event("employee_hired", company_id=company_id, employee=eid, name=name, title=title)
        return self.employee(eid)

    def update_employee(self, employee_id: str, **fields) -> dict:
        emp = self.employee(employee_id)
        allowed = {"name", "title", "level", "department_id", "reports_to", "responsibilities", "instructions",
                   "mbti", "skills", "status"}
        changes = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "level" in changes and changes["level"] not in LEVELS:
            raise ValueError(f"level must be one of {', '.join(LEVELS)}")
        if "skills" in changes:
            changes["skills"] = normalize_skills(changes["skills"])
        if changes.get("department_id") and self.department(changes["department_id"])["company_id"] != emp["company_id"]:
            raise ValueError("The department belongs to another company.")
        if changes:
            cols = ", ".join(f"{k}=?" for k in changes)
            self._exec(f"UPDATE employees SET {cols} WHERE id=?",
                       [*[_dump(v) if k in _JSON_COLS else v for k, v in changes.items()], employee_id])
            self.event("employee_updated", company_id=emp["company_id"], employee=employee_id, fields=sorted(changes))
        return self.employee(employee_id)

    def remove_employee(self, employee_id: str) -> dict:
        emp = self.employee(employee_id)
        busy = self._one(f"SELECT COUNT(*) n FROM tasks WHERE (assignee=? OR verifier=?) AND state IN "
                         f"({','.join('?' * len(ACTIVE_TASK_STATES))})", (employee_id, employee_id, *ACTIVE_TASK_STATES))
        if busy["n"]:
            raise ValueError("The employee is working on a task right now; wait or cancel the task first.")
        self._exec("UPDATE employees SET status='inactive' WHERE id=?", (employee_id,))
        self.event("employee_removed", company_id=emp["company_id"], employee=employee_id, name=emp["name"])
        return {"ok": True, "removed": employee_id}

    def workload(self, employee_id: str) -> int:
        row = self._one("SELECT COUNT(*) n FROM tasks WHERE (assignee=? OR verifier=?) AND state NOT IN "
                        "('completed','cancelled','failed')", (employee_id, employee_id))
        return int(row["n"])

    # ---- projects ------------------------------------------------------------------------

    def create_project(self, *, name: str, request: str, lead_company: str, companies: list[str], workspace: str,
                       mode: str = "balanced", trust_commands: bool = False, existing_folder: bool = False) -> dict:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")
        companies = list(dict.fromkeys([lead_company, *companies]))
        for cid in companies:
            if self.company(cid)["status"] != "active":
                raise ValueError(f"Company {cid} is not active.")
        pid = new_id("prj")
        self._exec("INSERT INTO projects(id, name, request, lead_company, companies, workspace, mode, status, created_at, "
                   "updated_at, trust_commands, existing_folder) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (pid, str(name)[:120], str(request)[:20000], lead_company, _dump(companies), workspace, mode,
                    "planning", now(), now(), int(bool(trust_commands)), int(bool(existing_folder))))
        self.event("project_created", project_id=pid, company_id=lead_company, name=name, companies=companies, mode=mode,
                   trust_commands=bool(trust_commands), existing_folder=bool(existing_folder))
        return self.project(pid)

    def projects(self, company_id: str | None = None) -> list[dict]:
        rows = self._all("SELECT * FROM projects ORDER BY created_at DESC")
        if company_id:
            rows = [p for p in rows if company_id in (p["companies"] or [])]
        for p in rows:
            p["progress"] = self.progress(p["id"])
        return rows

    def project(self, project_id: str) -> dict:
        row = self._one("SELECT * FROM projects WHERE id=?", (project_id,))
        if not row:
            raise KeyError(f"No project {project_id!r}")
        return row

    def delete_project(self, project_id: str) -> dict:
        project = self.project(project_id)
        with self._lock:
            for table in ("tasks", "records", "events"):
                self.conn.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
            self.conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            self.conn.commit()
        self.event("project_deleted", company_id=project["lead_company"], project_id=project_id, name=project["name"])
        return {"ok": True, "deleted": project_id}

    def set_project(self, project_id: str, **fields) -> dict:
        project = self.project(project_id)
        allowed = {"status", "spec", "report", "error", "name", "mode", "trust_commands", "checks_approved",
                   "checks_approval_id"}
        changes = {k: v for k, v in fields.items() if k in allowed}
        if "mode" in changes and changes["mode"] not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")
        if "status" in changes and changes["status"] not in PROJECT_STATES:
            raise ValueError(f"Unknown project status {changes['status']!r}")
        if changes:
            cols = ", ".join(f"{k}=?" for k in changes)
            self._exec(f"UPDATE projects SET {cols}, updated_at=? WHERE id=?",
                       [*[_dump(v) if k in _JSON_COLS else v for k, v in changes.items()], now(), project_id])
            if "status" in changes and changes["status"] != project["status"]:
                self.event("project_status", project_id=project_id, company_id=project["lead_company"],
                           status=changes["status"], previous=project["status"])
        return self.project(project_id)

    def progress(self, project_id: str) -> dict:
        rows = self._all("SELECT state, COUNT(*) n FROM tasks WHERE project_id=? GROUP BY state", (project_id,))
        by = {r["state"]: r["n"] for r in rows}
        total = sum(by.values())
        return {"total": total, "completed": by.get("completed", 0), "by_state": by}

    def add_record(self, project_id: str, kind: str, title: str, body: str, author: str = "system") -> dict:
        rid = new_id("rec")
        self._exec("INSERT INTO records(id, project_id, kind, title, body, author, created_at) VALUES(?,?,?,?,?,?,?)",
                   (rid, project_id, kind, str(title)[:200], str(body)[:60000], author, now()))
        self.event("record_added", project_id=project_id, kind=kind, title=title, actor=author)
        return {"id": rid}

    def records(self, project_id: str, kind: str | None = None) -> list[dict]:
        if kind:
            return self._all("SELECT * FROM records WHERE project_id=? AND kind=? ORDER BY created_at", (project_id, kind))
        return self._all("SELECT * FROM records WHERE project_id=? ORDER BY created_at", (project_id,))

    # ---- tasks ---------------------------------------------------------------------------

    def add_task(self, project_id: str, *, key: str, title: str, description: str = "", company_id: str | None = None,
                 department_id: str | None = None, depends: list[str] | None = None,
                 acceptance: list[str] | None = None, deliverables: list[str] | None = None,
                 parent_id: str | None = None, position: int = 0, state: str = "draft") -> dict:
        project = self.project(project_id)
        if company_id and company_id not in project["companies"]:
            raise ValueError(f"Company {company_id} is not authorized for this project.")
        tid = new_id("task")
        self._exec("INSERT INTO tasks(id, project_id, parent_id, key, title, description, company_id, department_id, state, "
                   "depends, acceptance, deliverables, position, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (tid, project_id, parent_id, slug(key, 40), str(title)[:200], str(description)[:8000], company_id,
                    department_id, state, _dump(depends or []), _dump(acceptance or []), _dump(deliverables or []),
                    position, now(), now()))
        return self.task(tid)

    def task(self, task_id: str) -> dict:
        row = self._one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not row:
            raise KeyError(f"No task {task_id!r}")
        return row

    def tasks(self, project_id: str) -> list[dict]:
        return self._all("SELECT * FROM tasks WHERE project_id=? ORDER BY position, created_at", (project_id,))

    def update_task(self, task_id: str, **fields) -> dict:
        allowed = {"assignee", "verifier", "result", "feedback", "evidence", "approval_id", "attempts", "description",
                   "acceptance", "deliverables", "company_id", "department_id"}
        changes = {k: v for k, v in fields.items() if k in allowed}
        if changes:
            cols = ", ".join(f"{k}=?" for k in changes)
            self._exec(f"UPDATE tasks SET {cols}, updated_at=? WHERE id=?",
                       [*[_dump(v) if k in _JSON_COLS else v for k, v in changes.items()], now(), task_id])
        return self.task(task_id)

    def transition(self, task_id: str, state: str, *, actor: str = "system", reason: str = "") -> dict:
        """Move a task to a new state; refuses changes the task lifecycle does not allow."""
        task = self.task(task_id)
        if state == task["state"]:
            return task
        if state not in TRANSITIONS.get(task["state"], set()):
            raise InvalidTransition(f"A task cannot go from {task['state']} to {state}.")
        if state == "completed":
            raise InvalidTransition("Use complete_task: completion needs verified evidence.")
        if state == "ready":
            pending = self.unmet_dependencies(task)
            if pending:
                raise InvalidTransition(f"Dependencies not completed yet: {', '.join(pending)}")
        self._exec("UPDATE tasks SET state=?, updated_at=? WHERE id=?", (state, now(), task_id))
        self.event("task_state", project_id=task["project_id"], company_id=task["company_id"], task_id=task_id,
                   actor=actor, key=task["key"], title=task["title"], state=state, previous=task["state"],
                   reason=reason[:500])
        return self.task(task_id)

    def complete_task(self, task_id: str, *, verifier: str, verdict: dict) -> dict:
        """The only way to complete a task: from verification, by a verifier who is not the assignee, with a
        passing verdict and recorded evidence."""
        task = self.task(task_id)
        if task["state"] != "verification":
            raise InvalidTransition(f"Only a task in verification can be completed (this one is {task['state']}).")
        if not verifier or verifier == task["assignee"]:
            raise InvalidTransition("A task must be verified by someone other than the person who did it.")
        if verdict.get("verdict") != "pass":
            raise InvalidTransition("The verification did not pass.")
        evidence = task["evidence"] or {}
        if not evidence.get("checks"):
            raise InvalidTransition("There is no recorded evidence for this task.")
        failed = [c for c in evidence["checks"] if not c.get("ok")]
        if failed:
            raise InvalidTransition(f"{len(failed)} evidence check(s) failed: " + "; ".join(c["name"] for c in failed[:4]))
        evidence = {**evidence, "verification": verdict, "verified_by": verifier, "verified_at": now()}
        self._exec("UPDATE tasks SET state='completed', evidence=?, updated_at=? WHERE id=?",
                   (_dump(evidence), now(), task_id))
        self.event("task_state", project_id=task["project_id"], company_id=task["company_id"], task_id=task_id,
                   actor=verifier, key=task["key"], title=task["title"], state="completed", previous="verification",
                   reason="verified")
        return self.task(task_id)

    def unmet_dependencies(self, task: dict) -> list[str]:
        if not task["depends"]:
            return []
        rows = self._all("SELECT key, state FROM tasks WHERE project_id=?", (task["project_id"],))
        states = {r["key"]: r["state"] for r in rows}
        return [d for d in task["depends"] if states.get(d) != "completed"]

    # ---- lessons: what went wrong (and what fixed it) in earlier tasks, shown to future employees --------

    def add_lesson(self, company_id: str, text: str, *, project_id: str | None = None, task_id: str | None = None) -> None:
        text = " ".join(str(text or "").split())[:400]
        if not text:
            return
        recent = self._all("SELECT data FROM events WHERE company_id=? AND type='lesson' ORDER BY id DESC LIMIT 30",
                           (company_id,))
        if any((r["data"] or {}).get("text") == text for r in recent):
            return  # the same lesson is already known
        self.event("lesson", company_id=company_id, project_id=project_id, task_id=task_id, text=text)

    def lessons(self, company_id: str, limit: int = 6) -> list[str]:
        rows = self._all("SELECT data FROM events WHERE company_id=? AND type='lesson' ORDER BY id DESC LIMIT ?",
                         (company_id, limit))
        return [(r["data"] or {}).get("text", "") for r in rows if (r["data"] or {}).get("text")]

    def recover_interrupted(self) -> list[str]:
        """After a restart, work that was mid-flight goes back to ready (nothing is silently lost)."""
        rows = self._all(f"SELECT id, state FROM tasks WHERE state IN ({','.join('?' * len(ACTIVE_TASK_STATES))})",
                         ACTIVE_TASK_STATES)
        for r in rows:  # an interrupted attempt is not a failed one
            self._exec("UPDATE tasks SET state='ready', attempts=MAX(0, attempts-1), updated_at=? WHERE id=?",
                       (now(), r["id"]))
            task = self.task(r["id"])
            self.event("task_state", project_id=task["project_id"], company_id=task["company_id"], task_id=r["id"],
                       key=task["key"], title=task["title"], state="ready", previous=r["state"],
                       reason="The app restarted while this task was running; it will be redone.")
        return [r["id"] for r in rows]


def normalize_skills(skills: Any) -> list[dict]:
    """[{name, tier}] from names or dicts; unknown tiers become 'supporting'."""
    out, seen = [], set()
    for item in skills or []:
        if isinstance(item, str):
            name, tier = item, "core"
        elif isinstance(item, dict):
            name, tier = item.get("name"), item.get("tier") or "core"
        else:
            continue
        name = slug(name, 60)
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "tier": tier if tier in SKILL_TIERS else "supporting"})
    return out[:30]
