from __future__ import annotations

from pathlib import Path
import datetime as dt
import json
import os
import shlex
import shutil
import socket
import sqlite3
import statistics
import subprocess
import time
import uuid

import httpx
import psutil

from .approval import ApprovalManager
from .config import data_dir
from .sqlite_utils import ThreadLocalSQLite
from .evaluation import EvaluationEngine, _git, _repo_root, _copy_project, _kill_tree
from .improvements import ImprovementEngine
from .sandbox import ContainerRuntime, SandboxSpec, sanitized_env
from .security_policy import classify_command
from .workspace import Workspace

SCHEMA = """
CREATE TABLE IF NOT EXISTS canary_runs(
  id TEXT PRIMARY KEY,
  evaluation_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  image TEXT,
  command TEXT NOT NULL,
  health_path TEXT NOT NULL,
  service_port INTEGER NOT NULL,
  status TEXT NOT NULL,
  verdict TEXT,
  config_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE INDEX IF NOT EXISTS canary_eval_idx ON canary_runs(evaluation_id, created_at);
"""


def _now() -> str:
    return dt.datetime.now().isoformat(timespec='seconds')


def _json(v) -> str:
    return json.dumps(v,sort_keys=True,default=str)


def _decode(v: str, fallback):
    try: return json.loads(v)
    except Exception: return fallback


def _free_port() -> int:
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1',0))
        return int(s.getsockname()[1])


class CanaryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir()/'assistant.sqlite3')
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA); self.conn.commit()

    def create(self,evaluation_id:str,provider:str,image:str|None,command:str,health_path:str,service_port:int,config:dict) -> dict:
        cid=uuid.uuid4().hex[:12]
        self.conn.execute("INSERT INTO canary_runs(id,evaluation_id,provider,image,command,health_path,service_port,status,config_json,created_at) VALUES(?,?,?,?,?,?,?,'created',?,?)",
                          (cid,evaluation_id,provider,image,command,health_path,int(service_port),_json(config),_now()))
        self.conn.commit(); return self.get(cid) or {}

    def update(self,canary_id:str,**fields):
        allowed={'status','verdict','result_json','error','started_at','finished_at'}
        clean={k:v for k,v in fields.items() if k in allowed}
        if not clean:return
        self.conn.execute(f"UPDATE canary_runs SET {','.join(f'{k}=?' for k in clean)} WHERE id=?",(*clean.values(),canary_id)); self.conn.commit()

    def get(self,canary_id:str)->dict|None:
        row=self.conn.execute('SELECT * FROM canary_runs WHERE id=?',(canary_id,)).fetchone()
        if not row:return None
        item=dict(row); item['config']=_decode(item.pop('config_json'),{}); item['result']=_decode(item.pop('result_json'),{})
        return item

    def list(self,evaluation_id:str|None=None,limit:int=100)->list[dict]:
        if evaluation_id:
            rows=self.conn.execute('SELECT id FROM canary_runs WHERE evaluation_id=? ORDER BY created_at DESC LIMIT ?',(evaluation_id,limit)).fetchall()
        else:
            rows=self.conn.execute('SELECT id FROM canary_runs ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()
        return [x for x in (self.get(str(r['id'])) for r in rows) if x]

    def latest_for_evaluation(self,evaluation_id:str)->dict|None:
        row=self.conn.execute('SELECT id FROM canary_runs WHERE evaluation_id=? ORDER BY created_at DESC LIMIT 1',(evaluation_id,)).fetchone()
        return self.get(str(row['id'])) if row else None


def _process_tree_stats(pid:int)->dict:
    rss=0; cpu=0.0
    try:
        root=psutil.Process(pid); procs=[root,*root.children(recursive=True)]
        for p in procs:
            try:
                rss+=p.memory_info().rss; cpu+=p.cpu_percent(interval=None)
            except Exception: pass
    except Exception: pass
    return {'rss_mb':round(rss/(1024**2),2),'cpu_percent':round(cpu,2)}


def _health_probe(url:str,timeout:float=2.0)->dict:
    started=time.perf_counter()
    try:
        r=httpx.get(url,timeout=timeout,follow_redirects=False)
        return {'ok':200 <= r.status_code < 400,'status_code':r.status_code,'latency_ms':round((time.perf_counter()-started)*1000,2)}
    except Exception as exc:
        return {'ok':False,'status_code':None,'latency_ms':round((time.perf_counter()-started)*1000,2),'error':str(exc)[:300]}


def _summarize(samples:list[dict],peak_rss:float,peak_cpu:float)->dict:
    good=[x for x in samples if x.get('ok')]
    return {
        'probe_count':len(samples),
        'health_success_pct':round((len(good)/len(samples))*100,2) if samples else 0.0,
        'median_latency_ms':round(statistics.median([x['latency_ms'] for x in good]),2) if good else None,
        'peak_rss_mb':round(peak_rss,2),
        'peak_cpu_percent':round(peak_cpu,2),
        'samples':samples[-100:],
    }


def compare_canary(baseline:dict,candidate:dict,min_health_success_pct:float,max_latency_regression_pct:float,max_memory_regression_pct:float)->dict:
    result={'passed':False,'valid':False,'health_threshold_pct':min_health_success_pct,'latency_regression_pct':None,'memory_regression_pct':None,
            'limits':{'max_latency_regression_pct':max_latency_regression_pct,'max_memory_regression_pct':max_memory_regression_pct}}
    if baseline.get('health_success_pct',0) < min_health_success_pct:
        result['reason']='Baseline canary did not meet the health success threshold.'; return result
    if candidate.get('health_success_pct',0) < min_health_success_pct:
        result['valid']=True; result['reason']='Candidate canary did not meet the health success threshold.'; return result
    b_lat=float(baseline.get('median_latency_ms') or 0); c_lat=float(candidate.get('median_latency_ms') or 0)
    b_mem=float(baseline.get('peak_rss_mb') or 0); c_mem=float(candidate.get('peak_rss_mb') or 0)
    lat=0.0 if b_lat<=1e-9 else ((c_lat-b_lat)/b_lat)*100
    mem=0.0 if b_mem<=1e-9 else ((c_mem-b_mem)/b_mem)*100
    result.update({'valid':True,'latency_regression_pct':round(lat,2),'memory_regression_pct':round(mem,2)})
    result['passed']=lat<=max_latency_regression_pct and mem<=max_memory_regression_pct
    if not result['passed']: result['reason']='Candidate exceeded canary latency or memory regression budget.'
    return result


class CanaryEngine:
    def __init__(self,workspace:Workspace,approval:ApprovalManager,improvements:ImprovementEngine,evaluations:EvaluationEngine,
                 store:CanaryStore,config:dict|None=None,profile:str='balanced'):
        self.workspace=workspace; self.approval=approval; self.improvements=improvements; self.evaluations=evaluations; self.store=store; self.profile=profile
        self.config=(config or {}).get('self_improvement',{}).get('canary',{})
        runtime_pref=str((config or {}).get('self_improvement',{}).get('sandbox',{}).get('runtime','auto'))
        self.container=ContainerRuntime(runtime_pref)

    def _profile_value(self,key:str,default):
        v=self.config.get(key,default)
        if isinstance(v,dict): return v.get(self.profile,default if not isinstance(default,dict) else None)
        return v

    def status(self)->dict:
        return {'enabled':bool(self.config.get('enabled',True)),'profile':self.profile,'container':self.container.status(),'config':self.config}

    def _run_host_service(self,command:str,cwd:Path,host_port:int,health_path:str,startup_timeout:int,observe_seconds:int)->dict:
        decision=classify_command(command,require_execute_approval=False)
        if not decision.allowed or decision.risk.value in {'PRIVILEGED','DESTRUCTIVE'}:
            return {'ok':False,'error':'Unsafe canary command rejected.'}
        try: argv=shlex.split(command.replace('{port}',str(host_port)),posix=(os.name!='nt'))
        except Exception as exc:return {'ok':False,'error':str(exc)}
        env=sanitized_env({'PORT':str(host_port),'LIVING_ASSISTANT_CANARY':'1'})
        log_path=data_dir()/'canary_logs'/f'{uuid.uuid4().hex[:10]}.log'; log_path.parent.mkdir(parents=True,exist_ok=True)
        fh=open(log_path,'w',encoding='utf-8')
        try:
            proc=subprocess.Popen(argv,cwd=str(cwd),shell=False,stdout=fh,stderr=subprocess.STDOUT,env=env)
        except Exception as exc:
            fh.close(); return {'ok':False,'error':str(exc)}
        url=f'http://127.0.0.1:{host_port}{health_path}'
        startup_samples=[]; samples=[]; peak_rss=0.0; peak_cpu=0.0; ready=False; started=time.monotonic()
        try:
            while time.monotonic()-started < startup_timeout:
                if proc.poll() is not None: break
                pr=_health_probe(url); startup_samples.append(pr)
                st=_process_tree_stats(proc.pid); peak_rss=max(peak_rss,st['rss_mb']); peak_cpu=max(peak_cpu,st['cpu_percent'])
                if pr.get('ok'): ready=True; samples.append(pr); break
                time.sleep(0.5)
            if ready:
                until=time.monotonic()+observe_seconds
                while time.monotonic()<until and proc.poll() is None:
                    samples.append(_health_probe(url)); st=_process_tree_stats(proc.pid); peak_rss=max(peak_rss,st['rss_mb']); peak_cpu=max(peak_cpu,st['cpu_percent']); time.sleep(0.5)
        finally:
            # Canary commands may spawn workers/children. Terminating only the
            # direct process can leave those descendants running after a startup
            # timeout or failed health check, so reuse the hardened evaluation
            # process-tree cleanup path.
            _kill_tree(proc.pid)
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            fh.close()
        summary=_summarize(samples,peak_rss,peak_cpu); summary.update({'ok':ready,'url':url,'log':str(log_path),'returncode':proc.poll(),'provider':'host','startup_probes':startup_samples[-50:]})
        if not ready:
            try: summary['log_tail']=log_path.read_text(encoding='utf-8',errors='replace')[-10000:]
            except Exception: pass
        return summary

    def _run_container_service(self,command:str,cwd:Path,image:str,container_port:int,health_path:str,startup_timeout:int,observe_seconds:int,memory_mb:int,cpus:float,pids:int)->dict:
        host_port=_free_port(); network='living-canary-net-'+uuid.uuid4().hex[:8]
        made=self.container.create_internal_network(network)
        if not made.get('ok'): return {'ok':False,'error':'Could not create isolated internal container network.','detail':made}
        spec=SandboxSpec(image=image,network=network,memory_mb=memory_mb,cpus=cpus,pids_limit=pids,read_only_root=True)
        started=self.container.start_service(command,cwd,spec,host_port,container_port,env={'PORT':str(container_port),'LIVING_ASSISTANT_CANARY':'1'})
        if not started.get('ok'):
            self.container.remove_network(network); return started
        name=started['name']; url=f'http://127.0.0.1:{host_port}{health_path}'; startup_samples=[]; samples=[]; peak_rss=0.0; peak_cpu=0.0; ready=False; t0=time.monotonic()
        try:
            while time.monotonic()-t0 < startup_timeout:
                pr=_health_probe(url); startup_samples.append(pr); st=self.container.service_stats(name); peak_rss=max(peak_rss,st['rss_mb']); peak_cpu=max(peak_cpu,st['cpu_percent'])
                if pr.get('ok'): ready=True; samples.append(pr); break
                time.sleep(0.5)
            if ready:
                until=time.monotonic()+observe_seconds
                while time.monotonic()<until:
                    samples.append(_health_probe(url)); st=self.container.service_stats(name); peak_rss=max(peak_rss,st['rss_mb']); peak_cpu=max(peak_cpu,st['cpu_percent']); time.sleep(0.5)
            summary=_summarize(samples,peak_rss,peak_cpu); summary.update({'ok':ready,'url':url,'provider':'container','runtime':self.container.binary,'sandbox':spec.public(),'image_id':started.get('image_id'),'startup_probes':startup_samples[-50:]})
            if not ready: summary['log_tail']=self.container.logs(name)
            return summary
        finally:
            self.container.stop(name); self.container.remove_network(network)

    def run(self,evaluation_id:str,command:str,health_path:str='/health',service_port:int=8000,provider:str='host',image:str|None=None,
            observe_seconds:int|None=None,startup_timeout:int|None=None,max_latency_regression_pct:float|None=None,
            max_memory_regression_pct:float|None=None,min_health_success_pct:float|None=None)->dict:
        if not bool(self.config.get('enabled',True)): return {'ok':False,'error':'Canary operations are disabled.'}
        ev=self.evaluations.store.get(evaluation_id)
        if not ev:return {'ok':False,'error':'Unknown evaluation id.'}
        if ev.get('status')!='completed' or ev.get('verdict')!='passed': return {'ok':False,'error':'Canary requires a completed passing evaluation.'}
        if provider not in {'host','container'}: return {'ok':False,'error':'Provider must be host or container.'}
        if provider=='container' and self.profile=='lite' and not bool(self.evaluations.sandbox_config.get('lite_enabled',False)):
            return {'ok':False,'error':'Container canary is disabled on the lite profile by default.'}
        if provider=='container' and not image:return {'ok':False,'error':'Container canary requires an explicit image.'}
        pinned_image=image
        image_state=None
        if provider=='container':
            state=self.container.status()
            if not state.get('available'): return {'ok':False,'container_unavailable':True,'error':state.get('error') or state.get('reason')}
            image_state=self.container.image_info(str(image))
            if not image_state.get('available') or not image_state.get('image_id'):
                return {'ok':False,'image_unavailable':True,'error':'Canary image must already exist locally; automatic pulls are disabled.','image':image_state}
            pinned_image=image_state['image_id']
        decision=classify_command(command,require_execute_approval=False)
        if not decision.allowed or decision.risk.value in {'PRIVILEGED','DESTRUCTIVE'}: return {'ok':False,'error':'Unsafe canary command rejected.'}
        observe=int(observe_seconds if observe_seconds is not None else self._profile_value('observe_seconds_by_profile',20))
        startup=int(startup_timeout if startup_timeout is not None else self.config.get('startup_timeout_seconds',30))
        lat=float(max_latency_regression_pct if max_latency_regression_pct is not None else self.config.get('max_latency_regression_pct',20))
        mem=float(max_memory_regression_pct if max_memory_regression_pct is not None else self.config.get('max_memory_regression_pct',20))
        health=float(min_health_success_pct if min_health_success_pct is not None else self.config.get('min_health_success_pct',95))
        cfg={'observe_seconds':max(2,min(observe,300)),'startup_timeout_seconds':max(2,min(startup,180)),'max_latency_regression_pct':lat,'max_memory_regression_pct':mem,'min_health_success_pct':health}
        action='Run paired canary for evaluation '+evaluation_id+': '+_json({'provider':provider,'image':image,'image_id':(image_state or {}).get('image_id'),'command':command,'health_path':health_path,'service_port':service_port,**cfg})
        reason='Launches the evaluated baseline and candidate as temporary local canary services, records health/latency/resource metrics, then terminates both. Promotion remains a separate approval.'
        req=self.approval.request(action,reason,'SELF_CANARY')
        if not req.get('allowed'): return {'ok':False,'approval_required':True,**req,'plan':{'provider':provider,'image':image,'image_id':(image_state or {}).get('image_id'),'command':command,**cfg}}
        run=self.store.create(evaluation_id,provider,str(pinned_image) if pinned_image else None,command,health_path,service_port,{**cfg,'requested_image':image,'image_id':(image_state or {}).get('image_id')}); cid=run['id']; self.store.update(cid,status='running',started_at=_now())
        root=data_dir()/'canary_worktrees'/cid; shutil.rmtree(root,ignore_errors=True); root.mkdir(parents=True,exist_ok=True)
        baseline_dir=root/'baseline'; candidate_dir=root/'candidate'; repo=None
        try:
            project=Path(ev['project_path']).resolve(); proposal=self.improvements.store.get(ev['proposal_id'])
            if not proposal: raise RuntimeError('Improvement proposal no longer exists.')
            target=self.workspace.resolve(proposal['target_path'])
            if ev['mode']=='git_worktree':
                repo=_repo_root(project)
                if repo is None: raise RuntimeError('Git repository is unavailable.')
                branch=ev.get('branch_name'); cand=ev.get('candidate_commit'); base=ev.get('base_commit')
                tip=_git(repo,['rev-parse',branch]) if branch else {'ok':False}
                if not branch or not cand or not base or not tip.get('ok') or tip.get('stdout','').strip()!=cand: raise RuntimeError('Evaluated candidate branch no longer matches its measured commit.')
                if not _git(repo,['worktree','add','--detach',str(baseline_dir),base],timeout=120)['ok']: raise RuntimeError('Could not create baseline canary worktree.')
                if not _git(repo,['worktree','add','--detach',str(candidate_dir),cand],timeout=120)['ok']: raise RuntimeError('Could not create candidate canary worktree.')
                rel=project.relative_to(repo); baseline_cwd=baseline_dir/rel; candidate_cwd=candidate_dir/rel
            else:
                max_files=int(self.evaluations.config.get('copy_max_files',8000)); max_mb=int(self.evaluations.config.get('copy_max_mb',500))
                _copy_project(project,baseline_dir,max_files,max_mb); _copy_project(project,candidate_dir,max_files,max_mb)
                rel_target=target.relative_to(project); (candidate_dir/rel_target).write_text(proposal['proposed_content'],encoding='utf-8')
                baseline_cwd=baseline_dir; candidate_cwd=candidate_dir
            memory_mb=int(self.config.get('container_memory_mb',1024)); cpus=float(self.config.get('container_cpus',1.0)); pids=int(self.config.get('container_pids_limit',256))
            if provider=='container':
                baseline=self._run_container_service(command,baseline_cwd,str(pinned_image),service_port,health_path,cfg['startup_timeout_seconds'],cfg['observe_seconds'],memory_mb,cpus,pids)
                candidate=self._run_container_service(command,candidate_cwd,str(pinned_image),service_port,health_path,cfg['startup_timeout_seconds'],cfg['observe_seconds'],memory_mb,cpus,pids)
            else:
                baseline=self._run_host_service(command,baseline_cwd,_free_port(),health_path,cfg['startup_timeout_seconds'],cfg['observe_seconds'])
                candidate=self._run_host_service(command,candidate_cwd,_free_port(),health_path,cfg['startup_timeout_seconds'],cfg['observe_seconds'])
            comparison=compare_canary(baseline,candidate,health,lat,mem)
            result={'baseline':baseline,'candidate':candidate,'comparison':comparison,'candidate_commit':ev.get('candidate_commit'),'base_commit':ev.get('base_commit')}
            verdict='passed' if comparison.get('passed') else 'failed'
            self.store.update(cid,status='completed',verdict=verdict,result_json=_json(result),finished_at=_now())
            return {'ok':True,**(self.store.get(cid) or {}),'promotable_after_canary':comparison.get('passed')}
        except Exception as exc:
            self.store.update(cid,status='error',verdict='error',error=str(exc),finished_at=_now()); return {'ok':False,**(self.store.get(cid) or {}),'error':str(exc)}
        finally:
            if repo is not None:
                for p in (baseline_dir,candidate_dir):
                    if p.exists(): _git(repo,['worktree','remove','--force',str(p)],timeout=120)
                _git(repo,['worktree','prune'])
            shutil.rmtree(root,ignore_errors=True)
