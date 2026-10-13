"""Agents, agent templates, teams and personalities for the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.experts.store import mbti_catalog

router = APIRouter(prefix="/experts", tags=["agents"])


def _store():
    store = getattr(runtime(), "experts", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Agents are not available.")
    return store


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class AgentBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="bot", max_length=40)
    color: str = Field(default="#6366f1", max_length=20)
    mbti: str = Field(default="", max_length=8)
    instructions: str = Field(default="", max_length=12_000)
    skills: list[str] = Field(default_factory=list, max_length=40)
    welcome: str = Field(default="", max_length=300)
    quick_prompts: list[dict] = Field(default_factory=list, max_length=6)


class HireBody(BaseModel):
    template: str = Field(min_length=1, max_length=80)
    name: str = Field(default="", max_length=80)


class TeamBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="users", max_length=40)
    color: str = Field(default="#0ea5e9", max_length=20)
    lead_instructions: str = Field(default="", max_length=12_000)
    members: list[str] = Field(default_factory=list, max_length=8)


class BindBody(BaseModel):
    target: str = Field(min_length=1, max_length=90)


@router.get("")
def experts_overview(authorization: str | None = Header(default=None)):
    """Everything the agent pages need in one call."""
    authorize(authorization)
    store = _store()
    return {"agents": store.agents(), "teams": store.teams(), "templates": store.templates(), "personalities": mbti_catalog()}


@router.post("/agents")
def agent_create(body: AgentBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().save_agent, body.model_dump())


@router.put("/agents/{agent_id}")
def agent_update(agent_id: str, body: AgentBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().save_agent, body.model_dump(), agent_id)


@router.delete("/agents/{agent_id}")
def agent_delete(agent_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().delete_agent, agent_id)


@router.post("/hire")
def agent_hire(body: HireBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().hire, body.template, body.name)


@router.post("/teams")
def team_create(body: TeamBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().save_team, body.model_dump())


@router.put("/teams/{team_id}")
def team_update(team_id: str, body: TeamBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().save_team, body.model_dump(), team_id)


@router.delete("/teams/{team_id}")
def team_delete(team_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_store().delete_team, team_id)


@router.get("/conversations/{session_id}")
def conversation_agent(session_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"session_id": session_id, "target": _store().bound(session_id)}


@router.put("/conversations/{session_id}")
def conversation_bind(session_id: str, body: BindBody, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"session_id": session_id, "target": _call(_store().bind, session_id, body.target)}
