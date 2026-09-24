from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from platformdirs import (
    user_cache_dir,
    user_config_dir,
    user_data_dir,
    user_log_dir,
    user_state_dir,
)

from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger("living_assistant.system.environment")

_SAFE_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_.,-]+\])?(?:[<>=!~]+[A-Za-z0-9_.*+-]+)?$")
_SENSITIVE_ENV_KEYS = {
    "API_KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "AUTH", "CREDENTIAL",
    "SERPER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GH_TOKEN", "GITHUB_TOKEN",
}


@dataclass(frozen=True)
class PlatformPaths:
    """Standardized operating system paths for LivingAssistant."""
    app_name: str = "LivingAssistant"
    app_author: str = "LivingAssistant"

    @property
    def data_dir(self) -> Path:
        return Path(user_data_dir(self.app_name, self.app_author))

    @property
    def config_dir(self) -> Path:
        return Path(user_config_dir(self.app_name, self.app_author))

    @property
    def cache_dir(self) -> Path:
        return Path(user_cache_dir(self.app_name, self.app_author))

    @property
    def log_dir(self) -> Path:
        return Path(user_log_dir(self.app_name, self.app_author))

    @property
    def state_dir(self) -> Path:
        return Path(user_state_dir(self.app_name, self.app_author))

    @property
    def venvs_dir(self) -> Path:
        return self.cache_dir / "venvs"

    def ensure_dirs(self) -> dict[str, Path]:
        """Create all required platform directories with safe permissions."""
        dirs = {
            "data": self.data_dir,
            "config": self.config_dir,
            "cache": self.cache_dir,
            "log": self.log_dir,
            "state": self.state_dir,
            "venvs": self.venvs_dir,
        }
        for name, p in dirs.items():
            p.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                try:
                    p.chmod(0o700)
                except OSError:
                    pass
        return dirs

    def migrate_from_legacy(self, legacy_root: Path | None = None) -> dict[str, Any]:
        """Non-destructive migration from legacy ~/.living_assistant path."""
        legacy = legacy_root or (Path.home() / ".living_assistant")
        if not legacy.exists() or not legacy.is_dir():
            return {
                "status": "skipped",
                "reason": "no_legacy_directory",
                "legacy_root": str(legacy),
                "migrated": [],
            }

        target_data = self.data_dir
        target_data.mkdir(parents=True, exist_ok=True)
        migrated: list[str] = []

        try:
            for item in legacy.iterdir():
                dest = target_data / item.name
                if not dest.exists():
                    if item.is_file():
                        shutil.copy2(item, dest)
                        migrated.append(item.name)
                    elif item.is_dir():
                        shutil.copytree(item, dest)
                        migrated.append(f"{item.name}/")
            return {
                "status": "completed",
                "legacy_root": str(legacy),
                "dest_root": str(target_data),
                "migrated": migrated,
            }
        except Exception as e:
            logger.warning("Error migrating legacy data from %s: %s", legacy, e)
            return {
                "status": "error",
                "error": str(e),
                "legacy_root": str(legacy),
                "migrated": migrated,
            }


