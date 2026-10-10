"""A llama.cpp server for one vision model, separate from the chat model's server.

Same launch recipe as the chat server (system/llama_server.py): find the binary,
pick CPU or a discrete GPU with enough free memory, run with the model's own chat
template. A vision model running *alongside* the chat model gets half the CPU cores
so both stay responsive.
"""
from __future__ import annotations

import base64
import io
import os
import subprocess
import threading
import time
from pathlib import Path

import httpx
import psutil

from living_assistant.system.llama_server import choose_device, find_llama_server, parse_devices

from .models import VisionModel


class VisionServer:
    def __init__(self, model: VisionModel, port: int, log_dir: Path, binary: str | None = None, threads: int | None = None):
        self.model = model
        self.port = int(port)
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.log_path = Path(log_dir) / f"vision-{model.name}.log"
        self.binary = binary
        self.threads = threads
        self.proc: subprocess.Popen | None = None
        self.mode = "stopped"
        self.last_used = 0.0
        self._lock = threading.RLock()

    # -- lifecycle ------------------------------------------------------------------

    def healthy(self, timeout: float = 2.0) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=timeout, trust_env=False)
            return r.status_code == 200
        except Exception:
            return False

    def argv(self, exe: Path) -> tuple[list[str], str]:
        cores = psutil.cpu_count(logical=False) or os.cpu_count() or 4
        threads = self.threads or (max(2, cores // 2) if self.model.mode == "alongside" else cores)
        argv = [str(exe), "-m", str(self.model.model_path), "--mmproj", str(self.model.mmproj_path),
                "--host", "127.0.0.1", "--port", str(self.port), "-c", str(self.model.context),
                "-np", "1", "-t", str(threads), "-fa", "auto", "--no-webui"] + (["--jinja"] if self.model.jinja else [])
        device = None
        if self.model.device != "cpu":
            try:
                out = subprocess.run([str(exe), "--list-devices"], capture_output=True, text=True, timeout=30,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                need_mb = int((self.model.model_path.stat().st_size + self.model.mmproj_path.stat().st_size) / 2**20 * 1.25)
                device, _ = choose_device(parse_devices(out.stdout + out.stderr), "auto" if self.model.device == "auto" else self.model.device,
                                          min_free_mb=need_mb)
            except (OSError, subprocess.TimeoutExpired):
                device = None
        if device is not None:
            argv += ["-dev", device.id, "-ngl", "99"]
            mode = f"gpu:{device.id}"
        else:
            argv += ["-dev", "none", "-ngl", "0"]
            mode = "cpu"
        return argv + list(self.model.extra_args), mode

    def start(self, timeout: float = 240.0) -> dict:
        with self._lock:
            if self.proc is not None and self.proc.poll() is None and self.healthy():
                return self.status()
            exe = find_llama_server(self.binary)
            if exe is None:
                raise RuntimeError("llama-server was not found; install llama.cpp to use local vision models.")
            if not self.model.downloaded():
                raise RuntimeError(f"Vision model {self.model.name} is not downloaded yet.")
            argv, mode = self.argv(exe)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "ab") as log:
                log.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(argv)}\n".encode())
                log.flush()
                self.proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    break
                if self.healthy():
                    self.mode = mode
                    self.last_used = time.monotonic()
                    return self.status()
                time.sleep(1.0)
            tail = self.log_tail()
            self.stop()
            raise RuntimeError(f"Vision model {self.model.name} did not start. Log tail:\n{tail}")

    def stop(self) -> None:
        with self._lock:
            proc, self.proc = self.proc, None
            self.mode = "stopped"
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def status(self) -> dict:
        rss = None
        if self.proc is not None and self.proc.poll() is None:
            try:
                rss = psutil.Process(self.proc.pid).memory_info().rss
            except psutil.Error:
                pass
        return {"model": self.model.name, "mode": self.mode, "pid": self.proc.pid if self.proc else None,
                "rss_mb": round(rss / 2**20) if rss else None, "base_url": self.base_url}

    def log_tail(self, lines: int = 15) -> str:
        try:
            return "\n".join(self.log_path.read_bytes()[-6000:].decode("utf-8", "replace").splitlines()[-lines:])
        except OSError:
            return ""

    # -- inference ---------------------------------------------------------------------

    def ask(self, image: bytes, question: str, max_tokens: int = 512, mime: str = "image/png",
            system: str | None = None, timeout: float = 600.0) -> dict:
        """One image + question -> answer text with timing."""
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": question}]}]
        started = time.perf_counter()
        r = httpx.post(f"{self.base_url}/v1/chat/completions", timeout=timeout, trust_env=False,
                       json={"model": self.model.name, "messages": messages, "temperature": 0, "max_tokens": max_tokens})
        r.raise_for_status()
        data = r.json()
        self.last_used = time.monotonic()
        return {"text": data["choices"][0]["message"].get("content") or "", "seconds": round(time.perf_counter() - started, 2),
                "timings": data.get("timings") or {}, "model": self.model.name}


def downscale(image: bytes, max_side: int = 1280) -> tuple[bytes, str]:
    """Large screenshots cost minutes of image encoding on a CPU; shrink them, keep them readable."""
    from PIL import Image

    img = Image.open(io.BytesIO(image))
    img = img.convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), "image/png"
