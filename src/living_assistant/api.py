from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .runtime import build_runtime

app = FastAPI(title='Living Assistant Local API', version='0.4.0')
runtime = None

class AskRequest(BaseModel):
    message: str
    context: str = ''

class ApprovalDecision(BaseModel):
    approved: bool

class BrowserStartRequest(BaseModel):
    name: str
    url: str
    persistent: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)

class BrowserInteractRequest(BaseModel):
    action: str
    selector: str
    value: str | None = None

class BrowserNavigateRequest(BaseModel):
    url: str


def _rt():
    global runtime
    if runtime is None: runtime = build_runtime(interactive=False)
    return runtime


def _auth(authorization: str | None):
    token = os.environ.get('ASSISTANT_API_TOKEN','')
    if token and authorization != f'Bearer {token}':
        raise HTTPException(status_code=401, detail='Invalid token')

@app.get('/health')
def health(): return {'ok':True,'service':'living-assistant','version':'0.4.0'}

@app.get('/status')
def status(authorization: str | None = Header(default=None)):
    _auth(authorization); rt=_rt()
    return {'profile':rt.profile,'hardware':rt.hardware.to_dict(),'resources':rt.resources.snapshot()}

@app.post('/ask')
def ask(req: AskRequest, authorization: str | None = Header(default=None)):
    _auth(authorization); return {'answer':_rt().orchestrator.run(req.message, req.context)}

@app.get('/projects')
def projects(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().projects.list()

@app.get('/groups')
def groups(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().groups.list()

@app.get('/processes')
def processes(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().processes.list()

@app.get('/events')
def events(limit: int=100, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().memory.list_events(min(max(limit,1),500))

@app.get('/todos')
def todos(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().memory.list_todos(include_done=True)

@app.get('/approvals')
def approvals(status: str='pending', authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().approvals.list(status=None if status=='all' else status)

@app.post('/approvals/{approval_id}')
def approval_decide(approval_id: str, decision: ApprovalDecision, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().approvals.resolve(approval_id, decision.approved)

@app.get('/watches')
def watches(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().watches.list()

@app.get('/skills')
def skills(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().skills.list()

@app.get('/quarantine')
def quarantine(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().quarantine.list()

@app.get('/routines')
def routines(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().routines.list()

@app.get('/improvements')
def improvements(status: str='pending', authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().improvements.store.list(None if status=='all' else status)

@app.post('/improvements/{proposal_id}/apply')
def improvement_apply(proposal_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().improvements.apply(proposal_id)

@app.post('/improvements/{proposal_id}/rollback')
def improvement_rollback(proposal_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().improvements.rollback(proposal_id)

@app.get('/voice/status')
def voice_status(authorization: str | None = Header(default=None)):
    _auth(authorization); rt=_rt(); return {'enabled':rt.voice.enabled(),'profile':rt.profile,'config':rt.config.get('voice',{})}

@app.get('/browser/sessions')
def browser_sessions(authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().browser.list_sessions()

@app.post('/browser/sessions')
def browser_session_start(req: BrowserStartRequest, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().browser.start_session(req.name,req.url,req.persistent,req.allowed_hosts)

@app.post('/browser/sessions/{name}/navigate')
def browser_session_navigate(name: str, req: BrowserNavigateRequest, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().browser.navigate_session(name,req.url)

@app.post('/browser/sessions/{name}/interact')
def browser_session_interact(name: str, req: BrowserInteractRequest, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().browser.interact_session(name,req.action,req.selector,req.value)

@app.delete('/browser/sessions/{name}')
def browser_session_close(name: str, authorization: str | None = Header(default=None)):
    _auth(authorization); return _rt().browser.close_session(name,False)

@app.get('/dashboard', response_class=HTMLResponse)
def dashboard():
    if os.environ.get('ASSISTANT_API_TOKEN'):
        return HTMLResponse('<h2>Living Assistant</h2><p>Dashboard is disabled while ASSISTANT_API_TOKEN is set. Use authenticated API endpoints.</p>')
    page = r'''<!doctype html><html><head><meta charset="utf-8"><title>Living Assistant</title>
<style>
body{font-family:system-ui;margin:24px;max-width:1400px;background:#f7f7f7;color:#171717}
header{display:flex;gap:12px;align-items:center;justify-content:space-between}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
section{background:white;border:1px solid #ddd;border-radius:12px;padding:14px}pre{background:#111;color:#eee;padding:12px;border-radius:8px;overflow:auto;max-height:420px}
button{padding:7px 11px;border-radius:8px;border:1px solid #aaa;cursor:pointer}.approve{background:#e6ffed}.deny{background:#ffecec}.approval{border-bottom:1px solid #ddd;padding:10px 0}
small{color:#666}@media(max-width:850px){.grid{grid-template-columns:1fr}}
</style></head><body>
<header><div><h1>Living Assistant Control Center</h1><small>Localhost-only desktop operator</small></div><button onclick="load()">Refresh</button></header>
<div class="grid">
<section><h2>Status</h2><pre id="status"></pre></section><section><h2>Approvals</h2><div id="approvals"></div></section>
<section><h2>Projects</h2><pre id="projects"></pre></section><section><h2>Groups</h2><pre id="groups"></pre></section>
<section><h2>Processes</h2><pre id="processes"></pre></section><section><h2>Quarantine</h2><pre id="quarantine"></pre></section>
<section><h2>Recent events</h2><pre id="events"></pre></section><section><h2>Todos</h2><pre id="todos"></pre></section>
<section><h2>Routines</h2><pre id="routines"></pre></section><section><h2>Improvements</h2><pre id="improvements"></pre></section>
<section><h2>Browser sessions</h2><pre id="browser-sessions"></pre></section><section><h2>Voice</h2><pre id="voice-status"></pre></section>
</div><script>
async function j(u,opt){let r=await fetch(u,opt);return await r.json()}
async function decide(id,approved){await j('/approvals/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});load()}
async function load(){
 for(let k of ['status','projects','groups','processes','quarantine','events','todos','routines','improvements']) document.getElementById(k).textContent=JSON.stringify(await j('/'+k),null,2);
 document.getElementById('browser-sessions').textContent=JSON.stringify(await j('/browser/sessions'),null,2);
 document.getElementById('voice-status').textContent=JSON.stringify(await j('/voice/status'),null,2);
 let a=await j('/approvals');let box=document.getElementById('approvals');box.innerHTML='';
 if(!a.length) box.textContent='No pending approvals.';
 for(let x of a){let d=document.createElement('div');d.className='approval';d.innerHTML='<b>'+esc(x.kind)+'</b><br>'+esc(x.action)+'<br><small>'+esc(x.reason)+'</small><br>'+
 '<button class="approve" onclick="decide(\''+x.id+'\',true)">Approve once</button> <button class="deny" onclick="decide(\''+x.id+'\',false)">Deny</button>';box.appendChild(d)}
}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
load();setInterval(load,8000)
</script></body></html>'''
    return HTMLResponse(page)
