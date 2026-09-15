from __future__ import annotations
from dataclasses import dataclass, asdict
import platform, subprocess, shutil
import psutil

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

    def to_dict(self):
        return asdict(self)

def _nvidia_info():
    if not shutil.which("nvidia-smi"):
        return None, None
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True, timeout=4, stderr=subprocess.DEVNULL
        ).strip().splitlines()
        if not out:
            return None, None
        name, mem = [x.strip() for x in out[0].rsplit(",", 1)]
        return name, round(float(mem) / 1024, 2)
    except Exception:
        return None, None

def detect_hardware() -> HardwareInfo:
    vm = psutil.virtual_memory()
    gpu_name, gpu_vram = _nvidia_info()
    return HardwareInfo(
        os=platform.system(),
        machine=platform.machine(),
        cpu_count_physical=psutil.cpu_count(logical=False),
        cpu_count_logical=psutil.cpu_count(logical=True),
        ram_gb=round(vm.total / (1024**3), 2),
        available_ram_gb=round(vm.available / (1024**3), 2),
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram,
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
