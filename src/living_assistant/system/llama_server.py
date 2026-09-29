"""Launch and supervise the local llama.cpp server that backs Collibri/LiteLLM.

The server is the slowest part of every assistant step, so how it is started
matters: a discrete GPU (even a small one) takes attention layers and the KV
cache, llama.cpp's own ``--fit`` sizes the offload to the card's free memory,
and Mixture-of-Experts weights that do not fit stay in system RAM. Machines
without a usable GPU get a CPU-tuned launch, and any failed GPU launch falls
back to CPU so the assistant keeps working.
"""
from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psutil

logger = logging.getLogger(__name__)

_DEVICE_RE = re.compile(r"^\s*(?P<id>[A-Za-z]+\d+):\s*(?P<name>.+?)\s*\((?P<total>\d+)\s*MiB,\s*(?P<free>\d+)\s*MiB free\)")
# Integrated GPUs share system RAM; offloading to them is usually no faster than the CPU.
_INTEGRATED_RE = re.compile(
    r"(?i)(radeon\(tm\)\s*graphics|radeon\s+graphics|vega\s*\d*\s*graphics|uhd graphics|iris|intel\(r\)\s*(hd\s*)?graphics|intel\(r\)\s*arc\(tm\)\s*graphics|adreno|mali|llvmpipe|microsoft basic)"
)


@dataclass
class GpuDevice:
    id: str
    name: str
    total_mb: int
    free_mb: int

    @property
    def integrated(self) -> bool:
        return bool(_INTEGRATED_RE.search(self.name))


@dataclass
class LaunchPlan:
    mode: str  # "gpu" | "cpu"
    argv: list[str]
    device: GpuDevice | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)

    def public(self) -> dict:
        return {
            "mode": self.mode,
            "device": None if self.device is None else {"id": self.device.id, "name": self.device.name, "free_mb": self.device.free_mb},
            "reason": self.reason,
            "notes": self.notes,
            "argv": self.argv,
        }


_GGUF_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


def gguf_expert_count(path: Path) -> int:
    """Read `<arch>.expert_count` from a GGUF header (0 = dense model or unreadable)."""
    import struct

    def read(fh, fmt):
        size = struct.calcsize(fmt)
        data = fh.read(size)
        if len(data) != size:
            raise EOFError
        return struct.unpack(fmt, data)[0]

    def read_str(fh):
        return fh.read(read(fh, "<Q")).decode("utf-8", "replace")

    def skip_value(fh, vtype):
        if vtype in _GGUF_SCALARS:
            fh.seek(struct.calcsize(_GGUF_SCALARS[vtype]), 1)
        elif vtype == 8:
            fh.seek(read(fh, "<Q"), 1)
        elif vtype == 9:
            itype, count = read(fh, "<I"), read(fh, "<Q")
            for _ in range(count):
                skip_value(fh, itype)
        else:
            raise ValueError(f"unknown GGUF type {vtype}")

    try:
        with open(path, "rb") as fh:
            if fh.read(4) != b"GGUF":
                return 0
            read(fh, "<I")
            read(fh, "<Q")
            for _ in range(read(fh, "<Q")):
                key, vtype = read_str(fh), read(fh, "<I")
                if key.startswith("tokenizer."):
                    return 0  # architecture keys precede the (huge) tokenizer tables
                if key.endswith(".expert_count") and vtype in _GGUF_SCALARS:
                    return int(read(fh, _GGUF_SCALARS[vtype]))
                skip_value(fh, vtype)
    except (OSError, EOFError, ValueError):
        return 0
    return 0


def find_llama_server(configured: str | None = None) -> Path | None:
    candidates: list[str] = []
    if configured:
        candidates.append(os.path.expandvars(os.path.expanduser(configured)))
    found = shutil.which("llama-server")
    if found:
        candidates.append(found)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "ggml.llamacpp*", "llama-server.exe")))
    for cand in candidates:
        p = Path(cand)
        if p.is_file():
            return p
    return None


def parse_devices(text: str) -> list[GpuDevice]:
    devices = []
    for line in text.splitlines():
        m = _DEVICE_RE.match(line)
        if m:
            devices.append(GpuDevice(m["id"], m["name"].strip(), int(m["total"]), int(m["free"])))
    return devices


