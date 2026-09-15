from __future__ import annotations
from pathlib import Path
import json
from .base import Tool
from ..workspace import Workspace
from ..config import data_dir

def detect_project(path: Path) -> dict:
    found = []
    commands = []
    if (path / "package.json").exists():
        found.append("node")
        try:
            pkg = json.loads((path / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "dev" in scripts: commands.append("npm run dev")
            elif "start" in scripts: commands.append("npm start")
        except Exception:
            pass
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        found.append("python")
    if (path / "docker-compose.yml").exists() or (path / "compose.yml").exists() or (path / "compose.yaml").exists():
        found.append("docker-compose")
        commands.append("docker compose up")
    if (path / "pom.xml").exists():
        found.append("maven"); commands.append("mvn spring-boot:run")
    if (path / "gradlew").exists() or (path / "gradlew.bat").exists():
        found.append("gradle"); commands.append("./gradlew bootRun")
    if (path / "go.mod").exists():
        found.append("go"); commands.append("go run .")
    if (path / "Cargo.toml").exists():
        found.append("rust"); commands.append("cargo run")
    return {"path": str(path), "types": found, "suggested_commands": commands}

class ProjectRegistry:
    def __init__(self):
        self.path = data_dir() / "projects.json"
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, name: str, path: str):
        data = self._load(); data[name] = str(Path(path).expanduser().resolve())
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data[name]

    def list(self):
        return self._load()

    def get(self, name: str):
        return self._load().get(name)

def build_project_tools(workspace: Workspace, registry: ProjectRegistry) -> list[Tool]:
    def project_detect(path: str = "."):
        return detect_project(workspace.resolve(path))

    def project_get(name: str):
        p = registry.get(name)
        if not p: return {"found": False}
        # Registered projects still must fall under approved roots.
        return {"found": True, **detect_project(workspace.resolve(p))}

    return [
        Tool("project_detect", "Detect project type and likely start commands in a workspace directory.",
             {"type":"object","properties":{"path":{"type":"string","default":"."}}}, project_detect),
        Tool("project_get", "Get a registered project and detect how it can be run.",
             {"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}, project_get),
    ]
