from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .runtime import build_runtime

app = FastAPI(title='Living Assistant Local API', version='0.9.1')
runtime = None

class AskRequest(BaseModel):
    message: str
    context: str = ''
    session_id: str | None = None
class ApprovalDecision(BaseModel): approved: bool
class BrowserStartRequest(BaseModel):
    name: str; url: str; persistent: bool = False; allowed_hosts: list[str] = Field(default_factory=list)
class BrowserInteractRequest(BaseModel):
    action: str; selector: str; value: str | None = None
class BrowserNavigateRequest(BaseModel): url: str
class CalendarEventRequest(BaseModel):
    title: str; start_at: str; end_at: str | None = None; location: str | None = None; notes: str | None = None
class FocusRequest(BaseModel): minutes: int = 60; label: str | None = None
class QuietRequest(BaseModel): start: str='22:00'; end: str='07:00'; enabled: bool=True
class IntegrityBaselineRequest(BaseModel):
    name: str; path: str; recursive: bool=True; extensions: list[str]=Field(default_factory=list)
class EvaluationSuiteRequest(BaseModel):
    name: str
    project_path: str
    test_commands: list[str] = Field(default_factory=list)
    lint_commands: list[str] = Field(default_factory=list)
    benchmark_commands: list[str] = Field(default_factory=list)
    repetitions: int | None = None
    max_latency_regression_pct: float | None = None
    max_memory_regression_pct: float | None = None
    execution_provider: str = 'host'
    sandbox_image: str | None = None
    require_canary: bool = False
class ImprovementEvaluateRequest(BaseModel):
    suite_name: str | None = None
    project_path: str | None = None
    test_commands: list[str] | None = None
    lint_commands: list[str] | None = None
    benchmark_commands: list[str] | None = None
    repetitions: int | None = None
    max_latency_regression_pct: float | None = None
    max_memory_regression_pct: float | None = None
    execution_provider: str | None = None
    sandbox_image: str | None = None

class CanaryRequest(BaseModel):
    command: str
    provider: str = 'host'
    image: str | None = None
    health_path: str = '/health'
    service_port: int = 8000
    observe_seconds: int | None = None
    startup_timeout_seconds: int | None = None
    max_latency_regression_pct: float | None = None
    max_memory_regression_pct: float | None = None
    min_health_success_pct: float | None = None

class ExperienceRecordRequest(BaseModel):
    kind: str
    situation: str
    lesson: str
    project: str | None = None
    action_taken: str | None = None
    outcome: str | None = None
    root_cause: str | None = None
    better_action: str | None = None
    verified: bool = False
    evidence: str | None = None

class ExperienceVerifyRequest(BaseModel):
    useful: bool
    evidence: str | None = None

class ExperienceConfirmRequest(BaseModel):
    notes: str | None = None


def _rt():
    global runtime
    if runtime is None: runtime = build_runtime(interactive=False)
    return runtime

def _auth(authorization: str | None):
    token=os.environ.get('ASSISTANT_API_TOKEN','')
    if token and authorization != f'Bearer {token}': raise HTTPException(status_code=401,detail='Invalid token')

