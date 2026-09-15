from __future__ import annotations
import psutil

class ResourceManager:
    def __init__(self, profile: str, config: dict):
        self.profile = profile
        self.config = config

    def snapshot(self) -> dict:
        vm = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.05),
            "ram_percent": vm.percent,
            "available_ram_gb": round(vm.available / (1024**3), 2),
        }

    def can_start_model(self) -> tuple[bool, str]:
        s = self.snapshot()
        minimum = {"lite": 0.7, "balanced": 1.5, "power": 3.0}.get(self.profile, 1.0)
        if s["available_ram_gb"] < minimum:
            return False, f"Only {s['available_ram_gb']} GB RAM is available; free memory before loading another model."
        return True, "ok"
