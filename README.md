# Living Assistant v0.6 — Security Guardian

A local-first, hardware-adaptive personal assistant for Windows, Ubuntu/Linux and macOS. A deterministic **nervous system** stays awake for lightweight monitoring and scheduling while local SLMs sleep until reasoning is actually needed.

v0.6 keeps the personal operating layer from v0.5 and adds a defensive endpoint **Security Guardian**. It is designed to help notice changes and weak security posture, not to claim that heuristics can prove a machine is clean.

## v0.6 highlights

Everything from v0.5 remains, plus:

- Persistent startup/persistence baseline for Windows, Linux and macOS.
- Startup-file content fingerprints for common Linux/macOS persistence folders.
- Persistent listening-service baseline.
- Protected file-integrity baselines for explicitly selected paths.
- Deterministic process triage using bounded, explainable signals.
- Process ancestry, executable path, listening sockets and remote-connection inspection.
- Live network-activity summary without scanning third-party systems.
- Firewall, antivirus/endpoint protection and disk-encryption posture checks.
- Optional on-demand update posture check.
- Persistent security findings with severity, deduplication, reopen/resolve state and first/last-seen timestamps.
- Approval-gated containment for non-critical processes owned by the current user.
- Executable signature/package-ownership inspection where the OS exposes it.
- Quarantine provenance: original filename, source host, SHA-256, risk reason, scan history and release history.
- Signed/download URLs are stripped of query strings before persistent quarantine storage.
- Startup commands are redacted for common credential patterns before persistence.
- Security baseline mutations through agent/API paths require approval.
- Dashboard uses cached posture data so it does not repeatedly invoke OS security commands.
- Expanded suite: **61 passing tests**.

## Hardware profiles

### Main target — Ryzen 5 5600H / GTX 1650 4 GB / 32 GB RAM

Use the auto-selected `balanced` profile. Default roles use 4B/2B-class local models, with normally one physical model active at a time. The Security Guardian itself is deterministic Python and does not require an SLM.

### 8 GB systems

The `lite` profile still uses one tiny SLM, short context and deterministic tools first. Browser and voice remain disabled by default, but startup/listener baselines, file integrity, process inspection, calendar, routines, briefings and the daemon remain usable.

## Upgrade from v0.5

v0.6 uses additive SQLite tables and the same platform-specific data directory, so existing projects, approvals, todos, calendar events, sessions, routines and skills remain reusable. Back up the assistant data directory before replacing a working install.

```bash
pip install -e .
```

## Install

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e .
```

Then:

```bash
organism doctor
```

Optional extras remain:

```bash
pip install -e ".[desktop]"
pip install -e ".[browser]"
pip install -e ".[voice]"
playwright install chromium
```

## Security onboarding — important

Do **not** let the daemon silently decide that whatever is present on first launch is trusted. v0.6 defaults to:

```yaml
security_guardian:
  auto_initialize_baselines: false
