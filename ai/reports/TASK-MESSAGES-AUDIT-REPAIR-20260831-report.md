# TASK-MESSAGES-AUDIT-REPAIR-20260831 — frontend audit repair report

## Mode and scope

Mode: `EXTEND → ACCEPTANCE → CLOSE`.

Scope was limited to the three concrete failures from the previous `/messages`
frontend audit. The previous result was `56/80`: 56 browser checks passed and
24 failed. The 24 failures were the same three checks repeated over eight
viewport projects, not 24 different product defects.

Non-goals: SMTP/IMAP, sending, queue processing, database, migrations,
request-link persistence, filters outside the failing assertion, production
configuration and unrelated cleanup.

## Findings and fixes

### 1. Reply editor did not receive focus — fixed

Reproduction: open an unmatched message on `/messages`, click `Ответить`, and
try typing immediately. The previous audit observed that the contenteditable
field was visible but `document.activeElement` was still the reply button.

Cause: `RichTextEditor` had no autofocus contract and the composer did not ask
it to focus.

Fix: added an opt-in `autoFocus` prop and enabled it only for the inbox reply
composer. The current audit verifies `#inbox-reply-body` is the active element.

### 2. Delivery-unknown correspondence could be hidden — fixed

Reproduction: open a request containing a supplier whose last outbound status
is `delivery_unknown`, then open `/messages`. With no unread messages, the
correspondence group could start collapsed, hiding the actionable supplier row.

Cause: default group collapse considered only `unread_count`; it ignored
outbound operational attention states.

Fix: groups with unread messages or active outbound states (`sending`,
`queued`, `failed`, `delivery_unknown`) now start expanded. The audit fixture
also declares the status fields that the real API uses, so the test exercises
the actual visibility rule rather than an incomplete fixture.

### 3. Outbound metric assertion used obsolete wording — fixed

Cause: the test expected `принято почтовым сервером`, while the current
`PageHeader` intentionally renders the user-facing metric as `отправлено`.

Fix: aligned the test expectation with the current UI wording. No delivery
logic or status semantics changed.

## Verification evidence

### Browser acceptance

- `npm run test:visual` — `80/80 passed` in `4.2m` across:
  `desktop-max`, `desktop-user`, `desktop-wide`, `desktop-compact`,
  `tablet-landscape`, `tablet-portrait`, `mobile-large`, `mobile-small`.
  This suite uses controlled API fixtures and checks UI behavior, accessibility
  and overflow for the audit scenarios.
- `npx playwright test --config=playwright.live-email.config.ts` — `1/1
  passed` in `1.7m` without route mocks. It exercised live `/messages` with
  HTML, plain text, CID, remote-image, no-image and long-mail cases at
  `390`, `1024`, `1440` and `1640` widths.
- Supplemental browser evidence at `1440x900` and `390x844` confirmed focused
  reply editors, visible delivery-unknown rows, no horizontal overflow and no
  console/page errors.

### Code/runtime checks

- `npm run typecheck` — passed; TypeScript reported no errors.
- `npm run lint` — passed with `0` errors and `8` warnings in pre-existing,
  unrelated files (`SupplierPanel`, `RegistryFinanceRow`, `StatusBits`,
  `auth`).
- `npm run build` — passed; Vite emitted only its existing large-chunk
  advisory.
- `powershell -ExecutionPolicy Bypass -File ..\scripts\doctor.ps1 -DryRun` —
  passed without errors. The project `.venv` is absent, but direct Python
  `3.11.7`, declared imports and the canonical SQLite file are available.
- HTTP smoke: `GET /messages` → `200`; `GET /api/auth/me` → `200`; an unknown
  request API was handled as `401` without crashing the server. The local
  server remained running at `127.0.0.1:8000`.
- The documented `tests/run-tests.ps1` helper is absent and was not run.

## Visual evidence

Candidate screenshots (no approved baseline exists) are stored in:

- `Temp/task-messages-audit-repair-20260831/unbound-reply-focused-1440.png`
- `Temp/task-messages-audit-repair-20260831/unbound-reply-focused-390.png`
- `Temp/task-messages-audit-repair-20260831/delivery-unknown-thread-1440.png`
- `Temp/task-messages-audit-repair-20260831/delivery-unknown-thread-390.png`
- `Temp/task-messages-audit-repair-20260831/browser-evidence.json`

Live no-mock email screenshots remain under
`Temp/live-browser-email-20260830/after/`, including desktop and mobile HTML,
plain-text, CID and no-image cases.

## Regression and remaining risk

The changed files are limited to `RichTextEditor`, `InboxReplyComposer`,
`ThreadList`, `threadStatus` and the frontend audit test. No mail transport,
API, database, queue or request-link code was changed. Outgoing mail remained
disabled throughout.

Remaining items are outside this repair: eight non-blocking lint warnings, the
missing legacy helper script, production/PostgreSQL/provider acceptance, and a
new live binary CID ingestion fixture. The broad worktree also contains
unrelated tracked and untracked changes that were preserved.

## Result

The three previously failing audit groups are locally repaired and verified.
This is not a claim that every historical or production check in the project
is complete; the limitations above remain explicit.
