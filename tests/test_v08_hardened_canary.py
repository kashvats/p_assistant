from __future__ import annotations
from pathlib import Path
import subprocess

from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.canary import CanaryEngine, CanaryStore, compare_canary
from living_assistant.evaluation import EvaluationEngine, EvaluationStore
from living_assistant.improvements import ImprovementEngine, ImprovementStore
from living_assistant.sandbox import ContainerRuntime, SandboxSpec
from living_assistant.workspace import Workspace


def approve_and_retry(store, first, retry):
    assert first['approval_required'] is True
    store.resolve(first['approval_id'], True)
    return retry()


def base_stack(tmp_path):
    project=tmp_path/'project'; project.mkdir()
    ws=Workspace([project])
    approvals=ApprovalStore(tmp_path/'approvals.sqlite3')
    manager=ApprovalManager(interactive=False,store=approvals)
    improvements=ImprovementEngine(ws,manager,ImprovementStore(tmp_path/'improvements.sqlite3'))
    cfg={'self_improvement':{
        'evaluation':{'enabled':True,'execution_provider':'host','command_timeout_seconds':5,'max_commands':8,'copy_max_files':100,'copy_max_mb':10},
        'sandbox':{'runtime':'auto','memory_mb':512,'cpus':0.5,'pids_limit':64,'read_only_root':True,'tmpfs_mb':32},
        'canary':{'enabled':True,'observe_seconds_by_profile':{'balanced':2},'startup_timeout_seconds':2,'min_health_success_pct':95,'max_latency_regression_pct':20,'max_memory_regression_pct':20},
    }}
    evaluations=EvaluationEngine(ws,manager,improvements,EvaluationStore(tmp_path/'eval.sqlite3'),cfg,profile='balanced')
    canary_store=CanaryStore(tmp_path/'canary.sqlite3')
    canaries=CanaryEngine(ws,manager,improvements,evaluations,canary_store,cfg,profile='balanced')
    evaluations.canary_store=canary_store
    return project,approvals,improvements,evaluations,canaries


