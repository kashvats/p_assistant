from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid

import psutil

from .security_policy import classify_command

_SIZE_RE = re.compile(r'^\s*([0-9.]+)\s*([kmgt]?i?b)?', re.I)

_SECRET_ENV_RE = re.compile(r'(TOKEN|PASSWORD|PASSWD|SECRET|CREDENTIAL|COOKIE|AUTH|PRIVATE[_-]?KEY|ACCESS[_-]?KEY|API[_-]?KEY)', re.I)

def sanitized_env(extra: dict[str,str] | None = None) -> dict[str,str]:
    env={}
    for key,value in os.environ.items():
        if _SECRET_ENV_RE.search(key):
            continue
        if key in {'SSH_AUTH_SOCK','GPG_AGENT_INFO'}:
            continue
        env[key]=value
    env.update(extra or {})
    return env



def _size_bytes(value: str) -> int:
    m = _SIZE_RE.match(value or '')
    if not m:
        return 0
    number = float(m.group(1)); unit = (m.group(2) or 'b').lower()
    factors = {'b':1,'kb':1000,'kib':1024,'mb':1000**2,'mib':1024**2,'gb':1000**3,'gib':1024**3,'tb':1000**4,'tib':1024**4}
    return int(number * factors.get(unit, 1))


@dataclass
class SandboxSpec:
    image: str
    network: str = 'none'
    memory_mb: int = 1024
    cpus: float = 1.0
    pids_limit: int = 256
    read_only_root: bool = True
    tmpfs_mb: int = 128

    def public(self) -> dict:
        return asdict(self)


