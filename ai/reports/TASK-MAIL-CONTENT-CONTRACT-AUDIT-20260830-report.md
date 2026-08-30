# TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830

Дата аудита UTC: `2026-08-30T18:56:25Z`
Режим: `AUDIT ONLY`

## STATUS

`COMPLETE — PARTIALLY CONFIRMED`

## REPOSITORY

- Repository: `edwatikhedwa-tech/supplydesk`
- Branch: `codex/TASK-STATE-CONTROL-20260830`
- HEAD at audit start: `602d7c42df6269513c9dc112ace90b19d8f9082a`
- Upstream: `origin/codex/TASK-STATE-CONTROL-20260830`
- Remote branch SHA at audit: `602d7c42df6269513c9dc112ace90b19d8f9082a`
- GitHub visibility: `PRIVATE`
- Worktree: `56` unrelated untracked porcelain entries; `0` tracked modifications; `0` staged entries.

## BUG VERDICT

`PARTIALLY CONFIRMED`.

The reported rich-text defect is confirmed for the existing single/thread
composer. It is not present as an HTML-editor defect in the bulk composer or
the unmatched-inbox reply composer because both of those inputs are plain
textareas. The application-wide outbound content contract is therefore mixed
and implicit, not consistently defined.

## CURRENT CONTENT CONTRACT

| Flow | UI input | API field | Backend treatment | Durable representation | Result |
|---|---|---|---|---|---|
| A. Bulk/new campaign | Plain `<textarea>` | `body: string` | `_render_outbound_target` treats it as plain text | `body_text` = input; `body_html` = escaped wrapper with `<br>` | Correct for plain input; MIME is multipart/alternative |
| B. Single/thread outbound | `contentEditable`; toolbar creates HTML; sends `innerHTML` | `body: string` | Same plain-text renderer; no content mode | Raw HTML is stored in `body_text`; `body_html` is escaped markup inside `<p>` | BUG: HTML is shown/sent as literal text |
| C. Unmatched-inbox reply | Plain `<textarea>` | `body: string` | `reply_to_inbox` treats it as plain text | `mail_inbox_replies.body_text` = input; `body_html` = escaped wrapper with `<br>` | Correct for plain input; one synchronous provider call |
| D. Campaign continuation | No new body input | Frozen operation target | Uses the stored frozen subject/body snapshot; falls back to escaped HTML from frozen text | `frozen_body_text` and `frozen_body_html` are copied into new targets/messages | Implicit; preserves the source snapshot, including a previously wrong snapshot |

The provider then builds `multipart/alternative` with a `text/plain` part and a
`text/html` part. That transport shape is not an explicit authoring contract:
the API has one generic `body` string and no `content_format`/separate HTML
field. `workspace_mail_templates` also stores only `body_text`.

## ROOT CAUSE

`frontend/src/components/mail/Composer.tsx` uses a rich `contentEditable` and
sends `editorRef.current.innerHTML` as `body`. The backend routes
`/api/mail/send` and `/api/mail/send-bulk` accept only that one string. In
`mail/service.py`, `_render_outbound_target` unconditionally sets
`body_text = personalized_body` and derives
`body_html = <p>{escape(body_text)}</p>`. Consequently, for
`<p>Hello <strong>world</strong></p>` the durable fields become:

```text
body_text: <p>Hello <strong>world</strong></p>
body_html: <p>&lt;p&gt;Hello &lt;strong&gt;world&lt;/strong&gt;&lt;/p&gt;</p>
```

The MIME builder correctly transports those fields; it cannot restore the
lost distinction. This is an HTML-as-plain-text contract mismatch, not a
provider MIME serialization defect.

## BULK FLOW

1. `frontend/src/components/Composer.tsx` keeps `body` in a textarea and sends
   it to `preflightBulk` and then `sendMailBulk`.
2. `supplier_app.py` reads the string from JSON and calls
   `MailService.preflight_bulk`/`queue_bulk`.
3. `queue_bulk` renders one target per eligible recipient and stores both
   fields in `mail_messages` and `mail_send_operation_targets`.
