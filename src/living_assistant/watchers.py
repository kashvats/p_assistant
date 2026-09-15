from __future__ import annotations
from pathlib import Path
import json, time
from .config import data_dir

class WatchRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "watches.json")
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
        self.snapshots: dict[str, dict[str, tuple[int, int]]] = {}

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict):
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, name: str, path: str, recursive: bool = True, extensions: list[str] | None = None) -> dict:
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            raise ValueError(f"Watch path is not a directory: {p}")
        data = self._load()
        data[name] = {
            "path": str(p),
            "recursive": bool(recursive),
            "extensions": extensions or [],
            "enabled": True,
            "created_at": time.time(),
        }
        self._save(data)
        return data[name]

    def remove(self, name: str) -> bool:
        data = self._load()
        existed = name in data
        data.pop(name, None)
        self.snapshots.pop(name, None)
        self._save(data)
        return existed

    def list(self) -> dict:
        return self._load()

    @staticmethod
    def _scan(cfg: dict, max_files: int = 3000) -> dict[str, tuple[int, int]]:
        root = Path(cfg["path"])
        iterator = root.rglob("*") if cfg.get("recursive", True) else root.glob("*")
        exts = {x.lower() if x.startswith(".") else "." + x.lower() for x in cfg.get("extensions", [])}
        out: dict[str, tuple[int, int]] = {}
        count = 0
        for p in iterator:
            if count >= max_files:
                break
            try:
                if not p.is_file():
                    continue
                if exts and p.suffix.lower() not in exts:
                    continue
                st = p.stat()
                out[str(p)] = (int(st.st_mtime_ns), int(st.st_size))
                count += 1
            except (OSError, PermissionError):
                continue
        return out

    def poll(self, max_events_per_watch: int = 50) -> list[dict]:
        events = []
        for name, cfg in self._load().items():
            if not cfg.get("enabled", True):
                continue
            root = Path(cfg["path"])
            if not root.exists():
                events.append({"kind": "watch_path_missing", "watch": name, "path": str(root)})
                continue
            current = self._scan(cfg)
            previous = self.snapshots.get(name)
            self.snapshots[name] = current
            if previous is None:
                continue
            added = current.keys() - previous.keys()
            removed = previous.keys() - current.keys()
            changed = {p for p in current.keys() & previous.keys() if current[p] != previous[p]}
            for p in list(sorted(added))[:max_events_per_watch]:
                events.append({"kind": "file_added", "watch": name, "path": p})
            for p in list(sorted(changed))[:max_events_per_watch]:
                events.append({"kind": "file_changed", "watch": name, "path": p})
            for p in list(sorted(removed))[:max_events_per_watch]:
                events.append({"kind": "file_removed", "watch": name, "path": p})
        return events
