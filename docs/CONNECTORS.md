# Connected Assistant — v0.12

v0.12 turns the old connector registry into executable, capability-scoped integrations. Credentials are resolved at call time from environment variables or, when the `connectors` optional extra is installed, the operating-system keyring.

## Security model

- Connector JSON contains metadata only: provider, capabilities, settings, environment prefix and enabled state.
- Secret-like keys are rejected recursively from connector settings.
- OAuth access/refresh tokens are stored in the OS keyring, not assistant JSON/SQLite files.
- Static tokens may be supplied as `<ENV_PREFIX>_ACCESS_TOKEN`, `_TOKEN` or `_BOT_TOKEN` depending on provider.
- Every external write/send/create/review action requires explicit one-time approval.
- Approval records do not persist full message/document bodies.
- External provider data is wrapped as `UNTRUSTED_EXTERNAL_OBSERVATION` before it reaches an agent.
- Provider/action calls are restricted to capabilities declared when the connector is registered.

Install optional keyring support:

```bash
pip install -e ".[connectors]"
```

Inspect providers:

```bash
organism integration providers
```

## Google — Gmail / Calendar / Drive

Example:

```bash
organism integration add work-google mail google \
  mail.read,mail.send,calendar.read,calendar.write,files.read \
  --env-prefix WORK_GOOGLE
```

Set `WORK_GOOGLE_CLIENT_ID` and, if your OAuth client requires it, `WORK_GOOGLE_CLIENT_SECRET`. Then:

```bash
organism integration auth work-google
```

The desktop flow uses a temporary loopback callback plus PKCE. Default scopes are chosen from the declared connector capabilities. Prefer read-only capabilities unless the assistant genuinely needs write access.

Actions: `gmail.list`, `gmail.get`, `gmail.send`, `calendar.list`, `calendar.create`, `drive.list`.

## Microsoft 365 — Outlook / Calendar / OneDrive

```bash
organism integration add work-ms mail microsoft \
  mail.read,mail.send,calendar.read,calendar.write,files.read \
  --env-prefix WORK_MS --settings '{"tenant":"common"}'
```

Set `WORK_MS_CLIENT_ID`, then run:

```bash
organism integration auth work-ms
```

The CLI uses Microsoft device authorization and stores the resulting token bundle in the OS keyring. `offline_access` is requested so access tokens can be refreshed.

Actions: `mail.list`, `mail.get`, `mail.send`, `calendar.list`, `calendar.create`, `drive.list`.

## GitHub pull-request supervisor

```bash
organism integration add github developer github pr.read,pr.review \
  --env-prefix GITHUB --settings '{"repo":"owner/repository"}'
```

Either provide `GITHUB_ACCESS_TOKEN` (a fine-grained token is preferred) or configure a GitHub OAuth/GitHub App client id as `GITHUB_CLIENT_ID` and run `organism integration auth github` with Device Flow enabled for the app.

Actions: `pr.list`, `pr.get`, `pr.files`, `pr.review`. Reviews are approval-gated.

## Telegram

```bash
organism integration add telegram messaging telegram messages.read,messages.send --env-prefix TELEGRAM
```

Provide `TELEGRAM_BOT_TOKEN`. Actions: `messages.updates`, `messages.send`.

## Discord

```bash
organism integration add discord messaging discord messages.read,messages.send \
  --env-prefix DISCORD --settings '{"channel_id":"123456789"}'
```

Provide `DISCORD_BOT_TOKEN`. Actions: `messages.list`, `messages.send`.

## Notion

```bash
organism integration add notion productivity notion pages.read,pages.write \
  --env-prefix NOTION --settings '{"parent_id":"YOUR_PARENT_PAGE_ID"}'
```

Provide `NOTION_TOKEN`. v0.12 sends the current `Notion-Version: 2026-03-11` header. Actions: `search`, `page.get`, `page.create`.

## Obsidian

Obsidian is local and requires no token:

```bash
organism integration add notes productivity obsidian notes.read,notes.write \
  --settings '{"vault_path":"/absolute/path/to/vault"}'
```

Actions: `notes.search`, `notes.read`, `notes.write`. All note paths are resolved underneath the configured vault; traversal outside it is rejected. Writes require approval.

## API and agent tools

Authenticated localhost API:

- `GET /connectors`
- `GET /connectors/{name}/status`
- `POST /connectors/{name}/call`

The orchestrator receives `connector_list`, `connector_status` and `connector_call`. The same capability and approval gates are used by CLI, API and agent calls.
