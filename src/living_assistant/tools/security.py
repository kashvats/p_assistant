from __future__ import annotations
import psutil, platform, shutil, subprocess, socket
from .base import Tool
from ..approval import ApprovalManager
from ..workspace import Workspace
from ..security_guardian import SecurityGuardian, inspect_process, file_signature, antivirus_posture, process_triage, network_activity_summary


def _conn_name(c):
    try:
        return f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None
    except Exception:
        return str(c.laddr)


def audit_local():
    listening=[]; established=[]
    try:
        for c in psutil.net_connections(kind='inet'):
            item={'pid':c.pid,'local':_conn_name(c),'status':c.status}
            if c.raddr:
                try: item['remote']=f"{c.raddr.ip}:{c.raddr.port}"
                except Exception: item['remote']=str(c.raddr)
            if c.pid:
                try:
                    p=psutil.Process(c.pid); item['process']=p.name()
                except Exception: pass
            if c.status==psutil.CONN_LISTEN: listening.append(item)
            elif c.status==psutil.CONN_ESTABLISHED: established.append(item)
    except (psutil.AccessDenied,PermissionError): pass

    procs=[]
    for p in psutil.process_iter(['pid','ppid','name','username']):
        try: procs.append(p.info)
        except Exception: pass
    return {
        'hostname':socket.gethostname(),'listening_ports':listening[:300],
        'established_connections':established[:300],'process_count':len(procs),
        'sample_processes':procs[:300],
        'note':'An unfamiliar port/process is not proof of compromise. Investigate before containment.'
    }


def antivirus_status():
    return antivirus_posture()


def build_security_tools(workspace: Workspace, approval: ApprovalManager, guardian: SecurityGuardian | None=None) -> list[Tool]:
    guardian=guardian or SecurityGuardian({},approval=approval)

    def local_security_audit(): return audit_local()
    def security_posture(include_updates: bool=False): return guardian.posture(include_updates=include_updates)
    def security_findings(status: str='open'): return guardian.findings(None if status=='all' else status,100)
    def security_process_inspect(pid: int): return inspect_process(pid)
    def security_process_triage(min_score: int=30): return process_triage(min_score=min_score,limit=50)
    def security_network_activity(limit: int=100): return network_activity_summary(limit)
    def security_startup_check(): return guardian.check_startup_baseline(record=True)
    def security_network_check(): return guardian.check_network_baseline(record=True)
    def security_integrity_list(): return guardian.list_integrity_baselines()
    def security_integrity_check(name: str): return guardian.check_integrity_baseline(name,record=True)

    def security_integrity_add_workspace(name: str,path: str='.',recursive: bool=True,extensions: list[str]|None=None):
        target=workspace.resolve(path)
        reason=f'Create or replace integrity baseline {name} for {target}'
        req=approval.request(f'Security baseline change: {name}',reason,'SECURITY_BASELINE_CHANGE')
        if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        return guardian.add_integrity_baseline(name,target,recursive,extensions or [])

    def security_file_signature(path: str):
        return file_signature(workspace.resolve(path))

    def security_contain_process(pid: int):
        return guardian.terminate_user_process(pid)

    def antivirus_quick_scan(path: str='.'):
        target=workspace.resolve(path); osname=platform.system()
        req=approval.request(f'Antivirus scan: {target}','This invokes the installed local antivirus scanner.','EXECUTE')
        if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        if osname=='Windows':
            cmd=['powershell','-NoProfile','-Command',f"Start-MpScan -ScanType CustomScan -ScanPath '{str(target).replace(chr(39),chr(39)+chr(39))}'"]
        elif shutil.which('clamscan'): cmd=['clamscan','-r',str(target)]
        else: return {'ok':False,'error':'No supported antivirus CLI found.'}
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
            return {'ok':p.returncode in (0,1),'returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-5000:]}
        except subprocess.TimeoutExpired: return {'ok':False,'timeout':True}

    return [
        Tool('local_security_audit','Defensive audit of this machine\'s listening ports, active connections and processes.',{'type':'object','properties':{}},local_security_audit),
        Tool('security_posture','Read firewall, antivirus, disk-encryption and optional update posture. Read-only.',{'type':'object','properties':{'include_updates':{'type':'boolean','default':False}}},security_posture),
        Tool('security_findings','List deterministic guardian findings. A finding is a signal, not proof of malware.',{'type':'object','properties':{'status':{'type':'string','enum':['open','resolved','all'],'default':'open'}}},security_findings),
        Tool('security_process_inspect','Inspect one local process, its ancestry, connections and heuristic signals.',{'type':'object','properties':{'pid':{'type':'integer'}},'required':['pid']},security_process_inspect),
        Tool('security_process_triage','List processes with deterministic suspicious signals. Signals are not proof of malware.',{'type':'object','properties':{'min_score':{'type':'integer','default':30}}},security_process_triage),
        Tool('security_network_activity','Summarize currently established local network connections and public/private scope.',{'type':'object','properties':{'limit':{'type':'integer','default':100}}},security_network_activity),
        Tool('security_startup_check','Compare current startup/persistence items with the saved local baseline.',{'type':'object','properties':{}},security_startup_check),
        Tool('security_network_check','Compare current listening services with the saved local baseline.',{'type':'object','properties':{}},security_network_check),
        Tool('security_integrity_list','List protected file-integrity baselines.',{'type':'object','properties':{}},security_integrity_list),
        Tool('security_integrity_check','Check one protected path for added, removed or modified files.',{'type':'object','properties':{'name':{'type':'string'}},'required':['name']},security_integrity_check),
        Tool('security_integrity_add_workspace','Create/refresh a file-integrity baseline inside an approved workspace.',{'type':'object','properties':{'name':{'type':'string'},'path':{'type':'string','default':'.'},'recursive':{'type':'boolean','default':True},'extensions':{'type':'array','items':{'type':'string'}}},'required':['name']},security_integrity_add_workspace),
        Tool('security_file_signature','Hash a workspace file and inspect OS signature/package ownership information when available.',{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},security_file_signature),
        Tool('security_contain_process','Terminate a non-critical process owned by the current user. Always requires approval.',{'type':'object','properties':{'pid':{'type':'integer'}},'required':['pid']},security_contain_process),
        Tool('antivirus_status','Check Microsoft Defender, ClamAV or platform protection status.',{'type':'object','properties':{}},antivirus_status),
        Tool('antivirus_quick_scan','Run an installed antivirus scanner on an approved workspace path. Requires approval.',{'type':'object','properties':{'path':{'type':'string','default':'.'}}},antivirus_quick_scan),
    ]
