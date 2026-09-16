# Living Assistant v0.12.0 Release Validation

## Automated gates

- Python compileall: PASS
- Full cumulative source test suite: **142/142 PASS**
- v0.12 focused connector tests: PASS
- Wheel build from source: PASS
- Installed-wheel import/version: PASS (`0.12.0`)
- Installed packaged default config: PASS
- Installed bundled dashboard asset: PASS
- Installed connector CLI provider listing: PASS
- Installed local API health/version: PASS
- Connector modules present in wheel: PASS
- Dashboard JavaScript syntax: PASS (`node --check`)
- Fresh ZIP extraction full suite: **142/142 PASS**

## v0.12 connector coverage

Mocked provider tests exercise capability gating, approval-gated writes, secret non-persistence, external-content trust marking, Google PKCE authorization URL construction, Microsoft device-code initiation, GitHub device-code initiation, and Obsidian vault traversal protection.

## Important live-service limitations

Automated release tests do **not** use real Gmail/Microsoft/GitHub/Telegram/Discord/Notion accounts. Live OAuth consent, tenant policy, provider rate limits and account-specific permissions must be validated on a real machine with the user's own app registrations. GitHub Device Flow must be enabled for the registered app. Microsoft organizational tenants may require administrator consent for some scopes. Google public-app scopes may require Google verification depending on distribution and requested access.

OS keyring persistence is optional and depends on a functioning platform keyring backend. Environment-token mode works without the keyring extra.
