"""SKILL.md skills on the dashboard: list, find (installed and SkillHub), install, read, learn, edit, remove, restore."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.skills.library import SkillError, skillhub_search

router = APIRouter(prefix="/skill-library", tags=["skills"])


def _lib():
    lib = getattr(runtime(), "skill_library", None)
    if lib is None:
        raise HTTPException(status_code=503, detail="The skill library is not available.")
    return lib


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class InstallRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2000)
    subpath: str = Field(default="", max_length=500)
    name: str = Field(default="", max_length=64)
    replace: bool = False


class LearnRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    goal: str = Field(default="", max_length=2000)
    material: str = Field(default="", max_length=200_000)
    replace: bool = False


class EditRequest(BaseModel):
    description: str = Field(default="", max_length=1000)
    instructions: str | None = Field(default=None, max_length=200_000)


@router.get("")
def skill_library_list(authorization: str | None = Header(default=None)):
    authorize(authorization)
    lib = _lib()
    return {"skills": lib.list(), "trash": [{k: t.get(k) for k in ("trash_name", "name", "description")} for t in lib.trash()],
            "folder": str(lib.root)}


@router.get("/search")
def skill_library_search(q: str = Query(min_length=1, max_length=300), hub: bool = True,
                         authorization: str | None = Header(default=None)):
    authorize(authorization)
    lib = _lib()
    out = {"installed": [{"name": r["name"], "description": r["description"]} for r in lib.relevant(q, 20)]}
    if hub:
        try:
            out["skillhub"] = skillhub_search(q, 20)
        except SkillError as exc:
            out["skillhub_error"] = str(exc)
    return out


@router.post("/preview")
def skill_library_preview(req: InstallRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"skills": _call(_lib().inspect, req.source, req.subpath, req.name)}


@router.post("/install")
def skill_library_install(req: InstallRequest, authorization: str | None = Header(default=None)):
    """Pressing Install on the dashboard is the user's consent; replace overwrites an installed copy."""
    authorize(authorization)
    return {"installed": _call(_lib().install, req.source, req.subpath, req.name, force=req.replace)}


@router.post("/learn")
def skill_library_learn(req: LearnRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_lib().learn, req.name, req.goal, req.material, force=req.replace)


@router.get("/{name}")
def skill_library_read(name: str, file: str = Query(default="", max_length=500), authorization: str | None = Header(default=None)):
    authorize(authorization)
    try:
        return _lib().read(name, file)
    except SkillError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/{name}")
def skill_library_edit(name: str, req: EditRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_lib().edit, name, description=req.description or None, instructions=req.instructions)


@router.delete("/{name}")
def skill_library_remove(name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_lib().remove, name)


@router.post("/trash/{trash_name}/restore")
def skill_library_restore(trash_name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    return _call(_lib().restore, trash_name)
