# Threat Model — v0.9.2

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


## v0.9.2 hardening additions

### Command and database policy bypass

Safe/read-only labels are not inferred from a permissive prefix. Shell metacharacters/composition operators invalidate the read-only exemption. SQL tools accept one statement only, reject known side-effecting read-like constructs, restrict PRAGMA usage and add database-level read-only/query-only controls.

Residual risk: SQL dialects and extensions evolve. The deterministic validator is a defense-in-depth layer, not a substitute for least-privilege database credentials.

### Local API browser/rebinding abuse

The localhost API validates `Host` and browser `Origin` values against loopback plus explicitly configured allowlists. Authentication remains required where configured.

Residual risk: software running as the same user can usually access localhost directly; this is not an OS sandbox.

### SSRF and private-network access

Web/browser targets are classified before access, common cloud metadata targets are denied, redirects are re-evaluated and private/local destinations require a dedicated approval. Managed-project health checks are loopback-only.

Residual risk: DNS resolution and the later socket connect are not a single atomic operation. A hostile resolver could theoretically exploit DNS rebinding/TOCTOU. Use network egress controls for stronger guarantees.

### Sensitive files and secret persistence

Credential-like workspace paths require explicit one-time approval and are excluded from content search. Common secrets/DSNs/tokens/private keys are redacted from several persisted and model-facing text paths. Remote model endpoints are disabled by default.

Residual risk: heuristic redaction cannot recognize every proprietary secret format. Keep real secrets in OS/environment secret stores and avoid granting broad workspace access to credential directories.

### Concurrency and process identity

Persistent SQLite stores use thread-local connections, WAL and a busy timeout. Approval consumption is atomic. Managed process records include process creation time before stop/restart operations. JSON registries use atomic file replacement.

Residual risk: atomic files prevent torn writes but do not make every higher-level multi-process update transactionally conflict-free.

### Experience and self-improvement boundaries

Unverified automatic recovery memories do not inject raw external/tool result text into system instructions. Assistant-core paths are protected from automatic apply/promotion; changes may still be proposed/evaluated for explicit human review.

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

v0.8 does not provide:

- kernel/container-grade sandboxing;
- proof that a benchmark represents production behavior;
- proof that a passing candidate is bug-free;
- automatic trust of code from the internet;
- unrestricted recursive self-modification.

Use containers/VMs for untrusted code and retain OS security controls, backups and normal code review.


## v0.8: container and canary threats

Additional threats considered:

- malicious or unexpectedly changed container images,
- image auto-pull introducing unreviewed code,
- container escape attempts,
- evaluation code using outbound network access,
- Docker/Podman socket exposure,
- root-owned artifacts written into the source tree,
- canary port exposure beyond localhost,
- unhealthy startup being confused with steady-state health,
- a canary result being reused after the evaluated branch changed,
- resource exhaustion through fork bombs or memory/CPU pressure,
- accidental credential exposure through inherited environment variables.

Controls in v0.8 include local-image-only execution (`--pull never`), immutable local image-ID pinning, network disabled for evaluation, capability dropping, `no-new-privileges`, read-only container root, bounded `/tmp`, PID/CPU/RAM limits, Unix UID/GID mapping, no runtime socket mount, localhost-only canary port publication, internal canary networks, separate startup/observation probes and exact commit matching before promotion, and secret-bearing environment-variable filtering for evaluation/canary subprocesses.

These controls reduce risk but do **not** make containers equivalent to a VM boundary. Untrusted hostile binaries still belong in a disposable VM or dedicated sandbox host.


## v0.9 Experience-memory threats

### Memory poisoning
A malicious webpage, log, repository comment or one-off failure could try to cause a dangerous lesson. Automatic traces therefore start as low-confidence candidates and external observations do not become verified lessons merely because they contain instructions.

### Stale operational knowledge
Projects change. Unconfirmed lessons decay over time, negative verification lowers confidence, contradictions are surfaced, and lessons can be superseded/rejected.

### Secret persistence
Tool arguments/results and lessons apply common credential redaction before persistence. The experience store is not a secret manager and should never be intentionally used as one.

### Authority confusion
Retrieved experiences are labeled advisory evidence. They cannot override command policy, approvals, workspace restrictions, database policy, Security Guardian controls or promotion gates.
