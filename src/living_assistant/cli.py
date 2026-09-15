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

app = typer.Typer(no_args_is_help=True, help='Living Assistant local-first personal agent.')
console = Console()
project_app = typer.Typer(help='Register, run and supervise projects.')
group_app = typer.Typer(help='Manage multi-project application groups.')
security_app = typer.Typer(help='Defensive local security tools.')
approval_app = typer.Typer(help='Review persistent approval requests.')
watch_app = typer.Typer(help='Manage low-resource filesystem watches.')
skill_app = typer.Typer(help='Manage user-confirmed reusable prompt skills.')
todo_app = typer.Typer(help='Manage reminders/todos.')
quarantine_app = typer.Typer(help='Inspect/release downloaded quarantined files.')
git_app = typer.Typer(help='Git-aware project inspection.')
desktop_app = typer.Typer(help='Optional clipboard/screenshot desktop actions.')
for sub, name in [
    (project_app,'project'),(group_app,'group'),(security_app,'security'),(approval_app,'approval'),
    (watch_app,'watch'),(skill_app,'skill'),(todo_app,'todo'),(quarantine_app,'quarantine'),
    (git_app,'git'),(desktop_app,'desktop')]:
    app.add_typer(sub, name=name)

@app.command()
def doctor():
    cfg = load_config(); hw = detect_hardware(); profile = choose_profile(cfg, hw)
    console.print('[bold]Hardware[/bold]', hw.to_dict())
    console.print('[bold]Selected profile[/bold]', profile)
    models = cfg['profiles'][profile]['models']
    console.print('[bold]Configured models[/bold]', sorted(set(models.values())))
    console.print('[bold]Optional desktop install[/bold] pip install -e ".[desktop]"')
    if profile != 'lite': console.print('[bold]Optional browser install[/bold] pip install -e ".[browser]" && playwright install chromium')
    try:
        rt = build_runtime(interactive=False)
        console.print('[bold]Resources[/bold]', rt.resources.snapshot())
        available = rt.model_manager.provider.available_models()
        console.print('[green]Ollama reachable[/green]')
        missing = [m for m in sorted(set(models.values())) if m not in available]
        if missing: console.print('[yellow]Models to pull:[/yellow]', missing)
        else: console.print('[green]All configured models appear installed.[/green]')
    except Exception as e:
        console.print(f'[red]Ollama check failed:[/red] {e}')

@app.command()
def ask(message: str, cwd: str = typer.Option('.', help='Workspace-relative working directory.')):
    rt = build_runtime(interactive=True)
    try: console.print(rt.orchestrator.run(message, context=f'Preferred working directory: {cwd}'))
    finally: rt.model_manager.sleep()

@app.command()
def chat():
    rt = build_runtime(interactive=True)
    console.print(f'[bold green]Living Assistant[/bold green] profile={rt.profile}. Type /exit to quit.')
    try:
        while True:
            text = input('you> ').strip()
            if not text: continue
            if text in {'/exit','/quit','exit','quit'}: break
            console.print(rt.orchestrator.run(text))
    finally: rt.model_manager.sleep()

@app.command()
def daemon():
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier).run_forever()

@app.command()
def tick():
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    console.print(NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier).tick())

@app.command()
def serve(host: str = '127.0.0.1', port: int = 8787):
    if host not in {'127.0.0.1','localhost','::1'}:
        console.print('[red]Refusing to expose the control API beyond localhost by default.[/red]'); raise typer.Exit(code=2)
    import uvicorn
    uvicorn.run('living_assistant.api:app', host=host, port=port, reload=False)

@app.command()
def tray():
    """Run optional system tray + nervous-system loop. Start `organism serve` separately for the dashboard."""
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    try:
        from .tray import run_tray
        run_tray(rt)
    except RuntimeError as e:
        console.print(f'[red]{e}[/red]'); raise typer.Exit(2)