```

After installing, review the machine while you believe it is in a known-good state, then run:

```bash
organism security initialize
```

The command warns before capturing the current startup/persistence items and listening services as the trusted reference.

Until this is done, the daemon produces a one-time medium-severity finding telling you that the startup/network baseline is missing.

## Security posture

Quick posture:

```bash
organism security posture
```

Include the slower package/update check:

```bash
organism security posture --updates
```

The exact information varies by OS. v0.6 can query, where available:

- Windows Defender Firewall / Microsoft Defender / BitLocker;
- macOS Application Firewall / FileVault / OS-managed protection metadata;
- Linux UFW, firewalld or nftables; ClamAV if installed; dm-crypt/LUKS detection; package-manager update metadata.

The daemon does **not** run the expensive update check every few minutes. Normal posture is refreshed on a slower interval and cached for the dashboard.

## Persistence monitoring

Inspect current persistence:

```bash
organism security startup-inventory
```

Compare against the trusted reference:

```bash
organism security startup-check
```

Deliberately replace the reference only when you know a legitimate change occurred:

```bash
organism security startup-capture
```

Typical inputs include:

- Windows StartupCommand and logon/boot scheduled tasks;
- Linux enabled systemd services, XDG autostart files and cron locations;
- macOS LaunchAgents/LaunchDaemons and launchctl labels.

Common startup/cron/plist files are hashed where practical, so editing an existing persistence file can be detected rather than only detecting a new filename.

## Listening-service baseline

```bash
organism security network-check
organism security network-activity
```

After a legitimate service change, explicitly recapture:

```bash
organism security network-capture
```

A public listening socket is treated as a stronger signal than a loopback-only listener, but **a new port is not proof of compromise**.

## Protected-file integrity

Protect a selected folder:

```bash
organism security baseline-add ssh-config ~/.ssh true "config,pub"
```

Protect a project/config folder:

```bash
organism security baseline-add retaileye-config /path/to/retaileye/config true "yaml,yml,json,toml,env"
```

Then:

```bash
organism security baseline-list
organism security baseline-check retaileye-config
```

When a legitimate change is reviewed and accepted:

```bash
organism security baseline-refresh retaileye-config
```

Agent/API baseline changes require explicit approval because replacing a baseline can erase evidence of a change. The CLI commands are explicit user actions.

For model-driven operations, integrity baselines can only be created inside approved workspaces.

## Process triage

Inspect one PID:

```bash
organism security process 1234
```

Show processes with deterministic suspicious signals:

```bash
organism security process-triage
```

Examples of signals currently used include:

- executable running from a temporary/download location;
- a temporary executable opening a listening socket;
- PowerShell using an encoded-command flag;
- Microsoft Office spawning selected script hosts / common LOLBins.

These are **signals, not malware verdicts**. The daemon only alerts automatically at a configurable score threshold.

Inspect a local file's SHA-256 and OS signature/package ownership where supported:

```bash
organism security file-signature /path/to/file
```

## Containment

A suspected user-owned process can be proposed for termination:

```bash
organism security contain-process 1234
```

Containment rules:

- explicit approval required;
- only current-user-owned processes;
- known critical OS processes are hard-blocked;
- the assistant will not automatically force-kill a process that ignores graceful termination;
- no automatic file deletion.

## Findings

```bash
organism security findings
organism security findings --status all
organism security resolve FINDING_ID
```

Findings are deduplicated using stable behavior/path keys. Repeated polls update `last_seen`/count rather than spamming a new item. A resolved finding can reopen if the same condition genuinely returns.

## Quarantine inspection

Risky web downloads remain isolated and are never auto-executed.

```bash
organism quarantine list
organism quarantine inspect ITEM_ID
organism quarantine scan ITEM_ID
organism quarantine release ITEM_ID destination/file.exe
```

Stored provenance includes source host/path, original filename, SHA-256, size, content type, risk reasons, scans and release history. URL credentials/query strings are intentionally not persisted.

## Security daemon

```bash
organism daemon
```

While idle, the security path remains deterministic:

```text
startup baseline ─────┐
listener baseline ────┤
protected files ──────┤
process signals ──────┤
firewall / AV posture ┤
                      ▼
               Security Guardian
                      │
                finding/event
                      │
        severity + quiet-hours policy
                      │
             notify / dashboard
                      │
              NO LLM REQUIRED
```

Default scan cadence:

```yaml
security_guardian:
  enabled: true
  auto_initialize_baselines: false
  scan_interval_seconds: 300
  posture_interval_seconds: 3600
  notify_min_severity: medium
  process_alert_score: 60
```

Low-severity observations remain in findings/events but do not generate desktop notifications when the minimum is `medium`.

## Existing personal/operator capabilities

v0.5 and earlier features remain available:

- local calendar, morning/evening briefing, todos/reminders;
- quiet hours, focus mode, notification queue;
- daily/weekly/event/interval routines;
- local session continuity with retention and common secret redaction;
- project registration, process supervision and multi-service groups;
- Git-aware coding, file diffs and approval-gated mutations;
- read-only-by-default SQL/Mongo access;
- bounded web/image download;
- optional isolated browser operator;
- optional push-to-talk local voice;
- reviewable self-improvement proposals.

## Control Center

```bash
organism serve
```

Open `http://127.0.0.1:8787/dashboard`.

The dashboard now includes cached Security Guardian posture, baseline status and open findings. Live posture remains an explicit API/CLI action rather than a dashboard-poll side effect.

## What this cannot guarantee

Living Assistant cannot guarantee that a laptop will never be hacked. It is a defensive monitoring and operator-assistance layer, not an EDR replacement or formal malware detector.

Keep OS updates, firewall, Defender/EDR/antivirus, disk encryption, MFA, secure backups and a password manager enabled. Do not treat a lack of guardian findings as proof that a machine is uncompromised.

## Tests

```bash
pytest -q
```

Current repository: **61 passing tests**.
