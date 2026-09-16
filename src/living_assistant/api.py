from __future__ import annotations
import os, hmac
from urllib.parse import urlparse
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from importlib import resources
import json
from .runtime import build_runtime
from .platform_hardening import platform_status, service_status

app = FastAPI(title='Living Assistant Local API', version='0.16.0')
runtime = None

_LOCAL_HOSTS = {'127.0.0.1', 'localhost', '::1', 'testserver'}

def _allowed_hostnames() -> set[str]:
    extra = {x.strip().lower() for x in os.environ.get('ASSISTANT_ALLOWED_HOSTS','').split(',') if x.strip()}
    return _LOCAL_HOSTS | extra

def _host_only(value: str) -> str:
    try:
        return (urlparse('//' + value).hostname or '').lower()
    except Exception:
        return ''

def _origin_is_local_or_same(origin: str, request_host: str) -> bool:
    try:
        p = urlparse(origin)
        return p.scheme in {'http','https'} and (p.hostname or '').lower() in (_allowed_hostnames() | {request_host})
    except Exception:
        return False

@app.middleware('http')
async def local_api_boundary(request: Request, call_next):
    host = _host_only(request.headers.get('host',''))
    if host not in _allowed_hostnames():
        return JSONResponse({'detail':'Invalid Host header for local assistant API.'}, status_code=400)
    origin = request.headers.get('origin')
    if origin and not _origin_is_local_or_same(origin, host):
        return JSONResponse({'detail':'Cross-origin browser access to the local assistant API is blocked.'}, status_code=403)
    return await call_next(request)

class AskRequest(BaseModel):
    message: str
    context: str = ''
    session_id: str | None = None
class ApprovalDecision(BaseModel): approved: bool
class TodoRequest(BaseModel):
    title: str
    due_at: str | None = None
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

class SecurityPathRequest(BaseModel):
    path: str
    label: str | None = None
    rules: list[str] = Field(default_factory=list)

class BackupBaselineCreateRequest(BaseModel):
    name: str
    path: str

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

class ConnectorCallRequest(BaseModel):
    action: str
    params: dict = Field(default_factory=dict)

class ModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=300)


def _rt():
    global runtime
    if runtime is None: runtime = build_runtime(interactive=False)
    return runtime

def _auth(authorization: str | None):
    token=os.environ.get('ASSISTANT_API_TOKEN','')
    if token and (not authorization or not hmac.compare_digest(authorization, f'Bearer {token}')): raise HTTPException(status_code=401,detail='Invalid token')

