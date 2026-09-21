# Living Assistant v0.15 — Security Sensor Platform

v0.15 extends the existing Security Guardian with optional, deterministic endpoint telemetry and integrity sensors. The design remains **sensor/rules first, AI explanation second**. A model does not directly decide that a process is malware, and high-impact containment remains policy/approval controlled.

## Architecture

```text
Windows Sysmon/Event Log ─┐
Linux auditd/journald ────┼─> normalized events ─> deterministic correlation ─> Guardian findings
macOS ES helper/logs ─────┘                         │
                                                    ├─ DNS context
YARA / reputation / signatures ────────────────────┤
USB / browser extensions / backups ────────────────┤
file-change burst detector ────────────────────────┘

Guardian findings -> notifications / dashboard / optional AI investigation
```

The daemon keeps these sensors model-free. Heavy local models remain asleep unless the user explicitly asks for investigation/explanation.

## Windows Event Log and Sysmon

On Windows, Living Assistant reads a bounded recent window from:

- `Microsoft-Windows-Sysmon/Operational`
- selected high-signal events from the Windows Security log

Normalized Sysmon signals include process creation, network connections, DNS queries, file creation/deletion, registry modifications, WMI persistence, process access/injection and process tampering. Security Event Log support includes process creation and selected persistence/account/audit-policy events when the current account can read them.

Living Assistant does not install or reconfigure Sysmon automatically. Sysmon network/DNS/file telemetry must be enabled by your own reviewed Sysmon configuration.

## Linux auditd

When available, the Linux sensor uses `ausearch` and falls back to audit records visible through `journald`. Audit records sharing the same audit serial number are grouped into one normalized event so SYSCALL/PATH/EXEC records can be correlated.

The assistant does not enable audit rules, change `/etc/audit/*`, or grant itself root privileges.

## macOS Endpoint Security

`native/macos_endpoint_security/` contains a **notification-only** native helper source and NDJSON protocol. Apple requires the Endpoint Security entitlement and code signing/system-extension deployment. The Python package cannot bypass those requirements.

Without the native helper, v0.15 can use a conservative macOS Unified Log fallback for selected security-related processes/subsystems.

## DNS monitoring

Windows Sysmon Event ID 22 is normalized directly. On Linux/macOS, where universal per-process DNS query telemetry is not reliably exposed to an unprivileged process, an optional local NDJSON collector can be configured:

```yaml
security_sensors:
  dns_context_jsonl: /path/to/local-dns-events.jsonl
```

The DNS analyzer reports top domains and a conservative "algorithmic-looking" hostname heuristic. That heuristic is not a malware verdict.

## TLS / SNI context

Universal passive SNI capture is intentionally **not faked**. It may require privileged packet/process telemetry, and Encrypted Client Hello can intentionally hide the server name.

v0.15 accepts bounded NDJSON metadata from a separately privileged local collector:

```yaml
security_sensors:
  tls_context_jsonl: /path/to/tls-events.jsonl
```

Supported fields include `pid`, `process`, `remote_ip`, `remote_port`, `server_name`, `tls_version`, `ja3`, `source`, and `time`.

## Process/file reputation

If `VIRUSTOTAL_API_KEY` is configured, a file or running process executable can be checked by SHA-256. **Only the hash is sent. File bytes are never uploaded.** Reputation calls are explicit; the daemon does not continuously submit hashes.

A configurable number of malicious-engine detections can create a high-confidence `known_malicious_hash` Guardian finding.

## Signed-binary trust database

A local trust record stores:

- resolved path
- SHA-256
- OS signature/package-owner status when available
- signer/owner information when available
- local label and timestamps

Later checks detect hash, signer, signature-status, or missing-file changes. Linux package ownership is useful provenance but is not equivalent to a cryptographic signature.

## YARA

YARA is optional (`pip install -e ".[security]"`) and can also use a locally installed `yara` CLI. Rules are never downloaded automatically. Scans are read-sensitive operations and require approval.

Configure reviewed rule files:

```yaml
security_sensors:
  yara_rules:
    - /path/to/rules/base.yar
```

## USB monitoring

The platform takes a device metadata inventory using native OS facilities:

- Windows PnP device metadata
- Linux `lsusb` or `/sys/bus/usb/devices`
- macOS `system_profiler SPUSBDataType`

A trusted baseline can be captured explicitly, then newly attached/removed devices are compared against it.

## Browser-extension monitoring

Chrome/Chromium/Edge/Brave extension manifests and Firefox `extensions.json` metadata are inspected. Browsing history, cookies, passwords and page content are not read.

Baseline checks detect:

- new extensions
- removed extensions
- version/manifest changes
- newly added extension permissions

Permission increases generate a higher-severity finding.

## Ransomware-like behavior detection

The detector keeps a bounded rolling window of file add/change/remove events and scores signals such as:

- unusually large file-change bursts
- activity across many directories
- mass removals
- many file types affected

This is deliberately heuristic. Backup tools, builds, migrations and bulk media conversion can produce similar patterns.

A file-change burst alone never automatically disconnects the machine.

## Backup integrity

Backup baselines store a bounded file manifest and root hash. Checks report missing backup paths, removed files and modified files. The baseline must be explicitly captured/refreshed.

## Network isolation

Manual network isolation always requires explicit approval and uses a reversible OS backend when available:

- Windows `Disable-NetAdapter` / `Enable-NetAdapter`
- Linux NetworkManager `nmcli networking off/on`
- macOS `networksetup` service disable/enable

Automatic isolation is **off and unarmed by default**. Even when explicitly armed it requires independent configured high-confidence signals. The default requires both:

```yaml
auto_required_signals:
  - mass_file_change
  - known_malicious_hash
```

Partial isolation state is persisted so restore remains possible if one interface/service action fails partway through.

## Useful commands

```bash
organism security sensor-status
organism security events --minutes 10
organism security correlate --minutes 10
organism security dns --minutes 10
organism security tls-context

organism security yara ./suspicious.bin
organism security reputation ./suspicious.bin
organism security reputation-process 1234
organism security binary-assess ./tool.exe
organism security binary-trust ./tool.exe
organism security binary-check

organism security usb-capture
organism security usb-check
organism security extensions-capture
organism security extensions-check

organism security backup-capture nightly ./backups
organism security backup-check nightly

organism security network-isolate
organism security network-restore
```

## Important limitations

This is still not a claim of commercial EDR equivalence. Full EDR products commonly add protected kernel/system-extension sensors, enterprise fleet telemetry, central threat intelligence, tamper resistance, signed policy distribution and much deeper forensic retention.

Real Sysmon configuration, auditd permissions, macOS Endpoint Security entitlement/signing, YARA installation, network isolation privileges and actual ransomware-like workload behavior must still be validated on real machines before v1.0.
