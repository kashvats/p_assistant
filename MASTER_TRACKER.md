# Living Assistant — Master Fix & Feature Tracker

> Track every bug, improvement, and new feature. Work through them one by one.
> Mark `[ ]` → `[x]` as you complete each item.

---

## 🔴 CRITICAL BUGS (Broken Right Now — Tests Failing)

### Security Tests (Phase 1)

- [x] **BUG-01** · `tools/webtools.py` · `web_search()` crashes with `SERPER_API_KEY is not configured` even when `provider=auto` should fall back to the browser scraper. LLM cannot search the web without a paid API key.
- [x] **BUG-02** · `tools/webtools.py` · `image_search()` same crash — no key, no results. No fallback exists.
- [x] **BUG-03** · `tools/webtools.py` · No `search_budget` counter. A looping agent can make unlimited search calls until it runs out of context or money.
- [x] **BUG-04** · `tools/database.py` · `build_database_tools()` signature is `(config)` but tests and new code call it as `(config, approval_manager)` → `TypeError` on every database operation.
- [x] **BUG-05** · `tools/database.py` · No enforcement of `allowed_tables` allowlist. LLM can query any table including `users`, `sessions`, `password_hash`.
- [x] **BUG-06** · `tools/database.py` · No `sensitive_columns` redaction. `SELECT * FROM users` returns raw `password_hash` values to the LLM.
- [x] **BUG-07** · `tools/gittools.py` · No workspace boundary check. Any `path` string is accepted including `../../etc` — git can be run outside workspace roots.
- [x] **BUG-08** · `tools/gittools.py` · `git_diff()` returns raw diffs with zero secret scanning. A diff containing `API_KEY=sk-abc123` is returned verbatim to the LLM.
- [x] **BUG-09** · `improvements.py` · `propose()` accepts any file path including `security_policy.py`, `approval.py`, `quarantine.py`. The assistant can propose self-jailbreaks.
- [x] **BUG-10** · `connectors.py` · `_SECRET_KEY_RE` only scans dict **keys** for secret patterns. A value like `{"webhook": "Bearer ghp_abc123"}` stores a live token under a benign key name with no error.
- [x] **BUG-11** · `connector_oauth.py` · `microsoft_begin_device()` and `github_begin_device()` return the raw `device_code` credential in the response dict — directly into LLM context. Security leak.
- [x] **BUG-12** · `desktop_intelligence.py` · Window title reading has no approval gate and no opt-in flag. The LLM passively knows what window you're looking at at all times.
- [x] **BUG-13** · `security_policy.py` · `redact_secrets()` does not catch unstructured provider tokens. `"ghp_abcdefghijklmnopqrstuvwxyz123456"` passes through completely unredacted.
- [x] **BUG-14** · `evaluation.py` · `measure_command()` sets `ok=True` on a process that was killed due to timeout. `checks_pass` reads `ok` to determine pass/fail — so timed-out tests are counted as passing. Failed candidates are promotable.
- [x] **BUG-15** · `evaluation.py` · The `timeout` enforcement in `measure_command()` does not set `timeout=True` reliably when the process is killed mid-sleep.
- [x] **BUG-16** · `sqlite_utils.py` · `ThreadLocalSQLite` has no `close_all()` method. `__getattr__` proxies to `sqlite3.Connection` which also has no such method → `AttributeError` in concurrent tests.
- [x] **BUG-17** · `browser.py` · Verify `_install_route_guard` and `_authorize_url` fixes are fully stable after our last session edits.

---

## 🟠 BROKEN FEATURES (Exist But Don't Work)

