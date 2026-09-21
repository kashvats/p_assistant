from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import PeerDelegateRequest

router = APIRouter(tags=["peers"])


@router.get("/peers")
def peers_list(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().peers.list_peers()


@router.post("/peer/delegate")
def peer_delegate(req: PeerDelegateRequest, authorization: str | None = Header(default=None)):
    result = runtime().peers.accept_delegation(
        authorization,
        role=req.role,
        task=req.task,
        context=req.context,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=int(result.pop("status_code", 500)), detail=result.get("error", "Peer delegation failed."))
    return result
