# Changelog

## 0.17.0

- Added versioned per-user runtime installs with one venv per release and stable launch shims.
- Added atomic install state tracking with current/previous versions and install history.
- Added pre-update local data backups with consistent SQLite snapshots and sensitive-cache exclusions.
- Added code rollback without implicit data downgrade, plus explicit backup restoration when requested.
- Added persistent-data schema marker/migration framework and newer-schema refusal.
- Added wheel identity and optional SHA-256 verification before installation.
- Added post-install runtime verification and stable-service restart through upgrade-safe daemon shims.
- Added uninstall flow that preserves user data by default and requires explicit double confirmation to purge it.
- Added per-user service removal for systemd, launchd and Windows Scheduled Tasks.
- Added Linux/macOS/Windows release installer/update/uninstall wrappers.
- Added Debian package builder, macOS pkg builder recipe, and Windows WiX staging recipe without embedding signing credentials.
- Added release-packaging and migration regression coverage.

## 0.16.0

- Added runtime cross-platform capability probes and `organism platform` diagnostics.
- Added Windows non-admin link fallback: symlink -> directory junction / file hard link; copies remain explicit only.
- Added conservative Windows reparse-point detection so security scans/watchers do not recurse through junctions.
- Made historical symlink-specific tests skip rather than fail when true symlink semantics are unavailable.
- Added sleep/resume detection with filesystem-watch rebaselining, listener refresh, health-counter reset and model-runtime resynchronization.
- Added graceful SIGTERM handling for background-service shutdown.
- Hardened macOS LaunchAgent generation with `plistlib`, `plutil`, `launchctl bootstrap/bootout` and user GUI domain targeting.
- Hardened Linux user-systemd unit quoting, stop timeout and service-status visibility.
- Hardened Windows Scheduled Task settings for non-admin/login use and battery operation.
- Removed Windows bootstrap dependency on PowerShell activation scripts/execution policy.
- Made workspace listings survive broken/inaccessible links or reparse points.
- Added platform status/service API routes and cross-platform regression coverage.


## 0.15.0

- Added normalized Windows Sysmon and selected Security Event Log ingestion with deterministic event-chain correlation.
- Added Linux auditd/ausearch ingestion with audit-serial record grouping and journald fallback.
- Added macOS Endpoint Security notification-helper source/protocol plus Unified Log fallback; entitlement/code signing remain mandatory.
- Added DNS telemetry normalization and optional local DNS NDJSON adapter.
- Added optional local TLS/SNI metadata adapter without pretending ECH-hidden SNI is universally observable.
- Added explicit SHA-256 reputation lookup for files/running processes; file bytes are never uploaded.
- Added signed-binary/local package trust database with hash/signer/status drift detection.
- Added optional local YARA scanning with explicit approval and no automatic rule downloads.
- Added USB device and browser-extension metadata baselines, including permission-gain detection.
- Added bounded ransomware-like mass file-change burst detection.
- Added backup-integrity baselines and checks.
- Added reversible approval-gated network isolation and separately armed multi-signal automatic isolation policy.
- Persisted partial isolation state so network restore remains available after partial failures.
- Added sensor API, CLI, agent-tool and dashboard status surfaces.
- Added 24 focused sensor/security regressions while preserving the full cumulative suite.

## 0.14.0

- Added accessibility-first Desktop Intelligence controller.
- Added Windows UI Automation foreground-tree inspection.
- Added macOS System Events accessibility inspection.
- Added Linux AT-SPI semantic inspection with window-list fallback.
- Added multi-monitor geometry and per-monitor screenshot capture.
- Added approval-gated mouse movement, clicks, typing and hotkeys.
- Added optional sleeping Ollama vision fallback, disabled by default.
- Blocked remote screenshot analysis unless explicitly enabled.
- Added desktop capability API/CLI/tool surfaces and dashboard status.
- Preserved v0.13 adaptive model runtime and all earlier hardening.


