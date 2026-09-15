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
        return [
            {"name": x.name, "path": str(x), "is_dir": x.is_dir(), "size": x.stat().st_size if x.is_file() else None}
            for x in sorted(p.iterdir(), key=lambda z: (not z.is_dir(), z.name.lower()))
        ]

    def read_text(self, path: str, base=None, max_chars: int = 200000) -> str:
        p = self.resolve(path, base)
        return p.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def write_text(self, path: str, content: str, base=None) -> str:
        p = self.resolve(path, base)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)