@project_app.command('add')
def project_add(name: str, path: str, start: str | None = typer.Option(None, '--start'),
                test: str | None = typer.Option(None, '--test'), auto_restart: bool = False,
                max_restarts: int = 3, health_url: str | None = None):
    rt = build_runtime(interactive=False); resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        console.print(f'[red]Project directory does not exist:[/red] {resolved}'); raise typer.Exit(1)
    console.print(rt.projects.add(name, str(resolved), start, test, auto_restart, max_restarts, health_url))

@project_app.command('list')
def project_list():
    rt = build_runtime(interactive=False); table = Table('Name','Path','Start','Test','Auto restart','Health')
    for name, item in rt.projects.list().items():
        table.add_row(name,item.get('path',''),item.get('start_command') or '-',item.get('test_command') or '-',str(item.get('auto_restart',False)),item.get('health_url') or '-')
    console.print(table)

@project_app.command('detect')
def project_detect(path: str = '.'):
    from .tools.projects import detect_project
    rt = build_runtime(interactive=False); console.print(detect_project(rt.workspace.resolve(path)))

@project_app.command('run')
def project_run(name: str):
    rt = build_runtime(interactive=True); item = rt.projects.get(name)
    if not item: console.print('[red]Unknown project.[/red]'); raise typer.Exit(1)
    command = item.get('start_command')
    if not command: console.print('[red]No start command configured.[/red]'); raise typer.Exit(1)
    decision = classify_command(command, True)
    if not decision.allowed: console.print({'ok':False,'blocked':True,'reason':decision.reason}); raise typer.Exit(2)
    if input(f'Start {name} with `{command}`? [y/N]: ').strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    console.print(rt.processes.start(command,item['path'],name=name,project=name,auto_restart=bool(item.get('auto_restart')),max_restarts=int(item.get('max_restarts',3)),health_url=item.get('health_url')))

@project_app.command('test')
def project_test(name: str):
    rt = build_runtime(interactive=True); item = rt.projects.get(name)
    if not item or not item.get('test_command'):
        console.print('[red]Unknown project or no test command configured.[/red]'); raise typer.Exit(1)
    cmd = item['test_command']
    if input(f'Run tests for {name} with `{cmd}`? [y/N]: ').strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    import subprocess
    p = subprocess.run(cmd,cwd=item['path'],shell=True,text=True,capture_output=True,timeout=600)
    console.print({'returncode':p.returncode,'stdout':p.stdout[-30000:],'stderr':p.stderr[-10000:]})

@project_app.command('processes')
def project_processes():
    for item in build_runtime(interactive=False).processes.list(): console.print(item)

@project_app.command('logs')
def project_logs(process_id: str, lines: int = 100):
    result = build_runtime(interactive=False).processes.tail(process_id, lines)
    console.print('\n'.join(result['lines']) if result.get('ok') else result)

@project_app.command('restart')
def project_restart(process_id: str):
    rt=build_runtime(interactive=True); item=rt.processes.get(process_id)
    if not item: console.print('Unknown process id'); raise typer.Exit(1)
    if input(f"Restart {item.get('name')}? [y/N]: ").strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    console.print(rt.processes.restart(process_id, automatic=False))

@project_app.command('stop')
def project_stop(process_id: str): console.print(build_runtime(interactive=False).processes.stop(process_id))

@group_app.command('add')
def group_add(name: str, projects: str):
    rt=build_runtime(interactive=False); console.print(rt.groups.add(name,[x.strip() for x in projects.split(',')]))

@group_app.command('list')
def group_list(): console.print(build_runtime(interactive=False).groups.list())

@group_app.command('plan')
def group_plan(name: str): console.print(build_runtime(interactive=False).group_controller.plan(name))

@group_app.command('run')
def group_run(name: str):
    rt=build_runtime(interactive=True); console.print(rt.group_controller.start(name))

@group_app.command('stop')
def group_stop(name: str): console.print(build_runtime(interactive=False).group_controller.stop(name))

@approval_app.command('list')
def approval_list(status: str='pending'):
    for item in build_runtime(interactive=False).approvals.list(status=status if status!='all' else None): console.print(item)