## 0.13.0
- Added hardware-adaptive model residency with strict single-model fallback on lite and low-VRAM systems.
- Added dedicated-VRAM, Apple unified-memory and CPU/system-RAM thresholds for 1/2/3 resident models.
- Added separate maximum resident-model and concurrent-generation budgets.
- Added per-model generation serialization by default to avoid multiplying context memory unexpectedly.
- Added LRU eviction of idle resident models and conservative RAM/VRAM admission checks.
- Added best-effort CPU/GPU thermal telemetry and concurrency throttling under configured temperature pressure.
- Added Ollama `/api/ps` running-model inspection and explicit model preload/unload support.
- Added longer keep-alive for multi-model residency while retaining the original short/sleeping behavior on single-model systems.
- Added `organism model` CLI controls, model-runtime API routes, dashboard resident-model status and doctor recommendations.
- Preserved compatibility with older/custom model managers that implement only the original `activate()` API.
- Added thread-level regression coverage for cross-model concurrency, same-model serialization, LRU eviction, pressure fallback and thermal throttling.

## 0.12.0
- Replaced metadata-only connector support with executable capability-scoped connectors.
- Added Google Gmail, Calendar and Drive actions with loopback OAuth + PKCE.
- Added Microsoft 365 Outlook, Calendar and OneDrive actions with OAuth device authorization.
- Added GitHub pull-request list/detail/files/review actions with device authorization or token auth.
- Added Telegram and Discord read/send bot bridges.
- Added Notion search/page read/create support and local Obsidian vault search/read/write support.
- Added environment + optional OS-keyring credential resolution; connector secrets are not stored in assistant JSON/SQLite state.
- Added per-connector capability enforcement and explicit approval for every external write/send/review action.
- Added untrusted-external wrapping and response bounds for connector reads.
- Added connector CLI, agent tools and authenticated localhost API routes.
- Added OAuth/capability/traversal/secret-handling regression coverage.

## 0.11.0
- Added opt-in hands-free local wake-word listening with explicit microphone approval.
- Added openWakeWord adapter with lazy model loading and a separate optional `wakeword` dependency extra.
- Added explicit approval-gated official wake-model download into the per-user data directory; models are never auto-downloaded.
- Added single-stream wake-word-to-command capture so speech immediately following the wake phrase is not lost.
- Added adaptive RMS voice-activity capture with ambient calibration, pre-roll and silence stop.
- Added configurable multilingual STT auto-detection/forced-language selection.
- Added optional TTS barge-in detection with denial-safe fallback to ordinary TTS.
- Added bounded microphone leases and profile gates; hands-free remains disabled by default and on lite unless explicitly enabled.
- Added voice presence/status/wake/model-download/utterance CLI commands and regression tests.

## 0.10.0
- Added bundled modern local web control center at `/dashboard`.
- Added token-by-token Ollama chat streaming over SSE at `POST /chat/stream`.
- Added in-process activity bus with tool/model/chat events and SSE activity feed.
- Added live CPU/RAM graph, active-model status, approvals, calendar/todo management and security views.
- Dashboard remains usable with API-token authentication and keeps the token in browser session storage.
- Streaming uses the existing orchestrator tool and approval path; it does not bypass policy controls.
- Added streaming/error redaction and interaction-layer regression tests.

## v0.9.2

- Hardened shell safe-read classification against chaining, redirection, substitution and command-composition bypasses.
- Hardened read-only SQL validation and added database-level read-only/query-only enforcement.
- Made one-time approval consumption atomic under concurrent callers.
- Replaced shared cross-thread SQLite connections with per-thread WAL connections and busy timeouts.
- Added sensitive-path classification and approval-gated reads/previews/writes; sensitive files are excluded from content search.
- Added localhost API Host/Origin validation to reduce DNS-rebinding and cross-origin browser abuse.
- Added private-network/metadata protections for web and browser tools, including redirect/subresource checks.
- Restricted project health checks to loopback targets.
- Added process-creation-time verification to managed-process stop/restart operations.
- Denied remote Ollama endpoints by default and separated remote TLS/insecure-HTTP opt-ins.
- Centralized secret redaction for common credentials, DSNs, tokens, authorization headers, private keys and command/log output.
- Removed raw external/tool outcome text from automatically learned system-context experience.
- Protected assistant core from automatic self-apply/promotion using repository paths rather than filenames.
- Added atomic JSON persistence and safer macOS notification argument passing.
- Added dedicated exploit/concurrency regression coverage; complete suite passes 114 tests.

## v0.9.1

