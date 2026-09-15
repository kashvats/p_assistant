# Changelog

## 0.5.0

- Added local SQLite personal calendar with create/list/cancel and iCalendar export.
- Added deterministic morning/evening briefings from calendar, todos, project state, approvals and recent attention events.
- Added quiet hours and bounded focus mode. Non-urgent notifications are durably queued and flushed after quiet mode.
- Added daily and weekly clock-based deterministic routine triggers.
- Added local session history with bounded context, retention pruning, search/delete controls and common secret redaction.
- Added native Tkinter approval review window.
- Added provider-neutral connector metadata registry that stores no credentials.
- Model-waking routines are suppressed while focus/quiet mode is active.
- Added personal/calendar/briefing/session/connectors/queued-notification API and dashboard surfaces.
- Expanded regression suite to 44 passing tests.

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