4. The worker later reconstructs `OutgoingMessage`; the provider builds the
   MIME message. Queueing itself made `0` provider calls in the isolated bulk
   probe; the fake SMTP MIME probe returned `post_data/250`.

Isolated bulk probe: two recipients produced exactly two queued message rows,
two operation-target rows, and zero fake-provider send calls before a worker
was invoked. Plain input `Hello <world> & test` remained literal in
`text/plain`, while the HTML alternative contained the escaped
`&lt;world&gt;`/`&amp;` form.

## REPLY FLOW

There are two distinct UI paths:

- A reply from an existing request thread uses the rich
  `frontend/src/components/mail/Composer.tsx` and calls `/api/mail/send`; it
  is the confirmed affected single/thread flow.
- A reply to an unmatched inbox message uses
  `frontend/src/components/mail/InboxReplyComposer.tsx`, a textarea, and calls
  `/api/mail/inbox/reply`. `MailService.reply_to_inbox` validates plain text,
  records `mail_inbox_replies`, then sends one `OutgoingMessage` synchronously.

The isolated unmatched-inbox test created one reply row, one provider call,
and one `multipart/alternative` message. Its `<literal> & text` remained
literal in `text/plain` and was escaped only in the HTML alternative. No
automatic second message was created.

## MIME RESULT

All mock-SMTP payloads were parsed after the provider's SMTP serialization.
For each tested outbound message:

- outer type: `multipart/alternative`;
- alternatives: `text/plain` and `text/html`;
- charset: `utf-8` on both parts;
- transfer encoding: `7bit` for ASCII cases, `8bit` for Cyrillic cases, and
  `quoted-printable` for the unsafe-markup ASCII case in the exercised Python
  email policy;
- fake SMTP response: `post_data`, code `250`.

The tested cases were:

1. `Hello <world> & test`: plain part is literal; HTML part is escaped.
2. `<p>Hello <strong>world</strong></p>`: both stored/plain and MIME text
   parts contain markup as text; HTML alternative contains escaped markup.
3. `<a href="https://example.com">Example</a>`: link is not a live HTML link;
   it is escaped text in the HTML alternative.
4. Script, `img onerror`, and `javascript:` URL: no executable HTML is put in
   the current HTML alternative because the backend escapes the whole input,
   but no outbound allowlist sanitizer is invoked.
5. Cyrillic text: round-tripped through UTF-8 MIME parts.
6. Single and double newlines: plain newlines are preserved; HTML uses one
   `<br>` per newline, including `<br><br>` for a blank line.

## SANITIZATION RESULT

`sanitize_email_html` is used on incoming/stored HTML when repository data is
prepared for reader display. Static call-site inspection found no call to it in
the outbound renderer, outbound queue, inbox-reply renderer, or MIME builder.
The current outbound safety effect for unsafe rich input is incidental HTML
escaping, not an explicit HTML sanitization policy. If rich HTML is supported
later, the backend must sanitize before MIME construction and must not rely on
the current plain-text escape path.

## STORAGE RESULT

The schema has `body_text` and `body_html` in `mail_messages`,
`mail_inbox_replies`, and frozen operation targets. It has no stored format
marker. The bulk probe showed both target and message rows receive the exact
same derived representations. For the affected rich single flow, the
original authored HTML format is not preserved as HTML: it is placed into
`body_text`, while `body_html` is a derived escaped string. No live database
was opened or changed; all storage probes used temporary SQLite files that
were removed automatically.

## TEST COVERAGE

Passed checks:

- `python -m unittest tests.test_mail_smtp_evidence tests.test_mailru_mvp tests.test_mail_integration tests.test_mail_deliverability tests.test_mail_status_semantics` — `171` tests, `OK`, `101.782s`.
- `python -m unittest tests.test_mail_pacing.MailPacingAcceptanceTests.test_provider_switch_dry_run_is_provider_neutral_and_repeatable` — `1` test, `OK`.
- Inline isolated temporary-SQLite/mock-provider probe — bulk queue, six content cases, inbox reply storage/provider/MIME assertions — `OK`.
- `npm --prefix frontend run typecheck` — `PASS`.
- `npm --prefix frontend run build` — `PASS`; Vite emitted only the existing chunk-size warning (>500 kB).

