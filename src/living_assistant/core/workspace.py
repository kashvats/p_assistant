from __future__ import annotations
from pathlib import Path

from living_assistant.core.scope import current_scope, within

class WorkspaceViolation(PermissionError):
    pass

class Workspace:
    def __init__(self, roots: list[str | Path]):
        self.roots = [Path(r).expanduser().resolve() for r in roots]
        for root in self.roots:
            root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | Path, base: str | Path | None = None) -> Path:
        scope = current_scope()
        resolved = self._resolve(path, base if base else scope)
        if scope is not None and not within(resolved, scope):
            # a company employee's turn: only its project folder is reachable
            raise WorkspaceViolation(f"Path is outside this project's folder ({scope}): {resolved}. "
                                     f"Use a path inside {scope}.")
        return resolved

    def _resolve(self, path: str | Path, base: str | Path | None = None) -> Path:
        raw_str = str(path).strip() if path is not None else ""
        base_path = Path(base).expanduser().resolve() if base else self.roots[0]

        if not raw_str or raw_str == ".":
            for root in self.roots:
                try:
                    base_path.relative_to(root)
                    return base_path
                except ValueError:
                    pass
            raise WorkspaceViolation(f"Path is outside allowed workspace roots: {base_path}")

        p = Path(raw_str).expanduser()
        clean = raw_str.replace("\\", "/").strip()
        if clean.startswith("./"):
            clean = clean[2:]
        clean_no_slash = clean.lstrip("/")
        parts = [part for part in clean_no_slash.split("/") if part and part != "."]

        candidates: list[Path] = []

        # Check if first path segment matches any workspace root name (e.g. 'workspace/books')
        matched_root_cand = None
        has_subfolder = False
        if parts:
            first_part = parts[0]
            rest_parts = parts[1:]
            rest_path = Path(*rest_parts) if rest_parts else Path(".")
            for root in self.roots:
                if first_part.lower() == root.name.lower():
                    matched_root_cand = root / rest_path
                    has_subfolder = (base_path / first_part).is_dir()
                    break

        if matched_root_cand:
            candidates.append(matched_root_cand)
            if has_subfolder:
                if not p.is_absolute() and not p.anchor:
                    candidates.append(base_path / p)
        else:
            if not p.is_absolute() and not p.anchor:
                candidates.append(base_path / p)
            elif p.is_absolute():
                candidates.append(p)

        # Windows drive anchor resolution if needed (e.g. C:\workspace\books)
        if p.is_absolute() and p.drive:
            try:
                rel_drive = p.relative_to(p.anchor)
                d_parts = [dp for dp in rel_drive.parts if dp and dp != "."]
                if d_parts:
                    first_d = d_parts[0]
                    rest_d = Path(*d_parts[1:]) if len(d_parts) > 1 else Path(".")
                    for root in self.roots:
                        if first_d.lower() == root.name.lower():
                            candidates.append(root / rest_d)
                            break
            except Exception:
                pass

        # Leading slash candidate (e.g. /books -> workspace/books) only if existing path within workspace
        if clean.startswith("/") and not p.drive and parts and not matched_root_cand:
            slash_target = base_path / Path(*parts)
            if slash_target.exists():
                candidates.append(slash_target)

        valid_candidates: list[Path] = []
        for cand in candidates:
            try:
                res = cand.resolve()
                for root in self.roots:
                    try:
                        res.relative_to(root)
                        valid_candidates.append(res)
                        break
                    except ValueError:
                        pass
            except Exception:
                pass

        if not valid_candidates:
            resolved_p = p.resolve() if not p.is_absolute() else p
            raise WorkspaceViolation(f"Path is outside allowed workspace roots: {resolved_p}")

        for cand in valid_candidates:
            if cand.exists():
                return cand
        return valid_candidates[0]

    def list(self, path: str = ".", base=None) -> list[dict]:
        p = self.resolve(path, base)
        if not p.exists():
            raise FileNotFoundError(f"Directory does not exist: {p}")
        if not p.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {p}")
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

    def edit_text(self, path: str, old_str: str, new_str: str, base=None) -> str:
        p = self.resolve(path, base)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        content = p.read_text(encoding="utf-8", errors="replace")
        if old_str not in content:
            raise ValueError(f"Target text not found in {p}")
        updated = content.replace(old_str, new_str, 1)
        return self.write_text(path, updated, base)

    def delete(self, path: str, recursive: bool = False, base=None) -> bool:
        import shutil
        p = self.resolve(path, base)
        # Protect root directories from deletion
        for root in self.roots:
            if p == root:
                raise WorkspaceViolation(f"Cannot delete workspace root directory: {p}")
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {p}")
        if p.is_dir():
            if not recursive:
                p.rmdir()
            else:
                shutil.rmtree(p)
        else:
            p.unlink()
        return True