class ContainerRuntime:
    """Small Docker/Podman adapter. It never shells out through a command shell."""
    def __init__(self, preferred: str = 'auto'):
        self.preferred = preferred
        self.binary = self._detect(preferred)

    @staticmethod
    def _detect(preferred: str) -> str | None:
        if preferred in {'docker','podman'}:
            return preferred if shutil.which(preferred) else None
        return next((x for x in ('docker','podman') if shutil.which(x)), None)

    def status(self) -> dict:
        if not self.binary:
            return {'available':False,'runtime':None,'reason':'Neither docker nor podman was found on PATH.'}
        try:
            p = subprocess.run([self.binary,'version','--format','{{.Server.Version}}'], capture_output=True, text=True, timeout=6)
            if p.returncode != 0 and self.binary == 'podman':
                p = subprocess.run([self.binary,'version','--format','{{.Version}}'], capture_output=True, text=True, timeout=6)
            return {'available':p.returncode==0,'runtime':self.binary,'version':p.stdout.strip() or None,'error':p.stderr.strip() or None}
        except Exception as exc:
            return {'available':False,'runtime':self.binary,'error':str(exc)}

    def _base_run_argv(self, name: str, workspace: Path, spec: SandboxSpec, detach: bool = False,
                       host_port: int | None = None, container_port: int | None = None,
                       env: dict[str,str] | None = None) -> list[str]:
        if not self.binary:
            raise RuntimeError('Container runtime is unavailable.')
        argv = [self.binary,'run','--rm','--pull','never','--name',name]
        if detach:
            argv.append('-d')
        argv += ['--workdir','/workspace']
        argv += ['--mount',f'type=bind,src={workspace.resolve()},dst=/workspace,rw']
        argv += ['--network',spec.network]
        argv += ['--memory',f'{max(128,int(spec.memory_mb))}m','--cpus',str(max(0.1,float(spec.cpus))),'--pids-limit',str(max(32,int(spec.pids_limit)))]
        argv += ['--cap-drop','ALL','--security-opt','no-new-privileges','--ipc','none','--ulimit','nofile=1024:1024']
        if hasattr(os,'getuid') and hasattr(os,'getgid'):
            argv += ['--user',f'{os.getuid()}:{os.getgid()}']
        if spec.read_only_root:
            argv.append('--read-only')
        argv += ['--tmpfs',f'/tmp:rw,nosuid,noexec,size={max(16,int(spec.tmpfs_mb))}m']
        if host_port and container_port:
            argv += ['-p',f'127.0.0.1:{host_port}:{container_port}']
        for key, value in sorted((env or {}).items()):
            argv += ['-e',f'{key}={value}']
        argv.append(spec.image)
        return argv

    def _stats(self, name: str) -> dict:
        if not self.binary:
            return {'rss_bytes':0,'cpu_percent':0.0}
        try:
            if self.binary == 'docker':
                p = subprocess.run([self.binary,'stats','--no-stream','--format','{{json .}}',name],capture_output=True,text=True,timeout=3)
                data = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else {}
                mem = str(data.get('MemUsage','')).split('/')[0].strip()
                cpu = str(data.get('CPUPerc','0')).replace('%','')
                return {'rss_bytes':_size_bytes(mem),'cpu_percent':float(cpu or 0)}
            p = subprocess.run([self.binary,'stats','--no-stream','--format','json',name],capture_output=True,text=True,timeout=3)
            arr = json.loads(p.stdout or '[]') if p.returncode == 0 else []
            data = arr[0] if isinstance(arr,list) and arr else {}
            return {'rss_bytes':int(data.get('mem_usage',0) or 0),'cpu_percent':float(data.get('cpu_percent',0) or 0)}
        except Exception:
            return {'rss_bytes':0,'cpu_percent':0.0}

    def image_info(self, image: str) -> dict:
        if not self.binary:
            return {'available':False,'error':'Container runtime unavailable.'}
        try:
            p=subprocess.run([self.binary,'image','inspect',image,'--format','{{.Id}}'],capture_output=True,text=True,timeout=8)
            return {'available':p.returncode==0,'image':image,'image_id':p.stdout.strip() or None,'error':p.stderr.strip() or None}
        except Exception as exc:
            return {'available':False,'image':image,'error':str(exc)}

    def run_command(self, command: str, cwd: Path, timeout_seconds: int, spec: SandboxSpec) -> dict:
        decision = classify_command(command, require_execute_approval=False)
        if not decision.allowed or decision.risk.value in {'PRIVILEGED','DESTRUCTIVE'}:
            return {'ok':False,'blocked':True,'command':command,'reason':'Unsafe command rejected before container execution.','duration_seconds':0.0,'peak_rss_mb':0.0}
        try:
            cmd_argv = shlex.split(command, posix=(os.name != 'nt'))
        except ValueError as exc:
            return {'ok':False,'blocked':True,'command':command,'reason':f'Could not parse command safely: {exc}','duration_seconds':0.0,'peak_rss_mb':0.0}
        if not cmd_argv:
            return {'ok':False,'blocked':True,'command':command,'reason':'Empty command.','duration_seconds':0.0,'peak_rss_mb':0.0}
        state = self.status()
        if not state.get('available'):
            return {'ok':False,'container_unavailable':True,'command':command,'error':state.get('error') or state.get('reason'),'duration_seconds':0.0,'peak_rss_mb':0.0}
        image_state=self.image_info(spec.image)
        if not image_state.get('available'):
            return {'ok':False,'image_unavailable':True,'command':command,'error':'Sandbox image is not present locally; automatic image pulls are disabled.','image':image_state,'duration_seconds':0.0,'peak_rss_mb':0.0}
        name = 'living-eval-' + uuid.uuid4().hex[:10]
        env = {'LIVING_ASSISTANT_EVALUATION':'1','CI':'1','PYTHONDONTWRITEBYTECODE':'1'}
        argv = self._base_run_argv(name,cwd,spec,env=env) + cmd_argv
        started = time.perf_counter(); peak = 0; timed_out = False
        with tempfile.TemporaryFile(mode='w+b') as out, tempfile.TemporaryFile(mode='w+b') as err:
            try:
                proc = subprocess.Popen(argv, shell=False, stdout=out, stderr=err)
            except Exception as exc:
                return {'ok':False,'command':command,'argv':argv,'error':str(exc),'duration_seconds':round(time.perf_counter()-started,4),'peak_rss_mb':0.0}
            while proc.poll() is None:
                if time.perf_counter() - started > timeout_seconds:
                    timed_out = True
                    self.stop(name)
                    try: proc.terminate()
                    except Exception: pass
                    break
                stats = self._stats(name); peak = max(peak, int(stats.get('rss_bytes',0)))
                time.sleep(0.08)
            try: rc = proc.wait(timeout=5)
            except Exception:
                self.stop(name); rc = proc.poll()
            out.seek(0); err.seek(0)
            stdout = out.read().decode('utf-8',errors='replace')[-30000:]
            stderr = err.read().decode('utf-8',errors='replace')[-10000:]
        return {'ok':rc==0 and not timed_out,'command':command,'argv':argv,'returncode':rc,'timeout':timed_out,
                'duration_seconds':round(time.perf_counter()-started,4),'peak_rss_mb':round(peak/(1024**2),2),
                'stdout':stdout,'stderr':stderr,'execution_provider':'container','runtime':self.binary,'sandbox':spec.public(),'image_id':image_state.get('image_id')}

    def create_internal_network(self, name: str) -> dict:
        if not self.binary:
            return {'ok':False,'error':'Container runtime unavailable.'}
        try:
            p = subprocess.run([self.binary,'network','create','--internal',name],capture_output=True,text=True,timeout=10)
            return {'ok':p.returncode==0,'name':name,'id':p.stdout.strip() or None,'stderr':p.stderr[-3000:]}
        except Exception as exc:
            return {'ok':False,'error':str(exc)}

    def remove_network(self, name: str):
        if not self.binary: return
        try:
            subprocess.run([self.binary,'network','rm',name],capture_output=True,text=True,timeout=8)
        except Exception:
            pass

    def start_service(self, command: str, cwd: Path, spec: SandboxSpec, host_port: int, container_port: int,
                      env: dict[str,str] | None = None) -> dict:
        try:
            cmd_argv = shlex.split(command, posix=(os.name != 'nt'))
        except ValueError as exc:
            return {'ok':False,'error':str(exc)}
        if not cmd_argv:
            return {'ok':False,'error':'Empty canary command.'}
        decision = classify_command(command, require_execute_approval=False)
        if not decision.allowed or decision.risk.value in {'PRIVILEGED','DESTRUCTIVE'}:
            return {'ok':False,'blocked':True,'error':'Unsafe canary command rejected.'}
        state = self.status()
        if not state.get('available'):
            return {'ok':False,'container_unavailable':True,'error':state.get('error') or state.get('reason')}
        image_state=self.image_info(spec.image)
        if not image_state.get('available'):
            return {'ok':False,'image_unavailable':True,'error':'Canary image is not present locally; automatic image pulls are disabled.','image':image_state}
        name = 'living-canary-' + uuid.uuid4().hex[:10]
        argv = self._base_run_argv(name,cwd,spec,detach=True,host_port=host_port,container_port=container_port,env=env) + cmd_argv
        p = subprocess.run(argv,capture_output=True,text=True,timeout=30)
        return {'ok':p.returncode==0,'name':name,'id':p.stdout.strip() or None,'argv':argv,'stderr':p.stderr[-5000:],
                'runtime':self.binary,'host_port':host_port,'container_port':container_port,'image_id':image_state.get('image_id')}

    def service_stats(self, name: str) -> dict:
        s = self._stats(name)
        return {'rss_mb':round(s.get('rss_bytes',0)/(1024**2),2),'cpu_percent':round(float(s.get('cpu_percent',0)),2)}

    def logs(self, name: str, tail: int = 200) -> str:
        if not self.binary: return ''
        try:
            p = subprocess.run([self.binary,'logs','--tail',str(max(1,min(tail,2000))),name],capture_output=True,text=True,timeout=5)
            return (p.stdout + '\n' + p.stderr)[-20000:]
        except Exception:
            return ''

    def stop(self, name: str):
        if not self.binary: return
        try:
            subprocess.run([self.binary,'stop','-t','3',name],capture_output=True,text=True,timeout=8)
        except Exception:
            try: subprocess.run([self.binary,'rm','-f',name],capture_output=True,text=True,timeout=5)
            except Exception: pass
