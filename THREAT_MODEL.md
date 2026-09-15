# Threat Model — v0.5

## Protected assets

Local files/repositories, credentials, databases, running services, browser state, microphone/clipboard/screen data, calendar/todo data, local session history, notification contents, assistant memory and OS security controls.

## Main threats

- Prompt injection from web pages, source comments, logs, DB rows, documents, emails or downloaded content.
- Hallucinated destructive shell/database/system actions.
- Secret leakage through clipboard, screenshots, voice recordings, environment files, browser profiles or conversation history.
- Long-term session storage unintentionally becoming a credential archive.
- Quiet/focus mode losing reminders or, conversely, a daemon spamming notifications repeatedly.
- A background routine waking models during focus time or triggering high-impact activity without review.
- Cloud/provider connector configuration accidentally persisting credentials.
- Browser actions changing an external account unexpectedly.
- Incorrect self-improvement weakening the policy layer.
- Resource exhaustion from models, browsers, routines or child processes.

## Controls

- Deterministic policy engine outside LLM control.
- Explicit approvals for sensitive sensors/state-changing actions.
- Localhost-only API by default.
- Workspace canonicalization; DB read-only defaults; risky-download quarantine.
- Browser profiles isolated from the user's normal browser and host-scoped.
- Quiet/focus state suppresses non-urgent delivery into a durable bounded queue instead of dropping reminders.
- Model-waking routines disabled by default and additionally suppressed during focus/quiet mode.
- Session context is bounded; retention is configurable; common passwords/tokens/API keys/private-key blocks are redacted before persistence.
- Connector registry stores metadata/env-prefixes only, not passwords/tokens.
- Self-improvement uses exact diff + base hash + backup + explicit approval, with security-critical core excluded from automatic apply.

## Limitations

Credential redaction is pattern-based and cannot recognize every possible secret. Treat session history and calendar data as sensitive local files and protect the user account/disk accordingly.

The assistant is not a replacement for OS patching, Defender/EDR, firewall, disk encryption, MFA, backups, secure networking or a password manager. It cannot guarantee that a laptop will never be compromised.
