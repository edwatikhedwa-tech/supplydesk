---
document_id: RUNBOOK-BACKEND-STARTUP-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: backend startup and safe HTTP probe

## Observe

Use `scripts/doctor.ps1 -Plan` to inspect intended checks. Use `-DryRun` for
the read-only runner. Safe route expectations are `/` → `200`,
`/api/auth/me` → `200` in the recorded local contract, protected mail route
→ `401`, and an unknown API route → `404`. A connection refusal is an
`ENVIRONMENT_GAP`, not a failed product assertion.

## Start boundary

If a human-approved local startup is needed, use the repository's documented
startup path with outgoing mail explicitly disabled and a disposable/local
database. This diagnostic task does not start a server and does not inspect
secret values.

## Stop conditions

Do not start a provider sync, queue worker or campaign. Do not change
`supplier_app.py`, `api/index.py`, runtime settings or the canonical DB while
diagnosing an HTTP failure.
