from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from living_assistant.core.workspace import Workspace
from living_assistant.skills.extractor import DocumentExtractor
from living_assistant.skills.guards import SkillPermissionGuard, SkillPermissionViolation


class PortableToolAdapter:
    """Stable, platform-independent tool interfaces with native dry-run mutation suppression,
    durable action logging, and conflict-aware reversible undo.
    """

    def __init__(
        self,
        workspace: Workspace,
        guard: SkillPermissionGuard | None = None,
        dry_run: bool = False,
        notifier: Any = None,
        store: Any = None,
        run_id: str | None = None,
        skill_id: str | None = None,
        step_id: str | None = None,
    ):
        self.workspace = workspace
        self.guard = guard
        self.dry_run = dry_run
        self.notifier = notifier
        self.store = store
        self.run_id = run_id
        self.skill_id = skill_id or "unknown"
        self.step_id = step_id or "step"
        self.recorded_actions: list[dict[str, Any]] = []

    def set_step_context(self, step_id: str):
        self.step_id = step_id

    def _resolve(self, path: str | Path, for_write: bool = False) -> Path:
        if self.guard:
            return self.guard.validate_path(path, for_write=for_write)
        return self.workspace.resolve(path)

    # ---------------------------------------------------------------------
    # files.list
    # ---------------------------------------------------------------------
    def files_list(self, path: str = ".") -> list[dict[str, Any]]:
        resolved = self._resolve(path, for_write=False)
        items = []
        if not resolved.exists() or not resolved.is_dir():
            return []
        for x in resolved.iterdir():
            try:
                is_file = x.is_file()
                size = x.stat().st_size if is_file else 0
                items.append({
                    "name": x.name,
                    "path": str(x).replace("\\", "/"),
                    "relative_path": str(x.relative_to(self.workspace.roots[0])).replace("\\", "/"),
                    "is_dir": x.is_dir(),
                    "is_file": is_file,
                    "size": size,
                    "extension": x.suffix.lower(),
                })
            except (OSError, PermissionError):
                pass
        return sorted(items, key=lambda z: (not z["is_dir"], z["name"].lower()))

    # ---------------------------------------------------------------------
    # files.read
    # ---------------------------------------------------------------------
    def files_read(self, path: str) -> str:
        resolved = self._resolve(path, for_write=False)
        return resolved.read_text(encoding="utf-8", errors="replace")

    # ---------------------------------------------------------------------
    # files.move (with collision resolution, durable action logging, dry-run preview & undo log)
    # ---------------------------------------------------------------------
    def files_move(self, source: str, destination: str, overwrite: bool = False) -> dict[str, Any]:
        if not source or not destination:
            return {"ok": False, "error": "Source and destination paths must be non-empty", "dry_run": self.dry_run}
        src = self._resolve(source, for_write=False)
        if not src.exists() or src.is_dir():
            return {"ok": False, "error": f"Source file does not exist or is a directory: {source}", "dry_run": self.dry_run}

        dst = self._resolve(destination, for_write=True)

        # Handle directory destination (e.g. moving a file into a folder)
        if dst.is_dir() or str(destination).endswith("/") or str(destination).endswith("\\"):
            final_dst = dst / src.name
        else:
            final_dst = dst

        # Collision avoidance strategy
        resolved_dst = final_dst
        collision_renamed = False
        if resolved_dst.exists() and not overwrite:
            stem = final_dst.stem
            suffix = final_dst.suffix
            counter = 1
            while resolved_dst.exists():
                resolved_dst = final_dst.parent / f"{stem}_{counter}{suffix}"
                counter += 1
            collision_renamed = True

        src_stat = src.stat()
        preconditions = {
            "source_exists": True,
            "source_size": src_stat.st_size,
            "source_mtime": src_stat.st_mtime,
            "destination_existed": final_dst.exists(),
            "collision_renamed": collision_renamed,
        }

        idempotency_key = f"move:{str(src)}->{str(resolved_dst)}:{src_stat.st_size}:{int(src_stat.st_mtime)}"

        action_summary = {
            "action": "move",
            "source": str(src).replace("\\", "/"),
            "destination": str(resolved_dst).replace("\\", "/"),
            "collision_renamed": collision_renamed,
            "dry_run": self.dry_run,
        }

        action_id = None
        if self.store and self.run_id and hasattr(self.store, "record_action_planned"):
            action_id = self.store.record_action_planned(
                run_id=self.run_id,
                skill_id=self.skill_id,
                step_id=self.step_id,
                idempotency_key=idempotency_key,
                operation="files.move",
                preconditions=preconditions,
                target_source=str(src),
                target_destination=str(resolved_dst),
            )

        if self.dry_run:
            self.recorded_actions.append(action_summary)
            if action_id and self.store:
                self.store.record_action_succeeded(action_id, {"dry_run": True, **action_summary})
            return {"ok": True, "dry_run": True, **action_summary}

        # Real execution: mark started in durable store
        if action_id and self.store:
            self.store.record_action_started(action_id)

        try:
            resolved_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(resolved_dst))
        except Exception as exc:
            if action_id and self.store:
                self.store.record_action_failed(action_id, str(exc))
            raise

        # Succeeded: record evidence
        evidence = {
            "destination_created": resolved_dst.exists(),
            "destination_size": resolved_dst.stat().st_size if resolved_dst.exists() else 0,
            "source_removed": not src.exists(),
        }
        if action_id and self.store:
            self.store.record_action_succeeded(action_id, evidence)

        # Record for reversible undo with expected metadata
        undo_record = {
            "type": "files.move",
            "source": str(resolved_dst).replace("\\", "/"),  # To reverse: current location
            "destination": str(src).replace("\\", "/"),       # original location
            "expected_size": src_stat.st_size,
            "expected_mtime": src_stat.st_mtime,
        }
        self.recorded_actions.append({**action_summary, "undo": undo_record})
        return {"ok": True, "dry_run": False, **action_summary}

    # ---------------------------------------------------------------------
    # files.write
    # ---------------------------------------------------------------------
    def files_write(self, path: str, content: str) -> dict[str, Any]:
        dst = self._resolve(path, for_write=True)
        if self.dry_run:
            return {"ok": True, "dry_run": True, "path": str(dst).replace("\\", "/"), "bytes": len(content)}
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        return {"ok": True, "dry_run": False, "path": str(dst).replace("\\", "/"), "bytes": len(content)}

    # ---------------------------------------------------------------------
    # documents.extract
    # ---------------------------------------------------------------------
    def documents_extract(self, path: str) -> dict[str, Any]:
        if not path or not path.strip():
            return {
                "ok": False,
                "error": "No file path provided for document extraction",
                "vendor": "Unknown",
                "vendor_clean": "Unknown",
                "date": None,
                "amount": None,
                "subtotal": None,
                "tax": None,
                "total": None,
                "currency": "USD",
                "year_month": "unknown-date",
                "needs_review": True,
                "review_reasons": ["Empty document path provided"],
            }
        p = self._resolve(path, for_write=False)
        return DocumentExtractor.extract_invoice_fields(p)

    # ---------------------------------------------------------------------
    # notifications.show
    # ---------------------------------------------------------------------
    def notifications_show(self, title: str, message: str) -> dict[str, Any]:
        if self.dry_run:
            return {"ok": True, "dry_run": True, "title": title, "message": message}
        if self.notifier:
            try:
                self.notifier.send(title, message)
            except Exception:
                pass
        return {"ok": True, "title": title, "message": message}

    # ---------------------------------------------------------------------
    # Reversal / Undo helper with conflict and permission checks
    # ---------------------------------------------------------------------
    def undo_action(self, reverse_data: dict[str, Any]) -> dict[str, Any]:
        act_type = reverse_data.get("type")
        if act_type == "files.move":
            src = Path(reverse_data["source"]).resolve()
            dst = Path(reverse_data["destination"]).resolve()

            # Recheck current permissions for both paths
            try:
                self._resolve(src, for_write=False)
                self._resolve(dst, for_write=True)
            except Exception as perm_exc:
                return {"ok": False, "error": f"Permission check failed during undo: {perm_exc}"}

            if not src.exists():
                return {"ok": False, "error": f"File no longer exists at moved location to revert: {src}"}

            # Detect later edits
            expected_size = reverse_data.get("expected_size")
            if expected_size is not None and src.stat().st_size != expected_size:
                return {
                    "ok": False,
                    "conflict": True,
                    "error": f"File at {src} has been modified since it was moved (size changed from {expected_size} to {src.stat().st_size}). Reversal aborted to protect user edits.",
                }

            # Detect occupied original location
            if dst.exists():
                return {
                    "ok": False,
                    "conflict": True,
                    "error": f"Original destination {dst} is now occupied by another file. Automatic overwrite prevented.",
                }

            # Clean reversal
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {"ok": True, "reverted": f"Moved {src.name} back to {dst}"}

        return {"ok": False, "error": f"Unsupported undo action: {act_type}"}
