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
from .security_guardian import startup_inventory, inspect_process, file_signature, process_triage, network_activity_summary

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
calendar_app = typer.Typer(help='Local personal calendar and agenda.')
personal_app = typer.Typer(help='Quiet hours, focus mode and personal operating state.')
briefing_app = typer.Typer(help='Morning/evening deterministic briefings.')
session_app = typer.Typer(help='Local conversation/session history.')
integration_app = typer.Typer(help='Connector metadata and future external integrations.')
for sub, name in [
    (project_app,'project'),(group_app,'group'),(security_app,'security'),(approval_app,'approval'),
    (watch_app,'watch'),(skill_app,'skill'),(todo_app,'todo'),(quarantine_app,'quarantine'),
    (git_app,'git'),(desktop_app,'desktop'),(browser_app,'browser'),(voice_app,'voice'),
    (routine_app,'routine'),(improve_app,'improve'),(calendar_app,'calendar'),(personal_app,'personal'),
    (briefing_app,'briefing'),(session_app,'session'),(integration_app,'integration')]:
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
    console.print('[bold]Security onboarding[/bold] organism security initialize')
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
def ask(message: str, cwd: str = typer.Option('.', help='Workspace-relative working directory.'),
        session: str | None = typer.Option(None, '--session', help='Optional local session id for continuity.')):
    rt = build_runtime(interactive=True)
    if session: rt.sessions.ensure(session, title='one-shot')
    try: console.print(rt.orchestrator.run(message, context=f'Preferred working directory: {cwd}', session_id=session))
    finally: rt.model_manager.sleep()

@app.command()
def chat(session: str | None = typer.Option(None, '--session'), history: bool = typer.Option(True, '--history/--no-history')):
    rt = build_runtime(interactive=True)
    sid = session
    if history:
        if sid: rt.sessions.ensure(sid)
        else: sid = rt.sessions.create('Interactive chat')['id']
    console.print(f'[bold green]Living Assistant[/bold green] profile={rt.profile}. Type /exit to quit.' + (f' Session={sid}' if sid else ' History disabled.'))
    try:
        while True:
            text = input('you> ').strip()
            if not text: continue
            if text in {'/exit','/quit','exit','quit'}: break
            console.print(rt.orchestrator.run(text, session_id=sid))
    finally: rt.model_manager.sleep()

@app.command()
def daemon():
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier,
                  routines=rt.routines, orchestrator=rt.orchestrator, model_manager=rt.model_manager,
                  briefings=rt.briefings, sessions=rt.sessions, guardian=rt.guardian).run_forever()

@app.command()
def tick():
    rt = build_runtime(interactive=False); rt.model_manager.sleep()
    console.print(NervousSystem(rt.config, rt.memory, rt.processes, rt.watches, rt.notifier,
                                routines=rt.routines, orchestrator=rt.orchestrator, model_manager=rt.model_manager,
                                briefings=rt.briefings, sessions=rt.sessions, guardian=rt.guardian).tick())

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

@approval_app.command('ui')
def approval_ui():
    rt=build_runtime(interactive=False)
    try:
        from .approval_ui import run_approval_ui
        run_approval_ui(rt)
    except RuntimeError as e:
        console.print(f'[red]{e}[/red]'); raise typer.Exit(2)

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

@todo_app.command('add')
def todo_add(title: str, due_at: str | None = None):
    console.print({'ok':True,'id':build_runtime(interactive=False).memory.add_todo(title,due_at)})

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
    verification=rt.quarantine.verify(item_id)
    if not verification.get('ok'): console.print({'ok':False,'blocked':True,'error':'Quarantine artifact changed after registration.','verification':verification}); raise typer.Exit(1)
    if input(f"Release {item_id} ({item.get('sha256')}) to {target}? [y/N]: ").strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    from pathlib import Path as P
    source=P(item['path']); target.parent.mkdir(parents=True,exist_ok=True); source.replace(target); rt.quarantine.mark_released(item_id,str(target)); console.print({'ok':True,'path':str(target)})

