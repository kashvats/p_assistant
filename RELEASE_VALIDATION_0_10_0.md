# Living Assistant v0.10.0 Release Validation

Validation performed on the cumulative v0.9.2 hardened base plus the v0.10 interaction layer.

- Python test suite: 121 passed.
- Dashboard JavaScript syntax: passed with Node syntax check.
- Security hardening regression suite retained.
- Streaming tool calls use the normal orchestrator tool/approval path.
- Streaming errors are secret-redacted before UI delivery/activity persistence.
- Dashboard supports API-token protected deployments.
- Dashboard response includes CSP, frame denial, no-sniff and no-referrer headers.
- Wheel/package test must verify bundled `webui/index.html` before release.

Remaining roadmap items are not claimed as part of v0.10.0: wake-word voice, OAuth connectors, adaptive multi-model residency, and full Windows non-admin symlink/junction compatibility.
- Built wheel SHA-256: `fbad5f9aa2eb287c4bbd0373f143e4250103be46718f3ae880641364b91aadec`.
- Isolated target-install smoke: version 0.10.0, dashboard HTTP 200, CSP present, packaged config present, streaming routes present, SSE token/final events verified.
