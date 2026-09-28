from __future__ import annotations
from pathlib import Path

class WorkspaceViolation(PermissionError):
    pass

class Workspace:
    def __init__(self, roots: list[str | Path]):
        self.roots = [Path(r).expanduser().resolve() for r in roots]
        for root in self.roots:
            root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | Path, base: str | Path | None = None) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            base_path = Path(base).expanduser().resolve() if base else self.roots[0]
            p = base_path / p
        resolved = p.resolve()
        for root in self.roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                pass
        raise WorkspaceViolation(f"Path is outside allowed workspace roots: {resolved}")

    def list(self, path: str = ".", base=None) -> list[dict]:
        p = self.resolve(path, base)
        items=[]
        for x in p.iterdir():
            try:
                is_dir=x.is_dir()
                is_file=x.is_file()
                size=x.stat().st_size if is_file else None
                inaccessible=False
            except (OSError, PermissionError):
                # Broken reparse points, offline mounts and permission-restricted
                # entries should not make an entire workspace listing fail.
                is_dir=False; is_file=False; size=None; inaccessible=True
            items.append({
                "name":x.name,"path":str(x),"is_dir":is_dir,"is_file":is_file,
                "is_symlink":x.is_symlink(),"size":size,"inaccessible":inaccessible,
            })
        return sorted(items,key=lambda z:(not z["is_dir"],z["name"].lower()))

    def read_text(self, path: str, base=None, max_chars: int = 200000) -> str:
        p = self.resolve(path, base)
        return p.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def write_text(self, path: str, content: str, base=None) -> str:
        import os
        import time
        import tempfile

        p = self.resolve(path, base)
        p.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic file write (Edge Case 38.2): write to .tmp and rename with retry loop for Windows locks
        tmp_fd, tmp_path = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            last_err = None
            for attempt in range(4):
                try:
                    os.replace(tmp_path, p)
                    last_err = None
                    break
                except OSError as exc:
                    last_err = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_err is not None:
                raise last_err
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return str(p)

