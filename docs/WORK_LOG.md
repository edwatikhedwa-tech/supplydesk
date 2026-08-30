# Work Log

## 2026-08-30 19:36 +03:00

TASK

Audit current SupplyDesk state and establish one verified project-state source
before selecting the next implementation task.

WHAT WAS VERIFIED

- Read current repository, migrations, deployment configuration, frontend/backend
  implementation, existing tests, and historical docs as non-authoritative
  context.
- Read the live/local SQLite only through read-only connections. Current count:
  493 supplier rows; request 1059 has 171 raw rows, 170 visible rows, and 140
  cards.
- Recomputed identity/card distributions and ran the current strict supplier
  scan: 0 strict-safe, 30 strict-unresolved, 2 ambiguous; three unknown
  supplier-reference tables remain in the audit inventory.
- Traced company-card selection through frontend Composer, API, service
  resolver, repository operation creation, and database uniqueness.
- Confirmed current outgoing safety: canonical runtime active, SQLite integrity
  ok, durable switch false, environment kill switch true, effective SMTP NO.
- Confirmed local SQLite and intended Vercel/PostgreSQL deployment paths.

WHAT CHANGED

- Created/updated `docs/ENGINEERING_CONTRACT.md`, `docs/CURRENT_STATE.md`,
  `docs/DECISIONS.md`, and this `docs/WORK_LOG.md`.
- No product code, schema, live supplier rows, mail messages, guards, jobs, or
  outgoing controls were changed in this audit.

TESTS

- `python -m unittest discover -s tests -p 'test_supplier_identity.py'`: 27 OK.
- `python -m unittest discover -s tests -p 'test_mail_status_semantics.py'`: 16 OK.
- `python -m unittest discover -s tests -p 'test_mailru_mvp.py'`: 12 OK.
- `npm run typecheck`: PASS.
- `npm run lint`: PASS, 8 existing warnings.
- `npm run build`: PASS.
- Previous full backend verification on this source state: 344 tests, OK,
  1 PostgreSQL skip.
- HTTP smoke: `/` 200, `/api/auth/me` 200, unauthenticated request endpoint 401.

DATABASE IMPACT

- Read-only only for the audit. No `supplier_identity_audit.py --apply` and no
  `--apply-strict-safe` were run. No real SMTP/IMAP send was run.

UNRESOLVED

- Supplier merge is not apply-ready: current strict-safe count is zero.
- PostgreSQL and real Mail.ru live acceptance remain unverified.
- Test suites lack a centralized production/live DB-path abort guard.
- Outgoing lifecycle and recyclable Vercel queue startup need hardening before
  any future enablement.

NEXT RECOMMENDED STEP

Design and implement the supplier-identity relation inventory/gate as one
isolated task. It must classify the two live FK relations and the immutable
reconciled evidence table before any future merge apply decision.
