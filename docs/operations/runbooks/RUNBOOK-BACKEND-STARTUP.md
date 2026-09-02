---
document_id: RUNBOOK-BACKEND-STARTUP-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-02
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: backend startup and safe HTTP probe

## Observe

Before any command that can start the backend, run the workspace guard from the
repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
```

It must print `WORKSPACE_GUARD: PASS`. The default local root is
`C:\Users\edwat\SupplyDesk`; an intentional Git worktree or CI checkout must
pass its exact absolute root with `-ExpectedRoot`. A
`BLOCKED_WRONG_WORKSPACE` result is a stop condition.

Use `scripts/doctor.ps1 -Plan` to inspect intended checks. Use `-DryRun` for
the read-only runner. Safe route expectations are `/` → `200`,
`/api/auth/me` → `200` in the recorded local contract, protected mail route
→ `401`, and an unknown API route → `404`. A connection refusal is an
`ENVIRONMENT_GAP`, not a failed product assertion.

## Start boundary

If a human-approved local startup is needed, use the repository's documented
startup path with outgoing mail explicitly disabled and a disposable/local
database. The startup wrappers run the workspace guard themselves and accept
the same explicit `-ExpectedRoot` override. This diagnostic task does not start
a server and does not inspect secret values.

## Stop conditions

Do not start a provider sync, queue worker or campaign. Do not change
`supplier_app.py`, `api/index.py`, runtime settings or the canonical DB while
diagnosing an HTTP failure.
