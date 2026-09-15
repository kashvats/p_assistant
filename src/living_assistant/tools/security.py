from __future__ import annotations
import psutil, platform, shutil, subprocess, socket
from .base import Tool
from ..approval import ApprovalManager
from ..workspace import Workspace

def _conn_name(c):
    try:
        return f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None
    except Exception:
        return str(c.laddr)

def audit_local():
    listening = []
    established = []
    try:
        for c in psutil.net_connections(kind="inet"):
            item = {"pid":c.pid,"local":_conn_name(c),"status":c.status}
            if c.raddr:
                try: item["remote"] = f"{c.raddr.ip}:{c.raddr.port}"
                except Exception: item["remote"] = str(c.raddr)
            if c.status == psutil.CONN_LISTEN:
                listening.append(item)
            elif c.status == psutil.CONN_ESTABLISHED:
                established.append(item)
    except (psutil.AccessDenied, PermissionError):
        pass

    procs = []
    for p in psutil.process_iter(["pid","ppid","name","username"]):
        try:
            procs.append(p.info)
        except Exception:
            pass

    return {
        "hostname":socket.gethostname(),
        "listening_ports":listening[:200],
        "established_connections":established[:200],
        "process_count":len(procs),
        "sample_processes":procs[:200],
        "note":"A port/process being unfamiliar is not proof of compromise. Investigate before acting."
    }

def antivirus_status():
    osname = platform.system()
    if osname == "Windows":
        cmd = ["powershell","-NoProfile","-Command",
               "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json"]
    elif shutil.which("clamscan"):
        cmd = ["clamscan","--version"]
    else:
        return {"available":False,"message":"No supported antivirus CLI detected by this MVP."}
    try:
        p = subprocess.run(cmd,capture_output=True,text=True,timeout=20)
        return {"available":True,"returncode":p.returncode,"stdout":p.stdout[-10000:],"stderr":p.stderr[-3000:]}
    except Exception as e:
        return {"available":False,"error":str(e)}

def build_security_tools(workspace: Workspace, approval: ApprovalManager) -> list[Tool]:
    def local_security_audit():
        return audit_local()

    def antivirus_quick_scan(path: str = "."):
        target = workspace.resolve(path)
        osname = platform.system()
        req = approval.request(f"Antivirus scan: {target}", "This invokes the installed local antivirus scanner.", "EXECUTE")
        if not req.get("allowed"):
            return {"ok":False,"approval_required":True,**req}
        if osname == "Windows":
            # Defender custom scan is bounded to the approved workspace path.
            cmd = ["powershell","-NoProfile","-Command", f"Start-MpScan -ScanType CustomScan -ScanPath '{str(target).replace(chr(39), chr(39)+chr(39))}'"]
        elif shutil.which("clamscan"):
            cmd = ["clamscan","-r",str(target)]
        else:
            return {"ok":False,"error":"No supported antivirus CLI found."}
        try:
            p = subprocess.run(cmd,capture_output=True,text=True,timeout=600)
            return {"ok":p.returncode in (0,1),"returncode":p.returncode,"stdout":p.stdout[-20000:],"stderr":p.stderr[-5000:]}
        except subprocess.TimeoutExpired:
            return {"ok":False,"timeout":True}

    return [
        Tool("local_security_audit", "Defensive audit of this machine's listening ports, active connections and processes.",
             {"type":"object","properties":{}}, local_security_audit),
        Tool("antivirus_status", "Check Windows Defender or ClamAV status/version if available.",
             {"type":"object","properties":{}}, antivirus_status),
        Tool("antivirus_quick_scan", "Run an installed antivirus scanner on an approved workspace path. Requires approval.",
             {"type":"object","properties":{"path":{"type":"string","default":"."}}}, antivirus_quick_scan),
    ]