@quarantine_app.command('inspect')
def quarantine_inspect(item_id: str):
    rt=build_runtime(interactive=False); item=rt.quarantine.get(item_id)
    if not item: console.print('[red]Unknown quarantine item.[/red]'); raise typer.Exit(1)
    console.print({'item':item,'file':file_signature(item['path'])})

@quarantine_app.command('scan')
def quarantine_scan(item_id: str):
    rt=build_runtime(interactive=True); item=rt.quarantine.get(item_id)
    if not item: console.print('[red]Unknown quarantine item.[/red]'); raise typer.Exit(1)
    result=rt.guardian.scan_path_antivirus(item['path'])
    if result.get('ok') or result.get('returncode') is not None:
        rt.quarantine.record_scan(item_id,result.get('provider','unknown'),result)
    console.print(result)

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

@security_app.command('posture')
def security_posture(include_updates: bool = typer.Option(False,'--updates')):
    console.print(build_runtime(interactive=False).guardian.posture(include_updates=include_updates))

@security_app.command('findings')
def security_findings(status: str = 'open'):
    console.print(build_runtime(interactive=False).guardian.findings(None if status=='all' else status))

@security_app.command('resolve')
def security_resolve(finding_id: str):
    console.print({'ok':build_runtime(interactive=False).guardian.resolve_finding(finding_id)})

@security_app.command('initialize')
def security_initialize():
    console.print('[yellow]This will treat the current startup items and listening services as the trusted reference.[/yellow]')
    if input('Only continue if you believe the machine is currently in a known-good state. Continue? [y/N]: ').strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    rt=build_runtime(interactive=False)
    console.print({'startup':rt.guardian.capture_startup_baseline(),'network':rt.guardian.capture_network_baseline(),'posture':rt.guardian.posture_scan(record=True)})

@security_app.command('startup-inventory')
def security_startup_inventory(): console.print(startup_inventory())

@security_app.command('startup-capture')
def security_startup_capture(): console.print(build_runtime(interactive=False).guardian.capture_startup_baseline())

@security_app.command('startup-check')
def security_startup_check(): console.print(build_runtime(interactive=False).guardian.check_startup_baseline(record=True))

@security_app.command('network-capture')
def security_network_capture(): console.print(build_runtime(interactive=False).guardian.capture_network_baseline())

@security_app.command('network-check')
def security_network_check(): console.print(build_runtime(interactive=False).guardian.check_network_baseline(record=True))

@security_app.command('process')
def security_process(pid: int): console.print(inspect_process(pid))

@security_app.command('process-triage')
def security_process_triage(min_score: int=30): console.print(process_triage(min_score=min_score,limit=100))

@security_app.command('network-activity')
def security_network_activity(limit: int=100): console.print(network_activity_summary(limit))

@security_app.command('file-signature')
def security_file_signature(path: str): console.print(file_signature(Path(path).expanduser()))

@security_app.command('baseline-add')
def security_baseline_add(name: str,path: str,recursive: bool=True,extensions: str=''):
    exts=[x.strip() for x in extensions.split(',') if x.strip()]
    console.print(build_runtime(interactive=False).guardian.add_integrity_baseline(name,Path(path).expanduser(),recursive,exts))

@security_app.command('baseline-list')
def security_baseline_list(): console.print(build_runtime(interactive=False).guardian.list_integrity_baselines())

@security_app.command('baseline-check')
def security_baseline_check(name: str): console.print(build_runtime(interactive=False).guardian.check_integrity_baseline(name,record=True))

@security_app.command('baseline-refresh')
def security_baseline_refresh(name: str): console.print(build_runtime(interactive=False).guardian.refresh_integrity_baseline(name))

@security_app.command('baseline-remove')
def security_baseline_remove(name: str): console.print({'ok':build_runtime(interactive=False).guardian.remove_integrity_baseline(name)})

@security_app.command('contain-process')
def security_contain_process(pid: int): console.print(build_runtime(interactive=True).guardian.terminate_user_process(pid))



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

