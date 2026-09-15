# Living Assistant v0.2

A local-first, hardware-adaptive personal assistant for Windows, Ubuntu/Linux, and macOS.

The design goal is a laptop assistant that feels persistent and proactive without keeping several LLMs resident in memory. A lightweight deterministic **nervous system** remains active; local SLMs wake only when a task needs reasoning.

## v0.2 highlights

- Sleeping specialist architecture: orchestrator + coder/research/security/database/planner/general roles.
- Hardware profiles for 8 GB machines through larger workstations.
- Ollama provider with one-active-model policy and explicit unload.
- Local shell/code execution guarded by deterministic policy and approval.
- Persistent approval queue for API/noninteractive use.
- Persistent project registry with start/test commands, health URL, auto-restart and bounded restart count.
- Persistent managed-process registry with logs, stop/restart/status.
- Lightweight crash supervisor and optional project health checks.
- Polling filesystem watchers with no model required.
- Native desktop notifications where supported.
- Todos/reminders that trigger from the daemon.
- New-listening-port monitoring and defensive local security inventory.
- Windows Defender / ClamAV integration when available.
- Local memory in SQLite/FTS5.
- User-confirmed reusable skills that can enrich prompts but cannot modify policy.
- Web fetch/search/image search/download tools.
- Read-only-by-default SQLite/PostgreSQL/MySQL/MongoDB tools.
- Local FastAPI control plane and a small localhost dashboard.
- Startup helpers for systemd user service, Windows Task Scheduler and macOS LaunchAgent.

## The architecture

```text
                       ┌─────────────────────┐
                       │ User / CLI / API    │
                       └──────────┬──────────┘
                                  │
                        ┌─────────▼─────────┐
                        │   Orchestrator    │
                        │ smallest capable │
                        │ model + tools    │
                        └──────┬─────┬─────┘
                               │     │
                    tools ─────┘     └── specialist handoff
                               │
          ┌────────────────────▼───────────────────┐
          │ Policy / approval / workspace boundary │
          └────────────────────┬───────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │ files | shell | projects | web | DB | memory | security │
  └─────────────────────────────────────────────────────────┘

  ALWAYS-ON, NO LLM:
  reminders + file watches + resource checks + port changes
  + process crash detection + bounded auto-restart + notify
```

## Hardware behavior

### Lite: ~8-12 GB RAM

- Default `qwen3.5:0.8b` for all roles.
- One model at a time.
- 4K context.
- One specialist handoff.
- Deterministic tools preferred over model delegation.
- Filesystem monitoring is polling-based and capped.

### Balanced: your Ryzen 5 5600H / GTX 1650 4 GB / 32 GB RAM

- Orchestrator/general/coder: `qwen3.5:4b`.
- Research/security/database/planner: `qwen3.5:2b`.
- One active model at a time.
- 8K context.
- Up to two specialist handoffs.
- CPU+GPU inference can be used by the local runtime; the design does not require every model to fit entirely in 4 GB VRAM.

### Power: 48+ GB RAM

- Larger configurable models and context.
- More handoffs, still bounded.

Every model name is configurable in `config/assistant.yaml`.

## Install

Python 3.11+ is recommended.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
organism doctor
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
organism doctor
```

Install/start Ollama separately, then pull the models shown by `organism doctor`.

Balanced example:

```bash
ollama pull qwen3.5:4b
ollama pull qwen3.5:2b
```

Optional database drivers:

```bash
pip install -e ".[db]"
```

## Chat and one-shot tasks

```bash
organism chat
organism ask "Inspect my backend, run its tests and explain failures"
```

Examples:

```text
Run my RetailEye backend.
Read the last process log and fix the Python error.
Check which local ports started listening recently.
Query my main database for failed jobs today.
Download this image into assets/reference.jpg.
Remember that this project uses port 8000.
Remind me tomorrow at 10:00 to renew the SSL certificate.
```

## Projects

Register a project. The registration itself makes that directory an approved workspace root on subsequent runs.

```bash
organism project add retaileye /path/to/retaileye
```

Specify behavior explicitly when desired:

```bash
organism project add retaileye /path/to/retaileye \
  --start "npm run dev" \
  --test "npm test" \
  --auto-restart \
  --max-restarts 3 \
  --health-url http://127.0.0.1:3000/health
