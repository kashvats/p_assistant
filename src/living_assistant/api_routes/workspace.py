from __future__ import annotations

from fastapi import APIRouter, Header

from living_assistant.api_routes.dependencies import authorize, runtime

router = APIRouter(tags=["workspace"])


@router.get("/projects")
def projects(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().projects.list()


@router.get("/groups")
def groups(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().groups.list()


@router.get("/processes")
def processes(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().processes.list()


@router.get("/watches")
def watches(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().watches.list()


@router.get("/skills")
def skills(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().skills.list()


@router.get("/routines")
def routines(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().routines.list()
