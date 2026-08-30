# Current State

Дата аудита: 2026-08-30. Это snapshot фактически проверенного состояния, не
changelog.

## SYSTEM

- Backend: Python HTTP application с DB-API repository; frontend: React +
  TypeScript/Vite.
- Локальный runtime на `127.0.0.1:8000` запущен и использует canonical
  `mail-data/supplier.sqlite3`.
- Source migration set заканчивается `031_manual_inbox_request_links`.

## DATABASE

- Текущая read-only SQLite содержит `493` supplier rows.
- `PRAGMA integrity_check` возвращает `ok`.
- В схеме есть SQLite и PostgreSQL ветки. Миграции выполняются repository при
  инициализации; отдельного applied-migrations ledger не обнаружено.
- В filenames есть два migration с префиксом `026`: это не ломает текущую
  idempotent SQLite инициализацию, но ухудшает операционную ясность порядка.

## MAIL

- Текущая база содержит две connected accounts: Yandex и Mail.ru.
- Outbound messages: `sent=62`, `queued=84`, `failed=2`,
  `delivery_unknown=1`; inbound messages: `16 received`.
- Для request 1059: `outbound_total=132`, `queued=84`, историческое SMTP
  acceptance `accepted=46`, эффективное accepted без bounced `45`, `failed=2`,
  `bounced=1`, replies `7`.
- UI-термин «Отправлено» означает SMTP/provider acceptance. Это не доказательство
  Inbox placement.
- Hard bounce распознаётся отдельно; soft bounce не превращается автоматически
  в permanent suppression.

## OUTGOING SAFETY

- `SAFETY-001` is closed for the verified SQLite/runtime path. The durable
  global control is `mail_runtime_controls.outgoing_enabled`; clean schema
  creation and a missing control row are fail-closed (`0`/`False`). Invalid
  values and database read failures are also treated as disabled and logged.
- The default for `mail_account_profiles.outgoing_enabled` and the account
  query fallback is `0`. A provider connection explicitly creates/refreshes
  that account's profile, but it never enables the global outgoing switch.
- The only implemented enable flow is `POST /api/mail/runtime/outgoing` with
  explicit JSON booleans `enabled` and `confirmation=true`, an authenticated
  CSRF-protected session, and durable `owner` membership. The global switch is
  database-wide; it is not a per-workspace switch. A new workspace does not
  create an enabling row and remains blocked while the global default is off.
- `api/index.py` no longer starts the mail queue during module import. The
  local `SupplierApp.run()` entry point starts workers explicitly. A running
  worker performs the durable gate check before claiming work, and the
  provider boundary retains the final race-safe check.
- With outgoing disabled, existing jobs remain `queued` and attempts do not
  increase. No real SMTP call was made by the safety acceptance.

## REQUEST / SUPPLIER

- Request 1059: `171` raw `request_suppliers` rows; `170` visible rows после
  исключения одной irrelevant row; `140` company cards.
- Card math: `112` cards of size 1, `27` of size 2, `0` of size 3, `1` of
  size 4+, so `112 + 27 + 1 = 140` cards and
  `112 + 27×2 + 4 = 170` visible supplier memberships. The reduction is
  `170 - 140 = 30` presentation-level collapsed memberships; it is not a
  physical delete.
- All-database identity grouping by confirmed `global_supplier_id`, with each
  unlinked supplier row as its own group: `485` groups; `6` groups contain more
  than one row. Distribution: size 1 = `479`, size 2 = `5`, size 3 = `0`, size
  4+ = `1` (the latter has 4 rows). The check is
  `479 + 5×2 + 4 = 493` rows and `479 + 5 + 1 = 485` groups.
- Request-level grouping uses the same confirmed identity plus the request
  view's unambiguous hostless-email attachment rule. Its distribution is the
  card distribution above. A card may retain several distinct emails.
- Current supplier strict cleanup scan: broad exact-host-email candidates `29`,
  base unresolved `1`, ambiguous `2`, strict unresolved `30`, strict safe `0`.
  No physical supplier row is currently approved for deletion/deactivation.
- Supplier merge audit reports unknown supplier relations:
  `mail_cross_provider_retries`, `mail_inbox_request_links`, and
  `mail_reconciled_outbound_events`. Each has one live row; their semantics are
  different and must be classified before any merge.

## RESEND PROTECTION

- **CLOSED FOR SQLITE** based on current code and isolated tests: composite
  `(workspace, request, normalized_email)` guard, transactional guard/message
  creation, database uniqueness, rollback, concurrency, operation idempotency,
  explicit repeat, and preflight/queue recipient agreement are covered.
