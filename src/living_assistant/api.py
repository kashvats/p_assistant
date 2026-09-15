from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from .runtime import build_runtime

app = FastAPI(title="Living Assistant Local API", version="0.1.0")
runtime = None

class AskRequest(BaseModel):
    message: str
    context: str = ""

def _rt():
    global runtime
    if runtime is None:
        runtime = build_runtime(interactive=False)
    return runtime

def _auth(authorization: str | None):
    token = os.environ.get("ASSISTANT_API_TOKEN","")
    if token:
        expected = f"Bearer {token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
def health():
    return {"ok":True,"service":"living-assistant"}

@app.get("/status")
def status(authorization: str | None = Header(default=None)):
    _auth(authorization)
    rt = _rt()
    return {"profile":rt.profile,"hardware":rt.hardware.to_dict()}

@app.post("/ask")
def ask(req: AskRequest, authorization: str | None = Header(default=None)):
    _auth(authorization)
    # Noninteractive API refuses actions that require approval.
    return {"answer":_rt().orchestrator.run(req.message, req.context)}
