# Living Assistant Architecture — through v0.17.2

```text
                         User / Voice / API / Tray
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Orchestrator   │
                         └───────┬─────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        deterministic tools   specialists     personal layer
                │                │                │
                ▼                ▼                ▼
        files/projects/db    sleeping SLMs   calendar/routines
        browser/security                    focus/briefings
                │
                ▼
      ┌───────────────────────────────┐
      │ Evaluated Self-Improvement    │
      │ proposal → evaluate → promote │
      └───────────────┬───────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
    baseline worktree       candidate worktree
        @ BASE                @ candidate commit
          │                       │
          └────── measurements ───┘
                      │
                regression gates
                      │
                approval boundary
                      │
                      ▼
                 active checkout
```


## v0.8 hardening layer

```text
Improvement proposal
        │
        ▼
Evaluation plan + approval
        │
   ┌────┴─────────────┐
   │                  │
Host provider     Container provider
worktree/copy     worktree/copy mounted /workspace
   │              network none / cap-drop ALL
   │              read-only root / RAM+CPU+PID limits
   └────┬─────────────┘
        ▼
Tests + lint + benchmarks
        │
        ▼
Optional required paired canary
 baseline service → observe → stop
 candidate service → observe → stop
        │
        ▼
Exact-commit canary gate
        │
        ▼
Separate promotion approval
```

Container evaluation pins an already-installed image ID and does not mount the container-engine socket. Canary container networking is created as a temporary internal network and only the health/service port is published to `127.0.0.1`.

## Nervous system

The daemon remains deterministic and low-resource. It monitors reminders, routines, projects, filesystem watches, security baselines and posture without keeping an LLM loaded.

## Model layer

One specialist model is normally active at a time. Roles can share the same physical SLM on small hardware. The model proposes and reasons; deterministic tools enforce workspace, security, DB and approval boundaries.

## Evaluation layer

`EvaluationStore` persists reusable suites and immutable evaluation reports in SQLite.

`EvaluationEngine` resolves a proposal, constructs an exact command plan, requests approval, creates isolated repository states, runs checks, records measurements, calculates gates and controls promotion/rollback.

### Git mode

```text
repo clean @ base SHA
   │
   ├── detached baseline worktree
   │
   └── candidate branch/worktree
             │
             └── exact proposal committed
```

The candidate branch survives worktree cleanup. Promotion verifies the branch tip still equals the candidate SHA and merges the SHA itself.

### Copy mode

Non-Git projects use bounded baseline/candidate copies under the assistant data directory. This has weaker reproducibility and no immutable commit identity, so Git mode is preferred.

## Approval boundaries

Separate approval classes include:

- `SELF_EVALUATION`: run exact local evaluation commands;
- `SELF_PROMOTION`: modify the active repository after a passing report;
- `SELF_PROMOTION_ROLLBACK`: create a Git revert;
- `SELF_EVALUATION_CLEANUP`: delete an isolated evaluation branch.

Approval for one class does not authorize another.

## Resource adaptation

Evaluation repetitions are profile-aware:

- lite: 1 measured run, no warmup;
- balanced: 3 measured runs, 1 warmup;
- power: 5 measured runs, 1 warmup.

An available-RAM floor is checked before evaluation starts.

## Security boundary

`security_policy.py`, `security_guardian.py`, `approval.py`, `improvements.py`, `evaluation.py`, `workspace.py`, `quarantine.py` and `assistant.yaml` are protected from automatic proposal application/promotion.

External content remains untrusted observation data. Evaluation commands are not taken as trusted merely because they appear in a proposal; the exact plan is approval-gated.


## v0.9 Experience Engine

```text
Task -> retrieve active relevant lessons -> orchestrator/tools
                                      |
Tool outcomes -> redacted episodes -> repeated recovery candidate
                                      |
                        verify/repeat/user confirm
                                      v
                                active lesson
                                      |
                         confidence decay/conflicts
```

Experience memory is advisory. Current tool evidence and deterministic policy always have higher authority. Automatic traces start below the normal context-injection threshold and only become influential after repeated evidence or verification.

## v0.12 connector boundary

