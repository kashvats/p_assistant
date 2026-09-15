# Living Assistant v0.9 — Experience Engine + Past-Mistake Learning

A local-first, hardware-adaptive personal operating assistant for Windows, Ubuntu/Linux and macOS. Its low-resource **nervous system** handles monitoring, routines, reminders, project supervision and defensive security while local SLMs stay asleep until reasoning is actually needed.

v0.9 adds an **Experience Engine** on top of the v0.8 hardened evaluation/canary platform. The assistant now keeps short-lived tool episodes, extracts repeated recovery candidates, stores verified postmortems, retrieves relevant past lessons before acting, decays stale knowledge, tracks contradictions and lets the user confirm/supersede/reject what it learned.

## v0.9 highlights

- Bounded local tool-outcome episodes with common-secret redaction.
- Automatic low-confidence recovery candidates when a failed tool attempt is followed by a successful variant.
- One automatic occurrence is **not** trusted; repeated evidence or explicit verification is required before automatic injection.
- Structured failure/success/procedure lessons with project scope, root cause, better action and evidence.
- Confidence scoring, positive/negative verification and age-based confidence decay.
- User-confirmed lessons receive high confidence and a slower decay window.
- Contradictory procedures are marked and injected with a verify-first warning.
- Old lessons can be superseded or rejected without deleting their audit history.
- Recurring failed-tool signatures are clustered into failure patterns.
- Relevant active lessons are retrieved before reasoning, in a bounded advisory section that cannot override policy.
- Experience episode retention is configurable and maintained by the model-free daemon.
- CLI, local API, dashboard and agent tools expose the experience layer.

See `EXPERIENCE_ENGINE.md` for the full learning model.





v0.8 extends evaluated self-improvement with two optional safety layers: **container-restricted evaluation** and **paired canary service observation**. Host evaluation remains available, but projects can opt into Docker/Podman execution with no network, dropped capabilities and resource limits, then require a healthy canary before promotion.

## v0.8 highlights

- Evaluation suites can use `host` or `container` execution.
- Container evaluation uses an already-installed image only; automatic image pulls are disabled.
- Image tags are resolved to a local immutable image ID before approval/execution.
- Evaluation containers default to `--network none`, `--cap-drop ALL`, `no-new-privileges`, read-only rootfs, PID/CPU/RAM limits, `/tmp` tmpfs and no Docker/Podman socket mount.
- Unix containers run as the invoking UID/GID to avoid root-owned project artifacts.
- Container evaluation is disabled by default on the 8-GB `lite` profile.
- Passing evaluations can run paired **baseline vs candidate canaries**.
- Canary health checks separate startup readiness from the steady-state observation window.
- Canary reports compare health success, median HTTP latency, peak RSS and peak CPU.
- Container canaries use a temporary **internal** container network plus a localhost-only published health port.
- Evaluation suites may set `require_canary=true`; promotion is then blocked until the exact evaluated commits have a passing canary.
- Evaluation approval, canary approval and promotion approval are three separate authorization steps.
- Evaluation/canary subprocesses strip common secret-bearing environment variables and SSH/GPG agent sockets before launch.

## Hardened container evaluation

Check availability:

```bash
organism improve sandbox-status
```

The assistant never installs Docker/Podman for you and never auto-pulls evaluation images. Pull/review an image yourself first, then create a suite:

```bash
organism improve suite-add backend-boxed /path/to/backend \
  --test "python -m pytest -q" \
  --lint "python -m compileall -q app" \
  --provider container \
  --image python:3.11-slim \
  --require-canary
```

When the evaluation starts, the configured image tag is resolved to the image already present on the laptop and the immutable local image ID is recorded in the approval/evaluation report.

> Container mode is a stronger boundary, not a perfect malware sandbox. Do not mount secrets, the container runtime socket, or sensitive host directories into evaluation containers.

## Canary before promotion

After a passing evaluation:

```bash
organism improve canary-run EVALUATION_ID \
  "python app.py" \
  --health-path /health \
  --service-port 8000 \
  --observe-seconds 15
```

For container canary mode:

```bash
organism improve canary-run EVALUATION_ID \
  "python app.py" \
  --provider container \
  --image my-reviewed-app-runtime:local \
  --health-path /health \
  --service-port 8000
```

The paired run is:

```text
exact baseline commit ── start ── readiness ── observe ── stop
exact candidate commit ─ start ── readiness ── observe ── stop
                                      │
                                      ▼
                        health / latency / RAM / CPU
                                      │
                              regression budgets
                                      │
                             PASS or FAIL
```

A suite marked `--require-canary` cannot be promoted until the latest canary passes **and** its stored base/candidate commit IDs match the evaluation being promoted.

v0.8 keeps the Security Guardian and Personal Operating Layer from earlier releases and adds a measured **evaluated self-improvement pipeline**. The assistant can propose a code change, test it away from the active checkout, compare before/after resource behavior, and only then request permission to promote the exact candidate that was evaluated.

## v0.8 highlights

Everything from v0.6 remains, plus:

