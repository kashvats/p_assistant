from pathlib import Path
from fastapi import APIRouter, Header, HTTPException

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import ProjectOnboardRequest
from living_assistant.system.codebase_onboarding import CodebaseOnboardingEngine, OnboardingResult

router = APIRouter(tags=["workspace"])


@router.post("/projects/onboard", response_model=OnboardingResult)
def onboard_project(
    request: ProjectOnboardRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    target = Path(request.path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Target path does not exist or is not a directory: {request.path}",
        )

    rt = runtime()
    ws = rt.workspace if hasattr(rt, "workspace") and rt.workspace else None
    if ws is not None:
        try:
            target = ws.resolve(target)
        except Exception:
            from living_assistant.core.workspace import Workspace
            ws = Workspace([target])
    else:
        from living_assistant.core.workspace import Workspace
        ws = Workspace([target])

    engine = CodebaseOnboardingEngine(
        workspace=ws,
        codebase_index=rt.code_index if hasattr(rt, "code_index") else None,
    )
    result = engine.onboard_repository(target, update_graph=request.update_graph)
    if result.status == "FAILED":
        raise HTTPException(status_code=500, detail=result.error or "Onboarding failed.")

    if hasattr(rt, "projects") and rt.projects is not None:
        try:
            rt.projects.add(name=result.project_name, path=str(target))
        except Exception:
            pass

    return result


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


@router.get("/routines")
def routines(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().routines.list()

