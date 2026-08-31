# Active Task

## Current task — idle after messages primary correspondence filter

Task ID: `NONE`
Agent: `Codex`
Mode: `CLOSE`
Started: `2026-08-31`
Scope: `show only sent/replied correspondence by default on /messages and keep pending outgoing mail in the queue`
Non-goals: `no API, database, queue, delivery, sending, request-link or other SupplyDesk behavior changes`
Status: `IDLE — TASK-MESSAGES-PRIMARY-FILTER-20260831 completed locally`
Last update: `2026-08-31T18:38:35Z`

## Latest completed task — messages primary correspondence filter

Task ID: `TASK-MESSAGES-PRIMARY-FILTER-20260831`
Mode: `IMPLEMENT → VERIFY → CLOSE`
Status: `COMPLETE LOCALLY — real browser checks passed; outgoing remained OFF`

- `/messages` теперь по умолчанию показывает только треды с отправленным
  исходящим письмом или ответом поставщика. Очередь остаётся отдельной вкладкой.
- Поле поиска и счётчик применяются к этому основному набору; пустое состояние
  объясняет, что отправленных писем или ответов пока нет.
- Скрытые из основного списка delivery-error треды по-прежнему доступны через
  прямое открытие из карточки поставщика, где остаются действия проверки и
  повторной отправки.
- Проверка реального локального runtime: correspondence `80`, основной список
  `77`, queue `64`; на `1440x900` и `390x844` горизонтального переполнения нет.
- Проверены `npm run typecheck`, `npm run lint`, `npm run build`; lint дал `0`
  ошибок и `8` существующих предупреждений в других компонентах.
- Route-mocked regression: final focused `2/2`, delivery-unknown desktop
  regression `1/1`; initial full viewport run for the new visibility case `8/8`.
- Реальный no-route-mock браузер: `2/2` viewport checks, `0` console errors,
  `0` page errors, `0` failed requests и `0` unexpected non-2xx API responses.
- API unknown-route check вернул ожидаемый `404`; отправка наружу не запускалась,
  outgoing switch остался выключен.
- Screenshots and JSON evidence: `Temp/messages-primary-filter-20260831/`.
- Report: `ai/reports/TASK-MESSAGES-PRIMARY-FILTER-20260831-report.md`.

## Latest completed task — CID image height fix

Task ID: `TASK-MESSAGES-CID-HEIGHT-FIX-20260831`
Mode: `IMPLEMENT → VERIFY`
Status: `COMPLETE LOCALLY — targeted browser and regression checks passed`

- Исправлена обрезка быстрого встроенного CID-изображения в iframe письма.
- Проверены реальные локальные MIME-данные, браузерные размеры и отсутствие
  внешних запросов на `390`, `1024`, `1440` и `1640` пикселях.
- Полный live no-route-mock прогон после исправления не подтверждён из-за двух
  тайм-аутов по 3 минуты; это не выдано за PASS.
- Report: `ai/reports/TASK-MESSAGES-CID-HEIGHT-FIX-20260831-report.md`.

Task ID: `TASK-FRONTEND-MAILRU-CONTINUATION-20260831`
Agent: `Codex`
Mode: `IMPLEMENT → VERIFY → CONTROLLED SEND → CLOSE`
Started: `2026-08-31`
Scope: `apply frontend audit fixes, verify the local runtime, reconcile request 1059 Mail.ru continuation recipients, and send only explicitly confirmed untouched Mail.ru jobs`
Non-goals: `no Yandex sending, no duplicate recipients, no direct SQL-created jobs, no credential changes, no automatic retry of uncertain delivery`
Status: `COMPLETE LOCALLY — two exact Mail.ru jobs sent once and verified; outgoing OFF`
Last update: `2026-08-31T18:08:46Z`

## Current evidence

- Frontend typecheck, build and lint passed; lint has `0` errors and `8`
  pre-existing warnings outside this task.
- Full visual audit passed `80/80` across desktop, tablet and mobile. Live
  browser checks confirmed the reply dialog role, editor focus, close action,
  touch target and no horizontal overflow at `390x844` and `1440x900`.
- Local HTTP smoke passed on `127.0.0.1:8001` with outgoing forced OFF:
  root `200`, `/api/auth/me` `200`, protected API `401`, unknown API `404`,
  and hashed assets returned gzip plus immutable cache headers.
- Targeted mail safety tests passed `230/230` with one expected skip. Full
  discovery remains blocked by the system `lxml` DLL/parser environment and
  one pre-existing `quotequail` folding assertion; no current task file is
  implicated.
- Canonical preflight identified only jobs `173`/`191` and `174`/`192` as the
  untouched Mail.ru continuation. The old Yandex jobs for the same addresses
  were cancelled and had zero attempts; they were not sent.
- After the owner's exact-list confirmation, job `173` and job `174` were
  processed one at a time by the штатная queue with a per-job runtime limit.
  Both ended `sent` with one `accepted` attempt, SMTP `post_data / 250`, and
  saved sent copies.
- Durable outgoing was switched OFF immediately after the second acceptance.
  The old Yandex queue stayed at `64` queued jobs; the uncertain Unicode-domain
  message was not retried and no new jobs/messages were created.

Task ID: `NONE`
Agent: `Codex`
Mode: `CLOSE`
Started: `2026-08-31`
Scope: `TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831 completed locally: verify real /messages link, reload, unlink and mobile flows`
Non-goals: `no SMTP/IMAP, no sending, no queue or database changes, no unrelated application cleanup`
Status: `IDLE — TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831 completed locally; no active task`
Last update: `2026-08-31T16:45:33Z`

