from __future__ import annotations

from pathlib import Path
import typer
from rich.table import Table

from living_assistant.career.filler import JobFormFiller
from living_assistant.career.parser import JobParser
from living_assistant.career.profile import CareerProfileStore
from living_assistant.career.tailor import TailoringEngine
from living_assistant.career.tracker import ApplicationStatus, ApplicationTracker
from .helpers import career_app, console


@career_app.command("profile")
def career_profile_cmd(
    resume: Path | None = typer.Option(None, "--resume", "-r", help="Path to resume file (PDF, DOCX, MD)"),
    name: str | None = typer.Option(None, "--name", help="Candidate full name"),
    email: str | None = typer.Option(None, "--email", help="Candidate email"),
    phone: str | None = typer.Option(None, "--phone", help="Candidate phone number"),
    linkedin: str | None = typer.Option(None, "--linkedin", help="Candidate LinkedIn URL"),
    github: str | None = typer.Option(None, "--github", help="Candidate GitHub URL"),
):
    """View or configure candidate career profile and master resume."""
    store = CareerProfileStore()

    updates: dict = {}
    if name is not None:
        updates["full_name"] = name
    if email is not None:
        updates["email"] = email
    if phone is not None:
        updates["phone"] = phone
    if linkedin is not None:
        updates["linkedin_url"] = linkedin
    if github is not None:
        updates["github_url"] = github

    if updates:
        store.update_profile(updates)

    if resume is not None:
        if not resume.is_file():
            console.print(f"[red]Resume file not found: {resume}[/red]")
            raise typer.Exit(1)
        saved = store.save_resume_file(resume.name, resume.read_bytes())
        console.print(f"[green]Saved and parsed resume to: {saved}[/green]")

    profile = store.get_profile()
    table = Table(title="Candidate Career Profile")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Full Name", profile.full_name or "[dim]Not set[/dim]")
    table.add_row("Email", profile.email or "[dim]Not set[/dim]")
    table.add_row("Phone", profile.phone or "[dim]Not set[/dim]")
    table.add_row("LinkedIn", profile.linkedin_url or "[dim]Not set[/dim]")
    table.add_row("GitHub", profile.github_url or "[dim]Not set[/dim]")
    table.add_row("Resume Path", profile.resume_file_path or "[dim]Not uploaded[/dim]")
    table.add_row("Resume Text Preview", (profile.resume_text[:120] + "...") if profile.resume_text else "[dim]Empty[/dim]")
    table.add_row("Skills", ", ".join(profile.skills) if profile.skills else "[dim]None listed[/dim]")
    table.add_row("Work Authorization", "Authorized" if profile.screener.legally_authorized else "Unauthorized")
    table.add_row("Visa Sponsorship", "Required" if profile.screener.requires_visa_sponsorship else "Not Required")

    console.print(table)


@career_app.command("analyze")
def career_analyze_cmd(url: str = typer.Argument(..., help="Job posting URL to inspect")):
    """Analyze a job posting, detect ATS platform, and harvest recruiter emails."""
    import urllib.request
    from living_assistant.desktop.browser import safe_browser_url

    if not safe_browser_url(url):
        console.print(f"[red]Invalid or blocked URL: {url}[/red]")
        raise typer.Exit(1)

    console.print(f"Fetching and analyzing: [cyan]{url}[/cyan]...")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        console.print(f"[yellow]Direct fetch warning: {e}. Parsing minimal fallback.[/yellow]")
        html = f"<html><body><h1>Opening at {url}</h1></body></html>"

    parser = JobParser()
    parsed = parser.parse_posting(url=url, html=html)
    tracker = ApplicationTracker()
    record = tracker.create_application(parsed)

    console.print(f"[bold green]Analyzed successfully! Application ID: {record.id}[/bold green]")
    console.print(f"Company: [cyan]{parsed.company}[/cyan] | Role: [cyan]{parsed.title}[/cyan] | ATS: [yellow]{parsed.platform.value}[/yellow]")

    if parsed.contacts:
        console.print("\n[bold]Harvested Recruiter / Hiring Emails:[/bold]")
        for c in parsed.contacts:
            flag = "[green](Hiring Specific)[/green]" if c.is_hiring_specific else ""
            console.print(f" - {c.email} (Confidence: {int(c.confidence * 100)}%) {flag}")
    else:
        console.print("\n[dim]No public recruiter emails discovered on the posting page.[/dim]")


