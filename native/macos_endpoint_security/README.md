# macOS Endpoint Security helper

This directory contains the native **notification-only** telemetry helper used by the
Living Assistant v0.15 sensor adapter. It is source code, not a pre-entitled binary.

Apple requires the `com.apple.developer.endpoint-security.client` entitlement. The
helper must be code-signed and deployed through the appropriate app/system-extension
workflow before Endpoint Security events can be collected.

The helper appends bounded NDJSON event records to a local file. Configure:

```yaml
security_sensors:
  macos_endpoint_security_jsonl: /var/run/living-assistant/es-events.jsonl
```

The Python assistant only reads that file. It does not attempt to bypass Apple TCC,
System Extension, or Endpoint Security entitlement requirements.

A basic developer build (after entitlements/signing are set up) uses the EndpointSecurity framework:

```bash
clang -fblocks main.c -framework EndpointSecurity -framework Foundation -o living-assistant-es
```

Do not deploy the unsigned helper as a security control.
