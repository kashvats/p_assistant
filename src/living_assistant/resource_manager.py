from __future__ import annotations
from dataclasses import dataclass, asdict
import shutil
import subprocess
import psutil
from .hardware import HardwareInfo, detect_hardware

GIB = 1024 ** 3

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

    def to_dict(self) -> dict:
        return asdict(self)


class ResourceManager:
    def __init__(self, profile: str, config: dict, hardware: HardwareInfo | None = None):
        self.profile = profile
        self.config = config
        self.hardware = hardware or detect_hardware()
        self.model_policy = self._select_model_policy()

    def _nvidia_runtime(self) -> tuple[float | None, float | None]:
        if not shutil.which("nvidia-smi"):
            return self.hardware.gpu_vram_free_gb, None
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.free,temperature.gpu", "--format=csv,noheader,nounits"],
                text=True, timeout=3, stderr=subprocess.DEVNULL,
            ).strip().splitlines()
            rows = []
            for line in out:
                free, temp = [x.strip() for x in line.rsplit(",", 1)]
                rows.append((float(free) / 1024, float(temp)))
            if not rows:
                return self.hardware.gpu_vram_free_gb, None
            # Match the runtime admission logic to the GPU with the most free VRAM.
            free, temp = max(rows, key=lambda row: row[0])
            return round(free, 2), round(temp, 1)
        except Exception:
            return self.hardware.gpu_vram_free_gb, None

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

    def snapshot(self) -> dict:
        vm = psutil.virtual_memory()
        result = {
            "cpu_percent": psutil.cpu_percent(interval=0.05),
            "ram_percent": vm.percent,
            "available_ram_gb": round(vm.available / GIB, 2),
        }
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
        )

    def can_start_model(self, size_bytes: int | None = None) -> tuple[bool, str]:
        s = self.snapshot()
        minimum = {"lite": 0.7, "balanced": 1.5, "power": 3.0}.get(self.profile, 1.0)
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
