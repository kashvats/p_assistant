# Threat Model — v0.7

## Protected assets

- local source repositories and personal files;
- credentials and connector secrets;
- databases;
- active project processes;
- operating-system security controls;
- personal memory/calendar/session history;
- the assistant policy/approval/security/evaluation core;
- integrity of self-improvement evidence.

## Existing threats

The v0.6 model still applies: prompt injection, destructive shell actions, path escape, accidental DB writes, secret exfiltration, malicious downloads, security-control disabling, unauthorized API access and resource exhaustion.

## New evaluated-self-improvement threats

### 1. Malicious test/benchmark command

A proposal or external file may suggest a command that has harmful side effects.

Controls:

- deterministic command policy check;
- privileged/destructive evaluation commands refused;
- exact command plan shown in an approval request;
- commands launch as argv with `shell=False`, preventing implicit shell chaining/redirection/substitution;
- timeout and output limits;
- evaluation and promotion remain separate.

Residual risk: approved commands still run as the local user. Worktrees are **not an OS sandbox**.

### 2. Benchmark gaming

A candidate could optimize only for a synthetic benchmark or manipulate output while harming real behavior.

Controls:

- reusable user-defined task suites;
- tests/static checks plus performance gates;
- reports preserve raw command output/metrics;
- no automatic promotion based on a model score.

Residual risk: benchmark quality is ultimately determined by the suite design.

### 3. Thermal/cache/order bias

Running all baseline trials first and candidate trials later could bias comparisons.

Controls:

- warmups;
- repeated runs;
- alternating baseline/candidate order;
- median metrics.

### 4. Candidate changes after evaluation

An evaluation branch could be modified after a passing report.

Controls:

- candidate committed before measurement;
- candidate SHA persisted;
- promotion verifies branch tip equals stored SHA;
- promotion merges the exact SHA, not arbitrary branch contents.

### 5. Active repository changes after evaluation

Another commit could land after the benchmark, invalidating the comparison.

Controls:

- base SHA persisted;
- promotion requires clean active checkout;
- current HEAD must equal evaluated base SHA;
- otherwise re-evaluation is required.

### 6. Test cross-contamination

One command could modify files used by later commands.

Controls in Git mode:

- reset to exact baseline/candidate commit before each check and benchmark repetition;
- remove untracked files between runs.

Copy-mode isolation is weaker and documented as such.

### 7. Self-modification of the guardrails

A candidate could attempt to weaken the code that decides whether it passes/promotes.

Controls:

- security/policy/approval/improvement/evaluation/workspace/quarantine/config core remains protected from automatic promotion;
- such changes require manual human review outside the automatic pipeline.

### 8. Resource exhaustion

A benchmark can consume excessive RAM/CPU or hang.

Controls:

- available-RAM precheck;
- profile-adaptive repetitions;
- per-command timeout;
- process-tree termination on timeout;
- bounded command count;
- copy size/file-count limits.

## Non-goals

v0.7 does not provide:

- kernel/container-grade sandboxing;
- proof that a benchmark represents production behavior;
- proof that a passing candidate is bug-free;
- automatic trust of code from the internet;
- unrestricted recursive self-modification.

Use containers/VMs for untrusted code and retain OS security controls, backups and normal code review.
