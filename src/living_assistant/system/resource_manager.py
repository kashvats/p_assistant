from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import shutil
import subprocess
import time
import psutil
from living_assistant.system.hardware import HardwareInfo, detect_hardware

GIB = 1024 ** 3


class GPUVendorInterface:
    """Pluggable vendor backend for GPU VRAM and temperature metrics."""

    def query_runtime(self) -> tuple[float | None, float | None]:
        """Returns (free_vram_gb, temperature_c)."""
        raise NotImplementedError


class NvidiaSmiBackend(GPUVendorInterface):
    """NVIDIA GPU backend querying nvidia-smi."""

    def __init__(self, fallback_free_gb: float | None = None) -> None:
        self.fallback_free_gb = fallback_free_gb

    def query_runtime(self) -> tuple[float | None, float | None]:
        if not shutil.which("nvidia-smi"):
            return self.fallback_free_gb, None
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.free,temperature.gpu", "--format=csv,noheader,nounits"],
                text=True,
                timeout=3,
                stderr=subprocess.DEVNULL,
            ).strip().splitlines()
            rows = []
            for line in out:
                free, temp = [x.strip() for x in line.rsplit(",", 1)]
                rows.append((float(free) / 1024, float(temp)))
            if not rows:
                return self.fallback_free_gb, None
            free, temp = max(rows, key=lambda row: row[0])
            return round(free, 2), round(temp, 1)
        except Exception:
            return self.fallback_free_gb, None


class AppleMlxBackend(GPUVendorInterface):
    """Apple Silicon unified memory interface."""

    def __init__(self, unified_ram_gb: float | None = None) -> None:
        self.unified_ram_gb = unified_ram_gb

    def query_runtime(self) -> tuple[float | None, float | None]:
        try:
            vm = psutil.virtual_memory()
            free_gb = round(vm.available / GIB, 2)
            return free_gb, None
        except Exception:
            return self.unified_ram_gb, None


class FallbackGPUBackend(GPUVendorInterface):
    """Fallback backend for CPU or unsupported GPUs."""

    def __init__(self, static_free_gb: float | None = None) -> None:
        self.static_free_gb = static_free_gb

    def query_runtime(self) -> tuple[float | None, float | None]:
        return self.static_free_gb, None


@dataclass(frozen=True)
class ModelRuntimePolicy:
    mode: str
    max_resident_models: int
    max_concurrent_generations: int
    max_parallel_per_model: int
    resident_keep_alive_seconds: int
    admission_timeout_seconds: float
    reserve_ram_gb: float
    reserve_vram_gb: float
    reason: str
    recommended_context_tokens: int = 4096

    def to_dict(self) -> dict:
        return asdict(self)


