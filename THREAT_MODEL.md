# Threat Model — v0.6

## Protected assets

Local files/repositories, credentials, databases, browser/sensor data, calendar/session history, running services, OS security settings, security baselines/findings and quarantine artifacts.

## Main threats

- Prompt injection from web pages, code/comments, logs, DB rows, documents, emails or downloaded content.
- Hallucinated destructive shell/database/system actions.
- Baseline poisoning: compromised state being silently accepted as trusted.
- Baseline tampering: an agent resetting integrity/startup/network references to hide a change.
- False-positive containment killing an important process.
- Secret persistence through startup commands, process command lines, session text or signed download URLs.
- Malware-like executable downloads being run before review.
- Disabled firewall/AV/real-time protection going unnoticed.
- High-volume polling spamming alerts or consuming resources.
- Self-improvement weakening deterministic security controls.

## Controls

- Security policy and guardian logic live outside the LLM.
- Baselines are not auto-initialized by default; known-good capture is explicit.
- Agent/API baseline mutation requires approval.
- Findings are deduplicated and severity-gated before native notifications.
- Containment is current-user-only, critical-process-blocked and approval-gated.
- No automatic force-kill or suspicious-file deletion.
- Startup/process text is redacted for common credential patterns before persistence.
- Quarantine strips URL query/userinfo and stores hashes/provenance instead of executing downloads.
- Browser profiles are isolated; DB writes/destructive shell remain policy-controlled.
- Live posture checks are read-only; the dashboard consumes cached posture.
- Unknown security-tool state is not interpreted as compromise.
- No offensive scanning of third-party systems.

## Important limitations

Heuristics can miss malware and can flag legitimate software. A clean guardian dashboard is not evidence that a machine is uncompromised. Baselines are only as trustworthy as the machine state when captured.

Pattern-based credential redaction is incomplete by nature. Local assistant data should still be protected by the OS account and disk encryption.

Living Assistant is not an EDR/antivirus replacement and cannot guarantee prevention of hacking. Keep the OS patched, firewall/endpoint protection enabled, disk encryption on, MFA configured, backups tested and credentials in a password manager/secret store.
