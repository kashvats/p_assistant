from __future__ import annotations
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from .runtime import build_runtime
from .hardware import detect_hardware, choose_profile
from .config import load_config
from .daemon import NervousSystem
from .tools.security import audit_local, antivirus_status
from .security_policy import classify_command

app = typer.Typer(no_args_is_help=True, help="Living Assistant local-first personal agent.")
console = Console()
project_app = typer.Typer(help="Register, run and supervise projects.")
security_app = typer.Typer(help="Defensive local security tools.")
approval_app = typer.Typer(help="Review persistent approval requests.")
watch_app = typer.Typer(help="Manage low-resource filesystem watches.")
skill_app = typer.Typer(help="Manage user-confirmed reusable prompt skills.")
todo_app = typer.Typer(help="Manage reminders/todos.")
app.add_typer(project_app, name="project")
app.add_typer(security_app, name="security")
app.add_typer(approval_app, name="approval")
app.add_typer(watch_app, name="watch")
app.add_typer(skill_app, name="skill")
app.add_typer(todo_app, name="todo")

@app.command()
def doctor():
    """Detect hardware, profile, Ollama connectivity and recommended models."""
    cfg = load_config(); hw = detect_hardware(); profile = choose_profile(cfg, hw)
    console.print("[bold]Hardware[/bold]", hw.to_dict())
    console.print("[bold]Selected profile[/bold]", profile)
    models = cfg["profiles"][profile]["models"]
    console.print("[bold]Configured models[/bold]", sorted(set(models.values())))
    try:
        rt = build_runtime(interactive=False)
        console.print("[bold]Resources[/bold]", rt.resources.snapshot())
        available = rt.model_manager.provider.available_models()
        console.print("[green]Ollama reachable[/green]")
        missing = [m for m in sorted(set(models.values())) if m not in available]
        if missing: console.print("[yellow]Models to pull:[/yellow]", missing)
        else: console.print("[green]All configured models appear installed.[/green]")
    except Exception as e:
        console.print(f"[red]Ollama check failed:[/red] {e}")

@app.command()
def ask(message: str, cwd: str = typer.Option(".", help="Workspace-relative working directory.")):
    rt = build_runtime(interactive=True)
    try: console.print(rt.orchestrator.run(message, context=f"Preferred working directory: {cwd}"))
    finally: rt.model_manager.sleep()

@app.command()
def chat():
    rt = build_runtime(interactive=True)
    console.print(f"[bold green]Living Assistant[/bold green] profile={rt.profile}. Type /exit to quit.")
    try:
        while True:
            text = input("you> ").strip()
            if not text: continue
            if text in {"/exit","/quit","exit","quit"}: break
            console.print(rt.orchestrator.run(text))
    finally: rt.model_manager.sleep()

@app.command()
def daemon():
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier).run_forever()

@app.command()
def tick():
    """Run one nervous-system cycle; useful for cron/Task Scheduler."""
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    console.print(NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier).tick())

@app.command()
def serve(host: str = "127.0.0.1", port: int = 8787):
    if host not in {"127.0.0.1","localhost","::1"}:
        console.print("[red]Refusing to expose the control API beyond localhost by default.[/red]")
        raise typer.Exit(code=2)
    import uvicorn
    uvicorn.run("living_assistant.api:app", host=host, port=port, reload=False)

@project_app.command("add")
def project_add(name: str, path: str, start: str | None = typer.Option(None, "--start"),
                test: str | None = typer.Option(None, "--test"), auto_restart: bool = False,
                max_restarts: int = 3, health_url: str | None = None):
    rt = build_runtime(interactive=False)
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        console.print(f"[red]Project directory does not exist:[/red] {resolved}"); raise typer.Exit(1)
    console.print(rt.projects.add(name, str(resolved), start, test, auto_restart, max_restarts, health_url))

@project_app.command("list")
def project_list():
    rt = build_runtime(interactive=False)
    table = Table("Name", "Path", "Start", "Auto restart", "Health")
    for name, item in rt.projects.list().items():
        table.add_row(name, item.get("path",""), item.get("start_command") or "-", str(item.get("auto_restart",False)), item.get("health_url") or "-")
    console.print(table)

@project_app.command("detect")
def project_detect(path: str = "."):
    from .tools.projects import detect_project
    rt = build_runtime(interactive=False); console.print(detect_project(rt.workspace.resolve(path)))

