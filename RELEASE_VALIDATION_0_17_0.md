# Living Assistant v0.17.0 Release Validation

## Source regression

- Full cumulative suite: **222/222 passed**
- Python compilation: PASS
- Dashboard JavaScript parse (`node --check`): PASS
- Linux/macOS shell syntax (`bash -n`): PASS

## Versioned installer lifecycle

Validated with real built wheels in isolated temporary runtime/data roots:

1. Install v0.16.0 with no dependency downloads: PASS
2. Create persistent user state: PASS
3. Update to v0.17.0: PASS
4. Pre-update backup creation: PASS
5. Verify active v0.17.0 runtime: PASS
6. Roll back code to v0.16.0: PASS
7. Verify rolled-back v0.16.0 runtime: PASS
8. Confirm user state survived update + rollback: PASS

The normal rollback does not restore an older data backup automatically. Backup restoration is explicit to avoid deleting newer user data.

## Installed wheel smoke

- Wheel package/version import: PASS (`0.17.0`)
- Packaged default config: PASS
- Packaged dashboard: PASS
- Packaged release manager: PASS
- Packaged macOS Endpoint Security helper: PASS
- `organism release status`: PASS
- `/health`: PASS (`0.17.0`)
- Host-header protection: PASS

## Installer security and recovery tests

- Reject foreign wheel identity: PASS
- Reject mismatched expected SHA-256 before install: PASS
- Validate optional extra names: PASS
- Consistent SQLite backup API: PASS
- Browser-profile/cache exclusion from update backups: PASS
- Data-schema migration idempotency: PASS
- Read-only release status: PASS
- Active-version removal refusal: PASS
- Data purge requires explicit confirmation before any runtime deletion: PASS
- Stable launcher changes on rollback: PASS
- User-service restart/removal is non-elevating and best effort: PASS

## Native/package payloads

- Python wheel: PASS
- Debian/Ubuntu `.deb` release payload build: PASS
- Debian payload contains `living-assistant-install`: PASS
- macOS `.pkg` build recipe: syntax checked; actual `pkgbuild`, signing and notarization require a macOS release host
- Windows release PowerShell installer: included; signed MSI payload staging requires a Windows release host and WiX/signing credentials

No platform signing identity or private signing key is embedded in the repository or release.

## Artifact checksums

See `SHA256SUMS.txt` for the wheel and Debian payload checksums. The outer source ZIP checksum is reported separately after the final archive is created.
