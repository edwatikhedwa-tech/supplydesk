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

## 2026-08-30 20:22 +03:00

TASK

Implement and adversarially accept `SAFETY-001`: outgoing mail must remain
disabled unless an explicit trusted action enables it.

ROOT CAUSE

- `migrations/022_outgoing_mail_integrity.sql` created the singleton durable
  control with default/insert value `1`.
- `migrations/026_mail_account_profiles.sql` and account query fallbacks also
  treated missing account configuration as enabled.
- `api/index.py` called `_APP.queue.start()` during module import.
- `RuntimeSession` cached the durable flag, so an in-process explicit change
  would not be observed until restart.

WHAT CHANGED

- Changed clean-schema durable defaults to `0` and made account-profile
  fallbacks fail-closed.
- Made repository control reads strict: missing, invalid, and DB-error states
  return disabled and emit a diagnostic log.
- Added owner-only, CSRF-protected explicit control API:
  `POST /api/mail/runtime/outgoing` with strict boolean `enabled` and
  `confirmation=true`; added a read-only GET status endpoint.
- Removed API-module queue startup; local process startup remains explicit via
  `SupplierApp.run()`.
- Runtime refreshes the durable flag before worker/provider gates.
- Added `tests/test_outgoing_safety.py` and updated positive-path temporary
  fixtures to explicitly enable their fake transport.
- `docs/CURRENT_STATE.md` and `docs/DECISIONS.md` updated. The engineering
  contract was unchanged because its existing no-real-send rule already covers
  this invariant.

TESTS

- `python -m unittest -v tests.test_outgoing_safety`: 11 OK.
- `python -m unittest tests.test_mail_integrity tests.test_mail_pacing tests.test_canonical_runtime tests.test_mail_integration`: 159 OK, 1 PostgreSQL skip.
- `python -m unittest discover -s tests -p 'test_*.py'`: 355 OK, 1 PostgreSQL skip.
- The prescribed `powershell -ExecutionPolicy Bypass -File .\tests\run-tests.ps1`
  and `.\scripts\doctor.ps1` entry points are absent from this repository;
  both commands were attempted and reported missing files.
- After restarting the local process with the changed source: `GET /` = 200,
  `/api/auth/me` = 200, unauthenticated `/api/requests/1059` = 401, and
  unauthenticated `/api/mail/runtime/outgoing` = 401.
- Read-only `scripts/runtime_status.py`: canonical runtime count `1`, SQLite
  integrity `ok`, durable outgoing `False`, kill switch `True`,
  `live_smtp_allowed=NO`.
- Read-only live queue snapshot: `queued=84`, `sent=62`, `failed=2`,
  `delivery_unknown=1`; no real SMTP call was made.

DATABASE / SMTP IMPACT

- All new safety tests use temporary SQLite databases and fake providers.
- No `supplier_identity_audit.py --apply` command was run.
- No real SMTP call was made. The canonical live database was inspected only
  read-only; its durable outgoing control remained `0`.

DEFERRED FINDINGS

- PostgreSQL safety acceptance still requires an isolated configured test
  database.
- Vercel needs a dedicated durable worker before background delivery can be
  enabled; import-time queue startup is intentionally removed.
- No unrelated supplier identity, resend, provider, retry, status UI, or
  campaign behavior was changed.

NEXT RECOMMENDED STEP

Run the PostgreSQL-specific safety acceptance in an isolated database, then
review whether the database-wide owner-controlled switch should eventually be
split into workspace-scoped controls.

## 2026-09-01 07:30 +03:00 — DOCUMENTATION CANONICALIZATION

STATUS

This entry supersedes the older current-state numbers in this append-only log.
The only current-state source is now [`ai/CURRENT_STATE.md`](../ai/CURRENT_STATE.md).
Older entries remain historical evidence and must not be used as a live queue
or supplier count.

CONFIRMED CURRENT SNAPSHOT

- Request `1059`: 171 relevant supplier links; outbound `sent=125`, `failed=4`,
  `delivery_unknown=2`, `cancelled=82`, `queued=0`.
- Durable outgoing switch is `0`; no new mail is sent by this documentation
  task.
- SQLite integrity check is `ok`.
- Current code contains a Mail.ru provider implementation; live Mail.ru
  acceptance remains a separate `NOT VERIFIED` item unless a fresh provider
  run is recorded.

DOCUMENTATION RULE

[`docs/DOCUMENTATION_POLICY.md`](DOCUMENTATION_POLICY.md) defines the maintenance
process: update the canonical state and affected feature documentation in the
same task, mark old snapshots `HISTORICAL — NOT CURRENT`, and run
state/link/secret/diff checks before closeout. No application code, database
rows, migrations, mail settings or deployment configuration changed in this
reconciliation.