@routine_app.command('add-daily-notify')
def routine_add_daily_notify(name: str, at: str, message: str):
    rt=build_runtime(interactive=False)
    console.print(rt.routines.add(name, {'type':'daily','time':at}, {'type':'notify','message':message}))

@routine_app.command('add-daily-todo')
def routine_add_daily_todo(name: str, at: str, title: str):
    rt=build_runtime(interactive=False)
    console.print(rt.routines.add(name, {'type':'daily','time':at}, {'type':'todo','title':title}))

@routine_app.command('add-weekly-notify')
def routine_add_weekly_notify(name: str, days: str, at: str, message: str):
    rt=build_runtime(interactive=False); day_list=[x.strip().lower() for x in days.split(',') if x.strip()]
    console.print(rt.routines.add(name, {'type':'weekly','days':day_list,'time':at}, {'type':'notify','message':message}))

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
def improve_propose(target_path: str, content_file: str, title: str, rationale: str, tests: str = typer.Option('', '--tests', help='Comma-separated suggested test commands.')):
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

@improve_app.command('suite-add')
def improve_suite_add(name: str, project_path: str,
                      test: list[str] = typer.Option([], '--test', help='Repeatable test command.'),
                      lint: list[str] = typer.Option([], '--lint', help='Repeatable lint/static-check command.'),
                      benchmark: list[str] = typer.Option([], '--benchmark', help='Repeatable benchmark command.'),
                      repetitions: int | None = typer.Option(None, '--repetitions'),
                      max_latency_regression_pct: float | None = typer.Option(None, '--max-latency-regression-pct'),
                      max_memory_regression_pct: float | None = typer.Option(None, '--max-memory-regression-pct')):
    rt=build_runtime(interactive=False)
    console.print(rt.evaluations.create_suite(name,project_path,test,lint,benchmark,repetitions,max_latency_regression_pct,max_memory_regression_pct))

@improve_app.command('suite-list')
def improve_suite_list():
    console.print(build_runtime(interactive=False).evaluations.store.list_suites())

@improve_app.command('suite-remove')
def improve_suite_remove(name: str):
    console.print({'ok':build_runtime(interactive=False).evaluations.store.delete_suite(name)})

@improve_app.command('evaluate')
def improve_evaluate(proposal_id: str, suite: str | None = typer.Option(None, '--suite'),
                     project_path: str | None = typer.Option(None, '--project'),
                     test: list[str] = typer.Option([], '--test'),
                     lint: list[str] = typer.Option([], '--lint'),
                     benchmark: list[str] = typer.Option([], '--benchmark'),
                     repetitions: int | None = typer.Option(None, '--repetitions')):
    rt=build_runtime(interactive=True)
    console.print(rt.evaluations.evaluate(
        proposal_id, suite_name=suite, project_path=project_path,
        test_commands=(test or None), lint_commands=(lint or None), benchmark_commands=(benchmark or None),
        repetitions=repetitions,
    ))

@improve_app.command('evaluations')
def improve_evaluations(status: str = 'all'):
    console.print(build_runtime(interactive=False).evaluations.store.list(None if status=='all' else status))

@improve_app.command('report')
def improve_report(evaluation_id: str):
    console.print(build_runtime(interactive=False).evaluations.store.get(evaluation_id))

@improve_app.command('promote')
def improve_promote(evaluation_id: str):
    console.print(build_runtime(interactive=True).evaluations.promote(evaluation_id))

@improve_app.command('revert-promotion')
def improve_revert_promotion(evaluation_id: str):
    console.print(build_runtime(interactive=True).evaluations.revert_promotion(evaluation_id))

@improve_app.command('cleanup-evaluation')
def improve_cleanup_evaluation(evaluation_id: str):
    console.print(build_runtime(interactive=True).evaluations.cleanup_branch(evaluation_id))


@calendar_app.command('add')
def calendar_add(title: str, start_at: str, end_at: str | None = None, location: str | None = None, notes: str | None = None):
    console.print(build_runtime(interactive=False).calendar.add(title,start_at,end_at,location,notes))

