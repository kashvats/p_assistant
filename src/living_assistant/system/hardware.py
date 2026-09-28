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


@dataclass
class GpuDeviceTelemetry:
    name: str
    vendor: str  # "nvidia" | "amd" | "intel" | "apple" | "integrated" | "generic"
    total_mb: float | None = None
    used_mb: float | None = None
    free_mb: float | None = None
    integrated: bool = False
    telemetry_supported: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _nvidia_devices() -> list[GpuDeviceTelemetry]:
    """Return all NVIDIA adapters and their VRAM metrics via nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=4,
            stderr=subprocess.DEVNULL,
        ).strip().splitlines()
        devs = []
        for line in out:
            parts = [x.strip() for x in line.rsplit(",", 3)]
            if len(parts) == 4:
                name, total, used, free = parts
                devs.append(
                    GpuDeviceTelemetry(
                        name=name,
                        vendor="nvidia",
                        total_mb=round(float(total), 2),
                        used_mb=round(float(used), 2),
                        free_mb=round(float(free), 2),
                        integrated=False,
                        telemetry_supported=True,
                    )
                )
        return devs
    except Exception:
        return []


def _amd_devices() -> list[GpuDeviceTelemetry]:
    """Return AMD adapters via rocm-smi if available."""
    if not shutil.which("rocm-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showmeminfo", "vram"],
            text=True,
            timeout=4,
            stderr=subprocess.DEVNULL,
        ).strip().splitlines()
        devs = []
        for line in out:
            if "Total Memory" in line or "Used Memory" in line:
                # Basic parsing when rocm-smi outputs text
                pass
        # Fallback or generic rocm detection
        devs.append(
            GpuDeviceTelemetry(
                name="AMD ROCm GPU",
                vendor="amd",
                total_mb=None,
                used_mb=None,
                free_mb=None,
                integrated=False,
                telemetry_supported=False,
            )
        )
        return devs
    except Exception:
        return []


def _intel_devices() -> list[GpuDeviceTelemetry]:
    """Return Intel GPU info if available."""
    if shutil.which("intel_gpu_top"):
        return [
            GpuDeviceTelemetry(
                name="Intel Iris Xe / Arc GPU",
                vendor="intel",
                total_mb=None,
                used_mb=None,
                free_mb=None,
                integrated=True,
                telemetry_supported=False,
            )
        ]
    return []


def get_gpu_telemetry() -> list[GpuDeviceTelemetry]:
    """Query telemetry across NVIDIA, AMD, Intel, Apple Silicon, or integrated devices without assuming CUDA."""
    devices: list[GpuDeviceTelemetry] = []

    # 1. NVIDIA
    devices.extend(_nvidia_devices())

    # 2. AMD
    if not devices:
        devices.extend(_amd_devices())

    # 3. Intel
    if not devices:
        devices.extend(_intel_devices())

    # 4. Apple Silicon
    if not devices and _apple_silicon():
        devices.append(
            GpuDeviceTelemetry(
                name="Apple Silicon (unified memory)",
                vendor="apple",
                total_mb=None,  # Do not confuse host RAM with dedicated VRAM
                used_mb=None,
                free_mb=None,
                integrated=True,
                telemetry_supported=False,
            )
        )

    return devices


def _nvidia_info():
    """Return primary NVIDIA adapter information without importing GPU SDKs (legacy helper)."""
    devs = _nvidia_devices()
    if not devs:
        return None, None, None, 0
    # The primary GPU is the one with the largest VRAM
    primary = max(devs, key=lambda d: d.total_mb or 0)
    total_gb = round((primary.total_mb or 0) / 1024, 2) if primary.total_mb else None
    free_gb = round((primary.free_mb or 0) / 1024, 2) if primary.free_mb else None
    return primary.name, total_gb, free_gb, len(devs)


def _apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def detect_hardware() -> HardwareInfo:
    vm = psutil.virtual_memory()
    devices = get_gpu_telemetry()
    apple = _apple_silicon()

    gpu_name = None
    gpu_vram = None
    gpu_vram_free = None
    gpu_count = len(devices)

    if devices:
        primary = devices[0]
        gpu_name = primary.name
        if primary.telemetry_supported and primary.total_mb is not None:
            gpu_vram = round(primary.total_mb / 1024, 2)
            gpu_vram_free = round((primary.free_mb or 0) / 1024, 2)

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
        unified_memory=apple or any(d.integrated for d in devices),
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
