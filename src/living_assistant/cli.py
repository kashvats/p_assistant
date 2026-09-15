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
browser_app = typer.Typer(help='Optional isolated browser sessions.')
voice_app = typer.Typer(help='Optional local push-to-talk STT/TTS.')
routine_app = typer.Typer(help='Deterministic event/interval routines.')
improve_app = typer.Typer(help='Reviewable self-improvement/file-change proposals.')
for sub, name in [
    (project_app,'project'),(group_app,'group'),(security_app,'security'),(approval_app,'approval'),
    (watch_app,'watch'),(skill_app,'skill'),(todo_app,'todo'),(quarantine_app,'quarantine'),
    (git_app,'git'),(desktop_app,'desktop'),(browser_app,'browser'),(voice_app,'voice'),
    (routine_app,'routine'),(improve_app,'improve')]:
    app.add_typer(sub, name=name)

@app.command()
def doctor():
    cfg = load_config(); hw = detect_hardware(); profile = choose_profile(cfg, hw)
    console.print('[bold]Hardware[/bold]', hw.to_dict())
    console.print('[bold]Selected profile[/bold]', profile)
    models = cfg['profiles'][profile]['models']
    console.print('[bold]Configured models[/bold]', sorted(set(models.values())))
    console.print('[bold]Optional desktop install[/bold] pip install -e ".[desktop]"')
    console.print('[bold]Optional voice install[/bold] pip install -e ".[voice]"')
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
    NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier,
                  routines=rt.routines, orchestrator=rt.orchestrator, model_manager=rt.model_manager).run_forever()

@app.command()
def tick():
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    console.print(NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier,
                                routines=rt.routines, orchestrator=rt.orchestrator, model_manager=rt.model_manager).tick())

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



@browser_app.command('live')
def browser_live(name: str, url: str, persistent: bool = False, allowed_hosts: str = ''):
    """Run a named browser session in this process until `quit`."""
    rt = build_runtime(interactive=True)
    hosts = [x.strip() for x in allowed_hosts.split(',') if x.strip()]
    started = rt.browser.start_session(name, url, persistent, hosts)
    console.print(started)
    if not started.get('ok'):
        raise typer.Exit(1)
    console.print('[dim]Commands: snapshot | goto URL | click SELECTOR | fill SELECTOR VALUE | quit[/dim]')
    try:
        while True:
            raw = input('browser> ').strip()
            if not raw:
                continue
            if raw in {'quit','exit'}:
                break
            if raw == 'snapshot':
                console.print(rt.browser.snapshot_session(name)); continue
            if raw.startswith('goto '):
                console.print(rt.browser.navigate_session(name, raw[5:].strip())); continue
            if raw.startswith('click '):
                console.print(rt.browser.interact_session(name, 'click', raw[6:].strip())); continue
            if raw.startswith('fill '):
                rest = raw[5:].strip()
                if ' ' not in rest:
                    console.print('Usage: fill SELECTOR VALUE'); continue
                selector, value = rest.split(' ', 1)
                console.print(rt.browser.interact_session(name, 'fill', selector, value)); continue
            console.print('Unknown command.')
    finally:
        console.print(rt.browser.close_session(name, False))

@browser_app.command('sessions')
def browser_sessions():
    console.print(build_runtime(interactive=False).browser.list_sessions())

@browser_app.command('start')
def browser_start(name: str, url: str, persistent: bool = False, allowed_hosts: str = ''):
    rt = build_runtime(interactive=True)
    hosts = [x.strip() for x in allowed_hosts.split(',') if x.strip()]
    console.print(rt.browser.start_session(name, url, persistent, hosts))

@browser_app.command('snapshot')
def browser_snapshot(name: str, screenshot: str | None = None):
    console.print(build_runtime(interactive=False).browser.snapshot_session(name, screenshot))

@browser_app.command('navigate')
def browser_navigate(name: str, url: str):
    console.print(build_runtime(interactive=True).browser.navigate_session(name, url))

@browser_app.command('click')
def browser_click(name: str, selector: str):
    console.print(build_runtime(interactive=True).browser.interact_session(name, 'click', selector))

@browser_app.command('fill')
def browser_fill(name: str, selector: str, value: str):
    console.print(build_runtime(interactive=True).browser.interact_session(name, 'fill', selector, value))

@browser_app.command('close')
def browser_close(name: str, delete_profile: bool = False):
    console.print(build_runtime(interactive=True).browser.close_session(name, delete_profile))