@calendar_app.command('list')
def calendar_list(start: str | None = None, end: str | None = None, limit: int = 50):
    console.print(build_runtime(interactive=False).calendar.list(start,end,limit=limit))

@calendar_app.command('upcoming')
def calendar_upcoming(hours: int = 24):
    console.print(build_runtime(interactive=False).calendar.upcoming(hours=hours))

@calendar_app.command('cancel')
def calendar_cancel(event_id: str):
    console.print({'ok':build_runtime(interactive=False).calendar.cancel(event_id)})

@calendar_app.command('export')
def calendar_export(destination: str = 'artifacts/calendar.ics'):
    rt=build_runtime(interactive=False); target=rt.workspace.resolve(destination)
    console.print({'ok':True,'path':rt.calendar.export_ics(target)})

@personal_app.command('status')
def personal_status():
    rt=build_runtime(interactive=False); console.print({**rt.personal.status(),'queued_notifications':len(rt.notifier.queued())})

@personal_app.command('quiet')
def personal_quiet(start: str = typer.Argument('22:00'), end: str = typer.Argument('07:00'), enabled: bool=True):
    console.print(build_runtime(interactive=False).personal.set_quiet_hours(start,end,enabled))

@personal_app.command('quiet-off')
def personal_quiet_off():
    console.print(build_runtime(interactive=False).personal.set_quiet_enabled(False))

@personal_app.command('focus')
def personal_focus(minutes: int = typer.Argument(60), label: str | None=None):
    console.print(build_runtime(interactive=False).personal.start_focus(minutes,label))

@personal_app.command('focus-off')
def personal_focus_off():
    rt=build_runtime(interactive=False); console.print(rt.personal.stop_focus()); console.print(rt.notifier.flush(max_items=20))

@personal_app.command('flush-notifications')
def personal_flush_notifications():
    console.print(build_runtime(interactive=False).notifier.flush(max_items=50))

@briefing_app.command('now')
def briefing_now(kind: str = typer.Argument('morning'), notify: bool=False):
    rt=build_runtime(interactive=False)
    if kind not in {'morning','evening'}: console.print('[red]kind must be morning or evening[/red]'); raise typer.Exit(2)
    result=rt.briefings.build(kind); console.print(result['text'])
    if notify: console.print(rt.notifier.send('Living Assistant',result['text']))

@session_app.command('list')
def session_list(limit: int=50):
    console.print(build_runtime(interactive=False).sessions.list(limit))

@session_app.command('show')
def session_show(session_id: str, limit: int=50):
    rt=build_runtime(interactive=False); console.print({'session':rt.sessions.get(session_id),'messages':rt.sessions.recent_messages(session_id,limit)})

@session_app.command('search')
def session_search(query: str, limit: int=50):
    console.print(build_runtime(interactive=False).sessions.search(query,limit))

@session_app.command('delete')
def session_delete(session_id: str):
    if input(f'Delete local session {session_id}? [y/N]: ').strip().lower() not in {'y','yes'}: raise typer.Exit(1)
    console.print({'ok':build_runtime(interactive=False).sessions.delete(session_id)})

@integration_app.command('list')
def integration_list():
    console.print(build_runtime(interactive=False).connectors.list())

@integration_app.command('add')
def integration_add(name: str, kind: str, provider: str, capabilities: str, env_prefix: str | None=None):
    caps=[x.strip() for x in capabilities.split(',') if x.strip()]
    console.print(build_runtime(interactive=False).connectors.add(name,kind,provider,caps,env_prefix))

@integration_app.command('enable')
def integration_enable(name: str):
    console.print({'ok':build_runtime(interactive=False).connectors.set_enabled(name,True)})

@integration_app.command('disable')
def integration_disable(name: str):
    console.print({'ok':build_runtime(interactive=False).connectors.set_enabled(name,False)})

@integration_app.command('remove')
def integration_remove(name: str):
    console.print({'ok':build_runtime(interactive=False).connectors.remove(name)})

if __name__ == '__main__': app()
