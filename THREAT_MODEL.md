# Threat Model

## Protected assets

- Local files and source repositories.
- Credentials/API keys.
- Databases.
- Running projects.
- Operating-system security controls.
- Personal memory/todos.
- Network privacy.

## Major threats

1. Prompt injection in web pages, source files, logs, database rows, emails/documents.
2. LLM hallucination causing destructive shell commands.
3. Path traversal outside workspace.
4. SQL/DML or Mongo writes triggered accidentally.
5. Secret exfiltration.
6. Malicious downloaded files.
7. Model-induced disabling of Defender/firewall/security tools.
8. Unauthorized remote access to the local REST API.
9. Resource exhaustion from too many models/processes.

## Controls

- Deterministic policy engine independent of the LLM.
- External content labeled as untrusted observations.
- Denylist for destructive/security-disabling/credential-exfil commands.
- Approval for execution/system modifications.
- Workspace path canonicalization.
- Read-only DB policy.
- Download limits and content-type checks.
- REST API binds to localhost by default.
- Model unload and RAM pressure controls.
- Audit logs.
- No automatic execution of downloaded binaries.

## Non-goals

This project is not a replacement for:
- operating-system updates,
- disk encryption,
- firewall,
- antivirus/EDR,
- backups,
- password manager,
- MFA,
- secure router configuration.

## v0.2 additional controls

- Noninteractive dangerous actions are queued for one-time approval instead of silently running.
- Approval is matched to the exact action/reason/risk hash and consumed once.
- Auto-restart can only replay a previously registered command and has a hard restart cap.
- User skills are prompt context only; they do not modify deterministic policy.
- File watchers are explicitly registered and bounded by a maximum scan/event count.
- The CLI refuses to expose the local control API on a non-loopback address.
