from __future__ import annotations

from pathlib import Path
from living_assistant.skills.manifest import (
    SkillManifest,
    SkillPermissionScope,
    SkillStep,
    SkillLimits,
    SkillProvenance,
    SkillExample,
)
from living_assistant.skills.package import SkillPackage


def get_daily_briefing_manifest() -> SkillManifest:
    return SkillManifest(
        schema_version="1.0.0",
        id="daily-briefing",
        name="Daily Briefing",
        description="Summarizes available calendar events, pending tasks, and recent notes offline, flagging any missing connectors.",
        version="1.0.0",
        type="declarative_workflow",
        triggers=["daily briefing", "morning brief", "what is on my schedule", "daily agenda"],
        required_tools=["briefings.get", "notifications.show"],
        permissions=SkillPermissionScope(
            filesystem=["."],
            network=False,
            destructive=False,
            subprocess=False,
            messaging=True,
        ),
        offline_capable=True,
        workflow=[
            SkillStep(
                id="get_local_briefing",
                tool="briefings.get",
                description="Fetch local events, active tasks, and status alerts",
                arguments={},
                output_variable="briefing_data",
            ),
            SkillStep(
                id="show_briefing",
                tool="notifications.show",
                description="Show daily briefing alert to user",
                arguments={
                    "title": "Daily Briefing",
                    "message": "Today's schedule and tasks are up to date.",
                },
            ),
        ],
        examples=[
            SkillExample(
                title="Morning start",
                inputs={},
                expected_outcome="Displays schedule and active tasks without external internet access.",
            )
        ],
        provenance=SkillProvenance(author="builtin", source="reference_skills"),
    )


def get_downloads_organizer_manifest() -> SkillManifest:
    return SkillManifest(
        schema_version="1.0.0",
        id="downloads-organizer",
        name="Downloads Organizer",
        description="Proposes categories and moves files into organized subfolders (Documents, Images, Installers), with collision handling, dry-run previews, and reversible undo.",
        version="1.0.0",
        type="declarative_workflow",
        triggers=["organize downloads", "clean downloads", "sort downloads", "clean up folder"],
        required_tools=["files.list", "files.move"],
        permissions=SkillPermissionScope(
            filesystem=["./downloads", "./workspace", "."],
            network=False,
            destructive=False,
            subprocess=False,
            messaging=False,
        ),
        offline_capable=True,
        workflow=[
            SkillStep(
                id="scan_folder",
                tool="files.list",
                description="List files in the target directory",
                arguments={"path": "{inputs.folder}"},
                output_variable="unorganized_files",
            ),
            SkillStep(
                id="move_file",
                tool="files.move",
                description="Move file to categorized subdirectory avoiding name collisions",
                arguments={
                    "source": "{inputs.source_file}",
                    "destination": "{inputs.target_dir}/",
                    "overwrite": False,
                },
            ),
        ],
        examples=[
            SkillExample(
                title="Organize synthetic downloads",
                inputs={"folder": "./downloads", "source_file": "./downloads/manual.pdf", "target_dir": "./downloads/Documents"},
                expected_outcome="Moves manual.pdf to ./downloads/Documents/manual.pdf with undo record.",
            )
        ],
        provenance=SkillProvenance(author="builtin", source="reference_skills"),
    )


def get_invoice_organizer_manifest() -> SkillManifest:
    return SkillManifest(
        schema_version="1.0.0",
        id="invoice-organizer",
        name="Invoice Organizer",
        description="Extracts vendor, date, and amount from document files using native parsing, sorts them into vendor/month folders, and flags uncertain extractions for review.",
        version="1.0.0",
        type="declarative_workflow",
        triggers=["organize invoices", "sort invoices", "process invoices", "organize my invoices by vendor and month"],
        required_tools=["files.list", "documents.extract", "files.move"],
        permissions=SkillPermissionScope(
            filesystem=["./invoices", "./workspace", "."],
            network=False,
            destructive=False,
            subprocess=False,
            messaging=False,
        ),
        offline_capable=True,
        workflow=[
            SkillStep(
                id="list_input_invoices",
                tool="files.list",
                description="Scan directory for incoming invoice files",
                arguments={"path": "{inputs.inbox_dir}"},
                output_variable="invoice_files",
            ),
            SkillStep(
                id="extract_metadata",
                tool="documents.extract",
                description="Extract vendor, date, and amount from the document",
                arguments={"path": "{inputs.invoice_path}"},
                output_variable="invoice_meta",
            ),
            SkillStep(
                id="move_to_organized_folder",
                tool="files.move",
                description="Move invoice to Vendor/Year-Month directory structure without overwriting",
                arguments={
                    "source": "{inputs.invoice_path}",
                    "destination": "{inputs.target_root}/{invoice_meta.vendor}/{invoice_meta.year_month}/",
                    "overwrite": False,
                },
            ),
        ],
        examples=[
            SkillExample(
                title="Organize Acme invoice",
                inputs={"inbox_dir": "./inbox", "invoice_path": "./inbox/acme_march.txt", "target_root": "./Organized_Invoices"},
                expected_outcome="Extracts Acme vendor & 2026-03 date, moves to ./Organized_Invoices/Acme/2026-03/acme_march.txt",
            )
        ],
        provenance=SkillProvenance(author="builtin", source="reference_skills"),
    )


def seed_reference_skills(target_dir: Path) -> list[SkillPackage]:
    """Seed the 3 reference skills into the given directory."""
    packages = []
    defs = [
        (get_daily_briefing_manifest(), "# Daily Briefing\n\nSummarizes tasks and calendar events offline."),
        (get_downloads_organizer_manifest(), "# Downloads Organizer\n\nCategorizes files safely with dry-run and undo."),
        (get_invoice_organizer_manifest(), "# Invoice Organizer\n\nExtracts vendor, date, and organizes into Vendor/Month folders."),
    ]
    for manifest, md in defs:
        p_dir = target_dir / manifest.id
        pkg = SkillPackage(root=p_dir, manifest=manifest, skill_md=md)
        pkg.save()
        packages.append(pkg)
    return packages
