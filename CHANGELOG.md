# Changelog

## 0.4.0

- Added optional local push-to-talk voice layer with microphone approval, local faster-whisper STT and offline pyttsx3 TTS interfaces.
- Added deterministic event/interval routines. Model-waking routines are disabled by default and must be explicitly enabled.
- Added reviewable improvement proposal engine with exact diffs, base-hash conflict detection, backups and approval-gated apply.
- Security-policy, approval and improvement-engine core files cannot be auto-applied by the improvement engine.
- Added named isolated Playwright browser sessions, optional assistant-only persistent browser profiles, host scoping and live-session CLI.
- Added native notification when a noninteractive high-impact action enters the approval queue.
- Added API/dashboard surfaces for routines, improvement proposals, browser sessions and voice status.
- Added `voice`, `routine`, `improve`, and expanded `browser` CLI command groups.
- Lite profile continues to omit browser and voice model/sensor tools by default.
- Expanded test suite to 33 passing tests.

## 0.3.0

- Git-aware coding tools, project groups, clipboard/screenshot tools, optional browser automation and download quarantine.

## 0.2.0

- Persistent process supervision, filesystem watches, notifications, approvals and user-confirmed skills.

## 0.1.0

- Initial local-first orchestrator, sleeping specialist agents, tools, memory and hardware profiles.
