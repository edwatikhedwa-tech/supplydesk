---
document_id: RUNBOOK-BACKEND-STARTUP-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-03
source_commit: b4fc8efcbce3d470748572e2287c43ed190ee5b6
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

## Runtime mode classification (required before any start command)

Before starting a backend process, classify the run against
`PROJECT_MANIFEST.yaml`'s `runtime_modes` block — the first source of truth —
then this runbook. Only two modes exist; do not invent a third without an
explicit owner task naming it:

- **`LOCAL_CANONICAL`** — the owner's normal local session. One command, no
  ambiguity:
  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
  python supplier_app.py
  ```
  Requires a repo-root `.env` (`backend/app_config.py`'s `load_dotenv` reads
  it). Base URL `http://127.0.0.1:8000`; database is the canonical
  `mail-data/supplier.sqlite3`. Real provider credentials (Yandex OAuth, SMTP,
  etc.) belong here only when the owner has explicitly authorized them for
  this checkout.
- **`SAFE_TEST`** — tests/browser/diagnostics only, never the owner's normal
  "log me in and let me use it" session:
  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_test_runtime.ps1 -Apply
  ```
  Default port `18000`, disposable database, real provider credentials are
  blanked by the script itself — Yandex/SMTP/IMAP login can never succeed
  here by design.

Starting `SAFE_TEST` when the owner asked to use the app normally (or vice
versa) is a stop condition, not a judgment call — ask which mode applies if
it is not already obvious from the request.

## Start boundary

Only start `LOCAL_CANONICAL` after a human-approved need for it, with
outgoing mail explicitly disabled unless the owner separately authorized real
sending. Both startup wrappers run the workspace guard themselves and accept
the same explicit `-ExpectedRoot` override. A read-only diagnostic task does
not start a server and does not inspect secret values.

## Stop conditions

Do not start a provider sync, queue worker or campaign. Do not change
`supplier_app.py`, `api/index.py`, runtime settings or the canonical DB while
diagnosing an HTTP failure.
