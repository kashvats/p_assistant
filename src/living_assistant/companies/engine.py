"""Runs company projects: plan -> task graph -> employees do the work -> independent verification -> delivery.

Every employee turn goes through the assistant's normal orchestrator (same tools, approvals, snapshots),
with the employee's role, persona and skill instructions as context. Nothing is marked complete unless
automated evidence checks pass *and* a different employee verified it (see CompanyStore.complete_task).
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Callable

from living_assistant.companies.store import CompanyStore, InvalidTransition, slug
from living_assistant.companies.templates import TEMPLATES, build_company
from living_assistant.core.scope import project_scope
from living_assistant.security.security_utils import redact_secrets

EMPLOYEE_MARKER = "[COMPANY EMPLOYEE:"
# Employees cannot reorganise companies, start goals, install/learn skills or hand work to other agents:
# learning never grants tools, and work is only routed through the project plan.
EMPLOYEE_EXCLUDED = (
    "team_ask", "agent_new", "agent_hire", "team_create", "goal_start", "goal_resume", "goal_cancel",
    "skill_list", "skill_find", "skill_install", "skill_read", "skill_learn", "skill_edit", "skill_remove",
    "skill_restore", "company_list", "company_create", "project_start", "project_status", "project_approve_plan",
    "project_control", "build_software_project",
)
# Employees get a fixed, role-based tool set instead of whatever the router ranks highest for the brief
# (which once handed a verifier a screen-reading tool). Everything else is blocked for the turn.
READ_TOOLS = ("list_files", "read_file", "search_files", "read_attachment", "run_command", "web_search",
              "web_extract_article", "web_fetch", "project_audit")
WORKER_TOOLS = READ_TOOLS + ("write_file", "edit_file")
VERIFIER_TOOLS = READ_TOOLS
MUTATING_TOOLS = ("write_file", "edit_file", "delete_file", "web_download", "download_file")
SHELL_TOOLS = ("run_command", "start_process")
PATH_ARGS = ("path", "target", "destination", "dest", "dst", "src", "source_path", "output_path", "directory")
MAX_ATTEMPTS = {"supervised": 2, "balanced": 2, "autonomous": 3}
TIER_WEIGHT = {"core": 3, "specialist": 2, "supporting": 1, "learning": 0}
SKILL_CHARS = 3500  # skill instruction text per employee turn: small local models have small context windows
STEPS = {"worker": 30, "verifier": 16}  # tool steps per turn: building and testing takes more than a chat answer
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build", ".next"}


def extract_json(text: str):
    """The first JSON object in a model reply (fenced or bare), ignoring <think> blocks."""
    text = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S)
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    for candidate in fenced:
        try:
            return json.loads(candidate)
        except ValueError:
            pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                esc = (ch == "\\" and not esc)
                if ch == '"' and not esc:
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    return None


def parse_args(raw) -> dict:
    """Tool-call args from a stream event: a dict, or a JSON string the orchestrator may have cut short
    (long file contents), from which the path-like fields are still recovered."""
    if isinstance(raw, dict):
        return raw
    text = str(raw or "")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    out = {}
    for key in PATH_ARGS + ("cwd", "command", "cmd"):
        m = re.search(r'"' + key + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            try:
                out[key] = json.loads(f'"{m.group(1)}"')
            except ValueError:
                out[key] = m.group(1)
    return out


@functools.lru_cache(maxsize=1)
def machine_note() -> str:
    """What employees' commands run on, so they use the right shell syntax and tools."""
    import platform
    import shutil
    version = platform.python_version()
    tools = ", ".join(t for t in ("python", "node", "npm", "git") if shutil.which(t)) or "none found"
    if platform.system() == "Windows":
        return (f"This machine: Windows {platform.release()}. run_command uses cmd.exe: use Windows syntax (dir, type, "
                f"copy, del, mkdir without -p, `venv\\Scripts\\python`); no Unix commands (ls, cat, touch, rm -rf, mkdir -p, "
                f"export, `source`). Create files and folders with write_file. Available on PATH: {tools}. "
                f"The assistant runs Python {version}.")
    return (f"This machine: {platform.system()} {platform.release()} with a POSIX shell (`venv/bin/python`). "
            f"Available on PATH: {tools}. The assistant runs Python {version}.")


def list_files(root: Path, *, limit: int = 200, since: float | None = None, max_scan: int = 20000) -> list[Path]:
    """Files under ``root`` (optionally only those changed since ``since``), skipping dependency and
    build folders, bounded so a large existing project stays cheap to inspect."""
    out, scanned, stack = [], 0, [Path(root)]
    while stack and len(out) < limit and scanned < max_scan:
        folder = stack.pop()
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for p in entries:
            scanned += 1
            if p.is_dir():
                if p.name not in SKIP_DIRS and not p.name.startswith("."):
                    stack.append(p)
            elif since is None or p.stat().st_mtime >= since:
                out.append(p)
                if len(out) >= limit:
                    break
    return sorted(out)


def find_cycle(nodes: dict[str, list[str]]) -> list[str] | None:
    """A dependency cycle among task keys, or None."""
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        stack.append(n)
        for d in nodes.get(n, []):
            if state.get(d) == 1:
                return stack[stack.index(d):] + [d]
            if state.get(d) is None:
                found = visit(d)
                if found:
                    return found
        state[n] = 2
        stack.pop()
        return None

    for node in nodes:
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None


