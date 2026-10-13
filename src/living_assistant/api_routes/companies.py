"""AI companies, their org charts and projects for the control centers."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.companies.store import InvalidTransition
from living_assistant.companies.templates import template_summaries

router = APIRouter(prefix="/companies", tags=["companies"])


def _engine():
    engine = getattr(runtime(), "companies", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Companies are not available.")
    return engine


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\""))
    except (ValueError, InvalidTransition) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


class CompanyBody(BaseModel):
    template: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=3000)
    name: str = Field(default="", max_length=80)


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    mission: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, max_length=20)
    skills: list[str] | None = Field(default=None, max_length=40)


class DepartmentBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    mission: str = Field(default="", max_length=1000)
    skills: list[str] = Field(default_factory=list, max_length=40)


class EmployeeBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    level: str = Field(default="specialist", max_length=20)
    department_id: str | None = Field(default=None, max_length=40)
    reports_to: str | None = Field(default=None, max_length=40)
    responsibilities: str = Field(default="", max_length=2000)
    instructions: str = Field(default="", max_length=6000)
    mbti: str = Field(default="", max_length=8)
    skills: list[dict] = Field(default_factory=list, max_length=30)


class EmployeePatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=20)
    department_id: str | None = Field(default=None, max_length=40)
    reports_to: str | None = Field(default=None, max_length=40)
    responsibilities: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=6000)
    mbti: str | None = Field(default=None, max_length=8)
    skills: list[dict] | None = Field(default=None, max_length=30)


class ProjectBody(BaseModel):
    request: str = Field(min_length=8, max_length=20000)
    company: str = Field(min_length=1, max_length=40)
    partners: list[str] = Field(default_factory=list, max_length=5)
    mode: str = Field(default="balanced", max_length=20)
    name: str = Field(default="", max_length=120)
    trust_commands: bool = False  # build/test commands inside the project folder run without asking
    folder: str = Field(default="", max_length=500)  # an existing project folder to improve


class RetryBody(BaseModel):
    note: str = Field(default="", max_length=4000)


@router.get("")
def companies_overview(authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine = _engine()
    return {"companies": engine.store.companies(), "templates": template_summaries(),
            "projects": engine.store.projects(), "skills": sorted(engine.known_skills())}


@router.post("")
def company_create(body: CompanyBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine = _engine()
    if body.template:
        return _call(engine.create_from_template, body.template, body.name)
    if body.description.strip():
        return _call(engine.create_from_description, body.description, body.name)
    raise HTTPException(status_code=400, detail="Choose a template or describe the company.")


@router.get("/projects/{project_id}")
def project_view(project_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().project_view, project_id)


@router.post("/projects")
def project_create(body: ProjectBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().start_project, body.request, body.company, body.partners, mode=body.mode, name=body.name,
                 trust_commands=body.trust_commands, folder=body.folder)


class ModeBody(BaseModel):
    mode: str = Field(min_length=1, max_length=20)


@router.put("/projects/{project_id}/mode")
def project_mode(project_id: str, body: ModeBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().set_mode, project_id, body.mode)


@router.delete("/projects/{project_id}")
def project_delete(project_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().delete_project, project_id)


@router.post("/projects/{project_id}/{action}")
def project_action(project_id: str, action: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine = _engine()
    actions = {
        "approve": engine.approve_plan,
        "pause": engine.pause,
        "resume": engine.resume,
        "cancel": engine.cancel,
        "delete": engine.delete_project,
    }
    if action not in actions:
        raise HTTPException(status_code=404, detail="Unknown project action.")
    return _call(actions[action], project_id)


@router.post("/tasks/{task_id}/retry")
def task_retry(task_id: str, body: RetryBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().retry_task, task_id, body.note)


@router.get("/{company_id}")
def company_view(company_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    engine = _engine()
    company = _call(engine.store.company_full, company_id)
    for emp in company["employees"]:
        emp["portfolio"] = engine.skill_portfolio(emp)
        emp["workload"] = engine.store.workload(emp["id"])
    company["projects"] = engine.store.projects(company_id)
    company["events"] = engine.store.events(company_id=company_id, limit=60)
    return company


@router.patch("/{company_id}")
def company_update(company_id: str, body: CompanyPatch, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().store.update_company, company_id, **body.model_dump())


@router.delete("/{company_id}")
def company_delete(company_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().store.delete_company, company_id)


@router.post("/{company_id}/departments")
def department_add(company_id: str, body: DepartmentBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().store.add_department, company_id, body.name, mission=body.mission, skills=body.skills)


@router.post("/{company_id}/employees")
def employee_add(company_id: str, body: EmployeeBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_engine().store.add_employee, company_id, **body.model_dump())


@router.patch("/{company_id}/employees/{employee_id}")
def employee_update(company_id: str, employee_id: str, body: EmployeePatch,
                    authorization: str | None = Header(default=None)):
    authorize(authorization)
    store = _engine().store
    if _call(store.employee, employee_id)["company_id"] != company_id:
        raise HTTPException(status_code=404, detail="No such employee in this company.")
    return _call(store.update_employee, employee_id, **body.model_dump())


@router.delete("/{company_id}/employees/{employee_id}")
def employee_remove(company_id: str, employee_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    store = _engine().store
    if _call(store.employee, employee_id)["company_id"] != company_id:
        raise HTTPException(status_code=404, detail="No such employee in this company.")
    return _call(store.remove_employee, employee_id)