- [x] **BROKEN-01** · `voice.py` + `cli.py` · Wake word approval/retry now verified against the live `listen_for_command()` flow: the approved SENSITIVE_READ request is consumed by the identical retry and wake-triggered command audio proceeds without a second pending approval. Added regression coverage for action-hash stability.
- [x] **BROKEN-02** · `experience.py` + `daemon.py` · Hourly maintenance now applies confidence-based lifecycle transitions: stale non-confirmed active lessons demote, sufficiently decayed lessons expire from retrieval, user-confirmed lessons are retained, and the daemon records maintenance events. Regression coverage verifies both decay/expiry behavior and daemon invocation.
- [x] **BROKEN-03** · `task_graph.py` + `tools/planning.py` + `runtime.py` · The existing DAG planner is now instantiated by Runtime, exposed as `runtime.planner`, and its five planning tools are registered with the Orchestrator using valid tool schemas. Regression tests verify dependency unlocking and live runtime registration.
- [x] **BROKEN-04** · `orchestrator.py` + `runtime.py` · The live runtime uses profile-configured `max_tool_steps` rather than a fixed 10-step ceiling, and the Orchestrator returns an explicit user-facing limit message when the configured ceiling is reached. Regression coverage verifies an 11-tool-call task completes when configured for 12 steps.
- [x] **BROKEN-05** · `orchestrator.py` + session config · Session history now defaults to 24 messages, supports up to 100 configured messages, and is bounded by a context-token-derived character budget that preserves the newest exchanges. Regression tests verify >12 short messages survive while long histories remain bounded.
- [x] **BROKEN-06** · `aggregator.py` · `aggregate()` now performs structured model synthesis with schema validation, supports legacy model managers without lease contexts, and falls back to a bounded structured synthesis of specialist summaries/evidence/actions when the model returns invalid JSON or is unavailable. Regression coverage verifies both primary and fallback synthesis.
- [x] **BROKEN-07** · `skills.py` + package data · Fresh registries are now seeded from packaged `default_skills.json` with conservative debugging/code-change/research workflows. Existing registries are never overwritten, and user-created skills outrank built-ins on trigger-score ties. Packaging and matching regressions are covered.
- [x] **BROKEN-08** · `webui/index.html` · Reworked the existing single-file dashboard into readable structured JavaScript with visible request/stream error handling, safe DOM-based Markdown rendering, dependency-free code highlighting, and packaged the dashboard HTML into production wheels. Regression tests verify rendering hooks, security headers, and package data.
- [ ] **BROKEN-09** · `overlay.py` · Has commented-out imports. Some UI components are incomplete stubs.
- [ ] **BROKEN-10** · `tools/webtools.py` · `download_url()` saves files to workspace but there is no image-specific download path — asking to "download an image" works inconsistently.

---

## 🟡 INCOMPLETE FEATURES (Started But Half-Built)

- [ ] **INCOMPLETE-01** · `improvements.py` · Self-improvement reads only the target file when proposing a patch. No cross-file context. Produces naive patches that break imports from other modules.
- [ ] **INCOMPLETE-02** · `groups.py` · Group project management exists but has no health monitoring. If one project in a group crashes, the rest keep running silently.
- [ ] **INCOMPLETE-03** · `routines.py` · `assistant_prompt` routine type silently skips when `allow_model_wake=False`. No notification is sent that the routine was skipped.
- [ ] **INCOMPLETE-04** · `connector_oauth.py` · Refresh token logic exists for Google and Microsoft but has no automatic background refresh. Tokens expire mid-session silently.
- [ ] **INCOMPLETE-05** · `security_sensors.py` · macOS Endpoint Security integration is present but Windows Event Log ingestion is not wired into the daemon loop.
- [ ] **INCOMPLETE-06** · `resource_manager.py` · Model eviction is LRU only. No priority-based eviction — a low-priority background model can evict the active foreground Orchestrator model.
- [ ] **INCOMPLETE-07** · `watchers.py` · File system watcher events have no debouncing. A build tool writing 100 files triggers 100 separate daemon events and can flood the system.
- [ ] **INCOMPLETE-08** · `briefing.py` · Morning/evening briefings pull no data from the security guardian or experience engine. Purely calendar + todo based.
- [ ] **INCOMPLETE-09** · `personal_state.py` · Focus mode exists but does not suppress desktop vision or browser activity during quiet hours.
- [ ] **INCOMPLETE-10** · `daemon.py` · No crash recovery. If the daemon crashes it stays dead. No auto-restart, no crash report, no user notification.
- [ ] **INCOMPLETE-11** · `release_manager.py` · Rollback exists in code but there is no simple CLI command to trigger it. User has no easy recovery path.