```

Run/status/logs/restart/stop:

```bash
organism project run retaileye
organism project processes
organism project logs PROCESS_ID --lines 200
organism project restart PROCESS_ID
organism project stop PROCESS_ID
```

If an auto-restart project crashes, the nervous system can restart the **same previously approved command** only up to the configured maximum. It cannot invent a replacement command.

## Nervous system

Run continuously:

```bash
organism daemon
```

Or one cycle, useful for cron/Task Scheduler:

```bash
organism tick
```

The daemon does not keep an LLM loaded. It handles deterministic jobs such as:

- CPU/RAM pressure observations,
- new listening ports,
- registered process crashes,
- bounded auto-restart,
- health URL failures,
- due reminders,
- watched-file changes,
- desktop notifications.

### Start automatically at login

Linux:

```bash
./scripts/install_daemon_linux.sh
```

macOS:

```bash
./scripts/install_daemon_macos.sh
```

Windows PowerShell:

```powershell
.\scripts\install_daemon_windows.ps1
```

These scripts must be run manually. They do not request administrator/root privileges.

## File watches

```bash
organism watch add source ./src --extensions py,js,ts,tsx
organism watch list
organism watch remove source
```

The v0.2 watcher intentionally uses bounded polling instead of a model or heavy indexer, which is suitable for low-memory machines.

## Approvals

Interactive CLI commands can ask directly. The local API cannot display a terminal prompt, so dangerous actions enter a persistent approval queue.

```bash
organism approval list
organism approval approve APPROVAL_ID
organism approval deny APPROVAL_ID
```

After approval, retry the original request. A matching one-time approval is consumed.

This prevents the API from becoming an unattended arbitrary-command interface.

## User-confirmed skills

Skills are small prompt packs for your own repeatable workflows. They **cannot** modify deterministic policy.

Create `my-skill.txt` with the instructions, then:

```bash
organism skill add retaileye-debug \
  "How I normally debug RetailEye" \
  "retaileye,retail eye,camera backend" \
  my-skill.txt
```

List/remove:

```bash
organism skill list
organism skill remove retaileye-debug
```

The orchestrator automatically includes up to three matching user-confirmed skills based on trigger phrases.

## Local API and dashboard

```bash
organism serve
```

Open:

```text
http://127.0.0.1:8787/dashboard
```

The server refuses non-localhost binding through the CLI. Set `ASSISTANT_API_TOKEN` if another trusted local client needs authenticated access. The simple browser dashboard is disabled when a token is configured; use authenticated API calls instead.

Useful endpoints:

```text
GET  /health
GET  /status
POST /ask
GET  /projects
GET  /processes
GET  /events
GET  /todos
GET  /approvals
POST /approvals/{id}
GET  /watches
GET  /skills
```

## Web and images

Direct HTTP(S) downloads work without a search API key. Downloads are size-limited and are never automatically executed.

For web/image search, set:

```env
SERPER_API_KEY=...
```

Then the agent can search, select a result, and download a file into an approved workspace.

## Databases

Store DSNs only in environment variables:

```env
DB_MAIN_URL=postgresql://user:password@127.0.0.1:5432/appdb
DB_ANALYTICS_URL=mongodb://127.0.0.1:27017/analytics
```

Examples:

```text
Query database alias main for today's failed jobs.
Find the latest 20 documents in MongoDB alias analytics.
```

SQL DDL/DML is rejected by default. MongoDB support in the default agent is `find` only.

## Security philosophy

The LLM is **not** the security boundary. Deterministic code enforces:

- workspace roots,
- shell command blocking/classification,
- explicit approvals,
- DB read-only policy,
- localhost control API,
- bounded downloads,
- bounded auto-restart,
- model handoff limits.

Web pages, source comments, logs, database values and downloaded text are treated as untrusted observations. They are not allowed to redefine security policy.

The assistant can help defend the laptop, but it cannot guarantee that the device will never be hacked. Continue to use firewall, OS updates, Defender/EDR/AV, disk encryption, MFA, backups and a password manager.

## Safe self-improvement

The assistant may improve its usefulness by learning **user-confirmed**:

- project commands,
- project health endpoints,
- reusable prompt skills,
- preferences and non-secret memory,
- failure/event history.

It should not silently rewrite its core code, policy, startup configuration or security protections. A future self-improvement flow should create a patch, run tests/evaluations and require explicit approval before applying it.

## Current limitations

v0.2 is still an engineering MVP. Not yet included:

- native tray GUI with rich approval cards,
- browser automation,
- voice wake word/STT/TTS,
- email/calendar connectors,
- cryptographic plugin signing,
- full EDR-style telemetry,
- semantic/vector memory,
- autonomous self-code modification.

See `ROADMAP.md`.
