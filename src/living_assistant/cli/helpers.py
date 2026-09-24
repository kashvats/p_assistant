from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="Living Assistant local-first personal agent.")
console = Console()

project_app = typer.Typer(help="Register, run and supervise projects.")
group_app = typer.Typer(help="Manage multi-project application groups.")
security_app = typer.Typer(help="Defensive local security tools.")
approval_app = typer.Typer(help="Review persistent approval requests.")
watch_app = typer.Typer(help="Manage low-resource filesystem watches.")
skill_app = typer.Typer(help="Manage user-confirmed reusable prompt skills.")
agent_app = typer.Typer(help="Manage and execute versioned custom agents.")
todo_app = typer.Typer(help="Manage reminders/todos.")
quarantine_app = typer.Typer(help="Inspect/release downloaded quarantined files.")
git_app = typer.Typer(help="Git-aware project inspection.")
desktop_app = typer.Typer(help="Optional clipboard/screenshot desktop actions.")
browser_app = typer.Typer(help="Optional isolated browser sessions.")
voice_app = typer.Typer(help="Local push-to-talk and optional hands-free wake-word voice.")
routine_app = typer.Typer(help="Deterministic event/interval routines.")
improve_app = typer.Typer(help="Reviewable self-improvement/file-change proposals.")
calendar_app = typer.Typer(help="Local personal calendar and agenda.")
personal_app = typer.Typer(help="Quiet hours, focus mode and personal operating state.")
briefing_app = typer.Typer(help="Morning/evening deterministic briefings.")
session_app = typer.Typer(help="Local conversation/session history.")
integration_app = typer.Typer(help="Real external app connectors with scoped capabilities and approval-gated writes.")
experience_app = typer.Typer(help="Evidence-weighted lessons from past mistakes and successful recoveries.")
model_app = typer.Typer(help="Inspect and manage adaptive local-model residency.")
platform_app = typer.Typer(help="Cross-platform capability, link, and background-service diagnostics.")
release_app = typer.Typer(help="Versioned install, backup, rollback, and runtime lifecycle.")

for sub, name in [
    (project_app, "project"),
    (group_app, "group"),
    (security_app, "security"),
    (approval_app, "approval"),
    (watch_app, "watch"),
    (skill_app, "skill"),
    (agent_app, "agent"),
    (todo_app, "todo"),
    (quarantine_app, "quarantine"),
    (git_app, "git"),
    (desktop_app, "desktop"),
    (browser_app, "browser"),
    (voice_app, "voice"),
    (routine_app, "routine"),
    (improve_app, "improve"),
    (calendar_app, "calendar"),
    (personal_app, "personal"),
    (briefing_app, "briefing"),
    (session_app, "session"),
    (integration_app, "integration"),
    (experience_app, "experience"),
    (model_app, "model"),
    (platform_app, "platform"),
    (release_app, "release"),
]:
    app.add_typer(sub, name=name)
