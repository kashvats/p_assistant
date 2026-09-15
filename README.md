# Living Assistant v0.5 — Personal Operating Layer

A local-first, hardware-adaptive personal assistant for Windows, Ubuntu/Linux and macOS. A deterministic **nervous system** stays awake for lightweight monitoring/scheduling while local SLMs sleep until reasoning is needed.

## v0.5 highlights

Everything from v0.4 remains, plus:

- **Local calendar/agenda** with create/list/cancel and `.ics` export.
- **Morning and evening briefings** built deterministically from calendar, todos, project health, approvals and recent important events.
- **Quiet hours + focus mode**. Non-urgent notifications are durably queued and flushed later instead of being lost.
- **Daily + weekly routines** in addition to event/interval routines. These do not need an LLM.
- **Local conversation/session history** with bounded context, configurable retention and common credential redaction.
- **Native approval window** using Tkinter (`organism approval ui`).
- **Connector registry** for future mail/calendar/files/contact providers. The registry stores metadata/env-prefixes, never credentials.
- Background model-waking routines are suppressed while quiet/focus mode is active.
- Expanded test suite: **44 passing tests**.

## Hardware profiles

### Main target — Ryzen 5 5600H / GTX 1650 4 GB / 32 GB RAM

Use the auto-selected `balanced` profile. Default roles use 4B/2B class local models, with normally one physical model active at a time. STT stays CPU-first by default so it does not fight a 4 GB GPU for VRAM.

### 8 GB systems

The `lite` profile uses one tiny SLM, short context and deterministic tools first. Browser and voice sensor tools remain disabled by default. Calendar, briefings, quiet hours, routines, sessions and the daemon are lightweight and still usable.

## Upgrading from v0.4

v0.5 uses additive SQLite tables and the same platform-specific data directory, so existing projects, approvals, todos, routines and skills remain reusable. Keep a backup of your assistant data directory before replacing a working installation, then install this repository with `pip install -e .`.

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

Install/start Ollama separately, then:

```bash
organism doctor
```

Optional extras:

```bash
pip install -e ".[desktop]"  # tray, clipboard, screenshots
pip install -e ".[browser]"  # Playwright operator
pip install -e ".[voice]"    # local push-to-talk STT/TTS
playwright install chromium    # when browser extra is used
```

## Personal calendar

```bash
organism calendar add "Client call" 2026-09-15T15:30:00 --end-at 2026-09-15T16:00:00
organism calendar upcoming --hours 48
organism calendar list
organism calendar export artifacts/my-calendar.ics
```

The calendar is local SQLite data. External calendar providers are intentionally not hard-wired into the core.

## Morning / evening briefing

```bash
organism briefing now morning
organism briefing now evening
```

Default daemon schedule:

```yaml
briefings:
  enabled: true
  morning_time: "08:30"
  evening_time: "20:30"
  notify: true
  use_model: false
```

Briefings are deterministic by default, so they do **not** load an SLM just to tell you today's agenda.

## Quiet hours and focus mode

```bash
organism personal quiet 22:00 07:00
organism personal focus 60 --label "Deep work"
organism personal status
organism personal focus-off
organism personal quiet-off
```

During quiet/focus mode, non-urgent notifications are placed into a local queue. They can be flushed automatically when quiet mode ends or manually:

```bash
organism personal flush-notifications
```

## Daily and weekly routines

```bash
organism routine add-daily-notify morning-water 09:00 "Drink water"
organism routine add-daily-todo logs 18:30 "Review production alerts"
organism routine add-weekly-notify backup "sun" 19:00 "Check laptop backup"
organism routine add-weekly-notify planning "mon,wed,fri" 09:15 "Review top priorities"
```

Existing event/interval routines still work. Model-waking `assistant_prompt` routines remain disabled by default and are also prevented from waking a model while focus/quiet mode is active.

## Session continuity

Interactive chat creates a local session by default:

```bash
organism chat
```

Reuse a known session:

```bash
organism chat --session SESSION_ID
organism ask "Continue debugging the API" --session SESSION_ID
```

Inspect/search/delete history:

```bash
organism session list
organism session show SESSION_ID
organism session search "RetailEye"
organism session delete SESSION_ID
```

Disable history for a chat:

```bash
organism chat --no-history
```

Default policy stores only a bounded history for 30 days and redacts common patterns such as `password=...`, bearer tokens, API keys and private-key blocks before persistence. This is defense-in-depth, **not** a substitute for keeping secrets in environment variables or a password manager.

## Native approval window

Pending noninteractive actions can be reviewed without living in a terminal:

```bash
organism approval ui
```

The Tkinter window shows the exact action, reason and risk kind and provides **Approve once** / **Deny** controls.

## Connector registry

v0.5 introduces a provider-neutral connector registry without storing credentials:

```bash
organism integration add work-mail mail gmail "read,draft" --env-prefix WORK_MAIL
organism integration list
organism integration disable work-mail
```

Actual Gmail/Google Calendar/etc. provider implementations remain separate capability modules. Secrets must come from environment variables or OS secret storage, not the registry JSON.

## Existing operator capabilities

The previous layers remain:

- project registration, process supervision, logs, health checks and bounded auto-restart;
- frontend/backend/worker project groups;
- Git status/diff and approval-gated branch/commit operations;
- file/code operations with workspace boundaries and diffs;
- bounded web fetch, image search/download and executable quarantine;
- SQLite/PostgreSQL/MySQL/MongoDB read-only adapters;
- defensive process/port/network inspection and Defender/ClamAV integration;
- optional isolated Playwright browser sessions;
- optional push-to-talk local STT/TTS;
- reviewable, approval-gated self-improvement proposals.

## Nervous system

```bash
organism daemon
```

While idle it performs deterministic work only:

```text
reminders / calendar / briefings / routines
              │
project health / crashes / file watches / ports
              │
quiet-hours queue / session retention maintenance
              │
              ▼
       NO LLM KEPT LOADED
```

## Control Center

```bash
organism serve
```

Open `http://127.0.0.1:8787/dashboard`.

v0.5 adds personal state, calendar, deterministic briefing, session history, queued notifications and connectors to the dashboard/API.

## Security model

The assistant is not an unrestricted root shell and cannot guarantee that your laptop will never be hacked. Deterministic code outside the LLM enforces destructive-command blocking, approvals, workspace boundaries, DB read-only defaults, quarantine and browser/sensor scope.

Keep OS updates, Defender/EDR/antivirus, firewall, disk encryption, MFA, backups and a password manager enabled.

## Tests

```bash
pytest -q
```

Current repository: **44 passing tests**.