class UVEnvironmentManager:
    """Manages isolated virtual environments using uv (preferred) or python -m venv (fallback)."""

    def __init__(self, paths: PlatformPaths | None = None, uv_binary: str | None = None) -> None:
        self.paths = paths or PlatformPaths()
        self._custom_uv = uv_binary

    @property
    def uv_path(self) -> str | None:
        return shutil.which(self._custom_uv or "uv")

    @property
    def has_uv(self) -> bool:
        return self.uv_path is not None

    @property
    def backend(self) -> str:
        return "uv" if self.has_uv else "venv"

    def status(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "has_uv": self.has_uv,
            "uv_binary": self.uv_path,
            "venvs_dir": str(self.paths.venvs_dir),
            "data_dir": str(self.paths.data_dir),
            "cache_dir": str(self.paths.cache_dir),
        }

    def _resolve_env_dir(self, name_or_path: str | Path) -> Path:
        p = Path(name_or_path)
        if p.is_absolute():
            return p
        return self.paths.venvs_dir / p

    def get_python_executable(self, env_dir: Path) -> Path:
        """Find the python executable in a virtual environment."""
        if os.name == "nt":
            cand = env_dir / "Scripts" / "python.exe"
            if cand.exists():
                return cand
            cand_alt = env_dir / "python.exe"
            if cand_alt.exists():
                return cand_alt
        else:
            cand = env_dir / "bin" / "python"
            if cand.exists():
                return cand
            cand_alt = env_dir / "bin" / "python3"
            if cand_alt.exists():
                return cand_alt
        # Default expected path even if not created yet
        return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def create_environment(
        self,
        name_or_path: str | Path,
        python_executable: str | None = None,
        timeout: float = 60.0,
    ) -> Path:
        """Create a dedicated, isolated virtual environment."""
        env_dir = self._resolve_env_dir(name_or_path)
        if (env_dir / "pyvenv.cfg").exists():
            return env_dir

        env_dir.parent.mkdir(parents=True, exist_ok=True)
        uv = self.uv_path

        if uv:
            cmd = [uv, "venv", str(env_dir)]
            if python_executable:
                cmd.extend(["--python", python_executable])
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            if res.returncode != 0:
                raise RuntimeError(f"Failed to create virtual environment via uv: {res.stderr.strip()}")
        else:
            py = python_executable or sys.executable
            cmd = [py, "-m", "venv", str(env_dir)]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            if res.returncode != 0:
                raise RuntimeError(f"Failed to create virtual environment via venv: {res.stderr.strip()}")

        return env_dir

    def install(
        self,
        env_dir: Path,
        packages: list[str],
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Install packages into the virtual environment safely."""
        # Validate package specifiers first
        for pkg in packages:
            if not _SAFE_PACKAGE_RE.match(pkg.strip()):
                return {
                    "ok": False,
                    "error": f"Invalid or disallowed package specifier: {pkg}",
                    "stdout": "",
                    "stderr": "",
                    "timeout": False,
                }

        env_dir = self._resolve_env_dir(env_dir)
        py_exe = self.get_python_executable(env_dir)
        if not py_exe.exists():
            return {
                "ok": False,
                "error": f"Environment python not found at {py_exe}",
                "stdout": "",
                "stderr": "",
                "timeout": False,
            }

        uv = self.uv_path
        if uv:
            cmd = [uv, "pip", "install", "--python", str(py_exe), *packages]
        else:
            cmd = [str(py_exe), "-m", "pip", "install", *packages]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            return {
                "ok": res.returncode == 0,
                "returncode": res.returncode,
                "stdout": redact_secrets(res.stdout),
                "stderr": redact_secrets(res.stderr),
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Installation timed out",
                "timeout": True,
            }
        except Exception as e:
            return {
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "timeout": False,
            }

    def run(
        self,
        env_dir: Path,
        command: list[str],
        timeout: float = 60.0,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
        max_output_chars: int = 65536,
    ) -> dict[str, Any]:
        """Execute a command inside the isolated virtual environment."""
        env_dir = self._resolve_env_dir(env_dir)
        py_exe = self.get_python_executable(env_dir)
        if not py_exe.exists():
            return {
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Virtualenv python not found: {py_exe}",
                "timeout": False,
            }

        exec_cmd = list(command)
        if not exec_cmd:
            return {
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Empty command provided",
                "timeout": False,
            }

        # Substitute python if invoked
        if exec_cmd[0] in ("python", "python3", "py"):
            exec_cmd[0] = str(py_exe)
        else:
            # Check if command is a script inside venv bin/Scripts
            script_dir = env_dir / ("Scripts" if os.name == "nt" else "bin")
            cand = script_dir / exec_cmd[0]
            if cand.exists():
                exec_cmd[0] = str(cand)
            elif os.name == "nt":
                cand_exe = script_dir / f"{exec_cmd[0]}.exe"
                if cand_exe.exists():
                    exec_cmd[0] = str(cand_exe)

        # Build clean environment scrubbed of sensitive secrets
        run_env = {}
        for k, v in os.environ.items():
            k_upper = k.upper()
            if any(s in k_upper for s in _SENSITIVE_ENV_KEYS):
                continue
            run_env[k] = v

        script_dir = env_dir / ("Scripts" if os.name == "nt" else "bin")
        path_var = os.environ.get("PATH", "")
        run_env["PATH"] = f"{script_dir}{os.pathsep}{path_var}"
        run_env["VIRTUAL_ENV"] = str(env_dir)
        run_env["PYTHONUNBUFFERED"] = "1"

        if extra_env:
            run_env.update(extra_env)

        try:
            res = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                env=run_env,
                shell=False,
            )
            stdout = redact_secrets(res.stdout, max_chars=max_output_chars)
            stderr = redact_secrets(res.stderr, max_chars=max_output_chars)
            return {
                "ok": res.returncode == 0,
                "returncode": res.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "timeout": True,
            }
        except Exception as e:
            return {
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "timeout": False,
            }

    def run_ephemeral(
        self,
        packages: list[str],
        command: list[str],
        timeout: float = 120.0,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a command with ephemeral dependencies.

        Uses `uv run --with <pkg> ...` when uv is available for zero startup overhead.
        Otherwise falls back to an on-demand cached virtual environment.
        """
        uv = self.uv_path
        if uv:
            cmd = [uv, "run"]
            for pkg in packages:
                if not _SAFE_PACKAGE_RE.match(pkg.strip()):
                    return {
                        "ok": False,
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"Invalid package specifier: {pkg}",
                        "timeout": False,
                    }
                cmd.extend(["--with", pkg.strip()])
            cmd.extend(command)

            run_env = {}
            for k, v in os.environ.items():
                if any(s in k.upper() for s in _SENSITIVE_ENV_KEYS):
                    continue
                run_env[k] = v
            if extra_env:
                run_env.update(extra_env)

            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cwd) if cwd else None,
                    env=run_env,
                    shell=False,
                )
                return {
                    "ok": res.returncode == 0,
                    "returncode": res.returncode,
                    "stdout": redact_secrets(res.stdout),
                    "stderr": redact_secrets(res.stderr),
                    "timeout": False,
                }
            except subprocess.TimeoutExpired:
                return {
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Ephemeral execution timed out after {timeout}s",
                    "timeout": True,
                }
            except Exception as e:
                return {
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "timeout": False,
                }

        # Fallback: Hash package set to reuse an isolated virtualenv in cache_dir
        pkg_key = hashlib.sha256(",".join(sorted(packages)).encode("utf-8")).hexdigest()[:12]
        env_path = self.paths.cache_dir / "ephemeral_venvs" / f"env_{pkg_key}"
        if not (env_path / "pyvenv.cfg").exists():
            self.create_environment(env_path, timeout=timeout)
            if packages:
                inst_res = self.install(env_path, packages, timeout=timeout)
                if not inst_res["ok"]:
                    return inst_res

        return self.run(env_path, command, timeout=timeout, cwd=cwd, extra_env=extra_env)


_default_paths: PlatformPaths | None = None
_default_manager: UVEnvironmentManager | None = None


def get_platform_paths() -> PlatformPaths:
    global _default_paths
    if _default_paths is None:
        _default_paths = PlatformPaths()
        _default_paths.ensure_dirs()
    return _default_paths


def get_environment_manager() -> UVEnvironmentManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = UVEnvironmentManager(get_platform_paths())
    return _default_manager