@app.get('/health')
def health(): return {'ok':True,'service':'living-assistant','version':'0.9.1'}
@app.get('/status')
def status(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return {'profile':rt.profile,'hardware':rt.hardware.to_dict(),'resources':rt.resources.snapshot(),'personal':rt.personal.status()}
@app.post('/ask')
def ask(req: AskRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt()
    if req.session_id: rt.sessions.ensure(req.session_id)
    return {'answer':rt.orchestrator.run(req.message,req.context,session_id=req.session_id),'session_id':req.session_id}
@app.get('/projects')
def projects(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().projects.list()
@app.get('/groups')
def groups(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().groups.list()
@app.get('/processes')
def processes(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().processes.list()
@app.get('/events')
def events(limit: int=100,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().memory.list_events(min(max(limit,1),500))
@app.get('/todos')
def todos(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().memory.list_todos(include_done=True)
@app.get('/approvals')
def approvals(status: str='pending',authorization: str | None=Header(default=None)): _auth(authorization); return _rt().approvals.list(status=None if status=='all' else status)
@app.post('/approvals/{approval_id}')
def approval_decide(approval_id: str,decision: ApprovalDecision,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().approvals.resolve(approval_id,decision.approved)
@app.get('/watches')
def watches(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().watches.list()
@app.get('/skills')
def skills(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().skills.list()
@app.get('/quarantine')
def quarantine(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().quarantine.list()
@app.get('/quarantine/{item_id}')
def quarantine_item(item_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); item=rt.quarantine.get(item_id)
    if not item: raise HTTPException(status_code=404,detail='Unknown quarantine item')
    from .security_guardian import file_signature
    return {'item':item,'file':file_signature(item['path'])}
@app.post('/quarantine/{item_id}/scan')
def quarantine_scan(item_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); item=rt.quarantine.get(item_id)
    if not item: raise HTTPException(status_code=404,detail='Unknown quarantine item')
    result=rt.guardian.scan_path_antivirus(item['path'])
    if result.get('ok') or result.get('returncode') is not None: rt.quarantine.record_scan(item_id,result.get('provider','unknown'),result)
    return result
@app.get('/security/summary')
def security_summary(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.summary()
@app.get('/security/posture')
def security_posture(updates: bool=False,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.posture(include_updates=updates)
@app.get('/security/findings')
def security_findings(status: str='open',authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.findings(None if status=='all' else status,200)
@app.post('/security/findings/{finding_id}/resolve')
def security_finding_resolve(finding_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); req=rt.approval_manager.request(f'Resolve security finding {finding_id}','Mark a security finding as resolved.','SECURITY_FINDING_RESOLVE')
    if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
    return {'ok':rt.guardian.resolve_finding(finding_id)}
@app.get('/security/startup')
def security_startup(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.check_startup_baseline(record=True)
@app.post('/security/startup/capture')
def security_startup_capture(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); req=rt.approval_manager.request('Replace startup persistence baseline','Capture current startup/persistence state as trusted reference.','SECURITY_BASELINE_CHANGE')
    if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
    return rt.guardian.capture_startup_baseline()
@app.get('/security/network')
def security_network(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.check_network_baseline(record=True)
@app.post('/security/network/capture')
def security_network_capture(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); req=rt.approval_manager.request('Replace listening-service baseline','Capture current listening services as trusted reference.','SECURITY_BASELINE_CHANGE')
    if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
    return rt.guardian.capture_network_baseline()
@app.get('/security/integrity')
def security_integrity(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.list_integrity_baselines()
@app.post('/security/integrity')
def security_integrity_add(req: IntegrityBaselineRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); target=rt.workspace.resolve(req.path); approval=rt.approval_manager.request(f'Security baseline change: {req.name}',f'Create or replace integrity baseline for {target}.','SECURITY_BASELINE_CHANGE')
    if not approval.get('allowed'): return {'ok':False,'approval_required':True,**approval}
    return rt.guardian.add_integrity_baseline(req.name,target,req.recursive,req.extensions)
@app.get('/security/integrity/{name}/check')
def security_integrity_check(name: str,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.check_integrity_baseline(name,record=True)
@app.post('/security/integrity/{name}/refresh')
def security_integrity_refresh(name: str,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); approval=rt.approval_manager.request(f'Refresh security baseline: {name}','Replace stored protected-file hashes with current file hashes.','SECURITY_BASELINE_CHANGE')
    if not approval.get('allowed'): return {'ok':False,'approval_required':True,**approval}
    return rt.guardian.refresh_integrity_baseline(name)
@app.delete('/security/integrity/{name}')
def security_integrity_remove(name: str,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); approval=rt.approval_manager.request(f'Remove security baseline: {name}','Stop monitoring this protected-file baseline.','SECURITY_BASELINE_CHANGE')
    if not approval.get('allowed'): return {'ok':False,'approval_required':True,**approval}
    return {'ok':rt.guardian.remove_integrity_baseline(name)}
@app.get('/security/processes/triage')
def security_processes_triage(min_score: int=30,authorization: str | None=Header(default=None)):
    _auth(authorization); from .security_guardian import process_triage; return process_triage(min_score=min_score,limit=100)
@app.get('/security/network/activity')
def security_network_activity(limit: int=100,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.network_activity(limit)
@app.get('/security/process/{pid}')
def security_process(pid: int,authorization: str | None=Header(default=None)):
    _auth(authorization); from .security_guardian import inspect_process; return inspect_process(pid)
@app.post('/security/process/{pid}/contain')
def security_process_contain(pid: int,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().guardian.terminate_user_process(pid)
@app.get('/routines')
def routines(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().routines.list()
@app.get('/improvements')
def improvements(status: str='pending',authorization: str | None=Header(default=None)): _auth(authorization); return _rt().improvements.store.list(None if status=='all' else status)
@app.post('/improvements/{proposal_id}/apply')
def improvement_apply(proposal_id: str,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().improvements.apply(proposal_id)
@app.post('/improvements/{proposal_id}/rollback')
def improvement_rollback(proposal_id: str,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().improvements.rollback(proposal_id)
@app.get('/improvement-suites')
def improvement_suites(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().evaluations.store.list_suites()
@app.post('/improvement-suites')
def improvement_suite_add(req: EvaluationSuiteRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().evaluations.create_suite(req.name,req.project_path,req.test_commands,req.lint_commands,req.benchmark_commands,req.repetitions,req.max_latency_regression_pct,req.max_memory_regression_pct,req.execution_provider,req.sandbox_image,'none',None,None,None,req.require_canary)
@app.delete('/improvement-suites/{name}')
def improvement_suite_delete(name: str,authorization: str | None=Header(default=None)):
    _auth(authorization); return {'ok':_rt().evaluations.store.delete_suite(name)}
@app.get('/improvement-evaluations')
def improvement_evaluations(status: str='all',authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().evaluations.store.list(None if status=='all' else status)
@app.get('/improvement-evaluations/{evaluation_id}')
def improvement_evaluation_get(evaluation_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); item=_rt().evaluations.store.get(evaluation_id)
    if not item: raise HTTPException(status_code=404,detail='Unknown evaluation id')
    return item
@app.post('/improvements/{proposal_id}/evaluate')
def improvement_evaluate(proposal_id: str,req: ImprovementEvaluateRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().evaluations.evaluate(proposal_id,req.suite_name,req.project_path,req.test_commands,req.lint_commands,req.benchmark_commands,req.repetitions,req.max_latency_regression_pct,req.max_memory_regression_pct,req.execution_provider,req.sandbox_image,None)
@app.get('/sandbox/status')
def sandbox_status(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return {'evaluation':rt.evaluations.sandbox_status(),'canary':rt.canaries.status()}
@app.get('/canaries')
def canaries(evaluation_id: str | None=None,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().canaries.store.list(evaluation_id)
@app.get('/canaries/{canary_id}')
def canary_get(canary_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); item=_rt().canaries.store.get(canary_id)
    if not item: raise HTTPException(status_code=404,detail='Unknown canary id')
    return item
@app.post('/improvement-evaluations/{evaluation_id}/canary')
def canary_run(evaluation_id: str,req: CanaryRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().canaries.run(evaluation_id,req.command,req.health_path,req.service_port,req.provider,req.image,req.observe_seconds,req.startup_timeout_seconds,req.max_latency_regression_pct,req.max_memory_regression_pct,req.min_health_success_pct)
@app.post('/improvement-evaluations/{evaluation_id}/promote')
def improvement_promote(evaluation_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().evaluations.promote(evaluation_id)
@app.post('/improvement-evaluations/{evaluation_id}/revert')
def improvement_revert(evaluation_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().evaluations.revert_promotion(evaluation_id)
@app.get('/voice/status')
def voice_status(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return {'enabled':rt.voice.enabled(),'profile':rt.profile,'config':rt.config.get('voice',{})}
@app.get('/browser/sessions')
def browser_sessions(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().browser.list_sessions()
@app.post('/browser/sessions')
def browser_session_start(req: BrowserStartRequest,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().browser.start_session(req.name,req.url,req.persistent,req.allowed_hosts)
@app.post('/browser/sessions/{name}/navigate')
def browser_session_navigate(name: str,req: BrowserNavigateRequest,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().browser.navigate_session(name,req.url)
@app.post('/browser/sessions/{name}/interact')
def browser_session_interact(name: str,req: BrowserInteractRequest,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().browser.interact_session(name,req.action,req.selector,req.value)
@app.delete('/browser/sessions/{name}')
def browser_session_close(name: str,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().browser.close_session(name,False)

@app.get('/calendar')
def calendar(start: str | None=None,end: str | None=None,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().calendar.list(start,end)
@app.post('/calendar')
def calendar_add(req: CalendarEventRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().calendar.add(req.title,req.start_at,req.end_at,req.location,req.notes)
@app.delete('/calendar/{event_id}')
def calendar_cancel(event_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); return {'ok':_rt().calendar.cancel(event_id)}
@app.get('/briefing/{kind}')
def briefing(kind: str,authorization: str | None=Header(default=None)):
    _auth(authorization)
    if kind not in {'morning','evening'}: raise HTTPException(status_code=400,detail='kind must be morning or evening')
    return _rt().briefings.build(kind)
@app.get('/personal')
def personal(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return {**rt.personal.status(),'queued_notifications':rt.notifier.queued()}
@app.post('/personal/focus')
def focus(req: FocusRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().personal.start_focus(req.minutes,req.label)
@app.delete('/personal/focus')
def focus_stop(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); state=rt.personal.stop_focus(); rt.notifier.flush(20); return state
@app.post('/personal/quiet')
def quiet(req: QuietRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().personal.set_quiet_hours(req.start,req.end,req.enabled)
@app.get('/sessions')
def sessions(limit: int=50,authorization: str | None=Header(default=None)): _auth(authorization); return _rt().sessions.list(limit)
@app.get('/sessions/{session_id}')
def session_get(session_id: str,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return {'session':rt.sessions.get(session_id),'messages':rt.sessions.recent_messages(session_id,50)}
@app.delete('/sessions/{session_id}')
def session_delete(session_id: str,authorization: str | None=Header(default=None)): _auth(authorization); return {'ok':_rt().sessions.delete(session_id)}
@app.get('/connectors')
def connectors(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().connectors.list()
@app.get('/notifications/queued')
def queued_notifications(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().notifier.queued()
@app.post('/notifications/flush')
def flush_notifications(authorization: str | None=Header(default=None)): _auth(authorization); return _rt().notifier.flush(50)

@app.get('/experiences')
def experiences(status: str='active', project: str | None=None, limit: int=100, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.list(None if status=='all' else status,project,limit)

@app.get('/experiences/search')
def experience_search(q: str, project: str | None=None, include_candidates: bool=False, limit: int=10, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.search(q,project,limit,include_candidates)

@app.get('/experiences/patterns')
def experience_patterns(limit: int=20, min_count: int=2, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.failure_patterns(limit,min_count)

@app.get('/experiences/stats')
def experience_stats(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.stats()

@app.get('/experiences/{experience_id}')
def experience_get(experience_id: str, authorization: str | None=Header(default=None)):
    _auth(authorization); item=_rt().experiences.get(experience_id)
    if not item: raise HTTPException(status_code=404,detail='Unknown experience id')
    return item

@app.post('/experiences')
def experience_record(req: ExperienceRecordRequest, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.record(req.kind,req.situation,req.lesson,req.project,req.action_taken,req.outcome,req.root_cause,req.better_action,req.verified,req.evidence,source='api')

@app.post('/experiences/{experience_id}/verify')
def experience_verify(experience_id: str, req: ExperienceVerifyRequest, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.verify(experience_id,req.useful,req.evidence)

@app.post('/experiences/{experience_id}/confirm')
def experience_confirm(experience_id: str, req: ExperienceConfirmRequest, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.confirm(experience_id,req.notes)

@app.delete('/experiences/{experience_id}')
def experience_reject(experience_id: str, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().experiences.reject(experience_id,'Rejected through local API')


@app.get('/dashboard',response_class=HTMLResponse)
def dashboard():
    if os.environ.get('ASSISTANT_API_TOKEN'):
        return HTMLResponse('<h2>Living Assistant</h2><p>Dashboard is disabled while ASSISTANT_API_TOKEN is set. Use authenticated API endpoints.</p>')
    page=r'''<!doctype html><html><head><meta charset="utf-8"><title>Living Assistant</title>
<style>body{font-family:system-ui;margin:24px;max-width:1450px;background:#f7f7f7;color:#171717}header{display:flex;gap:12px;align-items:center;justify-content:space-between}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}section{background:white;border:1px solid #ddd;border-radius:12px;padding:14px}pre{background:#111;color:#eee;padding:12px;border-radius:8px;overflow:auto;max-height:420px}button{padding:7px 11px;border-radius:8px;border:1px solid #aaa;cursor:pointer}.approve{background:#e6ffed}.deny{background:#ffecec}.approval{border-bottom:1px solid #ddd;padding:10px 0}small{color:#666}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style></head><body>
<header><div><h1>Living Assistant Control Center</h1><small>Localhost-only personal operating + security layer</small></div><button onclick="load()">Refresh</button></header><div class="grid">
<section><h2>Status</h2><pre id="status"></pre></section><section><h2>Approvals</h2><div id="approvals"></div></section>
<section><h2>Personal state</h2><pre id="personal"></pre></section><section><h2>Calendar</h2><pre id="calendar"></pre></section>
<section><h2>Morning briefing</h2><pre id="briefing"></pre></section><section><h2>Sessions</h2><pre id="sessions"></pre></section>
<section><h2>Projects</h2><pre id="projects"></pre></section><section><h2>Processes</h2><pre id="processes"></pre></section>
<section><h2>Recent events</h2><pre id="events"></pre></section><section><h2>Todos</h2><pre id="todos"></pre></section>
<section><h2>Routines</h2><pre id="routines"></pre></section><section><h2>Queued notifications</h2><pre id="notifications"></pre></section>
<section><h2>Security Guardian</h2><pre id="security"></pre></section><section><h2>Experience memory</h2><pre id="experiences"></pre></section><section><h2>Connectors</h2><pre id="connectors"></pre></section><section><h2>Improvements</h2><pre id="improvements"></pre></section><section><h2>Evaluation suites</h2><pre id="improvement-suites"></pre></section><section><h2>Evaluated improvements</h2><pre id="improvement-evaluations"></pre></section><section><h2>Sandbox</h2><pre id="sandbox"></pre></section><section><h2>Canaries</h2><pre id="canaries"></pre></section>
</div><script>
async function j(u,opt){let r=await fetch(u,opt);return await r.json()}async function decide(id,approved){await j('/approvals/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved})});load()}
async function load(){for(let k of ['status','personal','calendar','sessions','projects','processes','events','todos','routines','connectors','improvements','improvement-suites','improvement-evaluations','canaries','experiences']){let el=document.getElementById(k);if(el)el.textContent=JSON.stringify(await j('/'+k),null,2)}document.getElementById('sandbox').textContent=JSON.stringify(await j('/sandbox/status'),null,2);document.getElementById('briefing').textContent=JSON.stringify(await j('/briefing/morning'),null,2);document.getElementById('security').textContent=JSON.stringify(await j('/security/summary'),null,2);document.getElementById('notifications').textContent=JSON.stringify(await j('/notifications/queued'),null,2);let a=await j('/approvals');let box=document.getElementById('approvals');box.innerHTML='';if(!a.length)box.textContent='No pending approvals.';for(let x of a){let d=document.createElement('div');d.className='approval';d.innerHTML='<b>'+esc(x.kind)+'</b><br>'+esc(x.action)+'<br><small>'+esc(x.reason)+'</small><br><button class="approve" onclick="decide(\''+x.id+'\',true)">Approve once</button> <button class="deny" onclick="decide(\''+x.id+'\',false)">Deny</button>';box.appendChild(d)}}function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}load();setInterval(load,8000)
</script></body></html>'''
    return HTMLResponse(page)
