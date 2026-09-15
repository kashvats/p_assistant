# Living Assistant v0.7 — Evaluated Self-Improvement

A local-first, hardware-adaptive personal operating assistant for Windows, Ubuntu/Linux and macOS. Its low-resource **nervous system** handles monitoring, routines, reminders, project supervision and defensive security while local SLMs stay asleep until reasoning is actually needed.

v0.7 keeps the Security Guardian and Personal Operating Layer from earlier releases and adds a measured **evaluated self-improvement pipeline**. The assistant can propose a code change, test it away from the active checkout, compare before/after resource behavior, and only then request permission to promote the exact candidate that was evaluated.

## v0.7 highlights

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
- Full regression suite: **75 passing tests**.

## Why this architecture

Self-improvement should not mean:

```text
model thinks change is better
        ↓
rewrites itself
        ↓
hopes nothing broke
```

v0.7 uses:

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

## Upgrade from v0.6

v0.7 uses additive SQLite tables for evaluation suites and evaluation reports. Existing projects, approvals, security findings, baselines, todos, routines, sessions, skills and calendar data remain compatible.

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

For a non-Git project, v0.7 makes bounded copies of the selected project directory. Common heavy/generated folders such as `.venv`, `node_modules`, `dist`, `build` and cache folders are excluded.

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

v0.7 therefore:

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

v0.7 still includes:

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

New v0.7 surfaces include:

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

v0.7 regression suite:

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
