from __future__ import annotations
from pathlib import Path
import json, time
from living_assistant.core.config import data_dir
from living_assistant.core.storage_utils import atomic_write_json
from living_assistant.system.platform_hardening import iter_tree_without_link_traversal, is_link_like

class WatchRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "watches.json")
        if not self.path.exists():
            atomic_write_json(self.path, {})
        self.snapshots: dict[str, dict[str, tuple[int, int]]] = {}

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict):
        atomic_write_json(self.path, data)

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
        iterator = iter_tree_without_link_traversal(root, recursive=bool(cfg.get("recursive", True)))
        exts = {x.lower() if x.startswith(".") else "." + x.lower() for x in cfg.get("extensions", [])}
        out: dict[str, tuple[int, int]] = {}
        count = 0
        for p in iterator:
            if count >= max_files:
                break
            try:
                if is_link_like(p) or not p.is_file():
                    continue
                if exts and p.suffix.lower() not in exts:
                    continue
                st = p.stat()
                out[str(p)] = (int(st.st_mtime_ns), int(st.st_size))
                count += 1
            except (OSError, PermissionError):
                continue
        return out


    def rebaseline(self) -> dict:
        """Refresh in-memory snapshots without emitting file-change events.

        Used after system resume so filesystem timestamp churn/remounted volumes do
        not look like a ransomware burst or mass user edit.
        """
        refreshed = 0
        missing = []
        for name, cfg in self._load().items():
            if not cfg.get("enabled", True):
                continue
            root = Path(cfg["path"])
            if not root.exists():
                missing.append({"watch": name, "path": str(root)})
                continue
            self.snapshots[name] = self._scan(cfg)
            refreshed += 1
        return {"refreshed": refreshed, "missing": missing}

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
            total_changes = len(added) + len(changed) + len(removed)
            threshold = max(1, int(max_events_per_watch))
            if total_changes > threshold:
                # Coalesce build-tool bursts into one bounded event rather than flooding
                # the daemon/UI with hundreds of per-file events. Keep a generous,
                # bounded sample per change kind so security burst detection still has
                # representative paths while counts preserve the full magnitude.
                sample_limit = min(200, max(100, threshold))
                events.append({
                    "kind": "file_changes_batched",
                    "watch": name,
                    "root": str(root),
                    "total_changes": total_changes,
                    "counts": {
                        "file_added": len(added),
                        "file_changed": len(changed),
                        "file_removed": len(removed),
                    },
                    "paths": {
                        "file_added": list(sorted(added))[:sample_limit],
                        "file_changed": list(sorted(changed))[:sample_limit],
                        "file_removed": list(sorted(removed))[:sample_limit],
                    },
                    "sample_truncated": any(len(items) > sample_limit for items in (added, changed, removed)),
                })
                continue
            for p in sorted(added):
                events.append({"kind": "file_added", "watch": name, "path": p})
            for p in sorted(changed):
                events.append({"kind": "file_changed", "watch": name, "path": p})
            for p in sorted(removed):
                events.append({"kind": "file_removed", "watch": name, "path": p})
        return events
