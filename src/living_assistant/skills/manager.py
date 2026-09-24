from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from living_assistant.core.approval import ApprovalManager
from living_assistant.core.workspace import Workspace
from living_assistant.skills.creator import SkillCreator
from living_assistant.skills.examples import (
    get_daily_briefing_manifest,
    get_downloads_organizer_manifest,
    get_invoice_organizer_manifest,
)
from living_assistant.skills.manifest import SkillManifest
from living_assistant.skills.package import SkillPackage, default_skills_dir
from living_assistant.skills.runner import SkillExecutor
from living_assistant.skills.store import SkillStore
from living_assistant.tools.registry import ToolRegistry


class SkillManager:
    """Authoritative lifecycle and execution orchestrator for custom and built-in skills."""

    def __init__(
        self,
        workspace: Workspace,
        tool_registry: ToolRegistry,
        skills_dir: Path | None = None,
        store: SkillStore | None = None,
        approval_manager: ApprovalManager | None = None,
        notifier: Any = None,
        model_manager: Any = None,
    ):
        self.workspace = workspace
        self.tool_registry = tool_registry
        self.skills_dir = skills_dir or default_skills_dir()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.store = store or SkillStore()
        self.approval = approval_manager
        self.notifier = notifier
        self.model_manager = model_manager

        self.creator = SkillCreator(tool_registry, self.store, model_manager=model_manager, skills_dir=self.skills_dir)
        self.executor = SkillExecutor(tool_registry, self.store, workspace, approval_manager=approval_manager, notifier=notifier)

        self._seed_builtins_if_needed()

    def _seed_builtins_if_needed(self):
        """Seed the 3 working reference skills if not already present."""
        reference_defs = [
            get_daily_briefing_manifest(),
            get_downloads_organizer_manifest(),
            get_invoice_organizer_manifest(),
        ]
        for manifest in reference_defs:
            lifecycle = self.store.get_lifecycle(manifest.id)
            if not lifecycle:
                p_dir = self.skills_dir / manifest.id
                skill_md = f"# {manifest.name}\n\n{manifest.description}\n"
                pkg = SkillPackage(root=p_dir, manifest=manifest, skill_md=skill_md)
                pkg.save()
                # Builtins start as ACTIVE
                self.store.register_skill(manifest, skill_md, initial_state="ACTIVE", snapshot_dir=str(p_dir))
                # Seed approval record for built-in reference skills
                h = manifest.permissions.permission_hash()
                self.store.approve_skill(manifest.id, "builtin_preapproved", manifest.version, h)

    def list_skills(self, state: str | None = None) -> list[dict[str, Any]]:
        records = self.store.list_skills(state=state)
        out = []
        for r in records:
            skill_id = r["skill_id"]
            p_dir = self.skills_dir / skill_id
            if p_dir.exists() and (p_dir / "manifest.json").exists():
                try:
                    pkg = SkillPackage.load(p_dir)
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

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        lifecycle = self.store.get_lifecycle(skill_id)
        if not lifecycle:
            return None
        p_dir = self.skills_dir / skill_id
        manifest_data = {}
        skill_md = ""
        if p_dir.exists() and (p_dir / "manifest.json").exists():
            pkg = SkillPackage.load(p_dir)
            manifest_data = pkg.manifest.model_dump()
            skill_md = pkg.skill_md
        versions = self.store.get_versions(skill_id)
        executions = self.store.get_executions(skill_id=skill_id, limit=10)
        return {
            "lifecycle": lifecycle,
            "manifest": manifest_data,
            "skill_md": skill_md,
            "versions": versions,
            "recent_executions": executions,
        }

    def create_draft(self, prompt: str) -> SkillPackage:
        return self.creator.create_draft(prompt)

    def update_skill(self, skill_id: str, manifest_data: dict, skill_md: str) -> SkillPackage:
        manifest = SkillManifest.from_json(manifest_data)
        if manifest.id != skill_id:
            raise ValueError(f"Manifest ID '{manifest.id}' does not match target skill_id '{skill_id}'")

        # Increment semantic version patch if not changed
        current = self.store.get_lifecycle(skill_id)
        if current and current["current_version"] == manifest.version:
            parts = manifest.version.split(".")
            if len(parts) == 3 and parts[2].isdigit():
                manifest.version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

        target_dir = self.skills_dir / skill_id
        pkg = SkillPackage(root=target_dir, manifest=manifest, skill_md=skill_md)
        pkg.save()

        # Invalidate approvals because content changed
        self.store.save_version(skill_id, manifest, skill_md, snapshot_dir=str(target_dir))
        self.store.invalidate_approval(skill_id)
        return pkg

    def activate_skill(self, skill_id: str) -> dict[str, Any]:
        p_dir = self.skills_dir / skill_id
        if not p_dir.exists():
            raise ValueError(f"Skill '{skill_id}' not found.")

        pkg = SkillPackage.load(p_dir)
        manifest = pkg.manifest
        perm_hash = manifest.permissions.permission_hash()
        pkg_hash = pkg.deterministic_hash()

        # Create immutable version snapshot
        snap_dir = pkg.create_snapshot(self.skills_dir / "_snapshots")

        # Check / create approval
        approval_id = f"appr_skill_{skill_id}_{manifest.version}"
        self.store.approve_skill(
            skill_id,
            approval_id,
            manifest.version,
            perm_hash,
            package_hash=pkg_hash,
            snapshot_dir=str(snap_dir),
        )
        self.store.set_state(skill_id, "ACTIVE")
        return {
            "ok": True,
            "state": "ACTIVE",
            "skill_id": skill_id,
            "version": manifest.version,
            "package_hash": pkg_hash,
            "snapshot_dir": str(snap_dir),
        }

    def disable_skill(self, skill_id: str) -> bool:
        return self.store.set_state(skill_id, "DISABLED")

    def archive_skill(self, skill_id: str) -> bool:
        return self.store.set_state(skill_id, "ARCHIVED")

    def rollback_skill(self, skill_id: str, target_version: str) -> SkillPackage:
        manifest, skill_md = self.store.rollback_version(skill_id, target_version)
        target_dir = self.skills_dir / skill_id
        pkg = SkillPackage(root=target_dir, manifest=manifest, skill_md=skill_md)
        pkg.save()
        return pkg

    def export_skill(self, skill_id: str) -> bytes:
        p_dir = self.skills_dir / skill_id
        if not p_dir.exists():
            raise FileNotFoundError(f"Skill directory not found for {skill_id}")
        pkg = SkillPackage.load(p_dir)
        return pkg.export_zip()

    def import_skill_archive(self, archive_bytes: bytes) -> SkillPackage:
        pkg = SkillPackage.import_zip(archive_bytes, target_parent_dir=self.skills_dir)
        # Register as untrusted DRAFT
        self.store.register_skill(pkg.manifest, pkg.skill_md, initial_state="DRAFT", snapshot_dir=str(pkg.root))
        return pkg

    def execute_skill(self, skill_id: str, inputs: dict | None = None, dry_run: bool = False,
                      trigger: str = "manual") -> dict[str, Any]:
        p_dir = self.skills_dir / skill_id
        if not p_dir.exists():
            raise FileNotFoundError(f"Skill '{skill_id}' package directory not found.")
        pkg = SkillPackage.load(p_dir)
        pkg_hash = pkg.deterministic_hash()

        # Enforce that non-dry-run execution requires skill to be ACTIVE
        lifecycle = self.store.get_lifecycle(skill_id)
        state = lifecycle.get("state") if lifecycle else "DRAFT"

        if not dry_run and state != "ACTIVE":
            raise PermissionError(
                f"Skill '{skill_id}' is currently '{state}'. You must review and activate the skill before running with live disk modifications (or run in dry-run mode)."
            )

        # Integrity check: if active, verify files haven't been mutated since approval
        if state == "ACTIVE":
            perm_hash = pkg.manifest.permissions.permission_hash()
            if not self.store.is_approved(skill_id, pkg.manifest.version, perm_hash, pkg_hash):
                self.store.invalidate_approval(skill_id)
                raise PermissionError(
                    f"Skill '{skill_id}' has been modified on disk since approval was granted. Approval is invalidated; please review and re-activate."
                )
            snap_dir = lifecycle.get("snapshot_dir")
            if snap_dir and Path(snap_dir).exists():
                pkg = SkillPackage.load(Path(snap_dir))

        return self.executor.execute(pkg.manifest, inputs=inputs, dry_run=dry_run, trigger=trigger, package_hash=pkg_hash)

    def undo_execution(self, run_id: str) -> dict[str, Any]:
        """Revert side-effects recorded for a completed execution run."""
        records = self.store.get_undo_actions(run_id)
        if not records:
            return {"ok": False, "error": f"No undo records found for run {run_id}."}

        adapter = self.executor.execute.__func__.__globals__["PortableToolAdapter"](
            self.workspace,
            guard=None,
            dry_run=False,
            notifier=self.notifier,
        )
        reverted = []
        conflicts = []
        for r in records:
            rev_res = adapter.undo_action(r["reverse_data"])
            if rev_res.get("ok"):
                reverted.append(rev_res)
            else:
                conflicts.append(rev_res)

        return {
            "ok": len(conflicts) == 0,
            "reverted": reverted,
            "conflicts": conflicts,
            "run_id": run_id,
        }

    def reconcile_execution(self, run_id: str) -> dict[str, Any]:
        """Reconcile actions for an interrupted run."""
        return self.store.reconcile_interrupted_run(run_id)

    def match_active_skills(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        """Match user text against active skill triggers."""
        low = text.lower()
        active = self.list_skills(state="ACTIVE")
        scored = []
        for item in active:
            triggers = item.get("triggers", [])
            score = sum(1 for t in triggers if t and t.lower() in low)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:limit]]

    def get_orchestrator_summary(self) -> str:
        """Compact summary of active skills to expose to the Orchestrator without blowing prompt context."""
        active = self.list_skills(state="ACTIVE")
        if not active:
            return ""
        lines = ["[AVAILABLE USER SKILLS]"]
        for s in active:
            m = s.get("manifest") or {}
            triggers = ", ".join(s.get("triggers", []))
            lines.append(f"- {s['name']} (id: {s['skill_id']}, version: {s.get('current_version', '1.0.0')}): {s.get('description', '')} [Triggers: {triggers}]")
        return "\n".join(lines)