@project_app.command("run")
def project_run(name: str):
    """Deterministically start a registered project using its saved command."""
    rt = build_runtime(interactive=True); item = rt.projects.get(name)
    if not item: console.print("[red]Unknown project.[/red]"); raise typer.Exit(1)
    command = item.get("start_command")
    if not command: console.print("[red]No start command is configured. Use project add --start or ask the agent to inspect it.[/red]"); raise typer.Exit(1)
    decision = classify_command(command, True)
    if not decision.allowed: console.print({"ok":False,"blocked":True,"reason":decision.reason}); raise typer.Exit(2)
    req = rt.approvals.consume_preapproval(command, "Starting a registered project.", "EXECUTE")
    if not req:
        approval = input(f"Start {name} with `{command}`? [y/N]: ").strip().lower() in {"y","yes"}
        if not approval: console.print("Cancelled."); raise typer.Exit(1)
    result = rt.processes.start(command, item["path"], name=name, project=name,
                                auto_restart=bool(item.get("auto_restart")), max_restarts=int(item.get("max_restarts",3)),
                                health_url=item.get("health_url"))
    console.print(result)

@project_app.command("processes")
def project_processes():
    rt = build_runtime(interactive=False)
    for item in rt.processes.list(): console.print(item)

@project_app.command("logs")
def project_logs(process_id: str, lines: int = 100):
    rt = build_runtime(interactive=False); result = rt.processes.tail(process_id, lines)
    if result.get("ok"):
        console.print("\n".join(result["lines"]))
    else: console.print(result)

@project_app.command("restart")
def project_restart(process_id: str):
    rt = build_runtime(interactive=True); item = rt.processes.get(process_id)
    if not item: console.print("Unknown process id"); raise typer.Exit(1)
    if input(f"Restart {item.get('name')}? [y/N]: ").strip().lower() not in {"y","yes"}: raise typer.Exit(1)
    console.print(rt.processes.restart(process_id, automatic=False))

@project_app.command("stop")
def project_stop(process_id: str):
    rt = build_runtime(interactive=False); console.print(rt.processes.stop(process_id))

@approval_app.command("list")
def approval_list(status: str = "pending"):
    rt = build_runtime(interactive=False)
    for item in rt.approvals.list(status=status if status != "all" else None): console.print(item)

@approval_app.command("approve")
def approval_approve(approval_id: str):
    rt = build_runtime(interactive=False); console.print(rt.approvals.resolve(approval_id, True))

@approval_app.command("deny")
def approval_deny(approval_id: str):
    rt = build_runtime(interactive=False); console.print(rt.approvals.resolve(approval_id, False))

@watch_app.command("add")
def watch_add(name: str, path: str, recursive: bool = True, extensions: str = ""):
    rt = build_runtime(interactive=False)
    exts = [x.strip() for x in extensions.split(",") if x.strip()]
    console.print(rt.watches.add(name, path, recursive, exts))

@watch_app.command("list")
def watch_list():
    console.print(build_runtime(interactive=False).watches.list())

@watch_app.command("remove")
def watch_remove(name: str):
    console.print({"ok": build_runtime(interactive=False).watches.remove(name)})

@skill_app.command("add")
def skill_add(name: str, description: str, triggers: str, instructions_file: str):
    instructions = Path(instructions_file).expanduser().read_text(encoding="utf-8")
    rt = build_runtime(interactive=False)
    console.print(rt.skills.add(name, description, [x.strip() for x in triggers.split(",")], instructions))

@skill_app.command("list")
def skill_list():
    console.print(build_runtime(interactive=False).skills.list())

@skill_app.command("remove")
def skill_remove(name: str):
    console.print({"ok": build_runtime(interactive=False).skills.remove(name)})

@todo_app.command("list")
def todo_list(all: bool = False):
    console.print(build_runtime(interactive=False).memory.list_todos(include_done=all))

@todo_app.command("done")
def todo_done(todo_id: int):
    console.print({"ok": build_runtime(interactive=False).memory.complete_todo(todo_id)})

@security_app.command("audit")
def security_audit(): console.print(audit_local())

@security_app.command("antivirus-status")
def security_av_status(): console.print(antivirus_status())

if __name__ == "__main__": app()