class CompanyEngine:
    def __init__(self, store: CompanyStore, *, workspace_root: Path, get_orchestrator: Callable | None = None,
                 complete: Callable | None = None, skill_library=None, approval_status: Callable | None = None,
                 persona: Callable[[str], str] | None = None, max_parallel: int = 1,
                 background_planning: bool = True, resolve_folder: Callable[[str], Path] | None = None,
                 request_approval: Callable[[str, str], dict] | None = None):
        self.background_planning = background_planning
        self.request_approval = request_approval  # (action, reason) -> ApprovalManager decision
        self.resolve_folder = resolve_folder  # validates an existing project folder the user points a project at
        self.store = store
        self.workspace_root = Path(workspace_root).resolve()  # where file tools resolve relative paths
        self.root = self.workspace_root / "company_projects"
        self.get_orchestrator = get_orchestrator
        self.complete = complete
        self.skills = skill_library
        self.approval_status = approval_status or (lambda approval_id: None)
        self.persona = persona or (lambda mbti: "")
        self.max_parallel = max(1, int(max_parallel))
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._stop = False
        self._started = False
        self._busy: set[str] = set()
        self._lock = threading.Lock()

    # ---- companies -----------------------------------------------------------------------

    def known_skills(self) -> set[str]:
        if self.skills is None:
            return set()
        return {row["name"] for row in self.skills.list() if row.get("valid")}

    def create_from_template(self, template: str, name: str = "") -> dict:
        if template not in TEMPLATES:
            raise KeyError(f"No company template {template!r}; templates: {', '.join(TEMPLATES)}")
        return build_company(self.store, TEMPLATES[template], name=name, template=template,
                             known_skills=self.known_skills() if self.skills is not None else None)

    def create_from_description(self, description: str, name: str = "") -> dict:
        """Let the model draft a company (departments, employees, skills) for a described purpose."""
        if not self.complete:
            raise RuntimeError("Drafting a company needs the local model, which is unavailable.")
        skills = sorted(self.known_skills())
        prompt = (
            "Design a small AI company for this purpose:\n" + description[:3000] + "\n\n"
            "Return ONLY JSON: {\"name\": str, \"description\": str, \"mission\": str, \"skills\": [skill names for the "
            "whole company], \"departments\": [{\"key\": short-id, \"name\": str, \"mission\": str, \"skills\": [..], "
            "\"employees\": [{\"key\": short-id, \"name\": first name, \"title\": str, \"level\": "
            "\"director\"|\"lead\"|\"specialist\", \"responsibilities\": str, \"skills\": [{\"name\": skill, \"tier\": "
            "\"core\"|\"specialist\"|\"supporting\"}], \"mbti\": 4 letters}]}]}.\n"
            "Rules: 3-7 departments, 1-3 employees each; the first department is the executive office with a "
            "director whose key is \"project-director\" and who has the project-planning skill; include a "
            "department with key \"verification\" whose employees have independent-verification.\n"
            "Use only these skill names: " + ", ".join(skills))
        data = None
        for _ in range(2):
            data = extract_json(self.complete([{"role": "user", "content": prompt}], max_tokens=3000))
            if isinstance(data, dict) and isinstance(data.get("departments"), list) and data["departments"]:
                break
            data = None
        if not data:
            raise ValueError("The model did not produce a usable company design; try again or start from a template.")
        spec = self._normalize_design(data, skills=set(skills))
        return build_company(self.store, spec, name=name or spec["name"], template="custom",
                             known_skills=set(skills) if self.skills is not None else None)

    @staticmethod
    def _normalize_design(data: dict, skills: set[str]) -> dict:
        def skill_list(items):
            out = []
            for item in items or []:
                n = item.get("name") if isinstance(item, dict) else item
                t = (item.get("tier") if isinstance(item, dict) else "core") or "core"
                if isinstance(n, str) and n:
                    out.append((slug(n, 60), t))
            return out

        departments = []
        for dep in data.get("departments") or []:
            if not isinstance(dep, dict) or not dep.get("name"):
                continue
            employees = []
            for e in dep.get("employees") or []:
                if not isinstance(e, dict) or not (e.get("title") or e.get("name")):
                    continue
                level = e.get("level") if e.get("level") in ("director", "lead", "specialist") else "specialist"
                employees.append((e.get("key") or e.get("title"), str(e.get("name") or e.get("title"))[:40],
                                  str(e.get("title") or e.get("name"))[:80], level, str(e.get("responsibilities") or ""),
                                  skill_list(e.get("skills")), str(e.get("mbti") or "")[:4]))
            if employees:
                departments.append({"key": dep.get("key") or dep["name"], "name": str(dep["name"])[:60],
                                    "mission": str(dep.get("mission") or ""), "reports": "project-director",
                                    "skills": [s for s, _ in skill_list(dep.get("skills"))], "employees": employees})
        if not departments:
            raise ValueError("The company design had no departments with employees.")
        keys = {slug(e[0], 40) for d in departments for e in d["employees"]}
        if "project-director" not in keys:  # every company needs someone who plans
            departments.insert(0, {"key": "executive", "name": "Executive Office", "reports": None,
                                   "mission": "Plans projects and accepts deliveries.", "skills": ["project-planning"],
                                   "employees": [("project-director", "Morgan", "Project Director", "director",
                                                  "Plans projects and tracks them to delivery.",
                                                  [("project-planning", "core")], "ESTJ")]})
        if not any(s == "independent-verification" for d in departments for e in d["employees"] for s, _ in e[5]):
            departments.append({"key": "verification", "name": "Verification", "reports": "project-director",
                                "mission": "Independently verifies deliverables.", "skills": ["independent-verification"],
                                "employees": [("verifier", "Sage", "Verifier", "lead", "Checks work against its criteria.",
                                               [("independent-verification", "core")], "ISTJ")]})
        departments[0]["reports"] = None
        return {"name": str(data.get("name") or "New company")[:80], "description": str(data.get("description") or ""),
                "mission": str(data.get("mission") or ""),
                "skills": [s for s, _ in skill_list(data.get("skills"))],
                "departments": departments}

    # ---- employees as agents -------------------------------------------------------------

    def skill_portfolio(self, employee: dict) -> list[dict]:
        """The employee's skills with where each comes from; skills of other companies are never included."""
        company = self.store.company(employee["company_id"])
        dep = self.store.department(employee["department_id"]) if employee.get("department_id") else None
        out, seen = [], set()
        for item in employee.get("skills") or []:
            out.append({**item, "layer": "individual"}); seen.add(item["name"])
        for name in (dep or {}).get("skills") or []:
            if name not in seen:
                out.append({"name": name, "tier": "supporting", "layer": "department"}); seen.add(name)
        for name in company.get("skills") or []:
            if name not in seen:
                out.append({"name": name, "tier": "supporting", "layer": "company"}); seen.add(name)
        known = self.known_skills() if self.skills is not None else None
        for item in out:
            item["available"] = known is None or item["name"] in known
        return out

    def employee_context(self, employee: dict, project: dict | None = None) -> str:
        company = self.store.company(employee["company_id"])
        dep = self.store.department(employee["department_id"]) if employee.get("department_id") else None
        lines = [f"{EMPLOYEE_MARKER} {employee['name']}, {employee['title']} at {company['name']}]",
                 f"You are {employee['name']}, {employee['title']}" + (f" in {dep['name']}" if dep else "")
                 + f" at the AI company '{company['name']}'. Mission: {company.get('mission') or company.get('description')}",
                 "Responsibilities: " + (employee.get("responsibilities") or "as your title says"),
                 "Do the task yourself with your tools. Never claim you ran, tested or created something you did not."]
        persona = self.persona(employee.get("mbti") or "")
        if persona:
            lines.append(persona)
        if employee.get("instructions"):
            lines.append("Your instructions (never override safety rules or approvals):\n" + employee["instructions"])
        lines.append(machine_note())
        lessons = self.store.lessons(employee["company_id"], limit=6)
        if lessons:
            lines.append("Lessons from earlier work in this company (do not repeat these mistakes):\n"
                         + "\n".join(f"- {x}" for x in lessons))
        if project:
            lines.append(f"Project folder: {project['workspace']}. Your file paths and commands work inside this folder "
                         "(relative paths like 'app.py' or 'templates/index.html' are fine); nothing outside it is "
                         "reachable." + (" It is an existing project: read the relevant files before changing them "
                                         "and keep what already works." if project.get("existing_folder") else ""))
        budget = SKILL_CHARS
        loaded, listed = [], []
        for item in sorted(self.skill_portfolio(employee), key=lambda s: -TIER_WEIGHT.get(s["tier"], 0)):
            if not item["available"]:
                continue
            if item["tier"] == "core" and self.skills is not None and budget > 600:
                try:
                    text = self.skills.read(item["name"]).get("instructions") or ""
                except Exception:
                    text = ""
                if text:
                    # the steps and rules matter; the "when to use" section does not once the skill is chosen
                    text = re.sub(r"## When to use\n.*?(?=\n## )", "", text, flags=re.S).strip()[:budget]
                    budget -= len(text)
                    loaded.append(f"### Skill: {item['name']} ({item['tier']})\n{text}")
                    continue
            listed.append(item["name"])
        if loaded:
            lines.append("[YOUR SKILLS - follow them]\n" + "\n\n".join(loaded))
        if listed:
            lines.append("Other skills you know in outline: " + ", ".join(listed))
        return "\n".join(lines)

    # ---- projects ------------------------------------------------------------------------

    def start_project(self, request: str, lead_company: str, companies: list[str] | None = None, *,
                      mode: str = "balanced", name: str = "", background: bool | None = None,
                      trust_commands: bool = False, folder: str = "") -> dict:
        """Start a project in a new folder, or in an existing one (``folder``: a registered project or a
        folder inside the workspace) to improve software the user already has."""
        background = self.background_planning if background is None else background
        request = str(request or "").strip()
        if len(request) < 8:
            raise ValueError("Describe what the project should deliver.")
        existing = None
        if str(folder or "").strip():
            if self.resolve_folder is None:
                raise ValueError("Working in an existing folder is not available here.")
            existing = Path(self.resolve_folder(folder.strip())).resolve()
            if not existing.is_dir():
                raise ValueError(f"No such folder: {existing}")
        name = (name or request.split("\n")[0])[:80]
        project = self.store.create_project(name=name, request=request, lead_company=lead_company,
                                            companies=list(companies or []), workspace="(pending)", mode=mode,
                                            trust_commands=trust_commands, existing_folder=existing is not None)
        folder = existing or self.root / f"{slug(name, 32)}-{project['id'][-6:]}"
        folder.mkdir(parents=True, exist_ok=True)
        self.store._exec("UPDATE projects SET workspace=? WHERE id=?", (str(folder), project["id"]))
        if background:
            threading.Thread(target=self._plan_safely, args=(project["id"],), name=f"plan-{project['id']}",
                             daemon=True).start()
        else:
            self._plan_safely(project["id"])
        return self.store.project(project["id"])

    def _plan_safely(self, project_id: str) -> None:
        try:
            self.plan(project_id)
        except Exception as exc:
            self.store.set_project(project_id, status="failed", error=f"Planning failed: {redact_secrets(exc, 600)}")

    def _director(self, company_id: str) -> dict:
        employees = self.store.employees(company_id)
        for emp in employees:
            if emp["key"] == "project-director":
                return emp
        for emp in employees:
            if emp["level"] == "director" and any(s["name"] == "project-planning" for s in emp["skills"]):
                return emp
        directors = [e for e in employees if e["level"] == "director"] or employees
        if not directors:
            raise ValueError("The lead company has no employees to plan the project.")
        return directors[0]

    def _department_map(self, project: dict) -> dict[str, dict]:
        """'<company-key>/<dept-key>' and plain '<dept-key>' (lead company first) -> department."""
        out: dict[str, dict] = {}
        for cid in project["companies"]:
            company = self.store.company(cid)
            for dep in self.store.departments(cid):
                dep = {**dep, "company_name": company["name"]}
                out[f"{slug(company['name'], 30)}/{dep['key']}"] = dep
                out.setdefault(dep["key"], dep)
        return out

    def plan(self, project_id: str) -> dict:
        project = self.store.project(project_id)
        if not self.complete:
            raise RuntimeError("Planning needs the local model, which is unavailable.")
        director = self._director(project["lead_company"])
        departments = self._department_map(project)
        roster = []
        for cid in project["companies"]:
            company = self.store.company(cid)
            for dep in self.store.departments(cid):
                staff = [f"{e['title']} ({', '.join(s['name'] for s in e['skills'][:4])})"
                         for e in self.store.employees(cid) if e["department_id"] == dep["id"]]
                roster.append(f"- {slug(company['name'], 30)}/{dep['key']}: {dep['name']} - {dep.get('mission') or ''} "
                              f"Staff: {'; '.join(staff) or 'none'}")
        existing = [str(p.relative_to(project["workspace"])).replace("\\", "/")
                    for p in list_files(Path(project["workspace"]), limit=120)]
        self.store.event("planning_started", project_id=project_id, company_id=project["lead_company"],
                         actor=director["id"], name=director["name"])
        blueprint = self.blueprint_for(project["request"])
        if blueprint:
            self.store.event("blueprint_used", project_id=project_id, actor=director["id"], blueprint=blueprint[0])
        prompt = (
            self.employee_context(director, project) + "\n\n"
            f"PROJECT REQUEST:\n{project['request']}\n\n"
            f"Departments you can assign work to:\n" + "\n".join(roster) + "\n\n"
            f"Files already in the workspace: {', '.join(existing) or 'none'}\n\n"
            + (f"PRODUCT BLUEPRINT ({blueprint[0]}) - use it unless the request says otherwise:\n{blueprint[1]}\n\n"
               if blueprint else "") +
            "Write the specification and the plan. Return ONLY JSON:\n"
            "{\"spec\": {\"goal\": str, \"requirements\": [str], \"acceptance\": [str], \"assumptions\": [str], "
            "\"open_questions\": [str]}, \"tasks\": [{\"key\": short-id, \"title\": str, \"description\": "
            "self-contained instructions, \"department\": one id from the list above, \"depends\": [task keys], "
            "\"acceptance\": [checkable criteria], \"deliverables\": [file paths relative to the workspace]}]}\n"
            "Keep the plan as small as the request allows (usually 2-8 tasks). Each task must be doable by one "
            "person with file and shell tools in one sitting. Do not add a separate final verification task; "
            "every task is verified independently and a final check is added automatically.")
        messages = [{"role": "user", "content": prompt}]
        problems: list[str] = []
        for attempt in range(3):
            if problems:
                messages = [{"role": "user", "content": prompt + "\n\nYour previous plan was rejected: "
                             + "; ".join(problems[:8]) + ". Fix these and return the full JSON again."}]
            raw = self.complete(messages, max_tokens=4000)
            data = extract_json(raw)
            plan, problems = self.validate_plan(data, departments)
            if not problems:
                break
            self.store.event("plan_rejected", project_id=project_id, actor="system", attempt=attempt + 1,
                             problems=problems[:8])
        else:
            raise ValueError("The director could not produce a valid plan: " + "; ".join(problems[:5]))
        return self.apply_plan(project_id, plan, director)

    def blueprint_for(self, request: str) -> tuple[str, str] | None:
        """The product blueprint skill (blueprint-*) that best matches a request, as (name, instructions)."""
        if self.skills is None:
            return None
        try:
            matches = [r for r in self.skills.relevant(request, 12) if r["name"].startswith("blueprint-")]
            if not matches:
                return None
            return matches[0]["name"], (self.skills.read(matches[0]["name"]).get("instructions") or "")[:3500]
        except Exception:
            return None

    @staticmethod
    def validate_plan(data, departments: dict[str, dict]) -> tuple[dict, list[str]]:
        problems: list[str] = []
        if not isinstance(data, dict):
            return {}, ["the reply was not a JSON object"]
        spec = data.get("spec") if isinstance(data.get("spec"), dict) else {}
        tasks = data.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return {}, ["there were no tasks"]
        if len(tasks) > 25:
            problems.append(f"{len(tasks)} tasks is too many (at most 25)")
        clean, keys = [], set()
        for i, t in enumerate(tasks):
            if not isinstance(t, dict) or not str(t.get("title") or "").strip():
                problems.append(f"task {i + 1} has no title"); continue
            key = slug(t.get("key") or t["title"], 40)
            if key in keys:
                problems.append(f"duplicate task key {key}"); continue
            keys.add(key)
            dep_id = str(t.get("department") or "").strip().lower()
            dep = departments.get(dep_id) or departments.get(dep_id.split("/")[-1])
            if not dep:
                problems.append(f"task {key}: unknown department {dep_id!r}")
            clean.append({"key": key, "title": str(t["title"])[:200], "description": str(t.get("description") or t["title"]),
                          "department": dep, "depends": [slug(d, 40) for d in (t.get("depends") or []) if isinstance(d, str)],
                          "acceptance": [str(a)[:300] for a in (t.get("acceptance") or []) if str(a).strip()][:6],
                          "deliverables": [str(p).replace("\\", "/").lstrip("/")[:200]
                                           for p in (t.get("deliverables") or []) if str(p).strip()][:10]})
        for t in clean:
            for d in t["depends"]:
                if d not in keys:
                    problems.append(f"task {t['key']} depends on unknown task {d}")
            if not t["acceptance"]:
                problems.append(f"task {t['key']} has no acceptance criteria")
            if any(".." in p.split("/") or re.match(r"^[a-zA-Z]:", p) for p in t["deliverables"]):
                problems.append(f"task {t['key']} has a deliverable outside the workspace")
        cycle = find_cycle({t["key"]: [d for d in t["depends"] if d in keys] for t in clean})
        if cycle:
            problems.append("circular dependency: " + " -> ".join(cycle))
        return {"spec": spec, "tasks": clean}, problems

    def _pick(self, candidates: list[dict], text: str, exclude: set[str] = frozenset()) -> dict | None:
        words = set(re.findall(r"[a-z]{4,}", text.lower()))
        best, best_score = None, None
        for emp in candidates:
            if emp["id"] in exclude or emp["status"] != "active":
                continue
            score = 0.0
            for s in emp["skills"]:
                parts = set(s["name"].split("-"))
                score += TIER_WEIGHT.get(s["tier"], 0) * (1 + len(parts & words))
            score += {"specialist": 2, "lead": 1, "director": -3}.get(emp["level"], 0)
            score -= 2 * self.store.workload(emp["id"])
            if best_score is None or score > best_score:
                best, best_score = emp, score
        return best

    def _verifier_for(self, project: dict, task_text: str, assignee: str) -> dict | None:
        pools: list[list[dict]] = [[], [], []]
        for cid in project["companies"]:
            for emp in self.store.employees(cid):
                dep = self.store.department(emp["department_id"]) if emp.get("department_id") else {}
                if dep.get("key") == "verification":
                    pools[0].append(emp)
                elif any(s["name"] == "independent-verification" for s in emp["skills"]):
                    pools[1].append(emp)
                else:
                    pools[2].append(emp)
        for pool in pools:
            pick = self._pick(pool, task_text + " verification review", exclude={assignee})
            if pick:
                return pick
        return None

    def apply_plan(self, project_id: str, plan: dict, director: dict) -> dict:
        project = self.store.project(project_id)
        spec = plan.get("spec") or {}
        spec_md = "\n".join([f"# {project['name']}", "", f"**Goal:** {spec.get('goal') or project['request'][:300]}", ""]
                            + [f"## {title}\n" + "\n".join(f"- {x}" for x in spec.get(k) or []) + "\n"
                               for k, title in (("requirements", "Requirements"), ("acceptance", "Acceptance criteria"),
                                                ("assumptions", "Assumptions"), ("open_questions", "Open questions"))
                               if spec.get(k)])
        self.store.set_project(project_id, spec=spec)
        self.store.add_record(project_id, "spec", "Specification", spec_md, author=director["id"])
        tasks = list(plan["tasks"])
        if len(tasks) > 1:
            depended = {d for t in tasks for d in t["depends"]}
            sinks = [t["key"] for t in tasks if t["key"] not in depended]
            verification = next((d for d in self._department_map(project).values() if d["key"] == "verification"), None)
            tasks.append({"key": "final-check", "title": "Final end-to-end check of the whole delivery",
                          "description": "Check the complete project in the workspace against the specification: run "
                                         "it (or its tests) the way a user would, open the main files, and list "
                                         "anything missing or broken. Write your findings to FINAL_CHECK.md.",
                          "department": verification or tasks[-1]["department"], "depends": sinks,
                          "acceptance": ["Every acceptance criterion of the specification was checked and the result "
                                         "is written in FINAL_CHECK.md",
                                         *(spec.get("acceptance") or [])[:4]],
                          "deliverables": ["FINAL_CHECK.md"]})
        lines = []
        for position, t in enumerate(tasks):
            dep = t["department"]
            staff = [e for e in self.store.employees(dep["company_id"]) if e["department_id"] == dep["id"]]
            text = f"{t['title']} {t['description']}"
            assignee = self._pick(staff, text) or self._pick(self.store.employees(dep["company_id"]), text)
            if not assignee:
                raise ValueError(f"Nobody in {dep['name']} can take task {t['key']}.")
            verifier = self._verifier_for(project, text, assignee["id"])
            if not verifier:
                raise ValueError(f"No independent verifier is available for task {t['key']}.")
            row = self.store.add_task(project_id, key=t["key"], title=t["title"], description=t["description"],
                                      company_id=dep["company_id"], department_id=dep["id"], depends=t["depends"],
                                      acceptance=t["acceptance"], deliverables=t["deliverables"], position=position)
            self.store.update_task(row["id"], assignee=assignee["id"], verifier=verifier["id"])
            lines.append(f"{position + 1}. **{t['title']}** - {dep['name']} - {assignee['name']} ({assignee['title']}), "
                         f"verified by {verifier['name']}" + (f" - after: {', '.join(t['depends'])}" if t["depends"] else ""))
        self.store.add_record(project_id, "plan", "Plan", "\n".join(lines), author=director["id"])
        self.store.event("plan_ready", project_id=project_id, company_id=project["lead_company"], actor=director["id"],
                         tasks=len(tasks))
        if project["mode"] == "supervised":
            return self.store.set_project(project_id, status="awaiting_plan_approval")
        return self.approve_plan(project_id, actor="auto")

    def approve_plan(self, project_id: str, actor: str = "user") -> dict:
        project = self.store.project(project_id)
        if project["status"] not in ("awaiting_plan_approval", "planning"):
            raise ValueError(f"The project is {project['status']}, not waiting for plan approval.")
        self.store.event("plan_approved", project_id=project_id, company_id=project["lead_company"], actor=actor)
        project = self.store.set_project(project_id, status="running")
        self.request_test_permission(project)  # once, up front, so tests can gate every task
        self.wake()
        return project

    # ---- control -------------------------------------------------------------------------

    def pause(self, project_id: str) -> dict:
        return self.store.set_project(project_id, status="paused")

    def resume(self, project_id: str) -> dict:
        project = self.store.project(project_id)
        if project["status"] not in ("paused", "needs_user_input", "failed"):
            raise ValueError(f"The project is {project['status']}.")
        if project["status"] == "failed" and not self.store.tasks(project_id):
            threading.Thread(target=self._plan_safely, args=(project_id,), daemon=True).start()
            return self.store.set_project(project_id, status="planning", error=None)
        project = self.store.set_project(project_id, status="running", error=None)
        self.wake()
        return project

    def cancel(self, project_id: str) -> dict:
        for task in self.store.tasks(project_id):
            if task["state"] not in ("completed", "cancelled") and task["id"] not in self._busy:
                self.store.transition(task["id"], "cancelled", actor="user", reason="project cancelled")
        return self.store.set_project(project_id, status="cancelled")

    def retry_task(self, task_id: str, note: str = "") -> dict:
        task = self.store.task(task_id)
        if task["state"] not in ("failed", "needs_user_input", "blocked"):
            raise ValueError(f"Only failed, blocked or waiting tasks can be retried (this one is {task['state']}).")
        self.store.update_task(task_id, attempts=0, approval_id=None,
                               feedback=(note or task.get("feedback") or "")[:4000])
        self.store.transition(task_id, "ready", actor="user", reason=note or "retry")  # refuses unmet dependencies
        project = self.store.project(task["project_id"])
        if project["status"] in ("needs_user_input", "failed", "paused"):
            self.store.set_project(project["id"], status="running", error=None)
        self.wake()
        return self.store.task(task_id)

    # ---- scheduler -----------------------------------------------------------------------

    def start(self) -> None:
        """Recover interrupted work after a restart and start the scheduler thread."""
        self._started = True
        self.store.recover_interrupted()
        for project in self.store.projects():
            if project["status"] == "planning":
                if self.store.tasks(project["id"]):
                    self.store.set_project(project["id"], status="running")
                else:
                    threading.Thread(target=self._plan_safely, args=(project["id"],), daemon=True).start()
        self.ensure_thread()

    def ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, name="company-scheduler", daemon=True)
        self._thread.start()

    def wake(self) -> None:
        if self._started:  # before start() (tests, tools) the caller drives tick() itself
            self.ensure_thread()
        self._wake.set()

    def stop(self) -> None:
        self._stop = True
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop:
            try:
                did = self.tick()
            except Exception as exc:  # the scheduler must survive one bad project
                self.store.event("scheduler_error", error=redact_secrets(exc, 400))
                did = False
            if not did:
                self._wake.wait(3.0)
                self._wake.clear()

    def tick(self, run_inline: bool = False) -> bool:
        """One scheduling pass. Returns True when it started (or ran) work."""
        started = False
        for project in self.store.projects():
            if project["status"] != "running":
                continue
            tasks = self.store.tasks(project["id"])
            for task in tasks:
                if task["state"] == "draft" and not self.store.unmet_dependencies(task):
                    self.store.transition(task["id"], "ready", reason="dependencies completed")
                elif task["state"] == "needs_user_input" and task.get("approval_id"):
                    status = self.approval_status(task["approval_id"])
                    if status == "approved" and not self.store.unmet_dependencies(task):
                        # waiting for the user is not a failed attempt
                        self.store.update_task(task["id"], approval_id=None, attempts=max(0, int(task["attempts"]) - 1),
                                               feedback="Your earlier action was approved by the user - do it now.")
                        self.store.transition(task["id"], "ready", reason="approval granted")
                    elif status in ("denied", "expired"):
                        self.store.update_task(task["id"], approval_id=None)
                        self.store.transition(task["id"], "failed", reason=f"the user's approval was {status}")
            tasks = self.store.tasks(project["id"])
            if tasks and all(t["state"] in ("completed", "cancelled") for t in tasks):
                self.deliver(project["id"])
                continue
            ready = [t for t in tasks if t["state"] == "ready"]
            active = [t for t in tasks if t["state"] in ("assigned", "in_progress", "review", "verification")]
            if not ready and not active:
                stuck = [t for t in tasks if t["state"] in ("failed", "needs_user_input", "blocked")]
                if stuck:
                    waiting = [t for t in stuck if t["state"] == "needs_user_input" and t.get("approval_id")]
                    if not waiting or len(waiting) < len(stuck):
                        self.store.set_project(project["id"], status="needs_user_input",
                                               error=f"{len(stuck)} task(s) need you: " + ", ".join(t["title"] for t in stuck[:3]))
                continue
            for task in ready:
                with self._lock:
                    if len(self._busy) >= self.max_parallel or task["id"] in self._busy:
                        break
                    self._busy.add(task["id"])
                started = True
                if run_inline:
                    self._run_task_safely(task["id"])
                else:
                    threading.Thread(target=self._run_task_safely, args=(task["id"],), name=f"task-{task['id']}",
                                     daemon=True).start()
        return started

    def _run_task_safely(self, task_id: str) -> None:
        try:
            self.run_task(task_id)
        except Exception as exc:
            task = self.store.task(task_id)
            self.store.event("task_error", project_id=task["project_id"], task_id=task_id, error=redact_secrets(exc, 500))
            try:
                self.store.transition(task_id, "failed", reason=f"internal error: {redact_secrets(exc, 300)}")
            except InvalidTransition:
                pass
        finally:
            with self._lock:
                self._busy.discard(task_id)
            self._wake.set()

    # ---- one task ------------------------------------------------------------------------

    def _employee_turn(self, employee: dict, project: dict, task: dict, brief: str, role: str,
                       allowed: tuple[str, ...] = WORKER_TOOLS) -> dict:
        orchestrator = self.get_orchestrator() if self.get_orchestrator else None
        if orchestrator is None:
            raise RuntimeError("The assistant runtime is not available.")
        known = set(getattr(orchestrator, "tools", None) or ())
        pinned = tuple(n for n in allowed if n in known)
        excluded = tuple(sorted((known - set(allowed)) | set(EMPLOYEE_EXCLUDED)))
        calls: list[dict] = []
        answer, error, approval = "", None, None
        self.store.event("employee_started", project_id=project["id"], company_id=employee["company_id"],
                         task_id=task["id"], actor=employee["id"], name=employee["name"], title=employee["title"], role=role)
        started = time.time()
        pending_args: dict[str, list[dict]] = {}  # "started" events carry the args, "completed" ones the result
        # The tools run inside this scope (the stream is consumed here, in this thread): paths resolve in the
        # project folder and nothing outside it is reachable.
        with project_scope(project["workspace"], trust_commands=bool(project.get("trust_commands"))):
            stream = orchestrator.run_stream(brief, self.employee_context(employee, project), session_id=None,
                                             pinned_tools=pinned, excluded_tools=excluded, source="company",
                                             max_steps=STEPS.get(role, 20))
            for event in stream:
                kind = event.get("type")
                if kind == "tool" and event.get("status") == "started":
                    pending_args.setdefault(str(event.get("tool")), []).append(parse_args(event.get("args")))
                elif kind == "tool" and event.get("status") == "completed":
                    queue = pending_args.get(str(event.get("tool"))) or []
                    args = event.get("args") if isinstance(event.get("args"), dict) else (queue.pop(0) if queue else {})
                    call = {"tool": event.get("tool"), "ok": bool(event.get("ok")), "args": args,
                            "error": str(event.get("error") or "")[:300]}
                    calls.append(call)
                    if event.get("approval_id"):
                        approval = event.get("approval_id")
                    self.store.event("employee_step", project_id=project["id"], company_id=employee["company_id"],
                                     task_id=task["id"], actor=employee["id"], name=employee["name"], tool=call["tool"],
                                     ok=call["ok"], args=json.dumps(call["args"], ensure_ascii=False)[:240],
                                     error=call["error"][:200])
                elif kind == "final":
                    answer = str(event.get("text") or "")
                elif kind == "error":
                    error = str(event.get("error") or "the turn failed")
        self.store.event("employee_finished", project_id=project["id"], company_id=employee["company_id"],
                         task_id=task["id"], actor=employee["id"], name=employee["name"], role=role,
                         seconds=round(time.time() - started, 1), ok=error is None)
        return {"answer": answer, "calls": calls, "error": error, "approval_id": approval}

    def _dependency_notes(self, task: dict) -> str:
        if not task["depends"]:
            return ""
        notes = []
        for other in self.store.tasks(task["project_id"]):
            if other["key"] in task["depends"]:
                files = ", ".join(f["path"] for f in (other["evidence"] or {}).get("files", [])[:12])
                notes.append(f"- {other['title']}: {(other.get('result') or '')[:1500]}" + (f"\n  Files: {files}" if files else ""))
        return "Results of the tasks this one builds on:\n" + "\n".join(notes)

    def _inside(self, project: dict, raw: str, base: Path | None = None) -> bool:
        """Whether a path lands in the project folder. Relative paths resolve against ``base``: the main
        workspace for file tools (that is where they write), the project folder otherwise."""
        root = Path(project["workspace"]).resolve()
        p = Path(str(raw))
        resolved = (p if p.is_absolute() else (base or root) / p).resolve()
        return resolved == root or root in resolved.parents

    def collect_evidence(self, project: dict, task: dict, turn: dict, since: float | None = None) -> dict:
        root = Path(project["workspace"])
        checks = [{"name": "the employee reported back", "ok": bool(turn["answer"].strip()) and not turn["error"],
                   "detail": (turn["error"] or turn["answer"][:200])}]
        touched: list[str] = []
        violations, warnings = [], []
        for call in turn["calls"]:
            if call["tool"] in MUTATING_TOOLS:
                for key in PATH_ARGS:
                    value = call["args"].get(key)
                    if isinstance(value, str) and value.strip():
                        if call["ok"]:
                            touched.append(value)
                        # employee turns run in the project scope, so relative paths land in the project folder
                        if not self._inside(project, value):
                            violations.append(f"{call['tool']} {value} (use the full path inside {project['workspace']})")
            elif call["tool"] in SHELL_TOOLS:
                cwd = str(call["args"].get("cwd") or ".")
                if not self._inside(project, cwd) or cwd in (".", ""):
                    warnings.append(f"{call['tool']} ran outside the project folder (cwd={cwd})")
        checks.append({"name": "all file changes stayed inside the project workspace", "ok": not violations,
                       "detail": "; ".join(violations[:5]) or "ok"})
        files = []
        for rel in task["deliverables"]:
            target = (root / rel).resolve()
            if target.is_dir():  # a folder deliverable (venv/, templates/) must not be empty
                ok = any(target.iterdir()) and self._inside(project, str(target))
                detail = "folder with files" if ok else "empty folder"
            else:
                ok = target.is_file() and target.stat().st_size > 0 and self._inside(project, str(target))
                detail = f"{target.stat().st_size} bytes" if target.is_file() else "missing"
            checks.append({"name": f"deliverable exists: {rel}", "ok": ok, "detail": detail})
        # what this attempt produced (new projects: everything in the folder; existing ones: what changed)
        changed_since = since if project.get("existing_folder") else None
        for p in list_files(root, limit=200, since=changed_since):
            data = p.read_bytes()
            files.append({"path": str(p.relative_to(root)).replace("\\", "/"), "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()[:16], "modified": p.stat().st_mtime})
        return {"checks": checks, "tool_calls": [{k: c[k] for k in ("tool", "ok", "error")} |
                                                 {"args": json.dumps(c["args"], ensure_ascii=False)[:300]}
                                                 for c in turn["calls"][:60]],
                "touched": touched[:50], "warnings": warnings[:10], "files": files, "report": turn["answer"][:6000]}

    def run_task(self, task_id: str) -> dict:
        task = self.store.task(task_id)
        project = self.store.project(task["project_id"])
        if project["status"] != "running" or task["state"] != "ready":
            return task
        worker = self.store.employee(task["assignee"])
        verifier = self.store.employee(task["verifier"])
        if worker["company_id"] not in project["companies"] or verifier["company_id"] not in project["companies"]:
            self.store.transition(task_id, "blocked", reason="assigned employee's company is not authorized")
            return self.store.task(task_id)
        attempts = int(task["attempts"]) + 1
        self.store.update_task(task_id, attempts=attempts)
        self.store.transition(task_id, "assigned", actor="scheduler", reason=f"to {worker['name']}")
        self.store.transition(task_id, "in_progress", actor=worker["id"], reason=f"attempt {attempts}")
        criteria = "\n".join(f"- {a}" for a in task["acceptance"])
        deliverables = "\n".join(f"- {Path(project['workspace']) / d}" for d in task["deliverables"])
        brief = "\n\n".join(x for x in [
            f"Project: {project['name']}\nGoal: {(project['spec'] or {}).get('goal') or project['request'][:600]}",
            f"YOUR TASK: {task['title']}\n{task['description']}",
            f"Acceptance criteria (an independent verifier will check each one):\n{criteria}",
            f"Files you must produce:\n{deliverables}" if deliverables else "",
            self._dependency_notes(task),
            f"Feedback from the last check - fix this first:\n{task['feedback']}" if task.get("feedback") else "",
            f"Work in {project['workspace']}. Use the tools to create/change files and to run what you build. "
            "When finished, reply with a short report: what you did, the files you created or changed, the commands "
            "you ran and their real output, and anything not done.",
        ] if x)
        attempt_started = time.time() - 2
        turn = self._employee_turn(worker, project, task, brief, "worker")
        if turn["approval_id"]:
            status = self.approval_status(turn["approval_id"])
            if status in (None, "pending"):
                self.store.update_task(task_id, approval_id=turn["approval_id"], result=turn["answer"][:6000])
                self.store.transition(task_id, "needs_user_input", actor=worker["id"],
                                      reason="waiting for your approval of an action")
                return self.store.task(task_id)
            if status == "approved":  # approved while the turn was ending: just go again, no attempt used
                self.store.update_task(task_id, attempts=max(0, attempts - 1),
                                       feedback="Your earlier action was approved by the user - do it now and finish the task.")
                self.store.transition(task_id, "ready", actor="system", reason="approval granted")
                self.wake()
                return self.store.task(task_id)
        evidence = self.collect_evidence(project, task, turn, since=attempt_started)
        gate = self.quality_gate(self.store.project(project["id"]), since=attempt_started)
        evidence["checks"].extend(gate["checks"])
        evidence["audit"] = gate["audit"]
        self.store.update_task(task_id, evidence=evidence, result=turn["answer"][:6000])
        self.store.transition(task_id, "review", actor=worker["id"], reason="work submitted")
        failed = [c for c in evidence["checks"] if not c["ok"]]
        if failed:
            return self._reject(task_id, project, "Automated checks failed: " + "; ".join(
                f"{c['name']} ({c['detail']})" for c in failed), actor="system")
        self.store.transition(task_id, "verification", actor="system", reason=f"to {verifier['name']}")
        verdict = self.verify(task_id, project, verifier, evidence)
        if verdict.get("no_verdict"):  # the verifier's failure, not the worker's: ask once more
            verdict = self.verify(task_id, project, verifier, evidence)
        if verdict.get("verdict") == "pass":
            self.store.complete_task(task_id, verifier=verifier["id"], verdict=verdict)
            if task.get("feedback"):  # it failed before: remember what fixed it
                self.store.add_lesson(task["company_id"], f"'{task['title']}' passed after fixing: "
                                      f"{task['feedback'][:180]} -> {turn['answer'][:200]}", project_id=project["id"],
                                      task_id=task_id)
            self.wake()
            return self.store.task(task_id)
        if verdict.get("approval_id"):
            self.store.update_task(task_id, approval_id=verdict["approval_id"])
            self.store.transition(task_id, "needs_user_input", actor=verifier["id"],
                                  reason="the verifier is waiting for your approval of an action")
            return self.store.task(task_id)
        return self._reject(task_id, project, "Verification failed: " + "; ".join(verdict.get("problems") or ["no reason given"]),
                            actor=verifier["id"])

    # ---- deterministic quality gate (the project-audit skill's script) ------------------------

    def tests_allowed(self, project: dict) -> bool:
        """Running a project's tests executes AI-written code: allowed when the user trusted the project's
        commands or approved test runs for it (asked once per project, never per task)."""
        if project.get("trust_commands") or project.get("checks_approved"):
            return True
        approval_id = project.get("checks_approval_id")
        if approval_id and self.approval_status(approval_id) == "approved":
            self.store.set_project(project["id"], checks_approved=1)
            return True
        return False

    def request_test_permission(self, project: dict) -> None:
        if self.request_approval is None or self.tests_allowed(project):
            return
        if project.get("checks_approval_id") and self.approval_status(project["checks_approval_id"]) in ("pending", None):
            return  # already asked
        try:
            decision = self.request_approval(
                f"Let company project '{project['name']}' run its automated tests in {project['workspace']} after each task",
                "The company's quality gate runs the project's own test suite (e.g. pytest) inside the project folder "
                "to prove each task works. This executes the code the employees wrote. Asked once for this project.")
        except Exception:
            return
        if decision.get("allowed"):
            self.store.set_project(project["id"], checks_approved=1)
        elif decision.get("approval_id"):
            self.store.set_project(project["id"], checks_approval_id=decision["approval_id"])
            self.store.event("tests_permission_requested", project_id=project["id"], approval_id=decision["approval_id"])

    def quality_gate(self, project: dict, since: float | None = None) -> dict:
        """Deterministic checks after every task: Python syntax, security findings in what changed, and - when
        allowed - the project's own tests. They decide, not the model."""
        try:
            from living_assistant.companies.audit_gate import audit_module
            audit = audit_module()
        except Exception as exc:  # a broken audit install must not silently pass work
            return {"checks": [{"name": "quality gate available", "ok": False, "detail": redact_secrets(exc, 200)}],
                    "audit": {}}
        root = Path(project["workspace"])
        checks, details = [], {}
        syn = audit.syntax(root)
        details["syntax"] = syn
        checks.append({"name": "Python files parse", "ok": syn["ok"],
                       "detail": "; ".join(f"{e['path']}:{e['line']} {e['message']}" for e in syn["errors"][:3])
                                 or f"{syn['files_checked']} files"})
        changed = [str(p.relative_to(root)).replace("\\", "/") for p in list_files(root, limit=400, since=since)]
        sec = audit.security(root, files=changed)
        details["security"] = sec
        bad = [f for f in sec["findings"] if f["severity"] in ("critical", "high")]
        checks.append({"name": "no critical/high security findings in changed files", "ok": not bad,
                       "detail": "; ".join(f"{f['path']}:{f['line']} {f['message']}" for f in bad[:4]) or
                                 f"{len(changed)} changed files scanned"})
        plan = audit.checks(root)
        details["checks"] = plan
        if plan["has_checks"]:
            if self.tests_allowed(project):
                ran = audit.run_checks(root, timeout=300)
                details["tests"] = ran
                failing = [r for r in ran["results"] if not r["passed"]]
                checks.append({"name": "the project's automated tests pass", "ok": not failing,
                               "detail": "; ".join(f"{r['purpose']}: {r['summary'] or 'failed'}" for r in failing[:3])
                                         or "; ".join(r["summary"] for r in ran["results"] if r["summary"])[:300] or "passed"})
            else:
                self.request_test_permission(project)
                details["tests"] = {"ran": False, "reason": "waiting for your permission to run tests in this project"}
        return {"checks": checks, "audit": details}

    @staticmethod
    def _audit_summary(evidence: dict) -> str:
        audit = evidence.get("audit") or {}
        tests = audit.get("tests") or {}
        lines = []
        if tests.get("ran"):
            lines.append("Automated tests were run by the system: " + "; ".join(
                f"{r['purpose']}: {'PASSED' if r['passed'] else 'FAILED'} {r['summary']}" for r in tests["results"]))
        elif tests.get("reason"):
            lines.append(f"Automated tests were not run by the system ({tests['reason']}).")
        sec = (audit.get("security") or {}).get("findings") or []
        if sec:
            lines.append("Security scan notes: " + "; ".join(f"{f['path']}:{f['line']} {f['message']} ({f['severity']})"
                                                            for f in sec[:5]))
        return ("System checks (trustworthy):\n" + "\n".join(lines) + "\n\n") if lines else ""

    def verify(self, task_id: str, project: dict, verifier: dict, evidence: dict) -> dict:
        task = self.store.task(task_id)
        criteria = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(task["acceptance"]))
        files = "\n".join(f"- {f['path']} ({f['bytes']} bytes)" for f in evidence["files"][:40])
        brief = (
            f"VERIFY someone else's work. You did not do it; check it yourself.\nProject workspace: {project['workspace']}\n"
            f"Task: {task['title']}\n{task['description']}\n\nAcceptance criteria:\n{criteria}\n\n"
            f"The worker's report (do not trust it until checked):\n{evidence['report'][:3000]}\n\n"
            f"Files now in the workspace:\n{files or 'none'}\n\n"
            + self._audit_summary(evidence) +
            "Open the relevant files and run what can be run (run_command with the project workspace as cwd). You "
            "cannot change files: verification never alters the work. Then reply with ONLY JSON: {\"verdict\": "
            "\"pass\"|\"fail\", \"criteria\": [{\"criterion\": str, \"ok\": bool, \"evidence\": what you checked and "
            "saw}], \"problems\": [str]}. Pass only if every criterion is met.")
        turn = self._employee_turn(verifier, project, task, brief, "verifier", allowed=VERIFIER_TOOLS)
        data = extract_json(turn["answer"]) or {}
        verdict = {"verdict": "fail", "criteria": data.get("criteria") if isinstance(data.get("criteria"), list) else [],
                   "problems": [str(p)[:400] for p in (data.get("problems") or []) if str(p).strip()][:10],
                   "inspections": sum(1 for c in turn["calls"] if c["ok"]), "raw": turn["answer"][:3000]}
        if turn["approval_id"] and self.approval_status(turn["approval_id"]) in (None, "pending"):
            verdict["approval_id"] = turn["approval_id"]
            return verdict
        if turn["error"]:
            verdict["problems"].insert(0, f"verifier's turn failed: {turn['error'][:200]}")
            verdict["no_verdict"] = True
        elif str(data.get("verdict")).lower() != "pass":
            if not data:
                verdict["problems"].insert(0, "the verifier gave no verdict")
                verdict["no_verdict"] = True
        elif task["deliverables"] and verdict["inspections"] == 0:
            verdict["problems"].insert(0, "the verifier passed it without opening or running anything")
        elif verdict["criteria"] and not all(c.get("ok") for c in verdict["criteria"] if isinstance(c, dict)):
            verdict["problems"].insert(0, "the verifier said pass but marked a criterion as not met")
        else:
            verdict["verdict"] = "pass"
        self.store.event("verification", project_id=project["id"], company_id=verifier["company_id"], task_id=task_id,
                         actor=verifier["id"], name=verifier["name"], verdict=verdict["verdict"],
                         problems=verdict["problems"][:5])
        return verdict

    def _reject(self, task_id: str, project: dict, feedback: str, actor: str) -> dict:
        task = self.store.task(task_id)
        self.store.update_task(task_id, feedback=feedback[:4000])
        self.store.add_lesson(task["company_id"], f"'{task['title']}' was rejected: {feedback[:300]}",
                              project_id=project["id"], task_id=task_id)
        if int(task["attempts"]) < MAX_ATTEMPTS.get(project["mode"], 2):
            if task["state"] == "verification":
                self.store.transition(task_id, "in_progress", actor=actor, reason=feedback[:300])
            elif task["state"] == "review":
                self.store.transition(task_id, "in_progress", actor=actor, reason=feedback[:300])
            self.store.transition(task_id, "ready", actor=actor, reason="sent back for another attempt")
        else:
            self.store.transition(task_id, "failed", actor=actor, reason=feedback[:300])
        self.wake()
        return self.store.task(task_id)

    # ---- delivery ------------------------------------------------------------------------

    def deliver(self, project_id: str) -> dict:
        project = self.store.project(project_id)
        tasks = self.store.tasks(project_id)
        names = {}
        for cid in project["companies"]:
            for emp in self.store.employees(cid, include_inactive=True):
                names[emp["id"]] = f"{emp['name']} ({emp['title']})"
        lines = [f"# Delivery report: {project['name']}", "",
                 f"Goal: {(project['spec'] or {}).get('goal') or project['request'][:400]}", "",
                 f"Workspace: {project['workspace']}", "", "## Tasks", ""]
        for t in tasks:
            verification = (t["evidence"] or {}).get("verification") or {}
            lines.append(f"- [{t['state']}] **{t['title']}** - done by {names.get(t['assignee'], '?')}, verified by "
                         f"{names.get(t['verifier'], '?')} after {t['attempts']} attempt(s)")
            for c in verification.get("criteria") or []:
                if isinstance(c, dict):
                    lines.append(f"  - {'PASS' if c.get('ok') else 'FAIL'}: {c.get('criterion')} - {str(c.get('evidence'))[:200]}")
        files = sorted({f["path"] for t in tasks for f in (t["evidence"] or {}).get("files", [])})
        lines += ["", "## Files", ""] + [f"- {f}" for f in files[:200]]
        try:
            from living_assistant.companies.audit_gate import audit_module
            health = audit_module().health(Path(project["workspace"]), run=False)
            lines += ["", f"## Project health: {health['score']}/100", "",
                      ", ".join(f"{k} {v}" for k, v in health["dimensions"].items())]
            lines += [f"- {f.get('severity')}: {f.get('message')}" + (f" ({f['path']}:{f.get('line')})" if f.get("path") else "")
                      for f in health["findings"][:12]]
        except Exception:
            pass
        cancelled = [t for t in tasks if t["state"] == "cancelled"]
        if cancelled:
            lines += ["", "## Not done", ""] + [f"- {t['title']} (cancelled)" for t in cancelled]
        report = "\n".join(lines)
        if not project.get("existing_folder"):  # never add files to the user's own project unasked
            try:
                (Path(project["workspace"]) / "DELIVERY_REPORT.md").write_text(report, encoding="utf-8")
            except OSError:
                pass
        self.store.add_record(project_id, "report", "Delivery report", report)
        return self.store.set_project(project_id, status="delivered", report=report)

    # ---- views ---------------------------------------------------------------------------

    def project_view(self, project_id: str) -> dict:
        project = self.store.project(project_id)
        people = {}
        for cid in project["companies"]:
            company = self.store.company(cid)
            for emp in self.store.employees(cid, include_inactive=True):
                people[emp["id"]] = {"id": emp["id"], "name": emp["name"], "title": emp["title"], "company": company["name"]}
        tasks = self.store.tasks(project_id)
        busy = set(self._busy)
        for t in tasks:
            t["running"] = t["id"] in busy
            t["unmet"] = self.store.unmet_dependencies(t)
        return {"project": {**project, "progress": self.store.progress(project_id)}, "tasks": tasks, "people": people,
                "records": self.store.records(project_id), "events": self.store.events(project_id=project_id, limit=300),
                "companies": [self.store.company(c) for c in project["companies"]]}
