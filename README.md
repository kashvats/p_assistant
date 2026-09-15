# Living Assistant v0.4

A local-first, hardware-adaptive personal assistant for Windows, Ubuntu/Linux and macOS. It is designed to feel persistent without wasting resources: a deterministic nervous system stays awake while local SLMs sleep until reasoning is actually required.

## v0.4 highlights

- Local orchestrator + sleeping specialist personas.
- Safe shell/code execution, project supervision and multi-service groups.
- Files, Git, web/image download, DB reads, memory, todos and defensive security inspection.
- Optional clipboard/screenshot desktop tools.
- Optional isolated Playwright browser sessions.
- **Optional push-to-talk voice**: microphone → local STT → orchestrator → optional local TTS.
- **Deterministic routines** driven by time intervals or assistant events.
- **Reviewable self-improvement proposals** with diff, conflict check, backup and approval.
- Persistent approval queue with desktop notifications.
- Risky downloads go to quarantine rather than being executed.

## Hardware profiles

### Main target — Ryzen 5 5600H / GTX 1650 4 GB / 32 GB RAM

Use `balanced`. Default roles use 4B/2B class local models, but normally only one physical model is active at a time. Voice STT defaults to a small CPU model so it does not compete with the 4 GB GPU.

### 8 GB systems

Use `lite` automatically. The default keeps one tiny SLM, short context, one handoff, deterministic tools, and no browser/voice sensor tools unless explicitly enabled.

## Install

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e .
```

Install Ollama separately, start its local service, then:

```bash
organism doctor
```

### Optional extras

Desktop/tray/screenshot/clipboard:

```bash
pip install -e ".[desktop]"
```

Browser automation:

```bash
pip install -e ".[browser]"
playwright install chromium
```

Voice:

```bash
pip install -e ".[voice]"
```

Some operating systems may also require their normal microphone/PortAudio packages or permissions.

## Chat / one-shot

```bash
organism chat
organism ask "Inspect my project and explain why it fails"
```

## Push-to-talk voice

```bash
organism voice status
organism voice record --seconds 5
organism voice transcribe artifacts/voice-input.wav
organism voice ask --seconds 6 --speak
```

Microphone recording always goes through the sensitive-read approval path. There is **no always-on microphone** in v0.4.

## Isolated browser sessions

For natural-language browser work, use `organism chat` or the local API so one runtime stays alive. For direct CLI use, `browser live` keeps the session in one process:

```bash
organism browser live docs https://example.com
```

Inside it:

```text
snapshot
goto https://example.com/docs
click a.next
fill input[name=q] local agent
quit
```

A persistent browser profile is opt-in:

```bash
organism browser live work https://example.com --persistent
```

It uses an assistant-only profile, never your normal Chrome/Edge/Firefox profile.

## Routines

Event notification:

```bash
organism routine add-event-notify backend-crash project_process_crashed "A managed project crashed"
```

Periodic notification:

```bash
organism routine add-interval-notify posture 3600 "Stand up and stretch"
```

Periodic todo:

```bash
organism routine add-interval-todo review-logs 21600 "Review production alerts"
```

A model-waking prompt routine can be configured, but it remains inert while this setting is false:

```yaml
routines:
  allow_model_wake: false
```

This prevents a background scheduler from silently turning into an autonomous high-impact agent.

## Self-improvement proposal workflow

The model can call `propose_improvement`, or you can create a proposal from an edited candidate file:

```bash
organism improve propose workspace/app.py /tmp/new-app.py \
  "Improve retry handling" \
  "Repeated transient network failures are not retried" \
  --tests "pytest,python -m compileall src"
```

Review:

```bash
organism improve list
organism improve show PROPOSAL_ID
```

Apply exact proposal:

```bash
organism improve apply PROPOSAL_ID
organism improve rollback PROPOSAL_ID
```

The engine checks the original file hash, asks approval, makes a backup, and then writes the stored exact content. Security/approval/self-improvement core files are never auto-applied.

## Projects

```bash
organism project add api /path/to/backend \
  --start "uvicorn app.main:app --port 8000" \
  --test "pytest" \
  --auto-restart

organism project run api
organism project processes
organism project logs PROCESS_ID --lines 200
```

Project groups:

```bash
organism group add retaileye "mediamtx,api,frontend"
organism group plan retaileye
organism group run retaileye
```

## Nervous system

```bash
organism daemon
```

It handles process supervision, reminders, health checks, file watches, port changes and deterministic routines without keeping an SLM loaded.

## Control Center

```bash
organism serve
```

Open `http://127.0.0.1:8787/dashboard`.

The dashboard includes status, approvals, projects, groups, processes, quarantine, events, todos, routines, improvement proposals, browser sessions and voice status.

## Security model

The assistant is deliberately **not** an unrestricted root shell. It blocks destructive/security-disabling patterns, asks approval for privileged/state-changing operations, constrains file access to workspace roots, keeps DB access read-only by default, and treats external content as untrusted data.

It helps with defensive monitoring but cannot guarantee protection from hackers. Keep normal OS security, firewall/EDR/antivirus, disk encryption, updates, MFA and backups enabled.

## Tests

```bash
pytest -q
```

The v0.4 repository currently includes 33 passing tests covering prior safety/migration behavior plus routines, voice gating, approval notifications, browser scoping and self-improvement conflict/approval controls.