- Fixed installed-wheel runtime startup: the default `assistant.yaml` is now packaged as package data.
- Installed builds now place relative runtime workspaces under the per-user application data directory instead of relying on the current working directory or `site-packages`.
- Added `ASSISTANT_CONFIG` support for an explicit external configuration file.
- Added regression coverage for packaged configuration fallback.

## v0.9.0

- Added evidence-weighted Experience Engine for learning from past mistakes and successful recoveries.
- Added short-lived redacted tool episodes and repeated automatic recovery candidates.
- Added verified/user-confirmed lessons, confidence updates, stale-lesson decay and contradiction tracking.
- Added project-scoped retrieval of trusted lessons before model reasoning.
- Added failure-pattern clustering from recent failed episodes.
- Added experience search/confirm/verify/reject/supersede/stats/maintenance CLI commands.
- Added Experience Engine agent tools and localhost API/dashboard surfaces.
- Added hourly episode-retention maintenance through the deterministic daemon.
- Added tests for memory poisoning resistance properties, redaction, conflicts, decay and end-to-end orchestrator retrieval.


## 0.8.0

- Added optional Docker/Podman container execution provider for evaluated improvements.
- Added local-image-only policy and immutable image-ID pinning.
- Added no-network evaluation containers with capability, privilege, PID, CPU, RAM and rootfs restrictions.
- Added secret-bearing environment filtering for evaluation/canary subprocesses.
- Added host/container paired canary engine with health, latency, CPU and RSS metrics.
- Added internal-network + localhost-only port mapping for container canaries.
- Added required-canary promotion gate bound to the exact evaluated commit IDs.
- Added sandbox/canary CLI, API, dashboard and orchestrator tools.
- Disabled container execution by default for the lite hardware profile.
- Fixed readiness probes being incorrectly counted against steady-state canary health percentage.
- Protected `sandbox.py` and `canary.py` from automated self-promotion.


## 0.7.0

- Added persistent evaluated-self-improvement suites with tests, lint/static checks, benchmarks and regression budgets.
- Added Git baseline/candidate worktrees and dedicated `living-assistant/eval/<id>` candidate branches.
- Candidate changes are committed before measurement so reports identify an immutable candidate SHA.
- Added bounded non-Git baseline/candidate copy mode.
- Evaluation command plans are policy-checked and require a dedicated `SELF_EVALUATION` approval.
- Added per-command timeout, bounded logs, wall-clock timing and process-tree peak RSS measurement.
- Added hardware-adaptive benchmark repetition/warmup defaults for lite/balanced/power profiles.
- Added warmup and interleaved baseline/candidate benchmark ordering.
- Git worktrees reset to exact commits between checks and benchmark repetitions.
- Added candidate-check and latency/RAM regression gates.
- Added separate `SELF_PROMOTION` approval after a passing evaluation.
- Promotion requires a clean source checkout at the original base SHA.
- Promotion verifies the evaluation branch tip still equals the stored candidate SHA and merges that exact SHA.
- Added approval-gated `git revert` rollback for promoted evaluations without history rewriting.
- Added evaluation-branch cleanup action.
- Added evaluation suite/report CLI, API, dashboard and orchestrator tools.
- Added `evaluation.py` to the protected self-improvement core.
- Expanded regression suite to **75 passing tests**.

## 0.6.0

- Added cross-platform Security Guardian with persistent startup/persistence and listening-service baselines.
- Baselines are not silently initialized by default.
- Added protected-file integrity baselines, process triage, network summaries, security posture, findings and approval-gated containment.
- Added richer quarantine provenance and tamper checks.
- Expanded regression suite to 61 passing tests.

## 0.5.0

- Added local calendar, deterministic briefings, quiet/focus mode, clock routines, local session continuity, approval UI and connector metadata registry.

## 0.4.0

- Added push-to-talk voice, routines, reviewable self-improvement and persistent isolated browser sessions.

## 0.3.0

- Added Git-aware coding tools, project groups, desktop sensors, browser automation and download quarantine.

## 0.2.0

- Added persistent process supervision, filesystem watches, notifications, approvals and user-confirmed skills.

## 0.1.0

- Initial local-first orchestrator, sleeping specialist agents, tools, memory and hardware profiles.
