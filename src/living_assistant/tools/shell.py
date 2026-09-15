from __future__ import annotations
import subprocess, os, time, uuid, json, platform, threading
import psutil
from pathlib import Path
from .base import Tool
from ..security_policy import classify_command
from ..approval import ApprovalManager
from ..workspace import Workspace
from ..config import data_dir
from ..storage_utils import atomic_write_json
from ..security_utils import is_loopback_http_url, redact_secrets

class ProcessRegistry:
    def __init__(self, meta_path: Path | None = None):
        self.meta_path = meta_path or (data_dir() / "managed_processes.json")
        self._lock = threading.RLock()
        if not self.meta_path.exists():
            atomic_write_json(self.meta_path, {})

    def _load(self) -> dict:
        with self._lock:
            try:
                return json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception:
                return {}

    def _save(self, data: dict):
        with self._lock:
            atomic_write_json(self.meta_path, data)

    @staticmethod
    def _process_matches(pid: int, expected_create_time: float | None) -> bool:
        if expected_create_time is None:
            return False
        try:
            p = psutil.Process(pid)
            return (p.is_running() and p.status() != psutil.STATUS_ZOMBIE
                    and abs(float(p.create_time()) - float(expected_create_time)) < 0.01)
        except Exception:
            return False

    @staticmethod
    def _spawn(command: str, cwd: str, log_path: str) -> subprocess.Popen:
        log = open(log_path, "a", encoding="utf-8")
        kwargs = dict(
            cwd=cwd, shell=True, stdout=log, stderr=subprocess.STDOUT,
            text=True, env=os.environ.copy(),
        )
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            return subprocess.Popen(command, **kwargs)
        finally:
            log.close()

    def start(self, command: str, cwd: str, name: str | None = None,
              project: str | None = None, auto_restart: bool = False,
              max_restarts: int = 3, health_url: str | None = None) -> dict:
        key = uuid.uuid4().hex[:10]
        log_dir = data_dir() / "logs"; log_dir.mkdir(parents=True, exist_ok=True)
        log_path = str(log_dir / f"process-{key}.log")
        proc = self._spawn(command, cwd, log_path)
        now = time.time()
        try:
            pid_create_time = float(psutil.Process(proc.pid).create_time())
        except Exception:
            pid_create_time = None
        meta = {
            "name": name or project or command[:80],
            "project": project,
            "command": command,
            "cwd": cwd,
            "log": log_path,
            "pid": proc.pid,
            "pid_create_time": pid_create_time,
            "created_at": now,
            "last_started_at": now,
            "stopped_at": None,
            "desired_state": "running",
            "auto_restart": bool(auto_restart),
            "max_restarts": max(0, min(int(max_restarts), 20)),
            "restart_count": 0,
            "health_url": health_url,
        }
        data = self._load(); data[key] = meta; self._save(data)
        return {"ok": True, "id": key, **meta, "running": True}

    def list(self) -> list[dict]:
        data = self._load(); out = []; changed = False
        for key, meta in data.items():
            pid = int(meta.get("pid", -1)); running = self._process_matches(pid, meta.get("pid_create_time"))
            if not running and meta.get("desired_state") == "running" and meta.get("last_exit_observed_at") is None:
                meta["last_exit_observed_at"] = time.time(); changed = True
            out.append({**meta, "id": key, "running": running})
        if changed: self._save(data)
        return out

    def get(self, key: str) -> dict | None:
        meta = self._load().get(key)
        if not meta: return None
        return {**meta, "id": key, "running": self._process_matches(int(meta.get("pid", -1)), meta.get("pid_create_time")), "pid_identity_verified": meta.get("pid_create_time") is not None}

    def stop(self, key: str) -> dict:
        data = self._load(); meta = data.get(key)
        if not meta: return {"ok": False, "error": "Unknown process id"}
        pid = int(meta.get("pid", -1))
        meta["desired_state"] = "stopped"
        if not self._process_matches(pid, meta.get("pid_create_time")):
            self._save(data)
            return {"ok": False, "blocked": True, "error": "Stored PID no longer matches the process identity that Living Assistant started; refusing to terminate it."}
        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            for child in children:
                try: child.terminate()
                except Exception: pass
            proc.terminate()
            _, alive = psutil.wait_procs([proc, *children], timeout=8)
            for remaining in alive:
                try: remaining.kill()
                except Exception: pass
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self._save(data)
            return {"ok": False, "error": str(e)}
        meta["stopped_at"] = time.time(); self._save(data)
        return {"ok": True, "pid": pid}

    def restart(self, key: str, automatic: bool = False) -> dict:
        data = self._load(); meta = data.get(key)
        if not meta: return {"ok": False, "error": "Unknown process id"}
        if automatic:
            if not meta.get("auto_restart") or meta.get("desired_state") != "running":
                return {"ok": False, "error": "Automatic restart is not enabled for this process."}
            if int(meta.get("restart_count", 0)) >= int(meta.get("max_restarts", 3)):
                return {"ok": False, "error": "Maximum automatic restart count reached."}
        else:
            meta["desired_state"] = "running"
        if self._process_matches(int(meta.get("pid", -1)), meta.get("pid_create_time")):
            return {"ok": True, "already_running": True, "id": key, "pid": meta["pid"]}
        try:
            proc = self._spawn(meta["command"], meta["cwd"], meta["log"])
        except Exception as e:
            return {"ok": False, "error": str(e)}
        meta["pid"] = proc.pid
        try:
            meta["pid_create_time"] = float(psutil.Process(proc.pid).create_time())
        except Exception:
            meta["pid_create_time"] = None
        meta["last_started_at"] = time.time()
        meta["stopped_at"] = None
        meta["last_exit_observed_at"] = None
        if automatic:
            meta["restart_count"] = int(meta.get("restart_count", 0)) + 1
        data[key] = meta; self._save(data)
        return {"ok": True, "id": key, "pid": proc.pid, "automatic": automatic, "restart_count": meta.get("restart_count", 0)}

    def tail(self, key: str, lines: int = 100) -> dict:
        item = self.get(key)
        if not item: return {"ok": False, "error": "Unknown process id"}
        p = Path(item["log"])
        if not p.exists(): return {"ok": False, "error": "Log file does not exist yet."}
        try:
            content = p.read_text(encoding="utf-8", errors="replace").splitlines()
            return {"ok": True, "id": key, "log": str(p), "lines": [redact_secrets(x, 4000) for x in content[-max(1, min(lines, 1000)):]]}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def build_shell_tools(workspace: Workspace, approval: ApprovalManager, config: dict, registry: ProcessRegistry) -> list[Tool]:
    timeout = int(config.get("policy", {}).get("command_timeout_seconds", 120))
    require = bool(config.get("policy", {}).get("require_execute_approval", True))

    def run_command(command: str, cwd: str = ".", timeout_seconds: int | None = None):
        cwdp = workspace.resolve(cwd)
        decision = classify_command(command, require)
        if not decision.allowed:
            return {"ok": False, "blocked": True, "reason": decision.reason, "risk": decision.risk.value}
        if decision.requires_approval:
            req = approval.request(command, decision.reason, decision.risk.value)
            if not req.get("allowed"):
                return {"ok": False, "approval_required": True, **req, "risk": decision.risk.value}
        try:
            p = subprocess.run(
                command, cwd=str(cwdp), shell=True, text=True, capture_output=True,
                timeout=min(timeout_seconds or timeout, 600), env=os.environ.copy()
            )
            return {"ok": p.returncode == 0, "returncode": p.returncode, "stdout": redact_secrets(p.stdout[-20000:]), "stderr": redact_secrets(p.stderr[-20000:])}
        except subprocess.TimeoutExpired as e:
            return {"ok": False, "timeout": True, "stdout": redact_secrets((e.stdout or "")[-10000:]), "stderr": redact_secrets((e.stderr or "")[-10000:])}

    def start_process(command: str, cwd: str = ".", name: str | None = None, project: str | None = None,
                      auto_restart: bool = False, max_restarts: int = 3, health_url: str | None = None):
        cwdp = workspace.resolve(cwd)
        if health_url and not is_loopback_http_url(health_url):
            return {"ok": False, "blocked": True, "error": "Managed-process health checks are restricted to loopback http/https URLs."}
        decision = classify_command(command, True)
        if not decision.allowed:
            return {"ok": False, "blocked": True, "reason": decision.reason}
        req = approval.request(command, "Starting a long-running local project/process.", "EXECUTE")
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}
        return registry.start(command, str(cwdp), name, project, auto_restart, max_restarts, health_url)

    def list_processes(): return registry.list()
    def stop_process(process_id: str): return registry.stop(process_id)
    def tail_process_log(process_id: str, lines: int = 100): return registry.tail(process_id, lines)

    def restart_process(process_id: str):
        item = registry.get(process_id)
        if not item: return {"ok": False, "error": "Unknown process id"}
        req = approval.request(item["command"], "Restarting a previously managed process.", "EXECUTE")
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req}
        return registry.restart(process_id, automatic=False)

    return [
        Tool("run_command", "Run a bounded shell command inside the approved workspace. Policy may block or require approval.",
             {"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string","default":"."},"timeout_seconds":{"type":"integer"}},"required":["command"]}, run_command),
        Tool("start_process", "Start and supervise a long-running local process. When starting a registered project, copy its auto_restart/max_restarts/health_url settings.",
             {"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string","default":"."},"name":{"type":"string"},"project":{"type":"string"},"auto_restart":{"type":"boolean","default":False},"max_restarts":{"type":"integer","default":3},"health_url":{"type":"string"}},"required":["command"]}, start_process),
        Tool("list_managed_processes", "List persistent project/process records and whether each PID is currently running.", {"type":"object","properties":{}}, list_processes),
        Tool("stop_managed_process", "Stop a process previously started by this assistant and disable auto-restart until manually started again.",
             {"type":"object","properties":{"process_id":{"type":"string"}},"required":["process_id"]}, stop_process),
        Tool("restart_managed_process", "Restart a previously managed process using the same approved command and working directory. Requires approval.",
             {"type":"object","properties":{"process_id":{"type":"string"}},"required":["process_id"]}, restart_process),
        Tool("tail_process_log", "Read the last lines from a managed process log.",
             {"type":"object","properties":{"process_id":{"type":"string"},"lines":{"type":"integer","default":100}},"required":["process_id"]}, tail_process_log),
    ]