Existing coverage confirms inbound HTML allowlisting, MIME phase handling,
bulk snapshot equality, campaign status behavior, and unmatched-inbox reply
threading. It does not contain a regression test that starts at the rich
single Composer payload and asserts the final MIME HTML part. It also does
not contain an outbound sanitizer test. A pre-MIME payload assertion alone
would not be sufficient for this defect.

The repository helper paths `tests/run-tests.ps1` and `scripts/doctor.ps1` are
absent, so those specific checks are `NOT VERIFIED` and were not created.

## FILES INSPECTED

- `frontend/src/components/Composer.tsx`
- `frontend/src/components/mail/Composer.tsx`
- `frontend/src/components/mail/InboxReplyComposer.tsx`
- `frontend/src/pages/Messages.tsx`
- `frontend/src/pages/CampaignPage.tsx`
- `frontend/src/lib/api.ts`
- `supplier_app.py`
- `mail/service.py`
- `mail/repository.py`
- `mail/content.py`
- `mail/providers/yandex.py`
- `mail/providers/base.py`
- `mail/types.py`
- `migrations/001_mail_integration.sql`
- `migrations/006_inbox_reply.sql`
- `migrations/020_search_depth_and_mail_template.sql`
- `migrations/022_outgoing_mail_integrity.sql`
- relevant files under `tests/test_mail_integration.py`,
  `tests/test_mailru_mvp.py`, `tests/test_mail_smtp_evidence.py`,
  `tests/test_mail_deliverability.py`, `tests/test_mail_status_semantics.py`,
  and `tests/test_mail_pacing.py`.

## FILES CHANGED

- Product files changed: `NO`.
- Frontend/backend/migrations/tests changed: `NO`.
- Database schema or live database changed: `NO`.
- Allowed state/report files under `ai/**`: `YES`.

## DATABASE IMPACT

`NONE` for the live database. Temporary SQLite fixtures were created for
isolated tests and removed on process exit. No migration was run against a
live database.

## MAIL IMPACT

`NO LIVE SEND` and `NO LIVE SMTP/IMAP`. The mock-SMTP transport was called only
with synthetic recipients and synthetic tokens in an isolated process to
capture the serialized MIME payload.

## NEXT STEP

Do not fix in this audit. A product decision is required before implementation:

1. **Plain-text contract (smallest change):** make every composer submit plain
   text, remove/disable rich HTML authoring, and keep the current derived HTML
   alternative. This unifies A/B/C and requires no schema change.
2. **Explicit rich contract:** add an explicit content mode and separate
   `body_text`/`body_html` payload semantics, sanitize HTML server-side, derive
   a text alternative from sanitized HTML, and preserve the explicit pair in
   queue/reply/continuation snapshots. Existing storage columns are sufficient,
   but API, frontend, service and regression coverage must change.

Minimal implementation design if option 2 is chosen: change the rich composer
and API contract, validate/sanitize and normalize in `mail/service.py`, use the
existing `body_text`/`body_html` fields and snapshot columns, and add a final
fake-transport MIME regression matrix for bulk, single/thread, inbox reply and
continuation. Non-goals are provider changes, identity merging, resend/status
UI, migrations unless a later design proves a format marker is required, and
real SMTP/IMAP acceptance.

## RECOMMENDED ACTION

`DO NOT APPLY` — there is no database or supplier-identity apply operation in
this task. Do not implement the mail fix until the multi-format business
decision is recorded.

## INSTRUCTION CHECK

- Audit-only mode respected: `YES`.
- Product code changed: `NO`.
- Database changed: `NO` (temporary fixtures only).
- Real SMTP/IMAP or real email: `NO`.
- Supplier merge / supplier identity apply: `NO`.
- Resend protection/status UI changes: `NO`.
- `ai/**` report/state updates: `YES`.
- `Push`: `NOT RUN`.
