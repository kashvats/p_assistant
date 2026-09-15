from __future__ import annotations
import time, psutil
from .memory import MemoryStore
from .tools.security import audit_local

class NervousSystem:
    """Low-resource deterministic event loop. It does not keep an LLM loaded."""
    def __init__(self, config: dict, memory: MemoryStore):
        self.cfg = config.get("daemon", {})
        self.memory = memory
        self.last_ports: set[str] = set()

    def _ports(self):
        audit = audit_local()
        return {str(x.get("local")) for x in audit.get("listening_ports", []) if x.get("local")}

    def tick(self) -> list[dict]:
        events = []
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.2)
        if vm.percent >= float(self.cfg.get("high_memory_percent",88)):
            events.append({"kind":"high_memory","percent":vm.percent})
        if cpu >= float(self.cfg.get("high_cpu_percent",92)):
            events.append({"kind":"high_cpu","percent":cpu})

        if self.cfg.get("alert_on_new_listening_port",True):
            now = self._ports()
            if self.last_ports:
                for port in sorted(now - self.last_ports):
                    events.append({"kind":"new_listening_port","local":port})
            self.last_ports = now

        for e in events:
            self.memory.add_event(e["kind"], e)
        return events

    def run_forever(self):
        poll = max(5, int(self.cfg.get("poll_seconds",15)))
        print(f"Nervous system active (poll={poll}s). No model is kept loaded. Ctrl+C to stop.")
        while True:
            events = self.tick()
            for e in events:
                print("EVENT", e)
            time.sleep(poll)
