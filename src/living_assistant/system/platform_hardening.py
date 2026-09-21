from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import ctypes
import json
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import time


@dataclass(frozen=True)
class PlatformStatus:
    os: str
    release: str
    machine: str
    elevated: bool
    symlink_supported: bool
    symlink_reason: str
    junction_supported: bool
    hardlink_supported: bool
    developer_mode: bool | None
    long_paths_enabled: bool | None
    user_service_backend: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def is_elevated() -> bool:
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _windows_registry_dword(path: str, name: str) -> int | None:
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
    except Exception:
        return None


def windows_developer_mode() -> bool | None:
    value = _windows_registry_dword(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock",
        "AllowDevelopmentWithoutDevLicense",
    )
    return None if value is None else bool(value)


def windows_long_paths_enabled() -> bool | None:
    value = _windows_registry_dword(
        r"SYSTEM\CurrentControlSet\Control\FileSystem",
        "LongPathsEnabled",
    )
    return None if value is None else bool(value)



def is_link_like(path: str | Path) -> bool:
    """True for POSIX symlinks and Windows filesystem reparse points.

    Junctions are mount-point reparse points and are not equivalent to ordinary
    symbolic links. Treating every Windows reparse point as a traversal boundary is
    deliberately conservative for security scanners and workspace watchers.
    """
    p=Path(path)
    try:
        if p.is_symlink():
            return True
        st=p.lstat()
        attrs=int(getattr(st,'st_file_attributes',0) or 0)
        reparse=int(getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))
        return platform.system()=='Windows' and bool(attrs & reparse)
    except (OSError,PermissionError):
        return False


def link_target_description(path: str | Path) -> str:
    p=Path(path)
    try:
        return os.readlink(p)
    except (OSError,NotImplementedError):
        return '<reparse-point>' if is_link_like(p) else '<unavailable>'


def iter_tree_without_link_traversal(root: str | Path, recursive: bool=True):
    """Yield entries under root without descending into symlinks/junctions."""
    root=Path(root)
    if not recursive:
        try:
            yield from root.iterdir()
        except (OSError,PermissionError):
            return
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base=Path(dirpath)
        kept=[]
        for name in list(dirnames):
            child=base/name
            if is_link_like(child):
                yield child
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            yield base/name


def _create_windows_junction(target: Path, link: Path) -> None:
    """Create a directory junction without requiring symlink privilege.

    Prefer Python's private CreateJunction helper when present; otherwise use
    Windows' built-in mklink /J. This function is never used for remote targets.
    """
    if platform.system() != "Windows":
        raise OSError("Windows junctions are only available on Windows")
    target = target.resolve()
    if not target.is_dir():
        raise OSError("junction target must be a directory")
    if str(target).startswith("\\\\"):
        raise OSError("junctions to remote/UNC targets are not supported")
    try:
        import _winapi  # type: ignore
        create = getattr(_winapi, "CreateJunction", None)
        if callable(create):
            create(str(target), str(link))
            return
    except Exception:
        pass

    # mklink is a cmd builtin. Passing one carefully quoted command string avoids
    # shell=True and keeps the target/link values out of an additional shell layer.
    def q(value: str) -> str:
        # Double quotes are not valid Windows filename characters, so rejecting them
        # is both safe and semantically correct for filesystem paths.
        if '"' in value:
            raise OSError("invalid quote character in Windows path")
        return f'"{value}"'

    cmdline = f"mklink /J {q(str(link))} {q(str(target))}"
    proc = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", cmdline],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if proc.returncode != 0 or not link.exists():
        raise OSError((proc.stderr or proc.stdout or "mklink /J failed").strip())


def create_portable_link(
    target: str | Path,
    link: str | Path,
    *,
    allow_copy_fallback: bool = False,
) -> dict:
    """Create a link with Windows non-admin fallbacks while preserving semantics.

    Order:
      1. symbolic link
      2. Windows directory junction (directories)
      3. hard link (files; same-volume only)
      4. explicit copy fallback only when the caller opts in

    The function never silently copies by default because a copy is not a link and
    can invalidate security/integrity tests that depend on link semantics.
    """
    target_p = Path(target).expanduser().resolve()
    link_p = Path(link).expanduser().absolute()
    if not target_p.exists():
        raise FileNotFoundError(target_p)
    if link_p.exists() or link_p.is_symlink():
        raise FileExistsError(link_p)
    link_p.parent.mkdir(parents=True, exist_ok=True)
    is_dir = target_p.is_dir()

    try:
        os.symlink(str(target_p), str(link_p), target_is_directory=is_dir)
        return {"ok": True, "method": "symlink", "target": str(target_p), "link": str(link_p)}
    except (OSError, NotImplementedError) as symlink_error:
        first_error = str(symlink_error)

    if platform.system() == "Windows" and is_dir:
        try:
            _create_windows_junction(target_p, link_p)
            return {"ok": True, "method": "junction", "target": str(target_p), "link": str(link_p)}
        except OSError as exc:
            fallback_error = str(exc)
    elif target_p.is_file():
        try:
            os.link(str(target_p), str(link_p))
            return {"ok": True, "method": "hardlink", "target": str(target_p), "link": str(link_p)}
        except OSError as exc:
            fallback_error = str(exc)
    else:
        fallback_error = "no semantic-preserving fallback available"

    if allow_copy_fallback:
        if is_dir:
            shutil.copytree(target_p, link_p)
            method = "copytree"
        else:
            shutil.copy2(target_p, link_p)
            method = "copy"
        return {
            "ok": True,
            "method": method,
            "target": str(target_p),
            "link": str(link_p),
            "warning": "copy fallback does not preserve link semantics",
        }

    raise OSError(f"link creation failed: symlink={first_error}; fallback={fallback_error}")


