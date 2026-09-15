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

app = typer.Typer(no_args_is_help=True, help="Living Assistant local-first personal agent.")
console = Console()
project_app = typer.Typer(help="Register and inspect projects.")
security_app = typer.Typer(help="Defensive local security tools.")
app.add_typer(project_app, name="project")
app.add_typer(security_app, name="security")

@app.command()
def doctor():
    """Detect hardware, profile, Ollama connectivity and recommended models."""
    cfg = load_config()
    hw = detect_hardware()
    profile = choose_profile(cfg, hw)
    console.print("[bold]Hardware[/bold]", hw.to_dict())
    console.print("[bold]Selected profile[/bold]", profile)
    models = cfg["profiles"][profile]["models"]
    console.print("[bold]Configured models[/bold]", sorted(set(models.values())))
    try:
        rt = build_runtime(interactive=False)
        available = rt.model_manager.provider.available_models()
        console.print("[green]Ollama reachable[/green]")
        missing = [m for m in sorted(set(models.values())) if not any(x == m or x.startswith(m + ":") for x in available)]
        if missing:
            console.print("[yellow]Models to pull:[/yellow]", missing)
        else:
            console.print("[green]All configured models appear installed.[/green]")
    except Exception as e:
        console.print(f"[red]Ollama check failed:[/red] {e}")

@app.command()
def ask(message: str, cwd: str = typer.Option(".", help="Workspace-relative working directory.")):
    rt = build_runtime(interactive=True)
    answer = rt.orchestrator.run(message, context=f"Preferred working directory: {cwd}")
    console.print(answer)
    rt.model_manager.sleep()

@app.command()
def chat():
    rt = build_runtime(interactive=True)
    console.print(f"[bold green]Living Assistant[/bold green] profile={rt.profile}. Type /exit to quit.")
    try:
        while True:
            text = input("you> ").strip()
            if not text:
                continue
            if text in {"/exit","/quit","exit","quit"}:
                break
            console.print(rt.orchestrator.run(text))
    finally:
        rt.model_manager.sleep()

@app.command()
def daemon():
    rt = build_runtime(interactive=False)
    rt.model_manager.sleep()
    NervousSystem(rt.config, rt.memory).run_forever()

@app.command()
def serve(host: str = "127.0.0.1", port: int = 8787):
    if host not in {"127.0.0.1","localhost","::1"}:
        console.print("[yellow]Warning: exposing a control API beyond localhost is dangerous. Use auth + firewall.[/yellow]")
        raise typer.Exit(code=2)
    import uvicorn
    uvicorn.run("living_assistant.api:app", host=host, port=port, reload=False)

@project_app.command("add")
def project_add(name: str, path: str):
    rt = build_runtime(interactive=False)
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        console.print(f"[red]Project directory does not exist:[/red] {resolved}")
        raise typer.Exit(1)
    rt.projects.add(name, str(resolved))
    console.print(f"Registered and approved project root {name} -> {resolved}")

@project_app.command("list")
def project_list():
    rt = build_runtime(interactive=False)
    data = rt.projects.list()
    for name, path in data.items():
        console.print(f"{name}: {path}")

@project_app.command("detect")
def project_detect(path: str = "."):
    from .tools.projects import detect_project
    rt = build_runtime(interactive=False)
    console.print(detect_project(rt.workspace.resolve(path)))

@project_app.command("run")
def project_run(name: str):
    rt = build_runtime(interactive=True)
    p = rt.projects.get(name)
    if not p:
        console.print("[red]Unknown project.[/red]")
        raise typer.Exit(1)
    answer = rt.orchestrator.run(f"Run the registered project named {name}. Inspect it first and start the appropriate long-running process.", context=f"Project path: {p}")
    console.print(answer)

@project_app.command("processes")
def project_processes():
    rt = build_runtime(interactive=False)
    for item in rt.processes.list():
        console.print(item)

@project_app.command("stop")
def project_stop(process_id: str):
    rt = build_runtime(interactive=False)
    console.print(rt.processes.stop(process_id))

@security_app.command("audit")
def security_audit():
    console.print(audit_local())

@security_app.command("antivirus-status")
def security_av_status():
    console.print(antivirus_status())

if __name__ == "__main__":
    app()