---

## 🔵 STRUCTURAL / ARCHITECTURAL DEBT

- [ ] **ARCH-01** · `src/living_assistant/` has 50+ flat files. Needs restructuring into `core/`, `agents/`, `security/`, `learning/`, `connectors/`, `desktop/`, `system/`.
- [ ] **ARCH-02** · `api.py` (33KB) — all route handlers are one-liner minified functions. Run `ruff format` and split into domain routers.
- [ ] **ARCH-03** · `cli.py` (58KB) — too large. Split into `cli/commands.py` and `cli/helpers.py`.
- [ ] **ARCH-04** · `evaluation.py` (50KB) — mixes store, engine, measurement. Split into `eval_engine.py`, `eval_store.py`, `eval_measure.py`.
- [ ] **ARCH-05** · `security_sensors.py` (54KB) — mixes Windows and macOS platform code. Split into `sensors_windows.py`, `sensors_macos.py`.
- [ ] **ARCH-06** · All stores call `data_dir()` directly. No dependency injection → hard to test with temp paths.
- [ ] **ARCH-07** · `runtime.py` builds all tools inline. Needs a `ToolRegistry` pattern as tool count grows.

---

## 🟢 NEW FEATURES TO ADD

### Port from `new-curiosity` (Real Files — Already Implemented There)

- [ ] **FEAT-01** · **AST-Safe Patch Engine** — Port `patch_engine.py`. Apply code changes using AST-aware diffing. Eliminates bugs where the AI deletes half a file.
- [ ] **FEAT-02** · **Project Auditor** — Port `project_auditor.py`. Full project health scan: dependency audit, lint score, dead code, security patterns.
- [ ] **FEAT-03** · **Autonomous Repair Loop** — Port `repair_loop.py`. When tests fail after a patch, automatically attempt fix cycles (read error → propose fix → re-run tests → repeat up to N times).
- [ ] **FEAT-04** · **Statistical Regression Detection** — Port `regression_detection.py`. Detect benchmark regressions beyond noise floor instead of a simple percentage threshold.
- [ ] **FEAT-05** · **Per-Run Agent History** — Port `run_history.py`. Persistent audit log of every agent action on a project. Query: "what did you do to this repo last Tuesday?"
- [ ] **FEAT-06** · **Knowledge Gap Detection** — Port `knowledge_gap_detection.py`. Identify topics the assistant consistently fails at. Surface as learning opportunities.
- [ ] **FEAT-07** · **Model Usage Analytics** — Port `model_usage.py`. Track tokens in/out, latency per model per session. Expose in the dashboard.
- [ ] **FEAT-08** · **SearXNG Integration** — Port `web_search.py`. Self-hosted search via SearXNG. Zero-cost, privacy-preserving Serper alternative.
- [ ] **FEAT-09** · **Safe Terminal Command Explainer** — Port `safe_commands.py`. Before executing a shell command, show a human-readable explanation and risk level.

### Net New

- [ ] **FEAT-10** · **AirLLM Provider** — Add `AirLLMProvider` to `model_provider.py`. Run 70B+ models on 4GB VRAM by streaming layers from disk. Optional extra: `pip install -e ".[airllm]"`.
- [ ] **FEAT-11** · **Codebase RAG Indexing** — Index the user's project into a vector store with section-aware chunking. Let the Orchestrator answer "how does X work?" with semantic retrieval.
- [ ] **FEAT-12** · **Workspace Snapshots** — Before any AI touches a project, snapshot the directory. One command to restore to any previous snapshot. Works for non-git projects.
- [ ] **FEAT-13** · **Local Model Manager UI** — WebUI panel to list, pull, and delete Ollama models. Show disk usage and VRAM requirements.
- [ ] **FEAT-14** · **Mobile Bridge** — Telegram or Matrix bot connecting to the local daemon over an encrypted tunnel. Text your assistant from your phone.
- [ ] **FEAT-15** · **Structured Onboarding** — First-launch wizard: workspace setup, model selection, voice on/off, connector setup. Currently zero onboarding.
- [ ] **FEAT-16** · **Peer Agent Discovery** — mDNS-based auto-discovery of other Living Assistant instances on the local network. Delegate workloads to a more powerful machine.
- [ ] **FEAT-17** · **Approval Notification Sound** — Play a short sound when an approval gate fires. Currently silently adds to a list.
- [ ] **FEAT-18** · **Hot-Reload Config** — Watch `assistant.yaml` for changes and apply without a full daemon restart.

