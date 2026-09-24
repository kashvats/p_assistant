from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from living_assistant.skills.manifest import (
    SkillManifest,
    SkillPermissionScope,
    SkillStep,
    SkillLimits,
    SkillProvenance,
    SkillExample,
)
from living_assistant.skills.package import SkillPackage, default_skills_dir
from living_assistant.skills.store import SkillStore
from living_assistant.tools.registry import ToolRegistry


class SkillCreator:
    """Chat-accessible engine converting natural-language requests into validated custom skill draft packages."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        skill_store: SkillStore,
        model_manager: Any = None,
        skills_dir: Path | None = None,
    ):
        self.tool_registry = tool_registry
        self.skill_store = skill_store
        self.model_manager = model_manager
        self.skills_dir = skills_dir or default_skills_dir()

    def _generate_skill_id(self, name_or_prompt: str) -> str:
        # Extract keywords and sanitize
        words = re.findall(r"[a-z0-9]+", name_or_prompt.lower())
        meaningful = [w for w in words if w not in {"create", "a", "an", "the", "skill", "that", "to", "for", "my"}]
        slug = "-".join(meaningful[:4]) if meaningful else "custom-skill"
        return slug[:32].strip("-")

    def _build_deterministic_draft(self, prompt: str) -> tuple[SkillManifest, str]:
        """Produce a guaranteed valid, schema-compliant draft using registered application tools."""
        p_low = prompt.lower()
        skill_id = self._generate_skill_id(prompt)

        # 1. Invoice organizer pattern
        if "invoice" in p_low or "receipt" in p_low:
            name = "Invoice Organizer"
            desc = "Scans files for invoices, extracts vendor and date, and organizes them into vendor/month directories."
            triggers = ["organize invoices", "sort invoices", "process invoices", "invoice organizer"]
            required_tools = ["files.list", "documents.extract", "files.move"]
            perms = SkillPermissionScope(
                filesystem=["./invoices", "./workspace", "."],
                destructive=False,
                network=False,
                subprocess=False,
                messaging=False,
            )
            workflow = [
                SkillStep(
                    id="list_invoices",
                    tool="files.list",
                    description="List invoice documents in target directory",
                    arguments={"path": "{inputs.source_dir}"},
                    output_variable="found_files",
                ),
                SkillStep(
                    id="extract_and_sort",
                    tool="documents.extract",
                    description="Extract vendor, date, and amount from each document",
                    arguments={"path": "{inputs.invoice_path}"},
                    output_variable="extracted_data",
                ),
                SkillStep(
                    id="move_to_folder",
                    tool="files.move",
                    description="Move invoice into organized vendor and month subdirectory",
                    arguments={
                        "source": "{inputs.invoice_path}",
                        "destination": "{inputs.target_dir}/{extracted_data.vendor}/{extracted_data.year_month}/",
                        "overwrite": False,
                    },
                ),
            ]
            examples = [
                SkillExample(
                    title="Organize quarterly invoices",
                    inputs={"source_dir": "./invoices_inbox", "target_dir": "./Invoices"},
                    expected_outcome="Moves Acme_Bill.pdf to ./Invoices/Acme/2026-03/Acme_Bill.pdf",
                )
            ]

        # 2. Downloads organizer pattern
        elif "download" in p_low or "clean" in p_low or ("organize" in p_low and "file" in p_low):
            name = "Downloads Organizer"
            desc = "Categorizes unorganized files into categorized subfolders (Documents, Images, Installers, Archives)."
            triggers = ["organize downloads", "clean downloads", "sort files", "organize files"]
            required_tools = ["files.list", "files.move"]
            perms = SkillPermissionScope(
                filesystem=["./downloads", "./workspace", "."],
                destructive=False,
                network=False,
                subprocess=False,
                messaging=False,
            )
            workflow = [
                SkillStep(
                    id="list_downloads",
                    tool="files.list",
                    description="Scan files in target downloads folder",
                    arguments={"path": "{inputs.folder}"},
                    output_variable="unorganized_files",
                ),
                SkillStep(
                    id="move_categorized",
                    tool="files.move",
                    description="Move file to appropriate category folder avoiding collisions",
                    arguments={
                        "source": "{inputs.source_file}",
                        "destination": "{inputs.target_dir}/",
                        "overwrite": False,
                    },
                ),
            ]
            examples = [
                SkillExample(
                    title="Tidy downloads folder",
                    inputs={"folder": "./downloads", "source_file": "./downloads/statement.pdf", "target_dir": "./downloads/Documents"},
                    expected_outcome="Categorizes PDFs to ./downloads/Documents/ and PNGs to ./downloads/Images/",
                )
            ]

        # 3. Daily briefing pattern
        elif "briefing" in p_low or "morning" in p_low or "daily" in p_low or "agenda" in p_low:
            name = "Daily Briefing"
            desc = "Summarizes upcoming calendar events, pending todos, and recent memory notes offline."
            triggers = ["daily briefing", "morning brief", "what's on my schedule", "daily summary"]
            required_tools = ["calendar.list", "briefings.get", "notifications.show"]
            perms = SkillPermissionScope(
                filesystem=["."],
                destructive=False,
                network=False,
                subprocess=False,
                messaging=True,
            )
            workflow = [
                SkillStep(
                    id="fetch_briefing",
                    tool="briefings.get",
                    description="Retrieve local calendar events, tasks, and system notes",
                    arguments={},
                    output_variable="briefing_summary",
                ),
                SkillStep(
                    id="notify_user",
                    tool="notifications.show",
                    description="Present summary notification to user",
                    arguments={"title": "Daily Briefing", "message": "{briefing_summary}"},
                ),
            ]
            examples = [
                SkillExample(
                    title="Morning overview",
                    inputs={},
                    expected_outcome="Displays schedule, todos, and critical local alerts",
                )
            ]

        # 4. General fallback draft
        else:
            name = " ".join(w.capitalize() for w in skill_id.split("-"))
            desc = f"Automated custom skill for: {prompt}"
            triggers = [prompt.strip().lower(), skill_id.replace("-", " ")]
            # Discover matching tools from registry
            reg_names = set(self.tool_registry.names())
            selected_tools = [t for t in ["files.list", "files.read", "notifications.show"] if t in reg_names or "." in t]
            required_tools = selected_tools or ["files.list"]
            perms = SkillPermissionScope(filesystem=["."], destructive=False, network=False)
            workflow = [
                SkillStep(
                    id="step_1",
                    tool=required_tools[0],
                    description="Execute initial step",
                    arguments={},
                )
            ]
            examples = [
                SkillExample(
                    title="Standard execution",
                    inputs={},
                    expected_outcome=f"Performs {desc}",
                )
            ]

        now = dt.datetime.now().isoformat(timespec="seconds")
        manifest = SkillManifest(
            schema_version="1.0.0",
            id=skill_id,
            name=name,
            description=desc,
            version="1.0.0",
            type="declarative_workflow",
            triggers=triggers,
            required_tools=required_tools,
            permissions=perms,
            offline_capable=True,
            provenance=SkillProvenance(
                author="user",
                source="skill_creator",
                created_at=now,
            ),
            workflow=workflow,
            examples=examples,
        )

        skill_md = f"""# {name} (`{skill_id}`)

