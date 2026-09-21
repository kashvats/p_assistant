# Living Assistant v0.17.2 Production Packaging

v0.17 introduces a versioned, per-user runtime lifecycle. Application binaries and Python environments are disposable; user data is kept separately.

## Layout

- **Runtime:** platform-specific `LivingAssistantRuntime` directory
- **Versions:** `runtime/versions/<version>/venv`
- **Stable launchers:** `runtime/bin`
- **Install state:** `runtime/install-state.json`
- **Backups:** `runtime/backups`
- **Persistent data:** existing platform-specific `LivingAssistant` data directory

The updater never installs over the active environment. A new venv is built and self-checked, migrations run, stable launchers switch atomically, and an installed user service is best-effort restarted through the stable daemon shim.

## Install / update

From the extracted release:

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_release_windows.ps1
```

### Ubuntu/Linux

```bash
./scripts/install_release_linux.sh
```

### macOS

```bash
./scripts/install_release_macos.sh
```

By default release wrappers install common optional groups. Override with `LIVING_ASSISTANT_EXTRAS`.

The generic installer is also available:

```bash
python scripts/install.py install dist/living_assistant-0.17.2-py3-none-any.whl --sha256 <expected-sha256>
python scripts/install.py status
python scripts/install.py verify
```

## Backup and rollback

Updates create a local backup before switching versions. SQLite databases use SQLite's backup API for a consistent snapshot. Volatile logs, browser profiles, evaluation worktrees and canary worktrees are excluded. Backups may contain personal assistant state and should be treated as sensitive local files.

```bash
organism release backup
organism release status
organism release verify
organism release rollback
```

A normal rollback changes code only and keeps current user data. Restoring an older data backup is explicit because automatic restoration could erase data created after the update:

```bash
organism release rollback --restore-backup /path/to/data-before-0.17.2.zip
```

## Uninstall

Runtime uninstall preserves user data by default:

```bash
python scripts/install.py uninstall
```

A data purge requires two explicit flags:

```bash
python scripts/install.py uninstall --purge-data --yes-really-purge-data
```

The uninstaller also removes the per-user systemd/launchd/Scheduled Task service where supported.

## Migrations

`data_schema.json` tracks the persistent-data schema independently of code versions. v0.17 introduces schema 1 as a backwards-compatible marker only; the existing stores continue using idempotent `CREATE IF NOT EXISTS` migrations. The installer refuses a data schema newer than it understands.

If a migration fails after touching data, the updater attempts to restore the pre-update backup and leaves the previous runtime launcher active.

## Native package builders

- Linux: `packaging/linux/build_deb.sh` can build a native `.deb` release payload on Debian/Ubuntu.
- macOS: `packaging/macos/build_pkg.sh` builds an **unsigned** `.pkg` on macOS; release signing/notarization requires the distributor's Apple credentials.
- Windows: `packaging/windows/stage_msi_payload.ps1` stages the release payload for WiX on Windows. A distribution MSI must be authored, built, and signed on the Windows release host.

The project never generates, embeds, or pretends to possess platform signing identities.
