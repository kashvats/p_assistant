from __future__ import annotations
from pathlib import Path
import json, time, re
from .base import Tool
from ..workspace import Workspace
from ..config import data_dir
from ..storage_utils import atomic_write_json
from ..security_utils import is_loopback_http_url, redact_secrets

_SECRET_ENV_NAME = re.compile(r'(?i)(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|private[_-]?key|credential)')
_ENV_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def detect_project(path: Path) -> dict:
    found: list[str] = []
    commands: list[str] = []
    tests: list[str] = []
    if (path / "package.json").exists():
        found.append("node")
        try:
            pkg = json.loads((path / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "dev" in scripts:
                commands.append("npm run dev")
            elif "start" in scripts:
                commands.append("npm start")
            if "test" in scripts:
                tests.append("npm test")
        except Exception:
            pass
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        found.append("python")
        if (path / "manage.py").exists():
            commands.append("python manage.py runserver")
        if (path / "pytest.ini").exists() or (path / "tests").exists():
            tests.append("pytest")
    if any((path / n).exists() for n in ("docker-compose.yml", "compose.yml", "compose.yaml")):
        found.append("docker-compose")
        commands.append("docker compose up")
    if (path / "pom.xml").exists():
        found.append("maven")
        commands.append("mvn spring-boot:run")
        tests.append("mvn test")
    if (path / "gradlew").exists() or (path / "gradlew.bat").exists():
        found.append("gradle")
        commands.append("./gradlew bootRun")
        tests.append("./gradlew test")
    if (path / "go.mod").exists():
        found.append("go")
        commands.append("go run .")
        tests.append("go test ./...")
    if (path / "Cargo.toml").exists():
        found.append("rust")
        commands.append("cargo run")
        tests.append("cargo test")
    return {"path": str(path), "types": found, "suggested_commands": commands, "suggested_test_commands": tests}


class ProjectRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "projects.json")
        if not self.path.exists():
            atomic_write_json(self.path, {})
        self._migrate()

    def _load_raw(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict):
        atomic_write_json(self.path, data)

    def _migrate(self):
        data = self._load_raw()
        changed = False
        for name, item in list(data.items()):
            if isinstance(item, str):
                data[name] = {
                    "path": str(Path(item).expanduser().resolve()),
                    "start_command": None,
                    "test_command": None,
                    "auto_restart": False,
                    "max_restarts": 3,
                    "health_url": None,
                    "env": {},
                    "created_at": time.time(),
                }
                changed = True
            elif isinstance(item, dict) and 'env' not in item:
                item['env'] = {}
                changed = True
        if changed:
            self._save(data)

    @staticmethod
    def _clean_env(env: dict | None) -> dict[str,str]:
        clean={}
        for raw_key, raw_value in (env or {}).items():
            key=str(raw_key).strip(); value=str(raw_value)
            if not _ENV_NAME.fullmatch(key):
                raise ValueError(f'Invalid environment variable name: {key}')
            if _SECRET_ENV_NAME.search(key) or redact_secrets(value) != value:
                raise ValueError(f'Secret-like project environment values cannot be stored in projects.json: {key}')
            if len(value) > 4096:
                raise ValueError(f'Environment variable value is too large: {key}')
            clean[key]=value
        return clean

    def add(self, name: str, path: str, start_command: str | None = None,
            test_command: str | None = None, auto_restart: bool = False,
            max_restarts: int = 3, health_url: str | None = None, env: dict | None = None) -> dict:
        data = self._load_raw()
        resolved = Path(path).expanduser().resolve()
        detected = detect_project(resolved)
        if health_url and not is_loopback_http_url(str(health_url)):
            raise ValueError('Project health_url must be a loopback http/https URL.')
        item = {
            "path": str(resolved),
            "start_command": start_command or (detected["suggested_commands"][0] if detected["suggested_commands"] else None),
            "test_command": test_command or (detected["suggested_test_commands"][0] if detected["suggested_test_commands"] else None),
            "auto_restart": bool(auto_restart),
            "max_restarts": max(0, min(int(max_restarts), 20)),
            "health_url": health_url,
            "env": self._clean_env(env),
            "created_at": data.get(name, {}).get("created_at", time.time()) if isinstance(data.get(name), dict) else time.time(),
            "updated_at": time.time(),
        }
        data[name] = item
        self._save(data)
        return {"name": name, **item}

    def update(self, name: str, **changes) -> dict:
        data = self._load_raw()
        if name not in data:
            raise KeyError(name)
        allowed = {"start_command", "test_command", "auto_restart", "max_restarts", "health_url", "env"}
        for k, v in changes.items():
            if k in allowed and v is not None:
                if k == "max_restarts":
                    v = max(0, min(int(v), 20))
                if k == "health_url" and v and not is_loopback_http_url(str(v)):
                    raise ValueError('Project health_url must be a loopback http/https URL.')
                if k == "env":
                    v = self._clean_env(v)
                data[name][k] = v
        data[name]["updated_at"] = time.time()
        self._save(data)
        return {"name": name, **data[name]}

    def list(self) -> dict:
        return self._load_raw()

    def get(self, name: str) -> dict | None:
        item = self._load_raw().get(name)
        return {"name": name, **item} if isinstance(item, dict) else None

    def remove(self, name: str) -> bool:
        data = self._load_raw(); existed = name in data; data.pop(name, None); self._save(data); return existed


def build_project_tools(workspace: Workspace, registry: ProjectRegistry) -> list[Tool]:
    def project_detect(path: str = "."):
        return detect_project(workspace.resolve(path))

    def project_get(name: str):
        item = registry.get(name)
        if not item:
            return {"found": False}
        p = workspace.resolve(item["path"])
        return {"found": True, "project": item, "detected": detect_project(p)}

    return [
        Tool("project_detect", "Detect project type and likely start/test commands in a workspace directory.",
             {"type":"object","properties":{"path":{"type":"string","default":"."}}}, project_detect),
        Tool("project_get", "Get a registered project's approved path, commands, restart policy and detected project type.",
             {"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}, project_get),
    ]
