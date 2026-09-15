# Master Build Prompt — Living Assistant

Build a production-quality, local-first personal assistant called **Living Assistant** that turns a Windows, Ubuntu/Linux, or macOS laptop into a safe, resource-aware personal agent.

## Core goal

The assistant should feel persistent and proactive like a "living organism", but must not waste resources. Use a **lightweight deterministic nervous system** for monitoring, scheduling, reminders, resource checks, and event detection. Reasoning models must sleep when not needed.

The system must be usable on:

- Main target: AMD Ryzen 5 5600H, NVIDIA GTX 1650 4 GB VRAM, 32 GB RAM.
- Minimum target: 8 GB RAM laptop with no useful discrete GPU.
- Windows 10/11, Ubuntu/Linux, and macOS.
- Prefer Python 3.11+ for the orchestration layer.

## Architecture

Create these layers:

1. **Nervous System / Daemon**
   - Extremely low idle CPU/RAM.
   - No LLM kept loaded while idle.
   - Watches reminders, CPU/RAM pressure, registered project processes, selected folders, new listening ports, and security events.
   - Emits normalized events to the orchestrator only when reasoning is needed.

2. **Orchestrator**
   - Receives user intent/events.
   - Creates a short plan.
   - Chooses tools vs specialist agents.
   - Never uses an expensive model if deterministic code can solve the task.
   - Uses a finite state/task graph with hard limits on steps, hand-offs, time, and tool calls.
   - Maintains an audit trail.
   - Supports interruption/cancellation.

3. **Sleeping specialist agents**
   - General assistant
   - Coding agent
   - Research/web agent
   - Database agent
   - Defensive security agent
   - Planning/daily-life agent
   - Future optional agents through a plugin registry.

   Only one specialist model should normally be loaded at once. Specialists may use the same physical SLM with different system prompts on small hardware.

4. **Inter-agent handoff**
   - A specialist can return a structured handoff:
     `{role, task, context_needed, reason}`.
   - The orchestrator decides whether the handoff is justified.
   - Unload/sleep the prior model before loading a different model when memory pressure requires it.
   - Cap handoff depth to prevent loops.
   - When an agent lacks information, it should formulate a high-quality prompt/request for the next specialist instead of hallucinating.

5. **Model runtime abstraction**
   - Default: Ollama local API.
   - Also support an OpenAI-compatible local endpoint such as llama.cpp server.
   - Do not couple business logic to one model vendor.
   - Support model unload/keep-alive controls.

## Adaptive hardware profiles

At startup, inspect OS, RAM, CPU count, GPU vendor/VRAM where available, and current memory pressure.

Create at least:

### Lite
For 8-12 GB RAM:
- 0.5B-1B class quantized model.
- Small context.
- One agent at a time.
- Reduced automatic delegation.
- Prefer deterministic tools.
- No local embeddings model unless explicitly enabled.
- No always-on vision model.

### Balanced
For ~16-40 GB RAM and modest GPU:
- 2B-4B orchestrator/specialists.
- One loaded model at a time.
- Moderate context.
- Allow limited handoffs.

For Ryzen 5 5600H + GTX 1650 4 GB + 32 GB RAM, default to this profile. Do not assume the full model fits in VRAM; allow CPU+GPU hybrid inference.

### Power
For high-memory systems:
- 7B-14B class models when appropriate.
- Larger context.
- More parallel non-model tools, but still avoid unnecessary concurrently loaded LLMs.

All model names must be configurable. Never hard-code the architecture around a specific model family.

## Required tools/capabilities

### Local files
- List/read/search/write/move files.
- Default write boundary is an approved workspace.
- Block path traversal.
- Offer a diff before overwriting important files.
- Trash/quarantine instead of irreversible delete where possible.

### Code and shell execution
- Run Python and project commands.
- Detect common project types:
  - Python/pip/uv/poetry
  - Node/npm/pnpm/yarn
  - Docker Compose
  - Java/Maven/Gradle
  - Go
  - Rust/Cargo
- Start long-running projects and track PID/logs.
- Stop/restart/status.
- Stream/tail logs.
- Environment variable support without leaking secrets.

### Coding agent
- Inspect repository.
- Make a plan.
- Edit files.
- Run format/lint/tests.
- Fix failures iteratively within bounded attempts.
- Show final changed-file summary.
- Use git branches/commits optionally, never destructive git commands without approval.

### Web/research
- HTTP fetch with strict timeouts and download limits.
- Search provider abstraction.
- Image search provider abstraction.
- Download an image/file by URL.
- Validate content type, file size, and extension.
- Save only in approved workspace.
- Respect robots/terms and do not bypass access controls.

### Database
- Connection aliases loaded from environment variables or secret store.
- SQLite, PostgreSQL, MySQL, MongoDB adapters.
- Read-only by default.
- SQL parser/policy rejects DDL/DML unless user explicitly enables a write transaction.
- Add query timeout and row limit.
- Never print passwords/tokens.
- Database specialist should explain queries before high-impact operations.

