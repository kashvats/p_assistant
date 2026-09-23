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
- [x] **BROKEN-09** · `overlay.py` + desktop API · Removed dead commented import stubs, made the existing CustomTkinter overlay dependency explicit, repaired the error-state widget update, and wired the existing Screen eye control to an authenticated `/desktop/analyze-screen` route that delegates to the already approval-gated `DesktopController.analyze_screen()` implementation. Focused overlay/desktop regressions pass.
- [x] **BROKEN-10** · `tools/webtools.py` · `download_url()` saves files to workspace but there is no image-specific download path — asking to "download an image" works inconsistently.

---

## 🟡 INCOMPLETE FEATURES (Started But Half-Built)

- [x] **INCOMPLETE-01** · `improvements.py` · Self-improvement reads only the target file when proposing a patch. No cross-file context. Produces naive patches that break imports from other modules.
- [x] **INCOMPLETE-02** · `groups.py` · Group project management exists but has no health monitoring. If one project in a group crashes, the rest keep running silently.
- [x] **INCOMPLETE-03** · `routines.py` · `assistant_prompt` routine type silently skips when `allow_model_wake=False`. No notification is sent that the routine was skipped.
- [x] **INCOMPLETE-04** · `connector_oauth.py` · Refresh token logic exists for Google and Microsoft but has no automatic background refresh. Tokens expire mid-session silently.
- [x] **INCOMPLETE-05** · `security_sensors.py` · macOS Endpoint Security integration is present but Windows Event Log ingestion is not wired into the daemon loop.
- [x] **INCOMPLETE-06** · `resource_manager.py` · Model eviction is LRU only. No priority-based eviction — a low-priority background model can evict the active foreground Orchestrator model.
- [x] **INCOMPLETE-07** · `watchers.py` · File system watcher events have no debouncing. A build tool writing 100 files triggers 100 separate daemon events and can flood the system.
- [x] **INCOMPLETE-08** · `briefing.py` · Morning/evening briefings pull no data from the security guardian or experience engine. Purely calendar + todo based.
- [x] **INCOMPLETE-09** · `personal_state.py` · Focus mode exists but does not suppress desktop vision or browser activity during quiet hours.
- [x] **INCOMPLETE-10** · `daemon.py` · No crash recovery. If the daemon crashes it stays dead. No auto-restart, no crash report, no user notification.
- [x] **INCOMPLETE-11** · `release_manager.py` · Rollback exists in code but there is no simple CLI command to trigger it. User has no easy recovery path.

---

## 🔵 STRUCTURAL / ARCHITECTURAL DEBT

- [x] **ARCH-01** · `src/living_assistant/` has 50+ flat files. Needs restructuring into `core/`, `agents/`, `security/`, `learning/`, `connectors/`, `desktop/`, `system/`.
- [x] **ARCH-02** · `api.py` (33KB) — all route handlers are one-liner minified functions. Run `ruff format` and split into domain routers.
- [x] **ARCH-03** · `cli.py` (58KB) — split into compatibility-preserving `cli/commands.py` and `cli/helpers.py`; installed `living_assistant.cli:app` entry point verified.
- [x] **ARCH-04** · `evaluation.py` (50KB) — split into `eval_engine.py`, `eval_store.py`, and `eval_measure.py` behind the existing compatibility facade.
- [x] **ARCH-05** · `security_sensors.py` (54KB) — Windows and macOS collectors split into `sensors_windows.py` and `sensors_macos.py` behind the existing sensor platform API.
- [x] **ARCH-06** · Persistent stores expose injectable path/root constructor arguments while retaining `data_dir()` only as the default.
- [x] **ARCH-07** · `runtime.py` composes tools through `ToolRegistry` with ordered registration and duplicate-name protection; 124-tool runtime contract preserved.

---

## 🟢 NEW FEATURES TO ADD

### Port from `new-curiosity` (Real Files — Already Implemented There)