@voice_app.command('status')
def voice_status():
    rt = build_runtime(interactive=False)
    console.print({'enabled': rt.voice.enabled(), 'profile': rt.profile, 'config': rt.config.get('voice', {})})

@voice_app.command('record')
def voice_record(seconds: float = 6.0, destination: str = 'artifacts/voice-input.wav'):
    rt = build_runtime(interactive=True)
    console.print(rt.voice.record(destination, seconds))

@voice_app.command('transcribe')
def voice_transcribe(path: str, language: str | None = None):
    rt = build_runtime(interactive=True)
    try:
        console.print(rt.voice.transcribe(path, language))
    finally:
        rt.voice.sleep()

@voice_app.command('ask')
def voice_ask(seconds: float = 6.0, language: str | None = None, speak: bool = False):
    rt = build_runtime(interactive=True)
    try:
        recording = rt.voice.record('artifacts/voice-input.wav', seconds)
        if not recording.get('ok'):
            console.print(recording); raise typer.Exit(1)
        transcript = rt.voice.transcribe('artifacts/voice-input.wav', language)
        if not transcript.get('ok'):
            console.print(transcript); raise typer.Exit(1)
        console.print(f"[bold]You:[/bold] {transcript.get('text','')}")
        answer = rt.orchestrator.run(transcript.get('text',''))
        console.print(f"[bold green]Assistant:[/bold green] {answer}")
        if speak:
            rt.voice.speak(answer)
    finally:
        rt.voice.sleep(); rt.model_manager.sleep()

@routine_app.command('list')
def routine_list():
    console.print(build_runtime(interactive=False).routines.list())

@routine_app.command('add-event-notify')
def routine_add_event_notify(name: str, event_kind: str, message: str):
    rt=build_runtime(interactive=False)
    console.print(rt.routines.add(name, {'type':'event','kind':event_kind}, {'type':'notify','message':message}))

@routine_app.command('add-interval-notify')
def routine_add_interval_notify(name: str, seconds: int, message: str):
    rt=build_runtime(interactive=False)
    console.print(rt.routines.add(name, {'type':'interval','seconds':seconds}, {'type':'notify','message':message}))

@routine_app.command('add-interval-todo')
def routine_add_interval_todo(name: str, seconds: int, title: str):
    rt=build_runtime(interactive=False)
    console.print(rt.routines.add(name, {'type':'interval','seconds':seconds}, {'type':'todo','title':title}))

@routine_app.command('add-prompt')
def routine_add_prompt(name: str, seconds: int, prompt: str):
    rt=build_runtime(interactive=False)
    console.print(rt.routines.add(name, {'type':'interval','seconds':seconds}, {'type':'assistant_prompt','prompt':prompt}))
    if not rt.config.get('routines',{}).get('allow_model_wake',False):
        console.print('[yellow]Created, but model wake is disabled in config. It will be skipped until explicitly enabled.[/yellow]')

@routine_app.command('enable')
def routine_enable(name: str):
    console.print({'ok':build_runtime(interactive=False).routines.set_enabled(name, True)})

@routine_app.command('disable')
def routine_disable(name: str):
    console.print({'ok':build_runtime(interactive=False).routines.set_enabled(name, False)})

@routine_app.command('remove')
def routine_remove(name: str):
    console.print({'ok':build_runtime(interactive=False).routines.remove(name)})

@improve_app.command('list')
def improve_list(status: str = 'pending'):
    console.print(build_runtime(interactive=False).improvements.store.list(None if status == 'all' else status))

@improve_app.command('show')
def improve_show(proposal_id: str):
    console.print(build_runtime(interactive=False).improvements.store.get(proposal_id))

@improve_app.command('propose')
def improve_propose(target_path: str, content_file: str, title: str, rationale: str, tests: str = ''):
    rt=build_runtime(interactive=False)
    new_content=Path(content_file).expanduser().read_text(encoding='utf-8')
    test_list=[x.strip() for x in tests.split(',') if x.strip()]
    console.print(rt.improvements.propose(target_path,new_content,title,rationale,test_list))

@improve_app.command('apply')
def improve_apply(proposal_id: str):
    console.print(build_runtime(interactive=True).improvements.apply(proposal_id))

@improve_app.command('rollback')
def improve_rollback(proposal_id: str):
    console.print(build_runtime(interactive=True).improvements.rollback(proposal_id))

@improve_app.command('reject')
def improve_reject(proposal_id: str):
    console.print(build_runtime(interactive=False).improvements.reject(proposal_id))

if __name__ == '__main__': app()