@app.get('/health')
def health(): return {'ok':True,'service':'living-assistant','version':'0.16.0'}
@app.get('/status')
def status(authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt()
    model_runtime = rt.model_manager.status(refresh=False)
    return {
        'profile':rt.profile,
        'hardware':rt.hardware.to_dict(),
        'resources':rt.resources.snapshot(),
        'personal':rt.personal.status(),
        'active_model':rt.model_manager.active_model,
        'model_runtime':model_runtime,
    }

@app.get('/platform/status')
def platform_status_endpoint(authorization: str | None=Header(default=None)):
    _auth(authorization); return platform_status().to_dict()

@app.get('/platform/service-status')
def platform_service_status_endpoint(authorization: str | None=Header(default=None)):
    _auth(authorization); return service_status()

@app.get('/models/status')
def model_status(refresh: bool=False, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().model_manager.status(refresh=refresh)

@app.post('/models/preload')
def model_preload(req: ModelRequest, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().model_manager.preload(req.model)

@app.post('/models/unload')
def model_unload(req: ModelRequest, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().model_manager.unload(req.model)

@app.get('/desktop/status')
def desktop_status(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().desktop_controller.status()

@app.get('/desktop/monitors')
def desktop_monitors(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().desktop_controller.monitors()

@app.get('/desktop/windows')
def desktop_windows(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().desktop_controller.windows()
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
@app.post('/todos')
def todo_add(req: TodoRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); return {'ok':True,'id':_rt().memory.add_todo(req.title,req.due_at)}
@app.post('/todos/{todo_id}/complete')
def todo_complete(todo_id: int,authorization: str | None=Header(default=None)):
    _auth(authorization); return {'ok':_rt().memory.complete_todo(todo_id)}
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

@app.get('/security/sensors/status')
def security_sensors_status(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.status()
@app.get('/security/sensors/events')
def security_sensors_events(minutes: int=10,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.collect_events(minutes)
@app.get('/security/sensors/correlations')
def security_sensors_correlations(minutes: int=10,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.correlations(minutes)
@app.get('/security/sensors/dns')
def security_sensors_dns(minutes: int=10,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.dns_context(minutes)
@app.get('/security/sensors/tls')
def security_sensors_tls(limit: int=100,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.tls_context(limit)
@app.post('/security/sensors/yara')
def security_sensors_yara(req: SecurityPathRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return rt.security_sensors.yara_scan(rt.workspace.resolve(req.path),req.rules)
@app.post('/security/sensors/reputation')
def security_sensors_reputation(req: SecurityPathRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return rt.security_sensors.reputation_file(rt.workspace.resolve(req.path))
@app.get('/security/sensors/reputation/process/{pid}')
def security_sensors_reputation_process(pid: int,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.reputation_process(pid)
@app.post('/security/sensors/binary/assess')
def security_sensors_binary_assess(req: SecurityPathRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return rt.security_sensors.assess_binary(rt.workspace.resolve(req.path))
@app.post('/security/sensors/binary/trust')
def security_sensors_binary_trust(req: SecurityPathRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return rt.security_sensors.trust_binary(rt.workspace.resolve(req.path),req.label or 'trusted')
@app.get('/security/sensors/binary/check')
def security_sensors_binary_check(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.check_trusted_binaries()
@app.get('/security/sensors/usb')
def security_sensors_usb(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.check_usb()
@app.post('/security/sensors/usb/baseline')
def security_sensors_usb_baseline(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.capture_usb_baseline()
@app.get('/security/sensors/extensions')
def security_sensors_extensions(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.check_extensions()
@app.post('/security/sensors/extensions/baseline')
def security_sensors_extensions_baseline(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.capture_extension_baseline()
@app.get('/security/sensors/backups')
def security_sensors_backups(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.list_backup_baselines()
@app.post('/security/sensors/backups')
def security_sensors_backup_create(req: BackupBaselineCreateRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt(); return rt.security_sensors.capture_backup_baseline(req.name,rt.workspace.resolve(req.path))
@app.get('/security/sensors/backups/{name}/check')
def security_sensors_backup_check(name: str,authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.check_backup_baseline(name)
@app.post('/security/sensors/network/isolate')
def security_sensors_network_isolate(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.isolate_network(False)
@app.post('/security/sensors/network/restore')
def security_sensors_network_restore(authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().security_sensors.restore_network()
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
@app.get('/connectors/{name}/status')
def connector_status(name: str, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().connector_manager.status(name)
@app.post('/connectors/{name}/call')
def connector_call(name: str, req: ConnectorCallRequest, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().connector_manager.call(name, req.action, req.params)
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


def _sse(payload: dict, event: str | None = None, event_id: int | None = None) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    parts=[]
    if event_id is not None: parts.append(f'id: {event_id}')
    if event: parts.append(f'event: {event}')
    parts.append(f'data: {body}')
    return '\n'.join(parts)+'\n\n'

@app.get('/activity')
def activity(limit: int=100, after_id: int=0, authorization: str | None=Header(default=None)):
    _auth(authorization); return _rt().events_bus.recent(limit,after_id)

@app.get('/activity/stream')
def activity_stream(after_id: int=0, authorization: str | None=Header(default=None)):
    _auth(authorization); bus=_rt().events_bus
    def generate():
        for item in bus.stream(after_id=after_id,heartbeat_seconds=12):
            if item is None:
                yield ': heartbeat\n\n'
            else:
                yield _sse(item,event='activity',event_id=int(item['id']))
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

@app.post('/chat/stream')
def chat_stream(req: AskRequest,authorization: str | None=Header(default=None)):
    _auth(authorization); rt=_rt()
    if req.session_id: rt.sessions.ensure(req.session_id)
    def generate():
        for event in rt.orchestrator.run_stream(req.message,req.context,session_id=req.session_id):
            yield _sse(event,event=str(event.get('type','message')))
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

@app.get('/dashboard',response_class=HTMLResponse)
def dashboard():
    page=resources.files('living_assistant').joinpath('webui/index.html').read_text(encoding='utf-8')
    return HTMLResponse(page,headers={
        'Cache-Control':'no-store',
        'Content-Security-Policy':"default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
        'X-Frame-Options':'DENY',
        'X-Content-Type-Options':'nosniff',
        'Referrer-Policy':'no-referrer',
    })
