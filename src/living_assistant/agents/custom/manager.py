from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from living_assistant.agents.custom.creator import AgentCreator
from living_assistant.agents.custom.delegation import AgentDelegationCoordinator
from living_assistant.agents.custom.examples import (
    get_file_assistant_manifest,
    get_planner_agent_manifest,
    get_research_agent_manifest,
)
from living_assistant.agents.custom.manifest import AgentManifest
from living_assistant.agents.custom.package import AgentPackage
from living_assistant.agents.custom.runner import AgentExecutor
from living_assistant.agents.custom.store import AgentStore
from living_assistant.core.config import data_dir
from living_assistant.tools.registry import ToolRegistry


def default_agents_dir() -> Path:
    return data_dir() / "agents"


class AgentManager:
    """Coordinates custom agent creation, lifecycle management, storage, and execution."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        store: AgentStore | None = None,
        skills_manager: Any = None,
        agents_dir: Path | None = None,
        model_manager: Any = None,
        system_memory: Any = None,
    ):
        self.tool_registry = tool_registry
        self.store = store or AgentStore()
        self.skills_manager = skills_manager
        self.agents_dir = Path(agents_dir or default_agents_dir()).expanduser().resolve()
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.model_manager = model_manager
        self.system_memory = system_memory

        self.delegation_coordinator = AgentDelegationCoordinator()
        self.creator = AgentCreator(
            tool_registry=tool_registry,
            store=self.store,
            skills_manager=skills_manager,
            agents_dir=self.agents_dir,
            model_manager=model_manager,
        )
        self.executor = AgentExecutor(
            tool_registry=tool_registry,
            agent_store=self.store,
            skills_manager=skills_manager,
            model_manager=model_manager,
            delegation_coordinator=self.delegation_coordinator,
            system_memory=system_memory,
        )

        self._seed_builtins_if_needed()

    def _seed_builtins_if_needed(self):
        """Seed the 3 working reference agents if not already present."""
        reference_defs = [
            get_research_agent_manifest(),
            get_file_assistant_manifest(),
            get_planner_agent_manifest(),
        ]
        for manifest in reference_defs:
            lifecycle = self.store.get_lifecycle(manifest.id)
            if not lifecycle:
                p_dir = self.agents_dir / manifest.id
                agent_md = f"# {manifest.name}\n\n{manifest.description}\n"
                pkg = AgentPackage(root=p_dir, manifest=manifest, agent_md=agent_md)
                pkg.save()
                # Builtins start as ACTIVE
                pkg_hash = pkg.deterministic_hash()
                self.store.register_agent(manifest, agent_md, initial_state="ACTIVE", package_hash=pkg_hash, snapshot_dir=str(p_dir))
                h = manifest.permission_hash()
                self.store.approve_agent(manifest.id, "builtin_preapproved", manifest.version, h, package_hash=pkg_hash, snapshot_dir=str(p_dir))

    def list_agents(self, state: str | None = None) -> list[dict[str, Any]]:
        records = self.store.list_agents(state=state)
        out = []
        for r in records:
            agent_id = r["agent_id"]
            p_dir = self.agents_dir / agent_id
            if p_dir.exists() and (p_dir / "manifest.json").exists():
                try:
                    pkg = AgentPackage.load(p_dir)
                    out.append({
                        **r,
                        "manifest": pkg.manifest.model_dump(),
                        "triggers": pkg.manifest.triggers,
                        "description": pkg.manifest.description,
                        "name": pkg.manifest.name,
                    })
                    continue
                except Exception:
                    pass
            out.append(r)
        return out

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        lifecycle = self.store.get_lifecycle(agent_id)
        if not lifecycle:
            return None
        p_dir = self.agents_dir / agent_id
        manifest_data = {}
        agent_md = ""
        if p_dir.exists() and (p_dir / "manifest.json").exists():
            pkg = AgentPackage.load(p_dir)
            manifest_data = pkg.manifest.model_dump()
            agent_md = pkg.agent_md
        versions = self.store.get_versions(agent_id)
        executions = self.store.get_executions(agent_id=agent_id, limit=10)
        return {
            "lifecycle": lifecycle,
            "manifest": manifest_data,
            "agent_md": agent_md,
            "versions": versions,
            "recent_executions": executions,
        }

    def create_draft(self, prompt: str, form_data: dict[str, Any] | None = None) -> AgentPackage:
        return self.creator.create_draft(prompt, form_data=form_data)

    def update_agent(self, agent_id: str, manifest_data: dict[str, Any], agent_md: str) -> AgentPackage:
        manifest = AgentManifest.from_json(manifest_data)
        if manifest.id != agent_id:
            raise ValueError(f"Manifest ID '{manifest.id}' does not match target agent_id '{agent_id}'")

        p_dir = self.agents_dir / agent_id
        pkg = AgentPackage(root=p_dir, manifest=manifest, agent_md=agent_md)
        pkg.save()

        # Any disk update puts the agent into DRAFT state until re-approved
        self.store.register_agent(manifest, agent_md, initial_state="DRAFT")
        return pkg

    def activate_agent(self, agent_id: str) -> dict[str, Any]:
        p_dir = self.agents_dir / agent_id
        if not p_dir.exists():
            raise ValueError(f"Agent '{agent_id}' not found.")

        pkg = AgentPackage.load(p_dir)
        manifest = pkg.manifest
        perm_hash = manifest.permission_hash()
        pkg_hash = pkg.deterministic_hash()

        # Create immutable version snapshot
        snap_dir = pkg.create_snapshot(self.agents_dir / "_snapshots")

        # Record approval
        approval_id = f"appr_agent_{agent_id}_{manifest.version}"
        self.store.approve_agent(
            agent_id,
            approval_id,
            manifest.version,
            perm_hash,
            package_hash=pkg_hash,
            snapshot_dir=str(snap_dir),
        )
        self.store.set_state(agent_id, "ACTIVE")
        return {
            "ok": True,
            "state": "ACTIVE",
            "agent_id": agent_id,
            "version": manifest.version,
            "package_hash": pkg_hash,
            "snapshot_dir": str(snap_dir),
        }

    def disable_agent(self, agent_id: str) -> dict[str, Any]:
        self.store.set_state(agent_id, "DISABLED")
        return {"ok": True, "state": "DISABLED", "agent_id": agent_id}

    def archive_agent(self, agent_id: str) -> dict[str, Any]:
        self.store.set_state(agent_id, "ARCHIVED")
        return {"ok": True, "state": "ARCHIVED", "agent_id": agent_id}

    def execute_agent(
        self,
        agent_id: str,
        task: str,
        context: str = "",
        inputs: dict[str, Any] | None = None,
        dry_run: bool = False,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        p_dir = self.agents_dir / agent_id
        if not p_dir.exists():
            raise ValueError(f"Agent '{agent_id}' not found on disk.")

        pkg = AgentPackage.load(p_dir)
        current_hash = pkg.deterministic_hash()

        # Check if active agent was edited on disk
        lifecycle = self.store.get_lifecycle(agent_id)
        if lifecycle and lifecycle.get("state") == "ACTIVE":
            stored_hash = lifecycle.get("approved_package_hash")
            if stored_hash and stored_hash != current_hash:
                self.store.set_state(agent_id, "DRAFT")
                raise PermissionError(
                    f"Agent '{agent_id}' was modified on disk since approval (Hash mismatch). "
                    "Reverted to DRAFT state. Please review and re-activate."
                )

        return self.executor.execute(
            manifest=pkg.manifest,
            task=task,
            context=context,
            inputs=inputs,
            dry_run=dry_run,
            package_hash=current_hash,
            session_id=session_id,
        )

    def export_agent(self, agent_id: str, target_zip: Path) -> Path:
        p_dir = self.agents_dir / agent_id
        if not p_dir.exists():
            raise ValueError(f"Agent '{agent_id}' not found.")
        pkg = AgentPackage.load(p_dir)
        return pkg.export_zip(target_zip)

    def import_agent(self, zip_path: Path) -> AgentPackage:
        import tempfile
        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise ValueError("Zip does not contain manifest.json")
            manifest_bytes = zf.read("manifest.json")
            m_data = json.loads(manifest_bytes.decode("utf-8"))
            agent_id = m_data.get("id")
            if not agent_id:
                raise ValueError("Manifest has no id")

        target_dir = self.agents_dir / agent_id
        pkg = AgentPackage.import_zip(zip_path, target_dir)
        self.store.register_agent(pkg.manifest, pkg.agent_md, initial_state="DRAFT")
        return pkg
