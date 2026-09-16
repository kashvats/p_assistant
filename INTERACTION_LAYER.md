# Interaction Layer — v0.10.0

Living Assistant v0.10.0 adds a bundled browser-based control center without introducing a separate Node/Electron runtime.

## Dashboard

Run `organism serve`, then open `http://127.0.0.1:8787/dashboard`.

The dashboard provides:

- streamed local chat;
- live model/tool activity;
- CPU and RAM history;
- active-model status;
- pending approval actions;
- local calendar and todo management;
- Security Guardian summary/findings;
- activity timeline.

When `ASSISTANT_API_TOKEN` is configured, the dashboard asks for it and keeps it in browser session storage. The token is not embedded in the page or URL.

## Streaming protocol

`POST /chat/stream` accepts the same request body as `/ask` and returns `text/event-stream` events. Event types include `status`, `token`, `tool`, `final`, and `error`.

Streaming executes through the same orchestrator, tool registry, security policy, approvals, experience engine and session store as synchronous chat. It is not a privileged alternate execution path.

`GET /activity` returns recent non-sensitive execution metadata. `GET /activity/stream` emits the same activity bus in real time over SSE.

## Resource behavior

The UI is static bundled HTML/CSS/JavaScript. It does not require a second web server or a Node runtime in production. Resource charts are rendered locally in the browser. The activity bus is bounded in memory and is observability-only; it is not used as authoritative state.
