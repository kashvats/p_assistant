from __future__ import annotations
from dataclasses import dataclass, asdict
import platform
import shutil
import subprocess
import psutil

GIB = 1024 ** 3

@dataclass
class HardwareInfo:
    os: str
    machine: str
    cpu_count_physical: int | None
    cpu_count_logical: int | None
    ram_gb: float
    available_ram_gb: float
    gpu_name: str | None = None
    gpu_vram_gb: float | None = None
    gpu_vram_free_gb: float | None = None
    gpu_count: int = 0
    apple_silicon: bool = False
    unified_memory: bool = False

    def to_dict(self):
        return asdict(self)


def _nvidia_info():
    """Return primary NVIDIA adapter information without importing GPU SDKs."""
    if not shutil.which("nvidia-smi"):
        return None, None, None, 0
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=4,
            stderr=subprocess.DEVNULL,
        ).strip().splitlines()
        if not out:
            return None, None, None, 0
        rows = []
        for line in out:
            name, total, free = [x.strip() for x in line.rsplit(",", 2)]
            rows.append((name, float(total) / 1024, float(free) / 1024))
        # The model runtime currently reasons about the largest single device because
        # Ollama prefers a single GPU when a model completely fits there.
        primary = max(rows, key=lambda row: row[1])
        return primary[0], round(primary[1], 2), round(primary[2], 2), len(rows)
    except Exception:
        return None, None, None, 0


def _apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def detect_hardware() -> HardwareInfo:
    vm = psutil.virtual_memory()
    gpu_name, gpu_vram, gpu_vram_free, gpu_count = _nvidia_info()
    apple = _apple_silicon()
    if apple and not gpu_name:
        # Apple Silicon does not expose a separate VRAM pool: CPU and GPU share
        # unified memory. Keep gpu_vram_* unset so callers cannot mistake total RAM
        # for dedicated VRAM, and mark the topology explicitly instead.
        gpu_name = "Apple Silicon (unified memory)"
        gpu_count = 1
    return HardwareInfo(
        os=platform.system(),
        machine=platform.machine(),
        cpu_count_physical=psutil.cpu_count(logical=False),
        cpu_count_logical=psutil.cpu_count(logical=True),
        ram_gb=round(vm.total / GIB, 2),
        available_ram_gb=round(vm.available / GIB, 2),
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram,
        gpu_vram_free_gb=gpu_vram_free,
        gpu_count=gpu_count,
        apple_silicon=apple,
        unified_memory=apple,
    )


def choose_profile(config: dict, hw: HardwareInfo) -> str:
    explicit = str(config.get("profile", "auto")).lower()
    if explicit != "auto":
        return explicit

    ram = hw.ram_gb
    if ram >= 48:
        return "power"
    if ram >= 12:
        return "balanced"
    return "lite"