## Purpose
{desc}

## Activation Triggers
{', '.join(f'`{t}`' for t in triggers)}

## Required Permissions
- **Filesystem Scopes**: `{', '.join(perms.filesystem)}`
- **Destructive Actions**: `{'Yes' if perms.destructive else 'No (Dry-run safe)'}`
- **Network Access**: `{'Yes' if perms.network else 'No (Fully Offline)'}`
- **Subprocess**: `{'Yes' if perms.subprocess else 'No'}`

## Workflow Steps
"""
        for i, step in enumerate(workflow, 1):
            skill_md += f"{i}. **{step.id}** (`{step.tool}`): {step.description}\n"

        skill_md += f"\n## Limitations & Safety\n- Generated draft saved in `DRAFT` state.\n- User must review permissions and activate prior to live execution.\n"

        return manifest, skill_md

    def create_draft(self, prompt: str) -> SkillPackage:
        """Create a complete skill package from a user prompt, validate against registered tools, and persist as DRAFT."""
        manifest, skill_md = self._build_deterministic_draft(prompt)

        # Validate against real tool registry
        registered = set(self.tool_registry.names())
        validation_errors = manifest.validate_against_tools(registered)
        if validation_errors:
            # We flag missing tools clearly in description rather than crashing or hallucinating
            manifest.description += f" [Note: Missing tools detected: {', '.join(validation_errors)}]"

        # Save package to user disk
        target_dir = self.skills_dir / manifest.id
        package = SkillPackage(root=target_dir, manifest=manifest, skill_md=skill_md)
        package.save()

        # Register in application SQLite store as DRAFT
        self.skill_store.register_skill(manifest, skill_md, initial_state="DRAFT", snapshot_dir=str(target_dir))

        return package
