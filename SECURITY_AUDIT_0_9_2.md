# Living Assistant v0.9.2 Security Audit

## Scope

This audit covers the complete v0.9.1 codebase after hardening into v0.9.2. It does **not** claim code-level verification of the previously prototyped v1.0 RC1-only EDR/computer-use/advanced-voice additions, because their generated Python source was not available in the persisted workspace during this audit. Those features should be rebuilt on top of this hardened base.

## Release-blocking findings fixed

| Severity | Finding | Remediation |
| --- | --- | --- |
| Critical | Read-only shell exemption could be inherited by composed commands | Strict full-command patterns; shell composition/metacharacters invalidate the exemption |
| High | Read-only DB policy allowed some side effects | One-statement parser controls plus DB-level read-only/query-only modes |
| High | One-time approvals could race | Atomic conditional update/consume |
| High | Shared SQLite connection unsafe across API/daemon threads | Per-thread connections, WAL, busy timeout |
| High | Sensitive files could be read through file tools without dedicated approval | Sensitive-path policy, one-time approval, search exclusion |
| High | Localhost API exposed DNS-rebinding/cross-origin risk | Host and Origin validation |
| High | Web/browser tools could pivot to private/metadata targets | Address classification, metadata block, redirect/subresource checks, private-network approval |
| High | Unverified experience could persist raw attacker-controlled tool/web outcomes into trusted context | Constrained recovery hints only; raw outcomes excluded from system context |
| Medium | PID reuse could target unrelated process | Persist and verify process creation time |
| Medium | Remote Ollama could unintentionally exfiltrate prompts | Remote disabled by default; insecure remote HTTP requires separate opt-in |
| Medium | Core self-improvement protection relied too heavily on filenames | Repository/path-based protected-core boundary |
| Medium | macOS notification content interpolated into AppleScript | Static script + environment arguments |
| Medium | JSON state files could be torn on interrupted writes | Temp file + fsync + atomic replace |
| Medium | Secrets could appear in common command/session/DB error paths | Centralized heuristic redaction |

## Validation

- Python source/tests compile successfully.
- Full regression suite: **114 passed**.
- Dedicated v0.9.2 hardening suite includes exploit attempts for shell composition, SQL side effects, sensitive-file access, approval races, remote model endpoints, Host/Origin validation, DSN redaction, private health URLs, notification injection and concurrent SQLite writes.
- Wheel build and isolated installed-package smoke tests pass: version/config fallback/CLI startup and API Host/Origin controls were verified from the built wheel.

## Residual risks

- DNS validation and socket connect are separate operations; network-level egress controls are stronger against hostile rebinding.
- Heuristic secret redaction cannot cover every secret format.
- Container evaluation is defense in depth, not a malicious-code sandbox.
- The assistant runs primarily in user space and is not a full EDR/tamper-resistant security product.
- Automatic network isolation/ransomware response and deep OS telemetry belong to the future v1.x security-sensor layer and are not claimed as part of v0.9.2.
- macOS Endpoint Security requires Apple entitlement, signing and a native system extension/helper before it can provide full ES telemetry.

## Release recommendation

Use v0.9.2 as the hardened base for subsequent development. Rebuild future desktop/security-sensor/advanced-voice modules on this base, keeping privileged sensors modular and disabled unless explicitly enabled.
