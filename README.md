# Living Assistant v0.3 — Desktop Operator

A local-first, hardware-adaptive personal assistant for Windows, Ubuntu/Linux, and macOS. It combines a low-resource deterministic **nervous system** with a local-model orchestrator and sleeping specialist agents.

v0.3 adds a practical desktop/operator layer while preserving the v0.2 security model: the model proposes actions, but deterministic code enforces workspace boundaries, approvals, read-only database policy, download quarantine, command blocking, and resource limits.

## What is included

### Core intelligence
- Ollama local-model provider and one-active-model manager.
- Orchestrator with specialist handoffs: coder, researcher, security, database, planner, general.
- Hardware profiles: `lite`, `balanced`, `power`.
- Skills and local SQLite/FTS memory.
- Tool-step and handoff limits.

### Projects and coding
- Project detection for Python, Node, Docker Compose, Maven, Gradle, Go and Rust.
- Persistent project registry and supervised process registry.
- Start/stop/restart/logs, health URLs, bounded auto-restart.
- **Project groups** for multi-service applications such as frontend + backend + worker.
- Git status, diff, log, branch creation and commit tools.
- File writes return unified diffs; `preview_write_file` can show a diff before changing anything.

### Desktop operator
Optional `desktop` extra:
- Clipboard read/write.
- Full-desktop screenshots.
- System tray process.
- Native notifications inherited from v0.2.

Clipboard reads and screenshots always require approval because they may reveal sensitive information.

### Browser operator
Optional `browser` extra:
- Rendered-page snapshots with Playwright.
- Optional page screenshots.
- Approved click/fill operations.
- Browser downloads disabled in the isolated automation context.
- Disabled by default on the `lite` hardware profile.

The MVP browser controller intentionally does not reuse your normal browser profile or cookies.

### Safer downloads
- Normal images/documents can be downloaded into the approved workspace.
- Executables/scripts and dangerous MIME types are routed to a **quarantine vault**.
- Quarantined items record source URL, size and SHA-256.
- Release from quarantine requires explicit approval.
- Downloaded executables are never run automatically.

### Security
- Command deny rules for destructive/security-disabling actions.
- Privileged operations require approval.
- Read-only SQL by default.
- Workspace path canonicalization.
- Defensive local port/process/network inventory.
- Windows Defender / ClamAV hooks when available.
- Prompt-injection boundary for external observations.
- Local API binds to `127.0.0.1` by default.

## Recommended hardware profiles

### Your target — Ryzen 5 5600H / 32 GB RAM / GTX 1650 4 GB
Use `balanced`:
- Orchestrator/general/coder: configurable ~4B-class model.
- Research/security/database/planner: configurable ~2B-class model.
- Normally only one model stays loaded.
- Browser/desktop extras are available.

### 8 GB system
Use `lite`:
- ~0.5B–1B-class quantized model.
- 4K context by default.
- One handoff maximum.
- Browser automation hidden unless explicitly enabled.
- No always-on embeddings or vision model.
- Nervous system remains deterministic and lightweight.

## Install

Python 3.11+ is recommended.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e .
```

Optional desktop operator:

```bash
pip install -e ".[desktop]"
```

Optional browser operator:

```bash
pip install -e ".[browser]"
playwright install chromium
```

Database drivers:

```bash
pip install -e ".[db]"
```

Then install/start Ollama and run:

```bash
organism doctor
```

## Core usage

```bash
organism chat
organism ask "Inspect this repository and tell me why the tests fail"
organism daemon
organism serve
```

Control center:

```text
http://127.0.0.1:8787/dashboard
```

The v0.3 dashboard includes one-click **Approve once** / **Deny** controls for pending actions.

## Register a project

```bash
organism project add api /path/to/api \
  --start "uvicorn app:app --reload --port 8000" \
  --test "pytest" \
  --auto-restart \
  --health-url http://127.0.0.1:8000/health

organism project add web /path/to/web --start "npm run dev"
```

Run and inspect:

```bash
organism project run api
organism project processes
organism project logs PROCESS_ID --lines 200
organism project test api
```

## Multi-project groups

```bash
organism group add retaileye "api,web"
organism group plan retaileye
organism group run retaileye
organism group stop retaileye
```

A group start uses one approval for the exact registered set of commands. Automatic restart can only replay a command already stored for that project.

## Git-aware coding

```bash
organism git status /path/to/project
organism git diff /path/to/project
```

Inside agent chat, the coder can also use `git_status`, `git_diff`, `git_log`, approval-gated branch creation, and approval-gated commit. It cannot silently stage arbitrary files or run destructive resets through these Git tools.

## Desktop actions

```bash
organism desktop clipboard-read
organism desktop screenshot artifacts/current-screen.png
organism tray
```

`organism tray` runs the low-resource event loop from the tray. Run `organism serve` separately if you want the web control center available too.

## Quarantine

```bash
organism quarantine list
organism quarantine release ITEM_ID downloads/file.exe
```

Releasing a file does **not** run it. Scan and inspect it first.

## Example natural-language tasks

```text
Run my RetailEye stack.
Check git status, fix the failing backend test, show me the diff and rerun tests.
Take a screenshot so you can help me understand what is on screen.
Read my clipboard and turn the copied error into a bug report.
Open this web page in the isolated browser and summarize the rendered content.
Download this image into assets/reference.jpg.
Check what new ports opened since the last daemon tick.
Query my analytics database read-only and summarize today's failures.
```

## Why the system does not keep every SLM alive

A laptop gets better responsiveness by keeping deterministic watchers alive and loading reasoning only when necessary. Multiple specialist roles can share the same physical model with different prompts. A dedicated model can later be assigned to a role after benchmarking proves the quality improvement is worth its memory cost.

## Current limitations

- Browser automation is deliberately isolated and minimal; it is not yet a full human-like persistent browser controller.
- The tray is a lightweight operator surface, not a polished native desktop application.
- Voice/STT/TTS is not bundled yet.
- Security monitoring is useful defense-in-depth, not a guarantee against compromise and not a replacement for firewall, OS updates, Defender/EDR, disk encryption, backups and MFA.
- Self-improvement remains proposal/skill based; the assistant cannot silently rewrite its own policy engine.

See `ARCHITECTURE.md`, `THREAT_MODEL.md`, `ROADMAP.md`, and `BUILD_PROMPT.md`.