- [x] **FEAT-01** · **AST-Safe Patch Engine** — AST-aware Python proposal/apply guard added; syntax-invalid patches and silent function/class/method deletions are blocked before approval/write.
- [x] **FEAT-02** · **Project Auditor** — bounded offline project audit added with dependency checks, lint score, dead-code candidates, and redacted security-pattern findings; exposed via project tool/CLI.
- [x] **FEAT-03** · **Autonomous Repair Loop** — Bounded approval-gated repair cycles generate AST-safe pending candidates, re-run the exact isolated evaluation plan through an in-process capability, and never auto-apply or auto-promote.
- [x] **FEAT-04** · **Statistical Regression Detection** — Repeated benchmark samples now use robust variance/noise-floor estimation; statistically noisy over-budget point estimates are distinguished from reproducible regressions, with legacy fallback for insufficient samples.
- [x] **FEAT-05** · **Per-Run Agent History** — Persistent redacted run/tool audit history now records project-scoped orchestrator work with run IDs and supports queries such as `last Tuesday`, `last N days`, and YYYY-MM-DD.
- [x] **FEAT-06** · **Knowledge Gap Detection** — Recurring high-failure task topics are detected from redacted experience episodes, scored by project/failure rate, and surfaced through the `knowledge_gaps` learning-opportunity tool.
- [x] **FEAT-07** · **Model Usage Analytics** — Port `model_usage.py`. Track tokens in/out, latency per model per session. Expose in the dashboard.
- [x] **FEAT-08** · **SearXNG Integration** — Port `web_search.py`. Self-hosted search via SearXNG. Zero-cost, privacy-preserving Serper alternative.
- [x] **FEAT-09** · **Safe Terminal Command Explainer** — Port `safe_commands.py`. Before executing a shell command, show a human-readable explanation and risk level.

### Net New

- [x] **FEAT-10** · **AirLLM Provider** — Add `AirLLMProvider` to `model_provider.py`. Run 70B+ models on 4GB VRAM by streaming layers from disk. Optional extra: `pip install -e ".[airllm]"`.
- [x] **FEAT-11** · **Codebase RAG Indexing** — Index the user's project into a vector store with section-aware chunking. Let the Orchestrator answer "how does X work?" with semantic retrieval.
- [x] **FEAT-12** · **Workspace Snapshots** — Before any AI touches a project, snapshot the directory. One command to restore to any previous snapshot. Works for non-git projects.
- [x] **FEAT-13** · **Local Model Manager UI** — WebUI panel to list, pull, and delete Ollama models. Show disk usage and VRAM requirements.
- [x] **FEAT-14** · **Mobile Bridge** — Existing Telegram connector now provides an outbound-HTTPS mobile bridge with explicit chat/user allowlists, private-chat/bot rejection, persistent update offsets, rate limits, bounded/redacted replies, stable per-chat sessions, and daemon integration without exposing a public local API port.
- [x] **FEAT-15** · **Structured Onboarding** — Added an installed `organism onboard` first-launch wizard backed by the existing config/connector stores: atomic per-user config, workspace creation, detected-profile model selection, voice enable/disable, least-privilege connector capability setup without collecting secrets, user-config precedence, and first-launch guidance in `doctor`.
- [x] **FEAT-16** · **Peer Agent Discovery** — Added lazy optional zeroconf/mDNS discovery with stable peer IDs, explicit trust allowlists, HTTPS-only delegation using a separate peer token, resource-aware best-peer selection, daemon discovery lifecycle, peer API/tool surfaces, and tool-free specialist execution on the receiving machine.
- [x] **FEAT-17** · **Approval Notification Sound** — New approval gates now request a cross-platform audible alert through the existing notifier; duplicate pending requests/preapproved retries do not replay it, quiet mode suppresses it, and `notifications.approval_sound` can disable it.
- [x] **FEAT-18** · **Hot-Reload Config** — Watch `assistant.yaml` for changes and apply without a full daemon restart.

---

## 🎨 UI REBUILD (Phase Last — After Backend Is Stable)