### Memory
- Local SQLite store.
- Searchable conversational facts, user preferences, project facts, todos, and task history.
- User-controllable memory.
- Never store secrets unless explicitly designated in a secret store.
- Prefer FTS/local indexing before adding an embeddings model.

### Daily-life functions
- Todos/reminders.
- Notes.
- Project registry.
- Clipboard integration (optional).
- Calendar/email connector plugin interfaces.
- "Morning brief" and "end-of-day summary" plugins.
- Local notification integration.

### Defensive security
The assistant must help protect the local machine but must never claim perfect protection.

Include:
- Local listening-port inventory.
- Established connection inventory.
- Process inventory and parent/child relationships.
- Startup/persistence item checks.
- Recent suspicious file changes in watched folders.
- Optional hash/reputation provider interface.
- Windows Defender integration where present.
- ClamAV integration where installed.
- macOS security status checks where feasible.
- Alert on unknown new listening services.
- Optional quarantine workflow with explicit approval.
- Never disable firewall, antivirus, EDR, OS updates, disk encryption, or other protections.
- Never expose credentials.
- Never automatically run downloaded executables.
- Never perform offensive scanning against third-party systems.

## Permission/risk system

Classify actions:

- `READ`: normally auto-allowed.
- `WRITE_WORKSPACE`: allow if inside configured workspace, optionally show diff.
- `EXECUTE`: ask approval unless command is on a safe allowlist.
- `NETWORK_FETCH`: allow normal HTTPS fetch; enforce limits.
- `DB_READ`: allow against configured aliases.
- `DB_WRITE`: explicit confirmation per transaction.
- `SYSTEM_CHANGE`: explicit confirmation.
- `PRIVILEGED`: explicit confirmation and preferably require the user to perform the elevation manually.
- `DESTRUCTIVE`: block by default.

Have a deterministic policy engine outside the LLM. Never let the LLM override policy.

## Safety against prompt injection

Treat all external content as untrusted data:
- Web pages, README files, source code comments, DB values, logs, emails, documents and images can contain malicious instructions.
- Never allow retrieved content to redefine system policies.
- Separate `instructions` from `observations`.
- Before executing a command derived from external content, require policy validation and approval according to risk.
- Strip/ignore instructions that ask for secrets, policy changes, disabling security, or unrelated actions.

## Model behavior

Orchestrator system prompt should require:
- Prefer tools over guessing.
- Verify before modifying.
- Explain the intended action briefly before high-impact actions.
- Use the smallest capable specialist.
- Keep resource usage low.
- Avoid recursive agent chatter.
- Stop once the user goal is satisfied.
- Preserve user files by default.
- Never invent successful command results.
- If a tool fails, surface the real error and adapt.

## Resource manager

Implement:
- RAM thresholds.
- CPU load thresholds.
- model unload.
- context trimming/summarization.
- max concurrent subprocesses.
- download size limits.
- per-tool timeout.
- global task timeout.
- backpressure when system is under load.

When RAM is low:
1. unload model,
2. reduce context,
3. stop optional indexing,
4. pause nonessential watchers,
5. refuse to start another heavy task until resources recover.

## Persistence

Use a data directory appropriate to the OS (e.g. platformdirs). Store:
- config,
- SQLite memory,
- todos,
- events,
- task audit logs,
- registered projects,
- process metadata,
- downloaded artifacts,
- temporary files.

Keep secrets separate.

## Interfaces

Implement:
- CLI interactive chat.
- One-shot CLI.
- Local REST API bound to `127.0.0.1` by default.
- Later-ready interfaces for desktop tray UI, voice, mobile LAN client and browser extension.

Never bind an unauthenticated control API to `0.0.0.0` by default.

## Voice (future-ready)

Design interfaces for:
- wake word,
- speech-to-text,
- text-to-speech.

Do not require voice packages in the minimal install.

## "Living organism" behaviors

Add safe proactive behaviors:
- notify when a registered project crashes,
- alert when a new local port begins listening,
- notify on high sustained RAM/CPU,
- remind on due tasks,
- summarize recurring failures,
- suggest cleanup but never delete automatically,
- learn project start commands only after explicit user confirmation,
- sleep all models when idle.

## Testing

Include tests for:
- workspace path traversal rejection,
- destructive command blocking,
- privilege/security-disable command blocking,
- read-only SQL enforcement,
- model profile selection,
- handoff-depth limit,
- project command detection,
- URL/content-type validation,
- prompt-injection data boundary.

## Deliverables

Return a runnable repository with:
- `pyproject.toml`
- source package
- config template
- `.env.example`
- cross-platform setup scripts
- README
- architecture document
- threat model
- roadmap
- unit tests
- sample plugin
- local API
- CLI
- daemon
- no placeholder-only functions for the critical path.

Prioritize a reliable MVP over pretending every advanced feature is complete. Mark future interfaces clearly.