- Persistent **evaluation suites** with tests, lint/static checks and benchmark commands.
- Git repositories use separate **baseline + candidate worktrees**.
- The candidate is committed on a dedicated `living-assistant/eval/<id>` branch before measurements.
- Non-Git projects use bounded isolated project copies as a fallback.
- Every evaluation command is policy-checked and the complete command plan requires explicit approval.
- Per-command timeout and bounded output capture.
- Process-tree **wall-clock latency and peak RSS memory** measurement.
- Repeated benchmark runs with configurable regression budgets.
- Baseline/candidate benchmark runs are interleaved to reduce persistent first/second-run thermal/cache bias.
- Hardware-adaptive repetition counts: fewer repetitions on `lite`, more on `power`.
- Git worktrees are reset to their exact commits between checks/benchmark repetitions.
- Candidate checks must pass before an evaluation can be promotable.
- Benchmarks must remain within configured latency/RAM regression budgets.
- Promotion is a separate approval from evaluation.
- Promotion verifies the active repository is clean and still at the evaluated base commit.
- Promotion verifies the evaluation branch still points to the **exact immutable candidate commit hash** that was measured.
- Promotion uses a fast-forward to that exact commit; no hidden merge content is accepted.
- Security/policy/evaluation core files can be measured but are still blocked from automatic promotion.
- Promoted Git changes can be rolled back with an approval-gated `git revert`, preserving history.
- Evaluation reports are exposed through CLI, local API and dashboard.
- Full regression suite includes all prior releases plus v0.9 experience-learning tests.

## Why this architecture

Self-improvement should not mean:

```text
model thinks change is better
        ↓
rewrites itself
        ↓
hopes nothing broke
```

v0.8 uses:

```text
problem / opportunity
        ↓
reviewable proposal + exact diff
        ↓
evaluation plan
        ↓ approval
baseline state       candidate state
      │                     │
      ├── tests             ├── tests
      ├── lint/static       ├── lint/static
      └── benchmarks        └── benchmarks
              \             /
               measured report
                     ↓
             regression gates
                     ↓
            promotion request
                     ↓ approval
       exact evaluated commit only
                     ↓
                active branch
```

An LLM opinion is never itself a benchmark.

## Hardware profiles

### Main target — Ryzen 5 5600H / GTX 1650 4 GB / 32 GB RAM

Use the auto-selected `balanced` profile. Normally only one local reasoning model is resident at a time. Evaluation is mostly deterministic Python/subprocess work and does not require keeping an SLM active while tests run.

Default benchmark policy:

```yaml
balanced:
  measured_repetitions: 3
  warmup_runs: 1
```

### 8 GB systems

The `lite` profile reduces evaluation work:

```yaml
lite:
  measured_repetitions: 1
  warmup_runs: 0
```

The same safety gates still apply. Browser and voice remain optional/disabled by default on lightweight systems.

### Larger systems

`power` defaults to more measured repetitions while retaining one-change-at-a-time promotion and the same approval model.

## Upgrade from v0.8

v0.9 adds experience lessons and tool-episode tables to the existing local SQLite database. Evaluation/canary tables remain compatible. Existing projects, approvals, security findings, baselines, todos, routines, sessions, skills and calendar data remain compatible.

Back up your assistant data directory before upgrading a machine you depend on.

```bash
pip install -e .
```

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

Then:

```bash
organism doctor
```

Optional extras:

```bash
pip install -e ".[desktop]"
pip install -e ".[browser]"
pip install -e ".[voice]"
playwright install chromium
```

## 1. Create an improvement proposal

The existing proposal engine still creates an exact replacement + diff without modifying the target:

```bash
organism improve propose \
  src/my_module.py \
  /tmp/candidate.py \
  "Reduce parser allocations" \
  "Avoid repeated temporary string creation" \
  --tests "python -m pytest -q"
```

Or an agent can call `propose_improvement` after inspecting code and evidence.

## 2. Define a reusable evaluation suite

For a Python project:

```bash
organism improve suite-add core \
  /path/to/project \
  --test "python -m pytest -q" \
  --lint "python -m compileall -q src" \
  --benchmark "python benchmarks/parser_bench.py" \
  --repetitions 3 \
  --max-latency-regression-pct 10 \
  --max-memory-regression-pct 10
```

List suites:

```bash
organism improve suite-list
```

Suites store **commands and thresholds, not credentials**. Running them still requires evaluation approval.

## 3. Evaluate without modifying the active checkout

```bash
organism improve evaluate PROPOSAL_ID --suite core
```

The approval request includes the exact command plan.

### Git mode

If the project is a clean Git repository:

```text
active repo @ BASE
      │
      ├── baseline worktree @ BASE
      │
      └── candidate worktree
              │
              ├── apply proposed file
              ├── commit candidate
              └── branch living-assistant/eval/<id>
```

The active checkout remains unchanged during evaluation.

### Non-Git fallback

For a non-Git project, v0.8 makes bounded copies of the selected project directory. Common heavy/generated folders such as `.venv`, `node_modules`, `dist`, `build` and cache folders are excluded.

Git mode is preferred because it gives a stronger immutable audit trail and promotion semantics.

## 4. Inspect the report

```bash
organism improve evaluations
organism improve report EVALUATION_ID
```