def probe_link_capability(base_dir: str | Path | None = None) -> dict:
    root_parent = Path(base_dir).expanduser().resolve() if base_dir else None
    kwargs = {"dir": str(root_parent)} if root_parent else {}
    with tempfile.TemporaryDirectory(prefix="living-assistant-link-probe-", **kwargs) as temp:
        root = Path(temp)
        target = root / "target"
        target.mkdir()
        link = root / "link"
        try:
            result = create_portable_link(target, link)
            return {"supported": True, "method": result["method"], "reason": "ok"}
        except Exception as exc:
            return {"supported": False, "method": None, "reason": str(exc)}


def _probe_hardlink() -> bool:
    try:
        with tempfile.TemporaryDirectory(prefix="living-assistant-hardlink-") as temp:
            root = Path(temp)
            src = root / "a.txt"; dst = root / "b.txt"
            src.write_text("x", encoding="utf-8")
            os.link(src, dst)
            return dst.exists() and dst.read_text(encoding="utf-8") == "x"
    except Exception:
        return False


def detect_user_service_backend() -> str | None:
    system = platform.system()
    if system == "Windows":
        return "scheduled-task" if shutil.which("schtasks") else None
    if system == "Darwin":
        return "launchd" if shutil.which("launchctl") else None
    if system == "Linux":
        return "systemd-user" if shutil.which("systemctl") else None
    return None


def platform_status() -> PlatformStatus:
    probe = probe_link_capability()
    return PlatformStatus(
        os=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        elevated=is_elevated(),
        symlink_supported=bool(probe.get("supported")) and probe.get("method") == "symlink",
        symlink_reason=str(probe.get("reason") or ""),
        junction_supported=(platform.system() == "Windows" and bool(probe.get("supported")) and probe.get("method") == "junction"),
        hardlink_supported=_probe_hardlink(),
        developer_mode=windows_developer_mode(),
        long_paths_enabled=windows_long_paths_enabled(),
        user_service_backend=detect_user_service_backend(),
    )


class SleepResumeMonitor:
    """Best-effort suspend/resume detector requiring no privileged OS hooks.

    A large wall-clock gap between daemon ticks is treated as a resume-like event.
    wall-vs-monotonic drift is also tracked because some platforms pause monotonic
    clocks during suspend while others include the suspended interval.
    """
    def __init__(self, threshold_seconds: float = 60.0):
        self.threshold_seconds = max(5.0, float(threshold_seconds))
        self.last_wall = time.time()
        self.last_mono = time.monotonic()

    def observe(self, wall_now: float | None = None, mono_now: float | None = None) -> dict:
        wall_now = time.time() if wall_now is None else float(wall_now)
        mono_now = time.monotonic() if mono_now is None else float(mono_now)
        wall_delta = max(0.0, wall_now - self.last_wall)
        mono_delta = max(0.0, mono_now - self.last_mono)
        drift = max(0.0, wall_delta - mono_delta)
        self.last_wall = wall_now
        self.last_mono = mono_now
        resumed = wall_delta >= self.threshold_seconds or drift >= self.threshold_seconds
        return {
            "resumed": resumed,
            "wall_gap_seconds": round(wall_delta, 3),
            "monotonic_gap_seconds": round(mono_delta, 3),
            "suspend_drift_seconds": round(drift, 3),
        }


def service_status() -> dict:
    system = platform.system()
    backend = detect_user_service_backend()
    if system == "Windows" and backend:
        p = subprocess.run(["schtasks", "/Query", "/TN", "LivingAssistant", "/FO", "LIST"], text=True, capture_output=True, timeout=8)
        return {"backend": backend, "installed": p.returncode == 0, "detail": (p.stdout or p.stderr)[-4000:]}
    if system == "Darwin" and backend:
        uid = str(os.getuid()) if hasattr(os, "getuid") else ""
        label = "com.livingassistant.daemon"
        p = subprocess.run(["launchctl", "print", f"gui/{uid}/{label}"], text=True, capture_output=True, timeout=8)
        return {"backend": backend, "installed": p.returncode == 0, "detail": (p.stdout or p.stderr)[-4000:]}
    if system == "Linux" and backend:
        p = subprocess.run(["systemctl", "--user", "is-enabled", "living-assistant.service"], text=True, capture_output=True, timeout=8)
        active = subprocess.run(["systemctl", "--user", "is-active", "living-assistant.service"], text=True, capture_output=True, timeout=8)
        return {"backend": backend, "installed": p.returncode == 0, "enabled": p.stdout.strip(), "active": active.stdout.strip()}
    return {"backend": backend, "installed": False, "detail": "No supported per-user service manager detected."}
