# Evaluated Self-Improvement Guide

## Goal

Make improvement measurable and reversible without letting a model silently rewrite the active assistant or application.

## Invariants

1. A proposal never changes the active target.
2. Evaluation and promotion are separate approvals.
3. Tests/benchmarks run against a recorded baseline and candidate.
4. A passing report refers to an exact immutable candidate commit in Git mode.
5. Promotion refuses stale source state or branch tampering.
6. Security/policy/evaluation core remains manually controlled.
7. Failed or inconclusive candidates are not promotable.
8. Rollback preserves audit history.

## Evaluation modes

### Git worktree mode

Preferred.

- source repository must be clean;
- base commit is recorded;
- baseline worktree is detached at the base commit;
- candidate worktree is created on `living-assistant/eval/<evaluation-id>`;
- proposed content is applied and committed before measurement;
- worktrees are reset/cleaned between checks and benchmark repetitions;
- worktrees are removed after evaluation while the candidate branch remains for audit/promotion.

### Copy mode

Fallback for non-Git projects.

- baseline and candidate copies are made in the assistant data directory;
- copy size/file-count limits apply;
- common caches/dependency trees are skipped;
- copies are removed after evaluation;
- promotion reuses the exact proposal apply/backup path.

Git mode offers materially stronger reproducibility.

## Gates

A candidate is promotable only when:

```text
all candidate tests/static checks pass
AND
all configured benchmark comparisons are valid
AND
latency regression <= configured budget
AND
peak RSS regression <= configured budget
AND
target is not protected core
```

A baseline test is allowed to fail if the candidate fixes it. A candidate test is never allowed to fail.

A benchmark is considered valid only when all baseline and candidate measured repetitions succeed.

## Benchmark methodology

- optional warmup;
- repeated runs;
- alternating baseline/candidate execution order;
- median wall-clock duration;
- median process-tree peak RSS;
- reset Git worktree before each measured command;
- hard timeout per command;
- bounded stdout/stderr capture.

This is intended for practical regression detection, not laboratory-grade microbenchmarking. For noisy benchmarks, increase repetitions and use a task-level benchmark long enough to dominate process-startup noise.

## Threat boundary

Worktrees protect repository state. They do **not** remove OS permissions or network access.

Do not evaluate unknown/malicious repositories directly on the host. Use a VM/container sandbox when code provenance is untrusted.

## Promotion

Before Git promotion v0.7 verifies:

- evaluation verdict is passing;
- stored `promotable` gate is true;
- proposal is still pending;
- source repo is clean;
- current HEAD equals evaluated base commit;
- evaluation branch tip equals stored candidate commit;
- candidate target is not protected core.

Promotion then fast-forwards to the candidate **commit hash**, not arbitrary current branch contents.

## Rollback

A promoted Git evaluation is rolled back using a new revert commit. History is not reset or rewritten.
