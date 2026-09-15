from __future__ import annotations
import subprocess, os, time, uuid, json
import psutil
from pathlib import Path
from .base import Tool
from ..security_policy import classify_command
from ..approval import ApprovalManager
from ..workspace import Workspace
from ..config import data_dir

class ProcessRegistry:
    def __init__(self):
        self.items: dict[str, subprocess.Popen] = {}
        self.meta_path = data_dir() / "managed_processes.json"
        if not self.meta_path.exists():
            self.meta_path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict):
        self.meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, pid_key: str, proc: subprocess.Popen, meta: dict):
        self.items[pid_key] = proc
        data = self._load()
        data[pid_key] = {**meta, "pid": proc.pid, "created_at": time.time()}
        self._save(data)

    def list(self):
        data = self._load()
        out = []
        changed = False
        for key, meta in list(data.items()):
            pid = int(meta.get("pid", -1))
            running = pid > 0 and psutil.pid_exists(pid)
            out.append({**meta, "id": key, "running": running})
            if not running and meta.get("stopped_at") is None:
                meta["stopped_at"] = time.time(); changed = True
        if changed:
            self._save(data)
        return out

    def stop(self, key: str):
        data = self._load()
        meta = data.get(key)
        if not meta:
            return {"ok": False, "error": "Unknown process id"}
        pid = int(meta.get("pid", -1))
        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            for child in children:
                try: child.terminate()
                except Exception: pass
            proc.terminate()
            gone, alive = psutil.wait_procs([proc, *children], timeout=8)
            for remaining in alive:
                try: remaining.kill()
                except Exception: pass
            meta["stopped_at"] = time.time()
            self._save(data)
            return {"ok": True, "pid": pid}
        except psutil.NoSuchProcess:
            meta["stopped_at"] = time.time(); self._save(data)
            return {"ok": True, "pid": pid, "already_stopped": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

def build_shell_tools(workspace: Workspace, approval: ApprovalManager, config: dict, registry: ProcessRegistry) -> list[Tool]:
    timeout = int(config.get("policy", {}).get("command_timeout_seconds", 120))
    require = bool(config.get("policy", {}).get("require_execute_approval", True))
    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    def run_command(command: str, cwd: str = ".", timeout_seconds: int | None = None):
        cwdp = workspace.resolve(cwd)
        decision = classify_command(command, require)
        if not decision.allowed:
            return {"ok": False, "blocked": True, "reason": decision.reason, "risk": decision.risk.value}
        if decision.requires_approval and not approval.approve(command, decision.reason):
            return {"ok": False, "approved": False, "reason": "User did not approve."}
        try:
            p = subprocess.run(
                command, cwd=str(cwdp), shell=True, text=True, capture_output=True,
                timeout=min(timeout_seconds or timeout, 600),
                env=os.environ.copy()
            )
            return {"ok": p.returncode == 0, "returncode": p.returncode, "stdout": p.stdout[-20000:], "stderr": p.stderr[-20000:]}
        except subprocess.TimeoutExpired as e:
            return {"ok": False, "timeout": True, "stdout": (e.stdout or "")[-10000:], "stderr": (e.stderr or "")[-10000:]}

    def start_process(command: str, cwd: str = ".", name: str | None = None):
        cwdp = workspace.resolve(cwd)
        decision = classify_command(command, True)
        if not decision.allowed:
            return {"ok": False, "blocked": True, "reason": decision.reason}
        if not approval.approve(command, "Starting a long-running project/process."):
            return {"ok": False, "approved": False}
        key = uuid.uuid4().hex[:10]
        log_path = log_dir / f"process-{key}.log"
        fh = open(log_path, "a", encoding="utf-8")
        proc = subprocess.Popen(command, cwd=str(cwdp), shell=True, stdout=fh, stderr=subprocess.STDOUT, text=True, env=os.environ.copy())
        registry.add(key, proc, {"name": name or command[:80], "command": command, "cwd": str(cwdp), "log": str(log_path)})
        return {"ok": True, "id": key, "pid": proc.pid, "log": str(log_path)}

    def list_processes():
        return registry.list()

    def stop_process(process_id: str):
        return registry.stop(process_id)

    return [
        Tool("run_command", "Run a bounded shell command inside the approved workspace. Policy may block or require approval.",
             {"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string","default":"."},"timeout_seconds":{"type":"integer"}},"required":["command"]}, run_command),
        Tool("start_process", "Start a long-running local project/process, tracked with a log file.",
             {"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string","default":"."},"name":{"type":"string"}},"required":["command"]}, start_process),
        Tool("list_managed_processes", "List project/processes started by this assistant.",
             {"type":"object","properties":{}}, list_processes),
        Tool("stop_managed_process", "Stop a process previously started by this assistant.",
             {"type":"object","properties":{"process_id":{"type":"string"}},"required":["process_id"]}, stop_process),
    ]
