# Changelog

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