---

## 🎨 UI REBUILD (Phase Last — After Backend Is Stable)

- [ ] **UI-01** · Rebuild `webui/index.html` as a proper React + Vite + Tailwind CSS multi-page app.
- [ ] **UI-02** · Chat — Markdown rendering for assistant responses.
- [ ] **UI-03** · Chat — Code syntax highlighting (highlight.js or Prism).
- [ ] **UI-04** · Chat — Live streaming cursor / token indicator while LLM generates.
- [ ] **UI-05** · Approvals — Toast notifications (non-blocking) when approval needed.
- [ ] **UI-06** · Dashboard — Replace hand-drawn Canvas chart with Chart.js / Recharts.
- [ ] **UI-07** · Dashboard — New "Model Manager" page (list/pull/delete Ollama models).
- [ ] **UI-08** · Dashboard — Mobile-responsive layout.
- [ ] **UI-09** · Overlay — `Ctrl+Space` global hotkey → Spotlight-style command palette.
- [ ] **UI-10** · Overlay — Scrollable conversation history sidebar.
- [ ] **UI-11** · Overlay — Smooth expand/collapse animation (currently snaps instantly).
- [ ] **UI-12** · Overlay — In-overlay settings panel (model, voice, focus mode).
- [ ] **UI-13** · Overlay — Drag-to-resize the window.
- [ ] **UI-14** · Overlay — Red badge count on collapsed "eye" when approvals are pending.

---

## Recommended Priority Order

```
1st  → BUG-01 to BUG-17       Tests must be green before anything else
2nd  → BROKEN-01 to BROKEN-05  Core functionality must work
3rd  → ARCH-01 to ARCH-07      Restructure before adding more code
4th  → FEAT-01 to FEAT-09      Port proven code from new-curiosity
5th  → FEAT-10 to FEAT-18      Net new features
6th  → INCOMPLETE-01 to 11     Complete the half-built features
Last → UI-01 to UI-14          Rebuild the interface after backend is solid
```

---

## ?? ADDITIONAL CRITICAL BUGS (Found in Deep Audit Round 2)

- [x] **BUG-18** � pproval.py � ApprovalStore has no TTL or cleanup for stale pending approvals. A pending approval from 3 days ago sits in the queue forever, blocking re-queued actions. No prune() or expire_pending() method exists.
- [x] **BUG-19** � sessions.py � session_search() uses SQL LIKE '%query%' � full table scan on every search. No FTS5 (Full-Text Search) index. Becomes unusably slow after hundreds of sessions.
- [x] **BUG-20** � memory.py � search() also uses a plain LIKE query against the memories table. Same full-table-scan problem. No SQLite FTS index. Degrades with memory growth.
- [x] **BUG-21** � event_bus.py � EventBus is a pure in-memory deque (maxlen=500). On daemon restart, the entire activity history is lost. The WebUI "Activity" tab shows zero events after a restart.
- [x] **BUG-22** � 
otifications.py � _send_now() on Windows calls nothing � there is no Windows toast notification implementation. Only macOS (osascript) is implemented. Windows users get silent notifications with no visual or audio feedback.
- [x] **BUG-23** � watchers.py � poll() snapshots file mtimes but does NOT use debouncing. Any build tool that writes 100 files in 1 second triggers 100 individual file-change events flooding the daemon loop.
- [x] **BUG-24** � 	ools/voicetools.py � uild_voice_tools() returns [] when oice.enabled() is False. This means if voice is disabled in config, the LLM cannot call oice_record even for a one-shot transcription task. Should decouple 
ecord/	ranscribe availability from hands-free being enabled.
- [x] **BUG-25** � 	ools/shell.py � 
un_command has no output size cap in the tool-callable wrapper. A command that writes 500MB to stdout will buffer the entire thing in memory before returning. Only measure_command() in evaluation.py has the 30KB cap.
- [x] **BUG-26** � 
esource_manager.py � _evict_one_locked() uses pure LRU with no priority. The active Orchestrator model can be evicted by a background specialist model that was just loaded. Once evicted, the next Orchestrator turn reloads it � causing unnecessary stutter.
- [x] **BUG-27** � gents.py � SpecialistRouter.delegate() has no timeout. If a specialist model hangs generating a response, the entire calling Orchestrator turn hangs indefinitely.
- [x] **BUG-28** � security_policy.py � is_read_only_sql() does not handle SQL comments (e.g. -- DROP TABLE users or /* DROP */ SELECT 1). A cleverly commented SQL string can bypass the allowlist check.

