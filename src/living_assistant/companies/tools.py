"""Chat tools: list/create companies and run projects with them."""
from __future__ import annotations

import functools
from typing import Callable

from living_assistant.companies.templates import template_summaries
from living_assistant.security.security_utils import redact_secrets
from living_assistant.tools.base import Tool


def build_company_tools(get_engine: Callable) -> list[Tool]:
    def safe(fn):
        @functools.wraps(fn)
        def wrapper(**kwargs):
            try:
                return fn(**kwargs)
            except (KeyError, ValueError) as exc:
                return {"ok": False, "error": str(exc).strip("'\"")}
            except Exception as exc:
                return {"ok": False, "error": redact_secrets(exc, 600)}
        return wrapper

    def find_company(ref: str) -> dict:
        store = get_engine().store
        ref = str(ref or "").strip()
        for c in store.companies():
            if ref in (c["id"], c["name"]) or ref.lower() == c["name"].lower():
                return c
        matches = [c for c in store.companies() if ref.lower() in c["name"].lower()]
        if len(matches) == 1:
            return matches[0]
        raise KeyError(f"No company {ref!r}; use company_list to see them")

    @safe
    def company_list():
        store = get_engine().store
        return {"ok": True, "companies": [{"id": c["id"], "name": c["name"], "description": c["description"],
                                           "employees": c["employees"], "departments": c["departments"]}
                                          for c in store.companies()],
                "templates": template_summaries(),
                "projects": [{"id": p["id"], "name": p["name"], "status": p["status"], "progress": p["progress"]}
                             for p in store.projects()[:10]]}

    @safe
    def company_create(template: str = "", description: str = "", name: str = ""):
        engine = get_engine()
        if template:
            company = engine.create_from_template(template, name)
        elif description:
            company = engine.create_from_description(description, name)
        else:
            return {"ok": False, "error": "Give a template id (software, research, office) or describe the company."}
        return {"ok": True, "company": {"id": company["id"], "name": company["name"],
                                        "departments": [d["name"] for d in company["departments"]],
                                        "employees": [f"{e['name']} - {e['title']}" for e in company["employees"]]}}

    @safe
    def project_start(request: str, company: str, partner_companies: list | None = None, mode: str = "balanced",
                      name: str = "", folder: str = ""):
        engine = get_engine()
        lead = find_company(company)
        partners = [find_company(c)["id"] for c in partner_companies or []]
        # trusting commands is the user's choice in the Companies page, never something chat turns on
        project = engine.start_project(request, lead["id"], partners, mode=mode, name=name, folder=folder)
        return {"ok": True, "project_id": project["id"], "status": project["status"], "workspace": project["workspace"],
                "note": "The project director is planning it now; it runs in the background. Follow it on the "
                        "Companies page or with project_status."
                        + (" Supervised mode: the plan waits for your approval." if mode == "supervised" else "")}

    @safe
    def project_status(project: str = ""):
        engine = get_engine()
        if not project:
            return {"ok": True, "projects": [{"id": p["id"], "name": p["name"], "status": p["status"],
                                              "progress": p["progress"]} for p in engine.store.projects()[:20]]}
        view = engine.project_view(project)
        p = view["project"]
        return {"ok": True, "name": p["name"], "status": p["status"], "error": p.get("error"),
                "workspace": p["workspace"], "progress": p["progress"],
                "tasks": [{"id": t["id"], "title": t["title"], "state": t["state"],
                           "assignee": view["people"].get(t["assignee"], {}).get("name"),
                           "verifier": view["people"].get(t["verifier"], {}).get("name"),
                           "feedback": (t.get("feedback") or "")[:300]} for t in view["tasks"]],
                "report": (p.get("report") or "")[:3000]}

    @safe
    def project_approve_plan(project: str):
        return {"ok": True, "status": get_engine().approve_plan(project)["status"]}

    @safe
    def project_control(project: str, action: str, task: str = "", note: str = ""):
        engine = get_engine()
        if action == "pause":
            return {"ok": True, "status": engine.pause(project)["status"]}
        if action == "resume":
            return {"ok": True, "status": engine.resume(project)["status"]}
        if action == "cancel":
            return {"ok": True, "status": engine.cancel(project)["status"]}
        if action == "retry_task":
            return {"ok": True, "task_state": engine.retry_task(task, note)["state"]}
        return {"ok": False, "error": "action must be pause, resume, cancel or retry_task"}

    obj, s = {"type": "object"}, {"type": "string"}
    return [
        Tool("company_list", "List the user's AI companies (departments of employee agents), company templates and "
                             "recent company projects.", {**obj, "properties": {}}, company_list),
        Tool("company_create", "Create an AI company: from a template (software = full software development company, "
                               "research = research & content studio, office = office operations) or by describing "
                               "what the company should do.",
             {**obj, "properties": {"template": s, "description": s, "name": s}}, company_create),
        Tool("project_start", "Give a project to a company: its project director plans it, employees do the tasks, "
                              "independent verifiers check them, and a delivery report is written. Runs in the "
                              "background. mode: supervised (you approve the plan) | balanced | autonomous. folder: an "
                              "existing project folder to improve instead of building something new.",
             {**obj, "properties": {"request": s, "company": s, "partner_companies": {"type": "array", "items": s},
                                    "mode": {"type": "string", "enum": ["supervised", "balanced", "autonomous"]},
                                    "name": s, "folder": s}, "required": ["request", "company"]}, project_start),
        Tool("project_status", "Status of a company project (tasks, who does and verifies them, report); no id lists "
                               "projects.", {**obj, "properties": {"project": s}}, project_status),
        Tool("project_approve_plan", "Approve a supervised project's plan so the work starts.",
             {**obj, "properties": {"project": s}, "required": ["project"]}, project_approve_plan),
        Tool("project_control", "Pause, resume or cancel a company project, or retry a failed task (with a note).",
             {**obj, "properties": {"project": s, "action": {"type": "string",
                                                             "enum": ["pause", "resume", "cancel", "retry_task"]},
                                    "task": s, "note": s}, "required": ["project", "action"]}, project_control),
    ]
