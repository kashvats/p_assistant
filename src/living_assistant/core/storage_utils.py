from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile


def atomic_write_text(path: str | Path, text: str, encoding: str = 'utf-8', mode: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'w', encoding=encoding, newline='') as handle:
            handle.write(text)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        if mode is not None and os.name != 'nt':
            os.chmod(temp, mode)
        os.replace(temp, target)
        if os.name != 'nt':
            try:
                dir_fd = os.open(str(target.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    finally:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass


def atomic_write_json(path: str | Path, value: object, *, indent: int = 2, mode: int | None = None) -> None:
    atomic_write_text(path, json.dumps(value, indent=indent), mode=mode)