---

## ?? ADDITIONAL BROKEN FEATURES (Found in Deep Audit Round 2)

- [ ] **BROKEN-11** � pproval.py � Pre-approvals use SHA-256 of action+reason+kind. The hash must match **exactly** � a single space difference (e.g. trailing whitespace in a dynamic path string) silently creates a new pending approval instead of consuming the pre-approval. This is the root cause of voice wake-word approval mismatches.
- [ ] **BROKEN-12** � daemon.py � experiences.maintenance() is called in the daemon tick, but maintenance() only prunes episodes and merges duplicates � it does NOT call experience.decay(). The decay method exists but is never reached from any code path.
- [ ] **BROKEN-13** � canary.py � CanaryEngine._run_host_service() starts the candidate service as a background process but does not clean it up if the health check times out. Orphan processes are left running on the host.
- [ ] **BROKEN-14** � 
esource_manager.py � can_start_model() checks available RAM but not available VRAM when GPU is present. You can start loading a 13B model into a 4GB VRAM GPU even if 12GB are already committed, then Ollama silently falls back to CPU � killing performance without any warning.
- [ ] **BROKEN-15** � connector_oauth.py � Token refresh only triggers when expires_at <= now + 30s. But refresh is called inline during call(). If the refresh HTTP request takes >30s (slow network), the token expires mid-request and the API call fails with a 401.

---

## ?? ADDITIONAL INCOMPLETE FEATURES (Found in Deep Audit Round 2)

- [ ] **INCOMPLETE-12** � daemon.py � Sleep/resume detection (SleepResumeMonitor) fires a resume event correctly but the daemon does NOT re-sync process health checks or watcher baselines after a resume. A laptop that sleeps for 8 hours wakes up with stale health status.
- [ ] **INCOMPLETE-13** � riefing.py � Briefings have no content caching. If the LLM is sleeping/unavailable, calling GET /briefing/morning waits for model load and generation every time with no fallback or cached last result.
- [ ] **INCOMPLETE-14** � groups.py � GroupOrchestrator.start() starts all group projects sequentially. For large groups this is slow. There is no parallel startup option, and no dependency ordering within the group.
- [ ] **INCOMPLETE-15** � sessions.py � prune() deletes old sessions but does NOT archive them. Chat history older than 
etention_days is permanently deleted with no export path.
- [ ] **INCOMPLETE-16** � improvements.py � 
ollback() restores the original file from backup but does NOT check if the file was modified again after the proposal was applied. Rolling back may overwrite legitimate subsequent edits.
- [ ] **INCOMPLETE-17** � 	ools/filesystem.py � search_files() uses simple substring matching on file content. No regex support, no file-type filtering, no binary file detection. Searching a binary file returns garbage bytes.
- [ ] **INCOMPLETE-18** � 	ools/projects.py � Project registration exists (name, path, start_command) but there is no per-project environment variable management. You cannot set PORT=3000 for project A and PORT=4000 for project B separately.