External services are reached through `ConnectorManager`; providers do not get direct access to the orchestrator. `ConnectorRegistry` stores non-secret metadata, `CredentialStore` resolves environment/OS-keyring secrets, and `OAuthManager` owns Google/Microsoft/GitHub authorization flows. Each provider action maps to one declared capability and write actions are routed through `ApprovalManager`. Returned provider content is explicitly wrapped as untrusted external observation data.

## v0.13 adaptive model runtime

The model layer now separates **residency** from **generation concurrency**. `ResourceManager` derives a conservative runtime policy from the selected profile plus dedicated VRAM, Apple unified memory, or system RAM. `ModelManager` owns bounded generation leases, per-model slots, resident-model LRU state, preload/unload operations and pressure-aware admission.

```text
Orchestrator / Specialists
          │
          ▼
   ModelManager lease
    ├─ global generation budget
    ├─ per-model concurrency budget
    ├─ RAM/VRAM/thermal admission
    └─ LRU resident-model eviction
          │
          ▼
       Ollama API
   /api/chat · /api/ps
```

The assistant deliberately does not rewrite Ollama server environment variables. Its own budget can be stricter than Ollama's; the server may also enforce a stricter limit. Low-resource/lite machines retain the original one-model-at-a-time behavior.


## v0.15 Security Sensor Platform

Security sensors run in the deterministic/model-free layer. Platform collectors normalize recent OS telemetry into bounded event records. Correlation rules create Guardian findings; models may explain those findings but do not bypass policy or directly classify/contain based on free-form reasoning.

High-impact network isolation remains outside model authority. Manual isolation requires one-time approval. Automatic isolation is disabled/unarmed by default and, if explicitly enabled, requires multiple independent deterministic signals before the reversible platform backend is invoked.

The macOS Endpoint Security integration is split deliberately: an entitled/code-signed native notification helper produces local NDJSON, while Python consumes that telemetry. The Python process never claims or circumvents Apple's entitlement.


## v0.16 platform hardening layer

`platform_hardening.py` centralizes capability probes, semantic-preserving link creation and suspend/resume detection. On Windows, ordinary symlink creation is attempted first; directory junctions and file hard links are fallbacks when privilege/Developer Mode prevents a symlink. Copying is never implicit because it changes link semantics.

Security walkers use a no-link-traversal iterator that treats POSIX symlinks and Windows reparse points as boundaries. The daemon treats a long tick gap as a resume boundary, then refreshes ephemeral state before normal file/network/security processing to reduce false alerts. Per-user service installers remain unprivileged by default: Scheduled Task on Windows, systemd user service on Linux and LaunchAgent on macOS.



## v0.17.1 search and browser hardening

Web discovery and page automation are separate capabilities but now share one fallback path. `web_search.provider: auto` prefers Serper only when `SERPER_API_KEY` exists; otherwise it invokes the Playwright browser search adapter. A failed Serper request also falls back to the browser. Named browser sessions install a strict pre-request host guard, so their `allowed_hosts` list is an actual network allowlist rather than only a post-navigation check. Search result text is wrapped as untrusted external observation data before it reaches the model.

```text
web_search(query)
      |
      +-- provider=serper ------> Serper API
      |
      +-- provider=browser -----> Playwright search adapter
      |
      `-- provider=auto
              |
              +-- SERPER_API_KEY present -> Serper -> browser fallback on failure
              `-- no key -----------------> browser directly
```

## v0.17 release lifecycle

Runtime environments are versioned and disposable. Persistent data is outside the runtime. Updates install and self-check a new environment, snapshot user state, run idempotent migrations, switch stable shims, and best-effort restart the existing per-user daemon service. Rollback switches code versions without silently downgrading user data.

## v0.17.2 containment and DNS pinning

The security boundary now treats Git repositories, API authentication, shell process trees, sensitive self-improvement targets, database aliases, desktop titles and browser DNS resolution as explicit capabilities. Browser authorization returns the validated DNS answer set and Chromium is launched with host-resolver rules derived from that exact set. Strict request routing then limits traffic to the approved host set without re-running DNS classification, closing the validation/connect DNS-rebinding window for these scoped browser contexts.
