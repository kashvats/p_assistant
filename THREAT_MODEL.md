# Threat Model — v0.4

## Protected assets

Local files, repositories, credentials, databases, running services, browser state, microphone/clipboard/screen data, assistant memory, and operating-system security controls.

## Main threats

- Prompt injection from web pages, logs, code comments, DB rows, documents or downloaded content.
- Model hallucination resulting in destructive commands.
- Secret leakage from clipboard, screenshots, microphone recordings, environment files or browser profiles.
- A browser action changing an external account unexpectedly.
- Persistent browser cookies being reused outside their intended site scope.
- A malicious or incorrect "self-improvement" weakening the assistant's policy layer.
- Event/routine loops consuming resources or waking models repeatedly.
- Resource exhaustion from models, browsers or child processes.

## Controls

- Deterministic policy engine outside LLM control.
- Explicit approvals for sensitive sensors and state-changing actions.
- Localhost-only API by default.
- Workspace canonicalization and path traversal rejection.
- DB reads only by default.
- Quarantine for risky downloads and no automatic execution.
- Assistant browser profiles are isolated from the user's normal browser profile.
- Persistent browser state requires approval and host-scoped sessions.
- Model-waking routines disabled by default.
- Bounded routine intervals, process restart limits and model resource checks.
- Self-improvement stores an exact diff and base hash, makes a backup, and requires approval.
- Security-critical assistant core is excluded from automatic self-modification.

## Non-goals

The assistant is not a replacement for OS patching, Defender/EDR, firewall, disk encryption, MFA, backups, secure networking or a password manager. It cannot guarantee that a laptop will never be compromised.
