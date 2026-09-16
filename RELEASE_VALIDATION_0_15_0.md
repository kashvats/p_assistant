# Living Assistant v0.15.0 Release Validation

## Source/release gate

- Python compilation: PASS
- Cumulative pytest suite: **194/194 PASS**
- v0.15 focused sensor/security regressions: **24/24 PASS**
- Dashboard JavaScript syntax (`node --check`): PASS
- Wheel build: PASS
- Installed-wheel import/version: PASS (`0.15.0`)
- Packaged default configuration: PASS
- Packaged dashboard: PASS
- Packaged macOS Endpoint Security helper source: PASS
- `organism security sensor-status`: PASS
- `/health`: HTTP 200
- `/security/sensors/status`: HTTP 200
- `/dashboard`: HTTP 200
- hostile Host header: rejected (HTTP 400)
- cross-origin browser request: rejected (HTTP 403)

## Security-specific regression coverage

The v0.15 suite covers Sysmon and Windows Security-event normalization, auditd record grouping, execution-chain correlation, DNS heuristics, TLS/DNS local collector adapters, YARA approval gating, hash reputation without file upload, high-confidence malicious-hash findings, signed-binary trust drift, USB baselines, browser-extension permission changes, backup integrity, ransomware-like file bursts, automatic-isolation gating, reversible isolation and partial-isolation recovery state.

## Artifact installation note

This validation environment has no dependency-download access and newly created isolated venvs do not inherit the harness's preinstalled FastAPI/Typer/PyYAML packages. The wheel was therefore installed into an isolated target directory with `--no-deps` and executed with the harness's already-installed dependency set. All Living Assistant imports came from the built wheel, not the source checkout.

## Real-machine validation still required

- Windows Sysmon installation/configuration and Security Event Log permissions.
- Linux auditd rules/permissions on the target distribution.
- macOS Endpoint Security entitlement, signing and System Extension deployment.
- Real YARA installation/rules and endpoint performance.
- Real USB and browser-profile variations.
- Network-isolation administrator privileges and recovery on each OS.
- Real ransomware-like workload false-positive tuning.
- DNS/TLS collector permissions and Encrypted Client Hello limitations.

## Wheel SHA-256

```text
4a8fdba0200d510df4b4915a7fb1aab36def27093f1c5341bc635a3ad812efd8  living_assistant-0.15.0-py3-none-any.whl
```
