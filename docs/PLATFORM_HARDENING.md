# Living Assistant v0.16 — Platform Hardening

v0.16 focuses on predictable behavior across ordinary Windows, Linux and macOS user accounts. It does not require administrator/root privileges for the core assistant.

## Filesystem links

`organism platform link-probe` tests the filesystem actually used by the current process.

The semantic-preserving order is:

1. native symbolic link;
2. on Windows, a directory junction for a directory target;
3. a same-volume hard link for a file target;
4. a copy only when a caller explicitly opts into changed semantics.

Living Assistant never silently converts a failed symlink into a copy. Security/integrity walkers also treat Windows reparse points as traversal boundaries so a junction cannot make a protected-tree scan walk into an unrelated directory.

Windows status reports Developer Mode and long-path registry state when readable, but actual link creation is still probed because policy, filesystem type and privileges can differ from those registry values.

## Background services

### Windows

`scripts/install_daemon_windows.ps1` installs a limited-privilege Scheduled Task at user logon. It uses `StartWhenAvailable`, avoids duplicate concurrent instances and continues on battery power.

The Windows bootstrap invokes `.venv\\Scripts\\python.exe` directly and does not require PowerShell `Activate.ps1`, avoiding execution-policy failures on standard accounts.

### Linux

`scripts/install_daemon_linux.sh` installs `~/.config/systemd/user/living-assistant.service`. Paths are quoted/escaped, shutdown has a bounded timeout and status is printed after installation. The service follows the lifetime of the user's systemd manager; environments that need operation without an active login may separately configure user lingering according to local policy.

### macOS

`scripts/install_daemon_macos.sh` generates the LaunchAgent plist using Python `plistlib`, validates it with `plutil`, and loads it with the user's `gui/<uid>` launchd domain using `bootout/bootstrap/kickstart`.

## Suspend/resume

The nervous system uses a privilege-free sleep/resume heuristic based on the elapsed interval between daemon ticks. On a resume-like gap it:

- rebaselines filesystem watch snapshots without emitting file-change events;
- refreshes the current listener set;
- clears stale process-health failure counters;
- resynchronizes Ollama resident-model state when available;
- emits a `system_resume_detected` event.

This is intentionally a conservative heuristic rather than a platform-specific privileged power hook.

## Diagnostics

```bash
organism platform status
organism platform link-probe
organism platform service-status
organism doctor
```

`/platform/status` and `/platform/service-status` expose the same read-only information through the authenticated localhost API.

## Real-machine validation still required

Automated tests simulate Windows non-admin symlink denial and service-manager behavior, but the final v1.0 gate still requires real machines for:

- Windows standard user with Developer Mode both off and on;
- NTFS junction behavior and long paths;
- Windows Scheduled Task login/sleep/resume;
- Linux systemd user-service login/logout/suspend behavior;
- macOS LaunchAgent, Accessibility, microphone and Endpoint Security permissions;
- real multi-monitor and desktop-input behavior;
- long-running suspend/resume/soak tests.