def git(cwd:Path,*args):
    p=subprocess.run(['git',*args],cwd=cwd,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    return p.stdout.strip()


def test_sandbox_argv_drops_privilege_and_binds_localhost(tmp_path):
    rt=ContainerRuntime('docker'); rt.binary='docker'
    spec=SandboxSpec('python:3.11-slim',network='none',memory_mb=512,cpus=0.5,pids_limit=64,read_only_root=True,tmpfs_mb=32)
    argv=rt._base_run_argv('x',tmp_path,spec,detach=True,host_port=43210,container_port=8000,env={'PORT':'8000'})
    text=' '.join(argv)
    assert '--cap-drop ALL' in text
    assert '--security-opt no-new-privileges' in text
    assert '--read-only' in argv
    assert '--network none' in text
    assert '127.0.0.1:43210:8000' in argv
    assert '--privileged' not in argv
    assert '--pull' in argv and 'never' in argv
    assert '/var/run/docker.sock' not in text and '/run/podman/podman.sock' not in text


def test_container_suite_roundtrip_and_mocked_evaluation(tmp_path):
    project,approvals,improvements,evaluations,_=base_stack(tmp_path)
    (project/'a.txt').write_text('old')
    proposal=improvements.propose('a.txt','new','change','reason')
    suite=evaluations.create_suite('boxed',str(project),['python -c "print(1)"'],execution_provider='container',sandbox_image='python:3.11-slim',require_canary=True)
    assert suite['execution_provider']=='container' and suite['require_canary']==1
    seen=[]
    evaluations.container_runtime.status=lambda:{'available':True,'runtime':'docker'}
    evaluations.container_runtime.image_info=lambda image:{'available':True,'image':image,'image_id':'sha256:testimage'}
    def fake_run(command,cwd,timeout,spec):
        seen.append(spec)
        return {'ok':True,'command':command,'returncode':0,'duration_seconds':0.01,'peak_rss_mb':10,'stdout':'ok','stderr':'','execution_provider':'container'}
    evaluations.container_runtime.run_command=fake_run
    first=evaluations.evaluate(proposal['id'],suite_name='boxed')
    result=approve_and_retry(approvals,first,lambda:evaluations.evaluate(proposal['id'],suite_name='boxed'))
    assert result['verdict']=='passed'
    assert result['result']['execution_provider']=='container'
    assert result['result']['gates']['canary_required'] is True
    assert seen and all(x.network=='none' and x.image=='sha256:testimage' for x in seen)


def test_canary_comparison_enforces_health_and_budgets():
    base={'health_success_pct':100,'median_latency_ms':100,'peak_rss_mb':100}
    good={'health_success_pct':100,'median_latency_ms':110,'peak_rss_mb':105}
    bad_health={'health_success_pct':80,'median_latency_ms':90,'peak_rss_mb':90}
    assert compare_canary(base,good,95,20,20)['passed'] is True
    assert compare_canary(base,bad_health,95,20,20)['passed'] is False
    assert compare_canary(base,{'health_success_pct':100,'median_latency_ms':140,'peak_rss_mb':100},95,20,20)['passed'] is False


def test_promotion_requires_exact_passing_canary_when_suite_demands_it(tmp_path):
    project,approvals,improvements,evaluations,canaries=base_stack(tmp_path)
    git(project,'init'); git(project,'config','user.email','test@example.com'); git(project,'config','user.name','Test User')
    (project/'a.txt').write_text('old'); git(project,'add','a.txt'); git(project,'commit','-m','base')
    proposal=improvements.propose('a.txt','new','change','reason')
    evaluations.create_suite('need-canary',str(project),['python -c "print(1)"'],require_canary=True)
    first=evaluations.evaluate(proposal['id'],suite_name='need-canary')
    ev=approve_and_retry(approvals,first,lambda:evaluations.evaluate(proposal['id'],suite_name='need-canary'))
    blocked=evaluations.promote(ev['id'])
    assert blocked.get('canary_required') is True

    cr=canaries.store.create(ev['id'],'host',None,'python app.py','/health',8000,{})
    canaries.store.update(cr['id'],status='completed',verdict='passed',result_json='{"base_commit":"%s","candidate_commit":"%s"}'%(ev['base_commit'],ev['candidate_commit']))
    first_promote=evaluations.promote(ev['id'])
    promoted=approve_and_retry(approvals,first_promote,lambda:evaluations.promote(ev['id']))
    assert promoted['ok'] is True
    assert (project/'a.txt').read_text()=='new'


def test_canary_run_records_paired_measurement_without_promoting(tmp_path):
    project,approvals,improvements,evaluations,canaries=base_stack(tmp_path)
    (project/'a.txt').write_text('old')
    proposal=improvements.propose('a.txt','new','change','reason')
    first=evaluations.evaluate(proposal['id'],project_path=str(project),test_commands=['python -c "print(1)"'])
    ev=approve_and_retry(approvals,first,lambda:evaluations.evaluate(proposal['id'],project_path=str(project),test_commands=['python -c "print(1)"']))
    calls=[]
    def fake_host(command,cwd,host_port,health_path,startup_timeout,observe_seconds):
        calls.append(cwd)
        if len(calls)==1:
            return {'ok':True,'provider':'host','health_success_pct':100,'median_latency_ms':100,'peak_rss_mb':100,'peak_cpu_percent':10}
        return {'ok':True,'provider':'host','health_success_pct':100,'median_latency_ms':105,'peak_rss_mb':102,'peak_cpu_percent':11}
    canaries._run_host_service=fake_host
    c1=canaries.run(ev['id'],'python app.py',provider='host',observe_seconds=2)
    result=approve_and_retry(approvals,c1,lambda:canaries.run(ev['id'],'python app.py',provider='host',observe_seconds=2))
    assert result['verdict']=='passed'
    assert result['result']['comparison']['passed'] is True
    assert len(calls)==2
    assert (project/'a.txt').read_text()=='old'


def test_lite_profile_rejects_container_by_default(tmp_path):
    project,approvals,improvements,evaluations,_=base_stack(tmp_path)
    evaluations.profile='lite'; evaluations.sandbox_config['lite_enabled']=False
    (project/'a.txt').write_text('old'); proposal=improvements.propose('a.txt','new','change','reason')
    result=evaluations.evaluate(proposal['id'],project_path=str(project),test_commands=['python -c "print(1)"'],execution_provider='container',sandbox_image='python:3.11-slim')
    assert result['ok'] is False and 'lite profile' in result['error']


def test_real_host_canary_excludes_startup_failures_from_health_window(tmp_path):
    project,approvals,improvements,evaluations,canaries=base_stack(tmp_path)
    (project/'server.py').write_text('''import os\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200 if self.path=="/health" else 404); self.end_headers(); self.wfile.write(b"ok")\n def log_message(self,*a): pass\nHTTPServer(("127.0.0.1",int(os.environ["PORT"])),H).serve_forever()\n''')
    from living_assistant.canary import _free_port
    result=canaries._run_host_service('python server.py',project,_free_port(),'/health',3,1)
    assert result['ok'] is True
    assert result['health_success_pct'] == 100.0
    assert result['startup_probes']


def test_evaluation_subprocess_redacts_common_secret_environment(monkeypatch,tmp_path):
    monkeypatch.setenv('MY_API_KEY','super-secret')
    monkeypatch.setenv('NORMAL_BUILD_FLAG','ok')
    from living_assistant.evaluation import measure_command
    cmd='python -c "import os; assert os.getenv(\'MY_API_KEY\') is None; assert os.getenv(\'NORMAL_BUILD_FLAG\') == \'ok\'"'
    result=measure_command(cmd,tmp_path,timeout_seconds=3)
    assert result['ok'] is True