## Latest completed task — real-data messages acceptance

- 8/8 no-route-mock browser checks passed against real local data.
- Manual link, persistence after reload and unlink were verified and the
  original state was restored. Mobile link dialog and queue had no horizontal
  overflow.
- Outgoing remained disabled; no application code or permanent business data
  changed. Real binary CID content was not available for a production-like
  check.
- Report: `ai/reports/TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831-report.md`.

## Paused previous active task

Task ID: `TASK-PROJECT-RECOVERY-20260831`
Agent: `Codex`
Mode: `PRESERVE → BOOTSTRAP → SMOKE → CONTROLLED SEND`
Started: `2026-08-31`
Scope: `restore a reproducible project runtime, verify the server with outgoing OFF, then continue only untouched request-1059 supplier contacts through Mail.ru account 23`
Non-goals: `no destructive cleanup, no Yandex sending, no duplicate recipients, no direct SQL-created mail jobs, no credential changes, no campaign-state changes, no automatic retry`
Status: `PAUSED BY OWNER — outgoing remains OFF; no Mail.ru continuation in this task`
Last update: `2026-08-31`

The owner explicitly authorized continuation through the existing Mail.ru flow
and requested safe project recovery plus future cleanup documentation.
The canonical database preflight confirmed account `23` (`edwatik@mail.ru`)
is connected and has historical Mail.ru SMTP `250` acceptance evidence. The
only currently queued Mail.ru continuation jobs are `173`/`191` for supplier
`2855` (`support@prometall.ru`) and `174`/`192` for supplier `2875`
(`89087178701@mail.ru`). Outgoing is durably disabled.

The project now has read-only `scripts/doctor.ps1`, explicit-mode
`scripts/bootstrap_supplydesk.ps1`, and `scripts/recover_supplydesk.ps1`.
The direct system Python has all declared imports available, so
`supplier_app.py` is currently running as PID `23584` on
`http://127.0.0.1:8000/` with `MAIL_OUTGOING_DISABLED=1`. Root and API smoke
checks passed. The recovery script itself still requires `.venv`, so the
reproducible bootstrap path remains incomplete. No SMTP login or DATA command
was attempted.

The cleanup phase is intentionally deferred. No files were deleted or moved;
the dirty worktree must first be inventoried and checkpointed in a writable
Git environment.

The owner requested immediate execution again. The server startup portion is
now complete in the current environment; outgoing remains OFF. Mail.ru
continuation, SMTP authentication and SMTP DATA remain unattempted.

The remaining recovery work is to establish the documented `.venv` bootstrap
and separately review the bounded Mail.ru continuation. The current working
tree remains dirty and no cleanup was performed.

## Previous task context — Mail.ru remaining continuation

Task ID: `TASK-MAILRU-REMAINING-CONTINUATION-20260831`
Status: `BLOCKED — штатный сервер не стартует в текущем окружении; outgoing remains OFF`

## Previous task context — IDN pre-DATA fix and continuation safety

Task ID: `TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831`
Agent: `Codex`
Mode: `IMPLEMENT → RECONCILE → VERIFY`
Started: `2026-08-31`
Scope: `fix pre-DATA Unicode/IDN handling and recipient-scoped continuation deduplication; reconcile only the proven Mail.ru pre-DATA failure for job 172`
Allowed files: `mail/providers/yandex.py, mail/service.py, mail/repository.py, tests/**, ai/**, canonical DB row job 172/message 190 only`
Status: `COMPLETE LOCALLY — outgoing remains OFF; live provider transport is unavailable in this execution environment`
Last update: `2026-08-31T14:03:03Z`

Owner explicitly asked to stop the previous loop and finish the underlying
problem. The implementation scope therefore expands from the earlier
read-only verification to the narrow code/data fix described below; no live
send, reauthorization, account reconnect, campaign-state change or credential
change is allowed.

The root cause is confirmed in canonical SQLite: Mail.ru job `172` / message
`190` targets `info@печнойцентр73.рф`, and the previous SMTP path marked the
durable irreversible stage before MIME/envelope preparation. Python then raised
`UnicodeEncodeError` while serializing the non-ASCII SMTP envelope, with no SMTP
code, provider response or DATA evidence. This incorrectly became
`delivery_unknown`.

The code fix moves the durable gate to the provider callback immediately before
SMTP DATA and converts only the SMTP envelope domain to IDNA ASCII. Header
content remains human-readable. Recipient-scoped continuation checks are kept
independent of supplier identity and block the same normalized mailbox across
providers.

The proven job `172` / message `190` was reconciled transactionally to
`failed`/`failed` with `delivery_state=not_sent`; the historical attempt 70 and
its evidence were not rewritten. Yandex job `20` / message `28` remains
`delivery_unknown` because its external delivery is not proven either way.

Canonical DB checks after the change: SQLite integrity `ok`, outgoing `0`, no
active pacing reservations, campaign `2` still `paused_for_health`, and no
pending duplicate recipient groups in request `1059`. A database backup was
created at `mail-data/backups/supplier.sqlite3.pre-idn-reconcile-20260831-165009.bak`.

The full evidence is recorded in
`ai/reports/TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831-report.md`.

The earlier read-only IMAP verification remains historical evidence: external
TCP was blocked by this execution environment, so provider-side Sent-copy
lookups remain unavailable. That limitation does not block the local IDN fix
or the strict reconciliation above. Git commit/push still require a separate
permission fix because `.git/index.lock` cannot be created here.