def choose_device(devices: list[GpuDevice], preference: str = "auto", min_free_mb: int = 1500) -> tuple[GpuDevice | None, str]:
    pref = (preference or "auto").strip()
    if pref.lower() in {"cpu", "none", "off", "false"}:
        return None, "GPU disabled by configuration."
    if pref.lower() not in {"auto", ""}:
        for dev in devices:
            if dev.id.lower() == pref.lower() or pref.lower() in dev.name.lower():
                return dev, f"Configured device {dev.id} ({dev.name})."
        return None, f"Configured GPU '{pref}' was not found; using CPU."
    discrete = [d for d in devices if not d.integrated and d.free_mb >= min_free_mb]
    if not discrete:
        if devices:
            return None, "Only integrated or near-full GPUs found; CPU is faster for this model."
        return None, "No GPU detected; using CPU."
    best = max(discrete, key=lambda d: d.free_mb)
    return best, f"Discrete GPU {best.id} ({best.name}, {best.free_mb} MiB free)."


class LlamaServerManager:
    def __init__(self, config: dict, log_dir: Path) -> None:
        self.cfg = dict(config or {})
        self.base_url = str(self.cfg.get("base_url") or "http://127.0.0.1:8080").rstrip("/")
        parsed = urlparse(self.base_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 8080
        self.log_path = Path(log_dir) / "llama-server.log"
        self.proc: subprocess.Popen | None = None
        self.plan: LaunchPlan | None = None
        self.last_error: str | None = None
        self.external = False
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._watchdog: threading.Thread | None = None

    # -- discovery ---------------------------------------------------------------

    @property
    def local(self) -> bool:
        return self.host in {"127.0.0.1", "localhost", "::1"}

    def binary(self) -> Path | None:
        return find_llama_server(self.cfg.get("binary"))

    def model_path(self) -> Path | None:
        raw = self.cfg.get("model_path")
        if not raw:
            return None
        p = Path(os.path.expandvars(os.path.expanduser(str(raw))))
        return p if p.is_file() else None

    def devices(self) -> list[GpuDevice]:
        exe = self.binary()
        if exe is None:
            return []
        try:
            out = subprocess.run([str(exe), "--list-devices"], capture_output=True, text=True, timeout=30,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            return []
        return parse_devices(out.stdout + "\n" + out.stderr)

    def healthy(self, timeout: float = 2.0) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=timeout, trust_env=False)
            return r.status_code == 200 and "ok" in r.text
        except Exception:
            return False

    # -- planning -----------------------------------------------------------------

    def build_plan(self, force_cpu: bool = False) -> LaunchPlan:
        exe = self.binary()
        model = self.model_path()
        if exe is None:
            raise RuntimeError("llama-server was not found. Install llama.cpp (e.g. winget install ggml.llamacpp) or set llamacpp.binary.")
        if model is None:
            raise RuntimeError("llamacpp.model_path is not set or the GGUF file does not exist.")
        threads = int(self.cfg.get("threads") or psutil.cpu_count(logical=False) or os.cpu_count() or 4)
        argv = [
            str(exe), "-m", str(model),
            "--host", self.host, "--port", str(self.port),
            "-c", str(int(self.cfg.get("context_tokens", 16384))),
            # One slot: a single user's consecutive steps always hit the same prompt cache.
            "-np", "1",
            "--cache-reuse", str(int(self.cfg.get("cache_reuse", 256))),
            "-t", str(threads),
            # Large batches let MoE experts process many prompt tokens per pass
            # (measured on a Ryzen 5600H: 43 -> 103 tok/s CPU, 166 tok/s with a 4 GB GPU).
            "-b", str(int(self.cfg.get("batch_size", 2048))),
            "-ub", str(int(self.cfg.get("ubatch_size", 2048))),
            "-fa", "auto",
            "--jinja",
        ]
        device, reason = (None, "CPU fallback after a failed GPU launch.") if force_cpu else choose_device(
            self.devices(), str(self.cfg.get("gpu", "auto")), int(self.cfg.get("min_gpu_free_mb", 1500))
        )
        notes = []
        if device is not None:
            argv += ["-dev", device.id]
            experts = gguf_expert_count(model)
            if experts:
                # Attention + KV cache on the GPU, expert weights in RAM: fits small cards and
                # beat partial expert offload in benchmarks.
                argv += ["-ngl", "99", "--cpu-moe"]
                notes.append(f"MoE model ({experts} experts): experts stay in system RAM.")
            else:
                argv += ["--fit", "on"]  # llama.cpp sizes GPU layers/context to free VRAM
            mode = "gpu"
        else:
            argv += ["-dev", "none", "-ngl", "0"]
            mode = "cpu"
        argv += [str(x) for x in (self.cfg.get("extra_args") or [])]
        return LaunchPlan(mode=mode, argv=argv, device=device, reason=reason, notes=notes)

    # -- lifecycle ------------------------------------------------------------------

    def _spawn(self, plan: LaunchPlan) -> subprocess.Popen:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(self.log_path, "ab")
        log.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} launching ({plan.mode}): {' '.join(plan.argv)}\n".encode())
        log.flush()
        try:
            return subprocess.Popen(
                plan.argv, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        finally:
            log.close()

    def _wait_ready(self, proc: subprocess.Popen, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return False
            if self.healthy(timeout=2.0):
                return True
            time.sleep(1.0)
        return False

    def _log_tail(self, lines: int = 12) -> str:
        try:
            data = self.log_path.read_bytes()[-8000:].decode("utf-8", "replace").splitlines()
            return "\n".join(data[-lines:])
        except OSError:
            return ""

    def ensure_running(self, timeout: float | None = None) -> dict:
        """Start the server if nothing is serving the configured port. Never touches a server it did not start."""
        with self._lock:
            if self.healthy():
                if self.proc is None or self.proc.poll() is not None:
                    self.external = True
                return self.status()
            if not self.local:
                self.last_error = f"Model server {self.base_url} is remote and not reachable."
                return self.status()
            timeout = float(timeout or self.cfg.get("startup_timeout_seconds", 600))
            attempts = [False, True]
            for force_cpu in attempts:
                try:
                    plan = self.build_plan(force_cpu=force_cpu)
                except RuntimeError as exc:
                    self.last_error = str(exc)
                    return self.status()
                logger.info("[llama-server] launching in %s mode: %s", plan.mode, plan.reason)
                proc = self._spawn(plan)
                if self._wait_ready(proc, timeout):
                    self.proc, self.plan, self.external, self.last_error = proc, plan, False, None
                    return self.status()
                self._kill(proc)
                self.last_error = f"{plan.mode.upper()} launch failed: {self._log_tail(6)}"
                logger.warning("[llama-server] %s", self.last_error)
                if plan.mode == "cpu":
                    break
            return self.status()

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self.proc is not None:
                self._kill(self.proc)
                self.proc = None

    def restart(self) -> dict:
        self.stop()
        if self._watchdog is not None:
            self._watchdog.join(timeout=5)
        self._stop.clear()
        status = self.ensure_running()
        self.start_watchdog()
        return status

    def start_watchdog(self, interval: float = 15.0) -> None:
        """Bring the server back if the process we launched dies."""
        if self._watchdog and self._watchdog.is_alive():
            return

        def loop():
            backoff_until = 0.0
            while not self._stop.wait(interval):
                owned_dead = self.proc is not None and self.proc.poll() is not None
                missing = self.proc is None and not self.external and not self.healthy()
                if (owned_dead or missing) and time.monotonic() >= backoff_until:
                    logger.warning("[llama-server] not running; restarting")
                    self.proc = None
                    if not self.ensure_running().get("running"):
                        backoff_until = time.monotonic() + 300  # failing launches reload GBs; don't thrash

        self._watchdog = threading.Thread(target=loop, name="llama-server-watchdog", daemon=True)
        self._watchdog.start()

    def status(self) -> dict:
        running = self.healthy()
        return {
            "base_url": self.base_url,
            "running": running,
            "managed": self.proc is not None and self.proc.poll() is None,
            "external": self.external and running,
            "plan": self.plan.public() if self.plan else None,
            "last_error": self.last_error,
            "log": str(self.log_path),
        }
