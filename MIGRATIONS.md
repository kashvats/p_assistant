# Persistent Data Migrations

Living Assistant code versions and persistent-data schemas are deliberately separate.

- Installer state schema: **1**
- Persistent data schema: **1**
- v0.17 migration 0 -> 1: create only `data_schema.json`; no existing table or user content is rewritten.

Future migrations must be idempotent, bounded, locally backed up first, and tested both for successful upgrade and failed-migration recovery. Destructive down-migrations are not automatic. Code rollback keeps newer data unless the user explicitly restores a backup.