The stored report contains:

- proposal ID;
- project/mode;
- base commit;
- exact candidate commit;
- test results for baseline and candidate;
- static/lint results;
- benchmark repetitions;
- median wall time;
- median peak RSS;
- latency regression percentage;
- memory regression percentage;
- configured budgets;
- final verdict;
- whether the target is protected core;
- whether it is promotable.

## 5. Promote only a passing candidate

```bash
organism improve promote EVALUATION_ID
```

For Git mode, promotion refuses to proceed if:

- the evaluation failed;
- the active checkout is dirty;
- active `HEAD` changed since evaluation;
- the evaluation branch moved after measurement;
- the exact candidate commit is missing;
- the target is protected security/policy/evaluation core.

If all gates pass, a separate approval is requested and the repository is fast-forwarded to the **exact candidate commit hash** that produced the stored report.

## 6. Roll back a promotion

```bash
organism improve revert-promotion EVALUATION_ID
```

Git mode uses `git revert --no-edit`, so rollback creates new history rather than rewriting old commits.

Non-Git mode reuses the existing pre-change backup/rollback system.

## Evaluation command safety

Evaluation commands are powerful because tests are executable code.

v0.8 therefore:

1. rejects commands already blocked by the deterministic shell policy;
2. refuses privileged/destructive commands in automatic evaluation;
3. presents the exact command list for approval;
4. parses commands to argv and launches with `shell=False`, so shell chaining/redirection/substitution is not available;
5. applies per-command timeouts;
6. captures bounded output;
7. measures the process tree;
8. keeps evaluation separate from promotion.

### Important limitation

**Git worktrees/copies isolate repository state; they are not an operating-system or network sandbox.**

Approved evaluation commands still run as your local user and can access capabilities your user account has. For untrusted code, use a container/VM or a future hardened sandbox provider rather than the local worktree evaluator. Evaluation commands are argv-style; if you need a multi-step pipeline, place it in a reviewed script and invoke that script explicitly.

## Evaluation configuration

`config/assistant.yaml`:

```yaml
self_improvement:
  enabled: true
  auto_apply_security_core: false
  evaluation:
    enabled: true
    benchmark_repetitions_by_profile:
      lite: 1
      balanced: 3
      power: 5
    benchmark_warmup_runs_by_profile:
      lite: 0
      balanced: 1
      power: 1
    max_latency_regression_pct: 15
    max_memory_regression_pct: 15
    command_timeout_seconds: 300
    max_commands: 12
    max_command_chars: 4000
    copy_max_files: 8000
    copy_max_mb: 500
```

## Security Guardian still applies

First-time security onboarding remains explicit:

```bash
organism security initialize
```

Useful checks:

```bash
organism security posture
organism security findings
organism security startup-check
organism security network-check
organism security process-triage
organism security network-activity
```

Protected folders:

```bash
organism security baseline-add retaileye-config /path/to/config true "yaml,yml,json,toml,env"
organism security baseline-check retaileye-config
```

Containment remains approval-gated and limited to non-critical current-user-owned processes.

## Personal/operator features retained

v0.8 still includes:

- project and multi-service group supervision;
- crash detection/restart policy;
- filesystem watches;
- local calendar, todos, daily/weekly routines and briefings;
- quiet hours/focus mode;
- local bounded session continuity with secret redaction;
- local voice interfaces;
- isolated browser sessions;
- clipboard/screenshots behind approval;
- read-only-by-default SQL/Mongo tools;
- download quarantine;
- defensive endpoint monitoring;
- sleeping specialist SLMs and hardware-adaptive model profiles.

## Local API / dashboard

```bash
organism serve
```

Open:

```text
http://127.0.0.1:8787/dashboard
```

New v0.8 surfaces include:

```text
GET  /improvement-suites
POST /improvement-suites
GET  /improvement-evaluations
GET  /improvement-evaluations/{id}
POST /improvements/{proposal_id}/evaluate
POST /improvement-evaluations/{id}/promote
POST /improvement-evaluations/{id}/revert
```

The server still refuses non-loopback binding through the normal CLI path.

## Validation

v0.8 regression suite:

```text
75 passed
```

Tests cover earlier functionality plus:

- suite persistence;
- non-Git evaluation isolation;
- failed-candidate gating;
- latency/RAM regression budgets;
- dangerous evaluation-command rejection;
- evaluation timeout enforcement;
- Git worktree evaluation;
- separate evaluation/promotion approvals;
- stale `HEAD` refusal;
- dirty-checkout refusal;
- protected-core promotion refusal;
- promotion rollback using `git revert`;
- post-evaluation branch-tip tamper refusal;
- hardware-adaptive benchmark defaults;
- shell-chaining non-execution in the evaluator.

## Where next

The next useful stage is not unrestricted autonomy. A stronger v0.8 would add an optional **hardened execution provider** (container/VM), model/agent benchmark suites, canary promotion for long-running projects, and real external connector implementations while preserving the same deterministic approval and audit boundaries.

See `EVALUATED_SELF_IMPROVEMENT.md`, `ARCHITECTURE.md`, `THREAT_MODEL.md` and `ROADMAP.md`.