@approval_app.command('approve')
def approval_approve(approval_id: str): console.print(build_runtime(interactive=False).approvals.resolve(approval_id,True))

@approval_app.command('deny')
def approval_deny(approval_id: str): console.print(build_runtime(interactive=False).approvals.resolve(approval_id,False))

@watch_app.command('add')
def watch_add(name: str,path: str,recursive: bool=True,extensions: str=''):
    rt=build_runtime(interactive=False); console.print(rt.watches.add(name,path,recursive,[x.strip() for x in extensions.split(',') if x.strip()]))

@watch_app.command('list')
def watch_list(): console.print(build_runtime(interactive=False).watches.list())

@watch_app.command('remove')
def watch_remove(name: str): console.print({'ok':build_runtime(interactive=False).watches.remove(name)})

@skill_app.command('add')
def skill_add(name: str,description: str,triggers: str,instructions_file: str):
    instructions=Path(instructions_file).expanduser().read_text(encoding='utf-8'); rt=build_runtime(interactive=False)
    console.print(rt.skills.add(name,description,[x.strip() for x in triggers.split(',')],instructions))

@skill_app.command('list')
def skill_list(): console.print(build_runtime(interactive=False).skills.list())

@skill_app.command('remove')
def skill_remove(name: str): console.print({'ok':build_runtime(interactive=False).skills.remove(name)})

@todo_app.command('list')
def todo_list(all: bool=False): console.print(build_runtime(interactive=False).memory.list_todos(include_done=all))

@todo_app.command('done')
def todo_done(todo_id: int): console.print({'ok':build_runtime(interactive=False).memory.complete_todo(todo_id)})

@quarantine_app.command('list')
def quarantine_list(): console.print(build_runtime(interactive=False).quarantine.list())

@quarantine_app.command('release')
def quarantine_release(item_id: str,destination: str):
    rt=build_runtime(interactive=True); item=rt.quarantine.get(item_id)
    if not item: console.print('[red]Unknown quarantine item.[/red]'); raise typer.Exit(1)
    target=rt.workspace.resolve(destination)
    if input(f"Release {item_id} ({item.get('sha256')}) to {target}? [y/N]: ").strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    from pathlib import Path as P
    source=P(item['path']); target.parent.mkdir(parents=True,exist_ok=True); source.replace(target); rt.quarantine.mark_released(item_id,str(target)); console.print({'ok':True,'path':str(target)})

@git_app.command('status')
def git_status(path: str='.'):
    import subprocess
    rt=build_runtime(interactive=False); cwd=rt.workspace.resolve(path)
    p=subprocess.run(['git','status','--short','--branch'],cwd=str(cwd),capture_output=True,text=True); console.print(p.stdout or p.stderr)

@git_app.command('diff')
def git_diff(path: str='.',staged: bool=False):
    import subprocess
    rt=build_runtime(interactive=False); cwd=rt.workspace.resolve(path); args=['git','diff']+(['--cached'] if staged else [])
    p=subprocess.run(args,cwd=str(cwd),capture_output=True,text=True); console.print(p.stdout or p.stderr)

@desktop_app.command('screenshot')
def desktop_screenshot(destination: str='artifacts/desktop-screenshot.png'):
    rt=build_runtime(interactive=True); target=rt.workspace.resolve(destination)
    if input(f'Capture desktop screenshot to {target}? [y/N]: ').strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    from .tools.desktop import _screenshot_impl
    console.print({'ok':True,'path':_screenshot_impl(target)})

@desktop_app.command('clipboard-read')
def desktop_clipboard_read():
    if input('Read current clipboard? It may contain secrets. [y/N]: ').strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    from .tools.desktop import _clipboard_read_impl
    console.print(_clipboard_read_impl())

@security_app.command('audit')
def security_audit(): console.print(audit_local())

@security_app.command('antivirus-status')
def security_av_status(): console.print(antivirus_status())

if __name__ == '__main__': app()