- [x] **UI-01** · Rebuild `webui/index.html` as a proper React + Vite + Tailwind CSS multi-page app.
- [x] **UI-02** · Chat — Markdown rendering for assistant responses.
- [x] **UI-03** · Chat — Code syntax highlighting (highlight.js or Prism).
- [x] **UI-04** · Chat — Live streaming cursor / token indicator while LLM generates.
- [x] **UI-05** · Approvals — Toast notifications (non-blocking) when approval needed.
- [x] **UI-06** · Dashboard — Replace hand-drawn Canvas chart with a verified local Plotly component.
- [x] **UI-07** · Dashboard — New "Model Manager" page (list/pull/delete Ollama models).
- [x] **UI-08** · Dashboard — Mobile-responsive layout.
- [x] **UI-09** · Overlay — `Ctrl+Space` global hotkey → Spotlight-style command palette.
- [x] **UI-10** · Overlay — Scrollable conversation history sidebar.
- [x] **UI-11** · Overlay — Smooth expand/collapse animation (currently snaps instantly).
- [x] **UI-12** · Overlay — In-overlay settings panel (model, voice, focus mode).
- [x] **UI-13** · Overlay — Drag-to-resize the window.
- [x] **UI-14** · Overlay — Red badge count on collapsed "eye" when approvals are pending.

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

- [x] **BROKEN-11** � pproval.py � Pre-approvals use SHA-256 of action+reason+kind. The hash must match **exactly** � a single space difference (e.g. trailing whitespace in a dynamic path string) silently creates a new pending approval instead of consuming the pre-approval. This is the root cause of voice wake-word approval mismatches.
- [x] **BROKEN-12** � daemon.py � experiences.maintenance() is called in the daemon tick, but maintenance() only prunes episodes and merges duplicates � it does NOT call experience.decay(). The decay method exists but is never reached from any code path.
- [x] **BROKEN-13** � canary.py � CanaryEngine._run_host_service() starts the candidate service as a background process but does not clean it up if the health check times out. Orphan processes are left running on the host.
- [x] **BROKEN-14** � 
esource_manager.py � can_start_model() checks available RAM but not available VRAM when GPU is present. You can start loading a 13B model into a 4GB VRAM GPU even if 12GB are already committed, then Ollama silently falls back to CPU � killing performance without any warning.
- [x] **BROKEN-15** � connector_oauth.py � Token refresh only triggers when expires_at <= now + 30s. But refresh is called inline during call(). If the refresh HTTP request takes >30s (slow network), the token expires mid-request and the API call fails with a 401.

---

## ?? ADDITIONAL INCOMPLETE FEATURES (Found in Deep Audit Round 2)

- [x] **INCOMPLETE-12** � daemon.py � Sleep/resume detection (SleepResumeMonitor) fires a resume event correctly but the daemon does NOT re-sync process health checks or watcher baselines after a resume. A laptop that sleeps for 8 hours wakes up with stale health status.
- [x] **INCOMPLETE-13** � riefing.py � Briefings have no content caching. If the LLM is sleeping/unavailable, calling GET /briefing/morning waits for model load and generation every time with no fallback or cached last result.
- [x] **INCOMPLETE-14** � groups.py � GroupOrchestrator.start() starts all group projects sequentially. For large groups this is slow. There is no parallel startup option, and no dependency ordering within the group.
- [x] **INCOMPLETE-15** � sessions.py � prune() deletes old sessions but does NOT archive them. Chat history older than 
etention_days is permanently deleted with no export path.
- [x] **INCOMPLETE-16** � improvements.py � 
ollback() restores the original file from backup but does NOT check if the file was modified again after the proposal was applied. Rolling back may overwrite legitimate subsequent edits.
- [x] **INCOMPLETE-17** � 	ools/filesystem.py � search_files() uses simple substring matching on file content. No regex support, no file-type filtering, no binary file detection. Searching a binary file returns garbage bytes.
- [x] **INCOMPLETE-18** � 	ools/projects.py � Project registration exists (name, path, start_command) but there is no per-project environment variable management. You cannot set PORT=3000 for project A and PORT=4000 for project B separately.
