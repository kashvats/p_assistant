from __future__ import annotations
import os, html
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .runtime import build_runtime

app = FastAPI(title="Living Assistant Local API", version="0.2.0")
runtime = None

class AskRequest(BaseModel):
    message: str
    context: str = ""

class ApprovalDecision(BaseModel):
    approved: bool


def _rt():
    global runtime
    if runtime is None: runtime = build_runtime(interactive=False)
    return runtime


def _auth(authorization: str | None):
    token = os.environ.get("ASSISTANT_API_TOKEN", "")
    if token and authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
def health(): return {"ok":True,"service":"living-assistant","version":"0.2.0"}

@app.get("/status")
def status(authorization: str | None = Header(default=None)):
    _auth(authorization); rt = _rt()
    return {"profile":rt.profile,"hardware":rt.hardware.to_dict(),"resources":rt.resources.snapshot()}

@app.post("/ask")
def ask(req: AskRequest, authorization: str | None = Header(default=None)):
    _auth(authorization)
    return {"answer":_rt().orchestrator.run(req.message, req.context)}

@app.get("/projects")
def projects(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().projects.list()

@app.get("/processes")
def processes(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().processes.list()

@app.get("/events")
def events(limit: int = 100, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().memory.list_events(min(max(limit,1),500))

@app.get("/todos")
def todos(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().memory.list_todos(include_done=True)

@app.get("/approvals")
def approvals(status: str = "pending", authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().approvals.list(status=None if status == "all" else status)

@app.post("/approvals/{approval_id}")
def approval_decide(approval_id: str, decision: ApprovalDecision, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().approvals.resolve(approval_id, decision.approved)

@app.get("/watches")
def watches(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().watches.list()

@app.get("/skills")
def skills(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().skills.list()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    if os.environ.get("ASSISTANT_API_TOKEN"):
        return HTMLResponse("<h2>Living Assistant</h2><p>Dashboard is disabled while ASSISTANT_API_TOKEN is set. Use the authenticated API endpoints.</p>")
    page = r'''<!doctype html><html><head><meta charset="utf-8"><title>Living Assistant</title>
<style>body{font-family:system-ui;margin:24px;max-width:1200px}pre{background:#111;color:#eee;padding:14px;border-radius:8px;overflow:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:800px){.grid{grid-template-columns:1fr}}button{padding:8px 12px}</style></head>
<body><h1>Living Assistant Control Center</h1><p>Localhost-only control surface.</p><button onclick="load()">Refresh</button><div class="grid">
<section><h2>Status</h2><pre id="status"></pre></section><section><h2>Approvals</h2><pre id="approvals"></pre></section>
<section><h2>Projects</h2><pre id="projects"></pre></section><section><h2>Processes</h2><pre id="processes"></pre></section>
<section><h2>Recent events</h2><pre id="events"></pre></section><section><h2>Todos</h2><pre id="todos"></pre></section></div>
<script>async function j(u){let r=await fetch(u);return await r.json()}async function load(){for(let k of ['status','approvals','projects','processes','events','todos']){document.getElementById(k).textContent=JSON.stringify(await j('/'+k),null,2)}}load()</script></body></html>'''
    return HTMLResponse(page)
