# Threat Model — v0.3

## Protected assets
- Local files and source repositories.
- Credentials, clipboard contents and visible desktop data.
- Databases.
- Running projects and project start commands.
- Browser/account state.
- OS security controls.
- Personal memories, reminders and downloaded artifacts.

## Important threats
1. Prompt injection inside web pages, source files, logs, DB rows or documents.
2. Hallucinated or malicious shell commands.
3. Workspace path traversal.
4. Accidental production database mutation.
5. Clipboard/screenshot secret disclosure.
6. Drive-by or malicious downloads.
7. Browser automation changing external account state unexpectedly.
8. Abuse of auto-restart to execute an attacker-chosen command.
9. Unauthorized remote use of the control API.
10. Resource exhaustion from models, browsers or subprocesses.

## Controls
- Deterministic policy engine outside model control.
- External content labeled as untrusted observation data.
- Command deny patterns and approval classes.
- Canonical workspace boundaries.
- SQL read-only policy and row limits.
- Screenshot/clipboard approval gates.
- Isolated browser context; downloads disabled in browser automation; click/fill approval.
- Executable/script download quarantine with SHA-256 metadata.
- Auto-restart can replay only the already registered process command and has a restart cap.
- Local API defaults to loopback only.
- Resource manager and one-active-model policy.
- Audit/event persistence.

## Deliberately not automatic
- Running a downloaded executable.
- Disabling firewall, antivirus, EDR, updates or disk encryption.
- Destructive Git reset/clean workflows.
- Database writes.
- Arbitrary administrator/root elevation.
- Self-modifying policy/security code.
- Offensive scanning of third-party systems.

## Non-goals
The assistant is not a replacement for endpoint protection, patching, secure backups, full-disk encryption, MFA, a password manager, network/firewall hygiene or professional incident response.
