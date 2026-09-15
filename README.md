# Living Assistant v0.1

A local-first, hardware-adaptive personal assistant scaffold for Windows, Ubuntu/Linux, and macOS.

It is designed around a **sleeping-specialist architecture**:

- A lightweight orchestrator is the only reasoning model normally active.
- Specialist personas (coder, researcher, security analyst, database analyst, planner) are woken only when needed.
- On role/model switches, the previous model can be unloaded from Ollama.
- On low-memory machines, all roles can share a tiny model with different specialist prompts.
- Deterministic background services ("nervous system") handle reminders, health checks, and security observations without keeping an LLM loaded.

## What this build already includes

- Local Ollama model provider with tool-calling loop.
- Hardware profile auto-detection (`lite`, `balanced`, `power`).
- One-active-model policy and unload support.
- Agent delegation and chained specialist hand-offs.
- Safe shell/code execution with risk classification + interactive approval.
- Workspace-bounded file read/write/list/search.
- Project detection and project start/stop/list with logs.
- Web page fetch and direct image/file download.
- Optional Serper web/image search if `SERPER_API_KEY` is configured.
- SQLite, PostgreSQL, MySQL and MongoDB database adapters.
- Read-only database queries by default.
- Local memory + todo system backed by SQLite/FTS5.
- Defensive local security audit for listening ports/connections/processes.
- Native antivirus integration where available:
  - Windows Defender status/quick scan
  - ClamAV status/scan on Linux/macOS if installed
- Local REST API with FastAPI.
- Lightweight daemon loop that does **not** keep an SLM running.
- Cross-platform bootstrap scripts.
- Tests for important safety boundaries.

## Important security model

This is intentionally **not** an unrestricted autonomous root shell.

A model can make mistakes. Therefore:

1. Destructive, privilege-escalating, credential-stealing, or security-disabling commands are blocked.
2. Commands that modify the machine or start programs require user approval by default.
3. File writes are constrained to configured workspace roots.
4. Database operations are read-only by default.
5. Credentials belong in environment variables and are not written into assistant memory.
6. The security module monitors and assists; it cannot guarantee that your laptop will never be hacked.

## Recommended model profiles

The defaults are intentionally conservative.

### Your machine: Ryzen 5 5600H / 32 GB RAM / GTX 1650 4 GB

Default profile: `balanced`

- Orchestrator: `qwen3.5:4b`
- General assistant: `qwen3.5:4b`
- Coder: `qwen3.5:4b`
- Research: `qwen3.5:2b`
- Security: `qwen3.5:2b`
- Database: `qwen3.5:2b`

Because only one model is intended to be active at a time, this avoids trying to fit every specialist into 4 GB VRAM simultaneously. Ollama/llama.cpp can still use system RAM and partial GPU acceleration depending on the runtime and platform.

### 8 GB RAM machine

Default profile: `lite`

- All roles: `qwen3.5:0.8b`
- Smaller context window
- One task at a time
- No automatic multi-step specialist chains unless explicitly enabled
- Background daemon remains deterministic and model-free

### 48+ GB RAM / larger GPU

Profile: `power`

- Orchestrator/coder: `qwen3.5:9b`
- Specialists: `qwen3.5:4b`
- Larger context
- More specialist hand-offs

You can override every model in `config/assistant.yaml`.

## Install

### 1. Install Python 3.11+

Create a venv:

```bash
python -m venv .venv
```

Activate it:

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:
```bash
source .venv/bin/activate
```

### 2. Install this package

```bash
pip install -e .
```

Optional DB drivers:

```bash
pip install -e ".[db]"
```

Development/testing:

```bash
pip install -e ".[dev]"
```

### 3. Install Ollama

Install Ollama for your OS and make sure its local service is running.

Then let the assistant choose a profile:

```bash
organism doctor
```

Pull the models it recommends. Example balanced profile:

```bash
ollama pull qwen3.5:4b
ollama pull qwen3.5:2b
```

Lite:

```bash
ollama pull qwen3.5:0.8b
```

### 4. Configure

```bash
cp .env.example .env
```

On Windows:
```powershell
Copy-Item .env.example .env
```

Edit `config/assistant.yaml` if desired.

## Run

Interactive assistant:

```bash
organism chat
```

One-shot request:

```bash
organism ask "Inspect this Python project and tell me how to run it" --cwd /path/to/project
```

Project registry:

```bash
organism project add myapp /path/to/project
organism project run myapp
organism project list
organism project stop myapp
```

System/security check:

```bash
organism security audit
organism security antivirus-status
```

Start the lightweight event loop:

```bash
organism daemon
```

Start the local API:

```bash
organism serve --host 127.0.0.1 --port 8787
```

## Example tasks

```text
Run my backend project.
Open the project named RetailEye and start its frontend and backend.
Read the error in logs/process-123.log and propose a fix.
Create a Python script that cleans these CSVs and run its tests.
Query my production replica and summarize today's failed jobs.
Download the image from this URL into my workspace.
Check which local ports are listening and flag anything unusual.
Remember that I prefer my dev servers on ports 3000 and 8000.
Add a reminder to renew the SSL certificate on Friday.
```

## Web and image search

Direct downloads work without an API key:

```text
Download https://example.com/photo.jpg to assets/photo.jpg
```

For search, set:

```env
SERPER_API_KEY=...
```

Then the agent can use web or image search and download a selected URL.

The design deliberately avoids brittle search-engine scraping.

## Databases

Use environment variables for DSNs, e.g.:

```env
DB_MAIN_URL=postgresql://user:password@127.0.0.1:5432/appdb
DB_ANALYTICS_URL=mongodb://127.0.0.1:27017/analytics
```

The LLM refers to the alias (`main`, `analytics`) instead of seeing hard-coded secrets in config.

SQL adapters reject non-read-only statements unless you deliberately change the policy.

## "Living organism" design

The daemon is intentionally mostly non-AI. It can:

- watch CPU/RAM pressure,
- observe newly listening local ports,
- check due reminders,
- write local events,
- wake the orchestrator only for an event that actually needs interpretation.

This is much more efficient than leaving multiple agents generating or holding model weights continuously.

## Limitations of v0.1

- It is a strong scaffold/MVP, not an infallible autonomous operator.
- The security module is defensive monitoring, not an EDR replacement.
- The agent currently uses a CLI approval prompt. A desktop approval UI is a good v0.2.
- Browser automation is not bundled yet.
- Voice wake-word/STT/TTS are not bundled yet.
- Calendar/email integrations are not bundled yet.
- Model quality on the 0.8B profile is limited; use more deterministic tools and simpler requests there.

See `ROADMAP.md` and `BUILD_PROMPT.md`.