class ResourceManager:
    def __init__(self, profile: str, config: dict, hardware: HardwareInfo | None = None):
        self.profile = profile
        self.config = config
        self.hardware = hardware or detect_hardware()
        self.gpu_backend = self._init_gpu_backend()
        self._interactive_modes: set[str] = set()
        self._is_throttled: bool = False
        self._throttle_state_changed_at: float = 0.0
        self._throttle_hysteresis_seconds: float = float(
            (config.get("resource_limits", {}) or {}).get("throttle_hysteresis_seconds", 5.0)
        )
        self.model_policy = self._select_model_policy()

    def _init_gpu_backend(self) -> GPUVendorInterface:
        if self.hardware.apple_silicon or self.hardware.unified_memory:
            return AppleMlxBackend(self.hardware.gpu_vram_free_gb)
        if shutil.which("nvidia-smi"):
            return NvidiaSmiBackend(self.hardware.gpu_vram_free_gb)
        return FallbackGPUBackend(self.hardware.gpu_vram_free_gb)

    def _nvidia_runtime(self) -> tuple[float | None, float | None]:
        return self.gpu_backend.query_runtime()

    def _cpu_temperature_c(self) -> float | None:
        try:
            groups = psutil.sensors_temperatures(fahrenheit=False) or {}
        except Exception:
            return None
        values = []
        for entries in groups.values():
            for item in entries or []:
                current = getattr(item, 'current', None)
                if current is not None and 0 < float(current) < 150:
                    values.append(float(current))
        return round(max(values), 1) if values else None

    # ------------------------------------------------------------------
    # Process & System Telemetry (psutil)
    # ------------------------------------------------------------------

    def process_resource_snapshot(self, pid: int | None = None) -> dict[str, Any]:
        """Deep process metrics: memory RSS/VMS, CPU %, open files, thread count."""
        try:
            proc = psutil.Process(pid) if pid else psutil.Process()
            mem = proc.memory_info()
            num_files = 0
            try:
                num_files = len(proc.open_files())
            except Exception:
                pass
            return {
                "ok": True,
                "pid": proc.pid,
                "name": proc.name(),
                "status": proc.status(),
                "rss_mb": round(mem.rss / (1024 * 1024), 2),
                "vms_mb": round(mem.vms / (1024 * 1024), 2),
                "cpu_percent": proc.cpu_percent(interval=None),
                "threads": proc.num_threads(),
                "open_files": num_files,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def system_load_snapshot(self) -> dict[str, Any]:
        """System load metrics across CPU, RAM, and load averages."""
        vm = psutil.virtual_memory()
        load_1, load_5, load_15 = (None, None, None)
        if hasattr(psutil, "getloadavg"):
            try:
                load_1, load_5, load_15 = psutil.getloadavg()
            except Exception:
                pass
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.05),
            "ram_percent": vm.percent,
            "available_ram_gb": round(vm.available / GIB, 2),
            "total_ram_gb": round(vm.total / GIB, 2),
            "load_average": [load_1, load_5, load_15] if load_1 is not None else None,
        }

    # ------------------------------------------------------------------
    # Dynamic Job Scheduling & Throttling
    # ------------------------------------------------------------------

    def set_interactive_mode(self, active: bool, source: str = "chat") -> None:
        """Register that a foreground user activity (voice, chat) is active."""
        if active:
            self._interactive_modes.add(source)
        else:
            self._interactive_modes.discard(source)
            if not self._interactive_modes:
                self._is_throttled = False

    def is_interactive_active(self) -> bool:
        """True if user is actively engaged in voice, chat, or interactive sessions."""
        return len(self._interactive_modes) > 0

    def should_throttle_background_tasks(
        self,
        active_interactive: bool | None = None,
        max_cpu_percent: float = 85.0,
        min_available_ram_gb: float = 1.0,
    ) -> tuple[bool, str]:
        """Evaluate whether heavy background indexing or tasks must pause with hysteresis."""
        is_interactive = (
            self.is_interactive_active() if active_interactive is None else active_interactive
        )
        if is_interactive:
            return True, f"interactive foreground session active ({','.join(self._interactive_modes) or 'user'})"

        s = self.snapshot()
        cpu = s.get("cpu_percent", 0.0)
        avail_ram = s.get("available_ram_gb", 0.0)
        hot, heat_reason = self.thermal_pressure()
        now = time.monotonic()

        high_load = (cpu >= max_cpu_percent) or (avail_ram < min_available_ram_gb) or hot

        if not self._is_throttled:
            if high_load:
                self._is_throttled = True
                self._throttle_state_changed_at = now
                if cpu >= max_cpu_percent:
                    return True, f"high system CPU usage ({cpu}% >= {max_cpu_percent}%)"
                if avail_ram < min_available_ram_gb:
                    return True, f"low available RAM ({avail_ram} GB < {min_available_ram_gb} GB)"
                return True, f"thermal throttle active ({heat_reason})"
            return False, "ok"
        else:
            # We are currently in a throttled state.
            # Require minimum duration before unthrottling to prevent flapping/churn (hysteresis window)
            time_in_throttle = now - self._throttle_state_changed_at
            if time_in_throttle < self._throttle_hysteresis_seconds:
                return True, f"throttle active (hysteresis hold: {time_in_throttle:.1f}s / {self._throttle_hysteresis_seconds:.1f}s)"

            # To exit throttle state, metrics must be well below thresholds (hysteresis band)
            unthrottle_cpu_threshold = max_cpu_percent - 15.0  # e.g. 70% if max is 85%
            unthrottle_ram_threshold = min_available_ram_gb + 0.5  # e.g. 1.5GB if min is 1.0GB

            if cpu <= unthrottle_cpu_threshold and avail_ram >= unthrottle_ram_threshold and not hot:
                self._is_throttled = False
                self._throttle_state_changed_at = now
                return False, "ok"

            return True, f"throttle sustained (cooling down: cpu={cpu}%, ram={avail_ram}GB)"

    def disk_pressure(
        self,
        path: str | Path | None = None,
        min_free_gb: float = 0.5,
    ) -> tuple[bool, str, float]:
        """Check for disk exhaustion on the workspace or system drive."""
        try:
            target = Path(path).resolve() if path else Path.cwd().resolve()
            usage = shutil.disk_usage(target)
            free_gb = round(usage.free / GIB, 2)
            if free_gb < min_free_gb:
                return (
                    True,
                    f"Critical disk pressure: only {free_gb} GB free on {target.anchor} (< {min_free_gb} GB minimum)",
                    free_gb,
                )
            return False, "ok", free_gb
        except Exception as exc:
            return False, f"Disk check bypassed: {exc}", 999.0

    def snapshot(self) -> dict:
        vm = psutil.virtual_memory()
        result = {
            "cpu_percent": psutil.cpu_percent(interval=0.05),
            "ram_percent": vm.percent,
            "available_ram_gb": round(vm.available / GIB, 2),
            "interactive_active": self.is_interactive_active(),
            "throttled": self._is_throttled,
        }
        _disk_pressure, _msg, free_gb = self.disk_pressure()
        result["disk_free_gb"] = free_gb
        gpu_free, gpu_temp = self._nvidia_runtime()
        if gpu_free is not None:
            result["gpu_free_vram_gb"] = gpu_free
        if gpu_temp is not None:
            result["gpu_temperature_c"] = gpu_temp
        cpu_temp = self._cpu_temperature_c()
        if cpu_temp is not None:
            result["cpu_temperature_c"] = cpu_temp
        return result

    def thermal_pressure(self) -> tuple[bool, str]:
        cfg = self.config.get("model_runtime", {}) or {}
        if not bool(cfg.get("thermal_guard_enabled", True)):
            return False, "thermal guard disabled"
        s = self.snapshot()
        max_gpu = float(cfg.get("max_gpu_temperature_c", 83))
        max_cpu = float(cfg.get("max_cpu_temperature_c", 90))
        gt = s.get("gpu_temperature_c")
        ct = s.get("cpu_temperature_c")
        if gt is not None and gt >= max_gpu:
            return True, f"GPU temperature {gt}C >= {max_gpu:g}C threshold"
        if ct is not None and ct >= max_cpu:
            return True, f"CPU temperature {ct}C >= {max_cpu:g}C threshold"
        return False, "ok"

    def _select_model_policy(self) -> ModelRuntimePolicy:
        cfg = self.config.get("model_runtime", {}) or {}
        mode = str(cfg.get("mode", "auto")).lower()
        if mode not in {"auto", "single", "multi"}:
            mode = "auto"

        reserve_ram = float((cfg.get("reserve_ram_gb_by_profile", {}) or {}).get(
            self.profile, {"lite": 1.0, "balanced": 3.0, "power": 6.0}.get(self.profile, 3.0)
        ))
        reserve_vram = float(cfg.get("reserve_vram_gb", 1.0))
        keep_alive = max(0, int(cfg.get("resident_keep_alive_seconds", 300)))
        timeout = max(1.0, float(cfg.get("admission_timeout_seconds", 120)))
        per_model = max(1, int(cfg.get("max_parallel_per_model", 1)))

        # Lite is deliberately single-model even if the user asks for auto; it is
        # the safety profile for 8 GB-class machines.
        if mode == "single" or self.profile == "lite":
            max_resident, reason = 1, "single-model mode" if mode == "single" else "lite profile"
        else:
            hw = self.hardware
            if hw.apple_silicon:
                two = float(cfg.get("apple_unified_memory_gb_for_two", 32))
                three = float(cfg.get("apple_unified_memory_gb_for_three", 64))
                if hw.ram_gb >= three:
                    max_resident, reason = 3, f"Apple unified memory >= {three:g} GB"
                elif hw.ram_gb >= two:
                    max_resident, reason = 2, f"Apple unified memory >= {two:g} GB"
                else:
                    max_resident, reason = 1, "Apple unified memory below multi-model threshold"
            elif hw.gpu_vram_gb is not None:
                two = float(cfg.get("dedicated_vram_gb_for_two", 16))
                three = float(cfg.get("dedicated_vram_gb_for_three", 24))
                if hw.gpu_vram_gb >= three:
                    max_resident, reason = 3, f"dedicated VRAM >= {three:g} GB"
                elif hw.gpu_vram_gb >= two:
                    max_resident, reason = 2, f"dedicated VRAM >= {two:g} GB"
                else:
                    max_resident, reason = 1, "dedicated VRAM below multi-model threshold"
            else:
                two = float(cfg.get("cpu_ram_gb_for_two", 48))
                three = float(cfg.get("cpu_ram_gb_for_three", 96))
                if hw.ram_gb >= three:
                    max_resident, reason = 3, f"CPU/system RAM >= {three:g} GB"
                elif hw.ram_gb >= two:
                    max_resident, reason = 2, f"CPU/system RAM >= {two:g} GB"
                else:
                    max_resident, reason = 1, "system RAM below CPU multi-model threshold"

            if mode == "multi" and max_resident == 1:
                # Explicit multi requests are still bounded by a minimal memory gate.
                # Never force concurrency on hardware that cannot safely support it.
                reason = "multi requested but hardware safety gate kept one resident model"

        explicit_resident = int(cfg.get("max_resident_models", 0) or 0)
        if explicit_resident > 0:
            # An override may reduce the automatically selected count. Increasing
            # beyond the hardware-derived ceiling requires force_max_resident=true.
            if explicit_resident <= max_resident or bool(cfg.get("force_max_resident", False)):
                max_resident = max(1, min(explicit_resident, 8))
                reason += "; explicit resident limit"

        auto_concurrent = min(max_resident, 3)
        explicit_concurrent = int(cfg.get("max_concurrent_generations", 0) or 0)
        max_concurrent = explicit_concurrent if explicit_concurrent > 0 else auto_concurrent
        max_concurrent = max(1, min(max_concurrent, max_resident, 8))
        if max_resident == 1:
            max_concurrent = 1
            per_model = 1

        configured_context = max(1024, int(cfg.get("default_context_tokens", 8192)))
        if self.hardware.gpu_vram_gb is not None and not self.hardware.unified_memory:
            if self.hardware.gpu_vram_gb <= 4:
                context_cap = int(cfg.get("context_tokens_4gb_vram", 4096))
            elif self.hardware.gpu_vram_gb < 8:
                context_cap = int(cfg.get("context_tokens_under_8gb_vram", 6144))
            else:
                context_cap = configured_context
        else:
            context_cap = configured_context
        recommended_context = max(1024, min(configured_context, context_cap))

        return ModelRuntimePolicy(
            mode="single" if max_resident == 1 else "multi",
            max_resident_models=max_resident,
            max_concurrent_generations=max_concurrent,
            max_parallel_per_model=per_model,
            resident_keep_alive_seconds=keep_alive,
            admission_timeout_seconds=timeout,
            reserve_ram_gb=reserve_ram,
            reserve_vram_gb=reserve_vram,
            reason=reason,
            recommended_context_tokens=recommended_context,
        )

    def can_start_model(self, size_bytes: int | None = None) -> tuple[bool, str]:
        s = self.snapshot()
        if size_bytes == 0:
            if s["available_ram_gb"] < 0.25:
                return False, f"Only {s['available_ram_gb']} GB RAM is available; free memory before generation."
            return True, "ok"
        minimum = {"lite": 0.5, "balanced": 1.5, "power": 3.0}.get(self.profile, 1.0)
        minimum = max(minimum, self.model_policy.reserve_ram_gb)
        if s["available_ram_gb"] < minimum:
            return False, f"Only {s['available_ram_gb']} GB RAM is available; free memory before loading another model."

        # On dedicated-GPU systems, do not silently admit a model that is known
        # to exceed currently free VRAM. Ollama can otherwise fall back heavily
        # to CPU without surfacing that performance degradation to the caller.
        # Unified-memory systems intentionally skip this dedicated-VRAM gate.
        if self.hardware.gpu_vram_gb is not None and not self.hardware.unified_memory:
            free_vram = s.get("gpu_free_vram_gb")
            if free_vram is not None:
                reserve = self.model_policy.reserve_vram_gb
                if free_vram <= reserve:
                    return False, (
                        f"Only {free_vram} GB VRAM is free; {reserve:.2f} GB is reserved. "
                        "Free GPU memory before loading a model."
                    )
                if size_bytes:
                    estimated_gb = float(size_bytes) / GIB * 1.15
                    usable_vram = max(0.0, float(free_vram) - reserve)
                    if estimated_gb > usable_vram:
                        return False, (
                            f"VRAM start gate: {free_vram} GB free with {reserve:.2f} GB reserved, "
                            f"but the model is estimated to require ~{estimated_gb:.2f} GB. "
                            "Refusing silent CPU fallback."
                        )
        return True, "ok"

    def can_admit_model(self, size_bytes: int | None = None, resident_count: int = 0, resident_size_bytes: int = 0) -> tuple[bool, str]:
        """Conservative admission gate for an additional resident model.

        Disk/model size is only an estimate of runtime memory. Ollama remains the
        final allocator. The assistant uses this gate to avoid obvious pressure and
        falls back to one model when an additional model cannot safely fit.
        """
        s = self.snapshot()
        estimated_gb = (float(size_bytes) / GIB * 1.15) if size_bytes else 0.0
        resident_estimated_gb = (float(resident_size_bytes) / GIB * 1.15) if resident_size_bytes else 0.0
        required_ram = self.model_policy.reserve_ram_gb + (estimated_gb if self.hardware.unified_memory or self.hardware.gpu_vram_gb is None else min(estimated_gb, 2.0))
        if s["available_ram_gb"] < required_ram:
            return False, f"RAM admission gate: {s['available_ram_gb']} GB available, ~{required_ram:.2f} GB required."

        # For concurrent NVIDIA residency, follow Ollama's conservative rule that a
        # newly loaded GPU model must fit in available VRAM. The first model may still
        # use Ollama's normal CPU/GPU partial offload path.
        if resident_count > 0 and self.hardware.gpu_vram_gb is not None and estimated_gb > 0:
            required_total_vram = resident_estimated_gb + estimated_gb + self.model_policy.reserve_vram_gb
            if required_total_vram > self.hardware.gpu_vram_gb:
                return False, f"VRAM residency budget: ~{required_total_vram:.2f} GB estimated for resident models, {self.hardware.gpu_vram_gb} GB total."
            free_vram = s.get("gpu_free_vram_gb")
            if free_vram is not None:
                required_vram = estimated_gb + self.model_policy.reserve_vram_gb
                if free_vram < required_vram:
                    return False, f"VRAM admission gate: {free_vram} GB free, ~{required_vram:.2f} GB required for another resident model."
        elif resident_count > 0 and (self.hardware.unified_memory or self.hardware.gpu_vram_gb is None) and estimated_gb > 0:
            required_total_ram = resident_estimated_gb + estimated_gb + self.model_policy.reserve_ram_gb
            if required_total_ram > self.hardware.ram_gb:
                return False, f"RAM residency budget: ~{required_total_ram:.2f} GB estimated for resident models, {self.hardware.ram_gb} GB total."
        if resident_count > 0:
            hot, reason = self.thermal_pressure()
            if hot:
                return False, f"Thermal admission gate: {reason}."
        return True, "ok"

    def model_runtime_status(self) -> dict:
        return {"policy": self.model_policy.to_dict(), "resources": self.snapshot()}

    def metabolize(self) -> dict:
        """The Digestive System (Robust): Clear Ollama and PyTorch/CUDA VRAM caches."""
        import httpx
        import gc
        import sys
        
        freed_ollama = False
        try:
            # 1. Robust Ollama Eviction (with timeouts and connection error handling)
            with httpx.Client(timeout=2.0) as client:
                res = client.get("http://127.0.0.1:11434/api/ps")
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    for m in models:
                        model_name = m.get("model")
                        if model_name:
                            client.post("http://127.0.0.1:11434/api/generate", json={"model": model_name, "keep_alive": 0})
                            freed_ollama = True
        except Exception:
            pass
            
        # 2. Native Python GC
        collected = gc.collect()
        
        # 3. Robust PyTorch / CUDA cache clearing (AirLLM / Colibri style)
        cuda_cleared = False
        if "torch" in sys.modules:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                cuda_cleared = True
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # Apple Silicon robust clearing
                torch.mps.empty_cache()
                cuda_cleared = True

        return {
            "ollama_freed": freed_ollama, 
            "cuda_mps_cleared": cuda_cleared, 
            "gc_objects_collected": collected
        }
