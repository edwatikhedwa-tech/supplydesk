---
document_id: RUNBOOK-DATABASE-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: database diagnostics

## Observe

Run `powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1 -DryRun`.
The V1.1 runner opens the configured SQLite path with `file:...?mode=ro` and
reads `quick_check`, `integrity_check`, `journal_mode`, `user_version` and
table names. An absent `mail-data/supplier.sqlite3` is `ENVIRONMENT_GAP`.
A corrupt or unreadable database is `PRODUCT_FAILURE/FM-DATA-001`; the
negative fixture test exercises that classification against a disposable
SQLite file.

## Do not do

Do not instantiate `MailRepository` against the canonical database: its
initialization can ensure schema and write state. Do not run migrations,
`VACUUM`, `INSERT`, `UPDATE`, `DELETE`, or create a replacement canonical DB.

## Recovery

Stop at evidence collection and open an incident if integrity fails. A backup
or repair requires a separately approved, reversible operation with a precise
database path and human approval.