@career_app.command("apply")
def career_apply_cmd(url: str = typer.Argument(..., help="Job posting URL to apply to")):
    """Pre-fill an application form using your resume/profile with pre-submit approval gate."""
    import urllib.request
    from living_assistant.desktop.browser import safe_browser_url

    if not safe_browser_url(url):
        console.print(f"[red]Invalid or blocked URL: {url}[/red]")
        raise typer.Exit(1)

    console.print(f"Analyzing job for application: [cyan]{url}[/cyan]...")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        html = f"<html><body><h1>Opening at {url}</h1></body></html>"

    parser = JobParser()
    parsed = parser.parse_posting(url=url, html=html)
    tracker = ApplicationTracker()
    record = tracker.create_application(parsed)

    store = CareerProfileStore()
    profile = store.get_profile()

    filler = JobFormFiller(browser_controller=None, approval_manager=None, tracker=tracker)
    preview = filler.stage_application(record.id, profile)

    console.print(f"[bold yellow]Application Prepared & Staged for Approval![/bold yellow]")
    console.print(f"Company: {preview.company} | Title: {preview.title}")
    console.print(f"Status: [cyan]{preview.status}[/cyan]")
    console.print("Pre-filled fields:")
    for k, v in preview.fields_prepared.items():
        if v:
            console.print(f"  • {k}: {v}")

    confirm = typer.confirm("Approve final submission to employer?", default=False)
    if confirm:
        res = filler.execute_submission(record.id, approval_token="cli_approved")
        if res.get("ok"):
            console.print("[bold green]Application submitted successfully![/bold green]")
        else:
            console.print(f"[red]Submission error: {res.get('error')}[/red]")
    else:
        console.print("[yellow]Submission paused. Preserved as ready_for_review.[/yellow]")


@career_app.command("list")
def career_list_cmd(status: str | None = typer.Option(None, "--status", "-s", help="Filter by status")):
    """List tracked job applications and cold outreach pipelines."""
    tracker = ApplicationTracker()
    st_enum = ApplicationStatus(status) if status and status in [s.value for s in ApplicationStatus] else None
    records = tracker.list_applications(status=st_enum)

    table = Table(title="Job Applications Pipeline")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Company", style="bold")
    table.add_column("Role", style="cyan")
    table.add_column("Platform", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Recruiter Contacts", style="green")

    for r in records:
        table.add_row(
            r.id[:8],
            r.company,
            r.title,
            r.platform,
            r.status.value,
            ", ".join(r.recruiter_emails[:2]) if r.recruiter_emails else "[dim]None[/dim]",
        )

    console.print(table)


@career_app.command("outreach")
def career_outreach_cmd(application_id: str = typer.Argument(..., help="Application ID to generate cold email for")):
    """Generate or view a personalized cold outreach email draft for a job application."""
    tracker = ApplicationTracker()
    record = tracker.get_application(application_id)
    if not record:
        console.print(f"[red]Application {application_id} not found.[/red]")
        raise typer.Exit(1)

    store = CareerProfileStore()
    profile = store.get_profile()
    tailor = TailoringEngine()

    from living_assistant.career.parser import ATSPlatform, ContactEmail, ParsedJob

    contact = None
    if record.recruiter_emails:
        contact = ContactEmail(email=record.recruiter_emails[0], is_hiring_specific=True)

    job_mock = ParsedJob(
        title=record.title,
        company=record.company,
        url=record.url,
        platform=ATSPlatform(record.platform) if record.platform in [p.value for p in ATSPlatform] else ATSPlatform.GENERIC,
        description=record.notes or f"Opening at {record.company} for {record.title}",
    )
    draft = tailor.generate_cold_outreach(profile, job_mock, contact)
    tracker.save_outreach(application_id, draft)

    console.print(f"[bold cyan]Cold Outreach Email Draft ({draft.company} - {draft.title}):[/bold cyan]\n")
    console.print(f"[bold]To:[/bold] {draft.recipient}")
    console.print(f"[bold]Subject:[/bold] {draft.subject}")
    console.print("--------------------------------------------------")
    console.print(draft.body)
    console.print("--------------------------------------------------")