- One selected company card produces at most one outbound target/message in the
  tested grouped-company flow. When the requested primary is already used and
  an unambiguous NEVER_USED alternate exists, one alternate is selected.
- The current request Composer has no explicit alternate-email picker; this is a
  product/UX choice, not an automatic merge or a resend bypass.
- Current live guard row count is `0`; the guard table and constraints exist.
- PostgreSQL acceptance is not verified in this environment.

## MAIL PROVIDERS

- Mail.ru MVP uses application password, SMTP SSL 465 and IMAP SSL 993; OAuth
  Mail.ru is explicitly unsupported.
- Mail.ru unit/MVP tests use patched/dummy transports. Targeted current run:
  `12 tests, OK`.
- No real Mail.ru SMTP/IMAP acceptance was run during this audit. A connected
  account row is not live provider acceptance evidence.
- Failure classification distinguishes retryable/transient, permanent,
  policy/auth failures, and post-DATA delivery unknown in the tested provider
  adapter. Live provider confirmation remains open.

## FRONTEND

- Request company cards expose aggregated contacts/statuses. Selection sends a
  selected card's primary supplier row to Composer; backend resolves the final
  contact and the bulk operation creates one target per selected effective
  contact.
- `not_sent` is a company-card predicate: the card has email and all its email
  contacts are `not_sent`, with no queued/accepted/failed/unknown/bounced/
  cancelled contact. A mixed card is not classified as wholly not sent.
- Playwright default config points to local port 8000 but the audited frontend
  suites route-mock their `/api/**` calls. The live email regression reads real
  inbox/thread endpoints after login and does not send mail. No central test
  guard rejects a live DB path.
- Current checks: typecheck PASS, lint PASS with 8 existing warnings, build
  PASS. Full visual matrix was not rerun in this audit.

## TEST STATUS

- Backend full suite post-change: `355 tests`, `OK (skipped=1)`; the skip is
  the PostgreSQL branch without `DATABASE_URL`/isolated integration fixture.
- `tests/test_outgoing_safety.py`: `11 tests, OK`; this covers clean/missing,
  false/malformed/restart, missing account profile, import, owner control,
  runtime refresh, 84 queued jobs, and explicit fake-provider enable.
- Current targeted tests: supplier identity `27 OK`, status semantics `16 OK`,
  Mail.ru MVP `12 OK`.
- Existing backend tests use temporary SQLite paths in the inspected suites;
  no explicit centralized `if DB path == live: ABORT` guard was found.
- The missing guard is a test-infrastructure risk even though the observed
  current tests were isolated.

## PRODUCTION SAFETY

- Current runtime report: one active canonical runtime, canonical path match,
  SQLite integrity `ok`, live SMTP allowed `NO`.
- `MAIL_OUTGOING_DISABLED=1` is set in local environment and durable
  `mail_runtime_controls.outgoing_enabled=0` is present in the current DB.
- Account-level outgoing flags are `1` for the two existing connected accounts,
  but the global durable control and environment kill switch block transport.
  New account profiles default to `0`; explicit account connection is the
  account-level eligibility action, while the global switch remains separate.
- The source default for a new runtime control row is now `0`, and importing
  `api/index.py` has no queue-start side effect. Vercel still requires a
  dedicated durable worker before any production background delivery is
  enabled there.
- HTTP smoke passed while leaving the server running: `GET / = 200`,
  `/api/auth/me = 200`, unauthenticated `/api/requests/1059 = 401`.

## KNOWN LIMITATIONS

- PostgreSQL transaction/concurrency/continuation acceptance is not verified.
- Real Mail.ru live acceptance is not verified; no real sends were made.
- Supplier identity cleanup is not apply-ready. The old historical `132`
  candidate number is not a current metric.
- No explicit central test DB-path safety guard exists.
- Vercel durable worker behavior is not verified; the adapter intentionally
  does not start background delivery during import.
- The request Composer does not let the user explicitly choose among multiple
  company emails.

## UNRESOLVED

- `IDENTITY-001` (HIGH): 30 strict-unresolved identity records and 2 ambiguous
  records; no apply permitted.
- `IDENTITY-002` (HIGH): three live supplier-reference tables are absent from
  the merge auditor's known relation set; one is immutable evidence, two are
  live FK/association records.
- `MAIL-001` (MEDIUM): PostgreSQL acceptance is not verified.
- `MAIL-002` (MEDIUM): no real Mail.ru live acceptance evidence.
- `TEST-001` (MEDIUM): no centralized live-DB abort guard for backend/Playwright
  test execution.
- `UX-001` (LOW): explicit multi-email contact picker is absent; backend's
  automatic alternate policy is currently the behavior under test.
- `DB-001` (LOW): duplicate migration numeric prefix and no migration ledger.
