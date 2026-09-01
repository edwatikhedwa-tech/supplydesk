# Current State

## Current task update — canonical control baseline

- Date: `2026-09-01` (`TASK-CANONICAL-CONTROL-BASELINE-20260901`).
- A controlled worktree was created from audit commit
  `b5a454f9b39f3cbf01d640d5b67e4231ca25733a` on branch
  `control/canonical-baseline-20260901`; the source checkout remains at
  `c076e1be385c3ae6da2716159e1f46fc2fce23d7` and was not modified by this task.
- `PROJECT_MANIFEST.yaml` is the reconciled runtime manifest. This file remains
  the only current-state source; `ai/baselines/**` and the dated task report
  are evidence for the baseline, not a second state system.
- The selective ledger reduced project-owned unknowns from `62` to `3`; review,
  backup, generated, vendor, secret-local, runtime and real-mail data remain
  outside the canonical working set.
- Control evidence: backend `373 passed, 1 skipped`, frontend install/typecheck/
  build passed, lint had 8 warnings, and the public shell Playwright matrix was
  `8 passed`. Published audit evidence remains `18/18` live routes; no real
  email was sent.
- Report: `ai/reports/TASK-CANONICAL-CONTROL-BASELINE-20260901-report.md`.

## Current task update — canonical documentation and freshness rule

- Timestamp UTC: `2026-09-01T07:29:32Z`
  (`TASK-DOCS-CANONICAL-20260901`, completed locally).
- `ai/CURRENT_STATE.md` is explicitly established as the only current-state
  source. A new `docs/DOCUMENTATION_POLICY.md` defines mandatory same-task
  updates, evidence labels, historical markers, link/secret/state validation and
  rollback.
- `docs/CURRENT_STATE.md`, `docs/DECISIONS.md` and the dated
  `Documents/28-8/` catalog are marked as supporting or historical
  material; they link back to the canonical state instead of competing with it.
- Root `AGENTS.md`, `ai/AI_CONTRACT.md`, `ai/WORKFLOW.md`, `docs/ENGINEERING_CONTRACT.md`
  and `ai/DECISIONS.md` now carry the same documentation-freshness rule.
- Application code, frontend, API, database, migrations, mail settings,
  deployment configuration and external services remain unchanged.
- Acceptance passed: 116 relative Markdown links checked, secret-pattern scan
  passed, `python ai/tools/validate_state.py` passed and `git diff --check`
  passed. Report: `ai/reports/TASK-DOCS-CANONICAL-20260901-report.md`.

## Current task update — аудит системы и фронтенда

- Timestamp UTC: `2026-09-01T07:11:12Z`
  (`TASK-SYSTEM-FRONT-AUDIT-20260901`, completed locally).
- Read-only SQLite for request `1059` currently contains `171` relevant supplier
  links and outbound statuses `sent=125`, `failed=4`, `delivery_unknown=2`,
  `cancelled=82`, `queued=0`; durable outgoing switch is `0` (sending disabled).
- Confirmed documentation drift: older `docs/**`/`Documents/28-8/**` still show
  `sent=62`, `queued=84`, `failed=2`, `delivery_unknown=1`, old supplier totals,
  Yandex-only claims and deferred UI/live-SMTP statements that conflict with
  current code, DB and newer state records.
- Frontend checks: typecheck/build/route-mocked visual suite pass; lint passes
  with 8 warnings; Storybook build passes but visual suite is `3 passed, 4
  failed`; axe found a serious contrast issue in the matched reply composer.
- Full backend unittest is not reproducible in the current environment because
  bundled/system Python cannot import `nh3` and `requests`; this supersedes no
  historical pass claim and is recorded as an audit limitation.
- No application code, API, DB rows, migrations, mail settings or external
  services were changed. Report: `ai/reports/TASK-SYSTEM-FRONT-AUDIT-20260901-report.md`.

## Current task update — понятная проверка правил

- Timestamp UTC: `2026-09-01T06:38:31Z`
  (`TASK-INSTRUCTION-CHECK-UX-20260901`, completed locally).
- The final response check now uses the Russian heading
  `[ПРОВЕРКА ПРАВИЛ]` and requires one actual value per line with a short
  explanation. The old slash-separated English template is no longer the
  required output format.
- Updated the rule sources `AGENTS.md` and `ai/AI_CONTRACT.md`, plus the
  required state/report chronology; application code, frontend, API, database,
  mail, runtime settings and existing unrelated worktree files were not
  changed.
- Backups of both instruction files were saved before editing at
  `C:\Users\edwat\AppData\Local\Temp\supplydesk-instructions-backup-20260901\`.
- The state validator, relevant source search, HTTP smoke and final diff are
  the acceptance evidence for this documentation task.
- Report: `ai/reports/TASK-INSTRUCTION-CHECK-UX-20260901-report.md`.

## Current task update — historical mail queue reconciled

- Timestamp UTC: `2026-09-01T06:13:09Z`
  (`TASK-MAIL-STATUS-RECONCILIATION-20260901`, completed locally).
- Request `1059` has no queued mail jobs. Historical jobs `49` and `54` are
  now `delivery_unknown`; job `71` is cancelled and its target is marked
  `reconciled` because the exact address already has durable Mail.ru
  acceptance evidence.
- The reconciliation path is evidence-gated, allowlisted and idempotent. Its
  Plan, DryRun, Apply and repeated DryRun all reported `safe=true`,
  `smtp_calls=0`; outgoing stayed durably and process-level OFF.
- A consistent SQLite backup was created at
  `mail-data/backups/supplier.sqlite3.pre-status-reconcile-20260901-060602.bak`.
- Current request history has `125` sent rows for `125` distinct normalized
  recipients, duplicate sent recipients `0` and duplicate accepted-attempt
  recipients `0`.
- Final Mail.ru continuation check: `eligible_untouched=0`, `would_create=0`,
  `queued_in_current_campaign=0`. No remaining safe supplier send exists.
- Reconciled acceptances now participate in request mail facts. Grouped cards
  label counts as contacts, so `Отправлено · 4 контакта` cannot be mistaken
  for four repeats to one address.
- Live UI passed desktop `1640x900`, tablet `768x1024` and mobile `390x844`
  screenshot review with no clipping, overlap or horizontal overflow. The
  automated status regression passed all eight configured viewports.
- Full backend discovery passed `374` tests with one expected PostgreSQL skip;
  the focused mail suites and frontend typecheck/build/lint also passed.
- Server is running at `http://127.0.0.1:8000/`, PID `16704`, with
  `MAIL_OUTGOING_DISABLED=1`; HTTP/API smoke returned `200/401/404` as
  expected and authenticated request API returned `200`.
- Report:
  `ai/reports/TASK-MAIL-STATUS-RECONCILIATION-20260901-report.md`.

## Current task update — final Mail.ru continuation completed

- Timestamp UTC: `2026-09-01T05:43:31Z`
  (`TASK-MAILRU-FINAL-CONTINUATION-20260831`, completed).
- The continuation created `61` Mail.ru jobs from a fresh strictly-untouched
  selection: `60` ended with explicit SMTP `post_data / 250` acceptance and
  one ended as a permanent `rcpt_to / 550` invalid-recipient failure before
  the irreversible stage. There are no delivery-unknown outcomes in this run.
- Final safety proof: `eligible_untouched=0`, `would_create=0`, no duplicate
  sent recipient, no recipient with multiple accepted attempts, SQLite
  integrity `ok`, and active send reservations `0`.
- The mixed status screenshot is explained by the company-card aggregation:
  four distinct contacts were grouped together while three were accepted and
  one was awaiting a safe retry after a pre-DATA connection failure. The same
  live row now shows `Отправлено · 4` and no queued badge.
- Three older Yandex jobs still appear in aggregate queue counts. Two are
  historical disputed irreversible transients and must not be blindly retried;
  the third recipient has a reconciled Mail.ru acceptance and must not be sent
  again. Current continuation correctly excludes all three.
- The server is running at `http://127.0.0.1:8000/` with process-level and
  durable outgoing disabled. Root returned `200`, protected API without a
  session returned `401`, and an unknown API returned `404`.
- Consistent pre-send backup:
  `mail-data/backups/supplier.sqlite3.pre-mailru-final-20260831-215700.bak`.
- Report: `ai/reports/TASK-MAILRU-FINAL-CONTINUATION-20260831-report.md`.

## Current task update — messages primary correspondence filter

- Timestamp UTC: `2026-08-31T18:38:35Z`
  (`TASK-MESSAGES-PRIMARY-FILTER-20260831`, completed locally).
- `/messages` по умолчанию фильтрует основной список: остаются письма со
  статусом `sent` или с ответом поставщика; письма, которые ещё находятся в
  очереди, не смешиваются с перепиской и показываются во вкладке `Очередь`.
- Фильтр не меняет API или данные: при текущем read-only снимке
  `/api/correspondence` вернул `80` тредов, из них `77` попали в основной UI;
  `/api/mail/queue/messages` вернул `64` очереди.
- Реальный браузер без route-моков проверен на `1440x900` и `390x844`:
  выбранный режим остаётся основным после reload, queue sample открывается во
  вкладке очереди, горизонтального overflow нет.
- Browser runtime: `0` console errors, `0` page errors, `0` failed requests,
  `0` unexpected non-2xx responses; неизвестный API route ожидаемо вернул
  `404`.
- Typecheck and build passed. Lint passed with `0` errors and `8` pre-existing
  warnings outside this change. Outgoing remained disabled; SMTP/IMAP were not
  started.
- Changed application files: `frontend/src/components/mail/ThreadList.tsx`
  and `frontend/src/components/mail/threadStatus.ts`. Regression coverage:
  `frontend/tests/frontend-audit.spec.ts`.
- Evidence: `Temp/messages-primary-filter-20260831/`; report:
  `ai/reports/TASK-MESSAGES-PRIMARY-FILTER-20260831-report.md`.

## Current task update — local server started with outgoing OFF

- Timestamp UTC: `2026-08-31T18:28:01Z` (`TASK-SERVER-START-20260831`).
- SupplyDesk запущен на `http://127.0.0.1:8000/`; процесс оставлен работающим.
- Процессный аварийный выключатель `MAIL_OUTGOING_DISABLED=1`, durable
  `mail_runtime_controls.outgoing_enabled=0`; очередь писем не отправляется.
- Smoke-проверка: главная страница `200`, `/api/auth/me` `200`, защищённый
  `/api/requests` без сессии `401`, неизвестный API `404`.

## Latest task update — exact Mail.ru continuation sent and closed

- Timestamp UTC: `2026-08-31T18:08:46Z`
  (`TASK-FRONTEND-MAILRU-CONTINUATION-20260831`).
- After exact-list confirmation, only existing jobs `173`/`191`
  (`support@prometall.ru`) and `174`/`192` (`89087178701@mail.ru`) were
  processed through the штатная queue, one at a time.
- Both provider attempts were `accepted` with `smtp_stage=post_data`,
  `smtp_code=250`, one attempt per job, and `copy_status=saved`. Both message
  and job statuses are `sent`.
- Exact-recipient history contains one cancelled Yandex record with zero
  attempts plus one accepted Mail.ru record for each address. No duplicate
  Mail.ru message was created. Yandex's old queue remains `64` queued jobs.
- Durable outgoing was returned to `0` / OFF; active reservations are `0`,
  SQLite integrity check is `ok`, and the send-only local processes are stopped.

## Latest task update — CID image height fix

- Timestamp UTC: `2026-08-31` (`TASK-MESSAGES-CID-HEIGHT-FIX-20260831`).
- Fixed a race in `EmailRenderer` where a fast inline CID image could be
  marked complete before the height listener was attached, leaving the mail
  iframe at roughly `24px` and visually clipping the message.
- Added a local MIME-derived CID acceptance fixture, a Storybook scenario and
  a responsive Playwright regression covering `390`, `1024`, `1440` and
  `1640` pixels. All targeted CID checks passed after the fix; no external
  requests were observed and the fixture was removed after verification.
- Typecheck, lint, build and the three-case Storybook responsive suite passed.
  The full live no-route-mock suite remains unverified because two attempts
  reached its 3-minute timeout while waiting for a row or taking a screenshot.
- Report: `ai/reports/TASK-MESSAGES-CID-HEIGHT-FIX-20260831-report.md`.

## Latest task update — frontend fixes and Mail.ru continuation hold

- Timestamp UTC: `2026-08-31T17:52:01Z`
  (`TASK-FRONTEND-MAILRU-CONTINUATION-20260831`).
- Committed the frontend audit fixes in `568391d`: accessible/focus-trapped
  reply dialogs, mobile drawer isolation, filter/search semantics, supplier
  selection labels, route-level lazy loading, local font fallback and static
  asset gzip/immutable caching. Only task files were staged; unrelated dirty
  worktree files remain unstaged.
- Verified typecheck, build, lint, `80/80` visual scenarios, live browser
  screenshots at `390x844` and `1440x900`, targeted mail safety tests `230/230`,
  doctor DryRun and HTTP smoke on port `8001` with outgoing OFF.
- Canonical read-only reconciliation for request `1059` found exactly two
  queued Mail.ru jobs with zero attempts and no sent history:
  `support@prometall.ru` (supplier `2855`, job `173`, message `191`) and
  `89087178701@mail.ru` (supplier `2875`, job `174`, message `192`). No other
  recipients are eligible for this continuation; Yandex queued work remains
  untouched. The uncertain Unicode-domain result is excluded from retry.
- Actual Mail.ru sending is paused pending action-time confirmation of those
  exact two recipients. Durable outgoing remains `0` / OFF.

## Latest task update — real-data messages acceptance

- Timestamp UTC: `2026-08-31T16:45:33Z`
  (`TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831`).
- Completed an 8-check Playwright acceptance run against real local APIs on
  `/messages`, without route mocks. Manual link → reload persistence → unlink
  passed for real inbox message `30`; the original unmatched state was restored.
- Mobile link dialog and queue passed at `390x844` with no horizontal
  overflow. Browser runtime had `0` console errors, `0` page errors, `0` failed
  requests and `0` unexpected non-2xx responses.
- API snapshot: inbox `52`, correspondence `78`, queue `66`; outgoing runtime
  remained disabled (`false`/`false`).
- No application code changed in this task. Evidence and screenshots are in
  `Temp/real-data-acceptance-messages-20260831/`; report:
  `ai/reports/TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831-report.md`.
- A real binary CID email was not available in the inspected data, so that
  specific production-like scenario remains unverified.

## Latest task update — messages audit repair

- Timestamp UTC: `2026-08-31` (`TASK-MESSAGES-AUDIT-REPAIR-20260831`).
- Repaired the three confirmed frontend audit failures: reply-editor focus,
  default visibility of operational-attention correspondence groups, and the
  stale outbound metric assertion. Application mail transport, API contracts,
  queue, database and request-link behavior were not changed.
- Full route-mocked frontend audit passed `80/80` across eight viewport
  projects. Live no-mock email regression passed `1/1` for HTML, plain text,
  CID, remote images, no-image and long-mail cases at `390`, `1024`, `1440`
  and `1640` widths.
- Typecheck and build passed. Lint passed with `0` errors and `8` existing
  warnings in unrelated components. The local server remains on
  `127.0.0.1:8000`; `GET /messages` returned `200`.
- Fresh evidence is in `Temp/task-messages-audit-repair-20260831/`; live
  email evidence remains in `Temp/live-browser-email-20260830/after/`.
- Report: `ai/reports/TASK-MESSAGES-AUDIT-REPAIR-20260831-report.md`.

## Current task update — plain-language response rule

- Timestamp UTC: `2026-08-31` (`TASK-COMMUNICATION-RULE-20260831`).
- Added a shared response rule: explain substantial work in concise Russian
  using `Сделано`, `Проблемы и ограничения`, and `Следующий шаг`; explain
  technical terms and raw check results in ordinary language.
- Backups of `AGENTS.md` and `ai/AI_CONTRACT.md` are in
  `Temp/instructions-backup-20260831/`. Application code was not changed.
- Report: `ai/reports/TASK-COMMUNICATION-RULE-20260831-report.md`.

## Current task update — messages status filter

- Timestamp UTC: `2026-08-31` (`TASK-MESSAGES-STATUS-FILTER-20260831`).
- On `/messages`, the visible `Ожидает ответа` row badge was replaced by a
  top client-side filter; `Ответ получен` now uses a stronger accent-blue
  surface. No API, queue, delivery, request-link, or outbound behavior was
  changed.
- Real no-mock Playwright checks passed at `390`, `1024`, `1440`, and `1640`:
  filter isolation, keyboard activation, visible status color, and no page
  horizontal overflow. Live email regression passed `1/1`.
- The existing active recovery task remains unchanged; this UI task is
  recorded separately and does not replace its `ACTIVE_TASK` scope.
- Report: `ai/reports/TASK-MESSAGES-STATUS-FILTER-20260831-report.md`.

## Current task update — server started with outgoing disabled

- Timestamp UTC: `2026-08-31T15:01:57Z`
  (`TASK-PROJECT-RECOVERY-20260831`).
- The system Python `C:\Users\edwat\AppData\Local\Programs\Python\Python311\python.exe`
  is available and all declared requirement imports passed the doctor check.
- `supplier_app.py` is running as PID `23584` on `127.0.0.1:8000`, started
  with process-level `MAIL_OUTGOING_DISABLED=1`.
- Smoke checks passed: `/` → `200`, `/api/auth/me` → `200`, unauthenticated
  `/api/mail/inbox` → expected `401`, and an unknown API path → expected `404`.
- Read-only SQLite checks passed: `integrity_check=ok` and durable outgoing
  switch `0`. No SMTP authentication, SMTP DATA, queue, campaign, account or
  credential action was performed.
- The reproducible recovery script still requires `.venv`; this direct runtime
  start confirms the server is usable now but does not complete bootstrap.

## Current task update — safe project recovery

- Timestamp UTC: `2026-08-31T14:56:05Z`
  (`TASK-PROJECT-RECOVERY-20260831`).
- Added three non-destructive PowerShell tools: `scripts/doctor.ps1`,
  `scripts/bootstrap_supplydesk.ps1`, and `scripts/recover_supplydesk.ps1`.
  They support explicit `-Plan`, `-DryRun`, and `-Apply` modes; recovery starts
  the server only with `MAIL_OUTGOING_DISABLED=1` and requires HTTP `200`.
- PowerShell parsing and Plan/DryRun checks passed. Apply correctly stopped
  before creating `.venv` because `py.exe` reports no installed Python.
- No cleanup, deletion, file moves, database writes, campaign changes,
  credential changes or mail transport actions were performed.
- The project remains blocked on a usable normal Windows Python/runtime with
  declared dependencies. Once that runtime is available, bootstrap → doctor →
  recovery is the documented order; only then can the Mail.ru continuation be
  resumed.
- A fresh explicit bootstrap `-Apply` retry stopped before creating `.venv`
  because `py.exe` reports no installed Python. No server, SMTP auth or SMTP
  DATA was attempted.
- No local wheel cache or usable alternate runtime was found. The remaining
  recovery action requires the ordinary Windows runtime outside this isolated
  execution environment.

## Current task update — Mail.ru remaining continuation launch attempt

- Timestamp UTC: `2026-08-31T14:22:36Z`
  (`TASK-MAILRU-REMAINING-CONTINUATION-20260831`).
- Owner authorized continuing request `1059` only for companies without a
  previous outbound message, using Mail.ru account `23`.
- Canonical preflight: account `23` (`edwatik@mail.ru`) is `connected`; the
  latest durable outgoing flag is `0`; active reservations are `0`; SQLite
  integrity is `ok`; campaign `2` remains unchanged.
- Historical Mail.ru acceptance is present in the evidence table: `19`
  accepted attempts with SMTP stage `post_data` and code `250`.
- Current queued Mail.ru continuation jobs are `173`/`191` for supplier
  `2855` (`support@prometall.ru`) and `174`/`192` for supplier `2875`
  (`89087178701@mail.ru`).
- The standard launch attempt stopped before HTTP binding because the bundled
  Python lacks `nh3`. Installing `requirements.txt` could not reach PyPI
  because outbound TCP is denied by this execution environment
  (`WinError 10013`). No SMTP authentication or DATA command was attempted.
- Result: live continuation is blocked in this environment; outgoing remains
  OFF and no queue, campaign, account or credential state was changed.

## Current task update — IDN pre-DATA fix and continuation safety

- Timestamp UTC: `2026-08-31T14:03:03Z` (`TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831`).
- Root cause confirmed: Mail.ru `job 172` / `message 190` targeted the IDN
  recipient `info@печнойцентр73.рф`. The old service entered the durable
  irreversible marker before MIME/envelope preparation; `UnicodeEncodeError`
  then occurred with no SMTP code, provider response or DATA evidence, which
  incorrectly produced `delivery_unknown`.
- Code fix: `mail/service.py` now enters the durable gate through the provider
  callback immediately before SMTP DATA. `mail/providers/yandex.py` converts
  SMTP envelope domains to IDNA ASCII while preserving the readable message
  header. Mail.ru inherits this provider path.
- Continuation safety is recipient-scoped: normalized email checks span
  supplier identities and providers; duplicate emails within one continuation
  selection are rejected; prepared/accepted/history checks no longer rely only
  on `supplier_id`.
- Canonical DB backup created before the one-row reconciliation:
  `mail-data/backups/supplier.sqlite3.pre-idn-reconcile-20260831-165009.bak`.
- Strict evidence matched all conditions for `job 172`/`message 190`:
  account `23`, `uncertain`, `internal-uncertain`, `UnicodeEncodeError`, no
  SMTP code/response, no provider message ID, no sent timestamp and no active
  reservation. The row is now `failed`/`failed` with a `not_sent` resolution;
  historical attempt `70` and its evidence remain unchanged.
- Yandex `job 20`/`message 28` remains `delivery_unknown`; it was not retried
  or rewritten because its delivery result is not proven.
- Post-change canonical checks: SQLite integrity `ok`, outgoing `0`, no active
  reservations, campaign `2` still `paused_for_health` with unchanged pause
  reason/timestamp, and zero pending duplicate recipient groups in request
  `1059`. Existing duplicate rows are cancelled-vs-sent history, not two
  accepted rows; `s-kl@yandex.ru` has one outbound row.
- No SMTP DATA, live send, account reconnect, credential change, cursor change
  or campaign-state change was performed.
- `py_compile` passed for changed source and tests. Full unittest execution is
  unavailable because the bundled runtime lacks `nh3` (and `bs4`/`quotequail`);
  this is disclosed rather than inferred away.
- Isolated provider smoke passed for the real IDN envelope conversion. The
  reconciliation method passed both apply and repeat/idempotency smoke tests
  against disposable copies of the canonical database.
- Report: `ai/reports/TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831-report.md`.
- Scoped Git commit was attempted but blocked by permission denied creating
  `.git/index.lock`; no paths were staged and no push was run.

## Current task update — delivery-unknown read-only verification

- Timestamp UTC: `2026-08-31T13:25:18Z` (`TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831`).
- Canonical SQLite was opened read-only and still contains exactly two
  `delivery_unknown` rows: Yandex account `1`, job `20`/message `28`; and
  Mail.ru account `23`, job `172`/message `190`.
- Both account-specific encrypted credentials decrypted successfully in
  memory. Yandex has access and refresh token ciphertexts; its stored expiry
  is in the future, so no OAuth refresh was attempted. Mail.ru has its own app
  password ciphertext.
- Read-only IMAP checks used the project endpoints `imap.yandex.com:993` and
  `imap.mail.ru:993` with SSL. Both TCP connects failed before authentication
  with local Windows `WinError 10013` / `PermissionError`; Sent-copy presence
  is therefore unverified, not absent.
- The same socket error was reproduced against unrelated public TCP targets
  `www.microsoft.com:443` and `1.1.1.1:443`; `127.0.0.1:8000` returned ordinary
  connection refusal. Windows Firewall reports `AllowOutbound`, no proxy is
  configured, and no explicit enabled outbound block rule was found. The
  remaining blocker is the isolated execution environment's external TCP
  policy, not provider selection or account credentials.
- Starting the local app with `MAIL_OUTGOING_DISABLED=1` was attempted, but the
  only bundled Python stopped before binding because `nh3` is missing; the
  same runtime also lacks `quotequail` and `bs4`. No alternate Python,
  accessible WSL distro or running Docker engine is available.
- Browser fallback: authenticated Yandex Mail was searched by the exact RFC
  `<178792659593.14496.8632352531530487831@yandex.ru>` with the
  `Отправленные` filter. The provider UI returned `Таких писем не нашлось`.
- This confirms that the exact RFC has no copy in the selected Yandex
  `Отправленные` view. It does not prove external non-delivery, so the
  database `delivery_unknown` row was intentionally not changed and no
  resend was started.
- Mail.ru redirected to VK authentication, which the connected browser safety
  policy blocked. No workaround was attempted; Mail.ru Sent remains
  unverified pending manual completion of that login.
- No database, mail status, attempt, credential, cursor, campaign or runtime
  control was changed. No SMTP module or SMTP DATA operation was used.
- Outgoing remains OFF; campaign `2` remains `paused_for_health`; the two
  `delivery_unknown` rows remain a blocking condition for continuation.
- Report: `ai/reports/TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831-report.md`.
- Commit attempt for this state-only update was blocked because Git could not
  create `.git/index.lock` (`Permission denied`); push is not run.

## Current task update — duplicate recipient safety

- Timestamp UTC: `2026-08-31T12:35:07Z` (`TASK-MAIL-DUPLICATE-GUARD-20260831`).
- The continuation evaluator now deduplicates by normalized recipient email
  across supplier IDs and across continuation plans for the whole request.
- For request `1059`, `20` queued Yandex jobs/messages that had a prepared or
  accepted Mail.ru counterpart were marked `cancelled`/`excluded`; no data was
  deleted. The earlier Yandex `message 78 / job 70` remains unchanged.
- Post-reconciliation there are `0` active duplicate-delivery candidates in
  request `1059`; `64` Yandex jobs remain queued for recipients without a
  recorded Mail.ru counterpart.
- Outgoing remains OFF, campaign `2` remains `paused_for_health`, and the
  existing Mail.ru `delivery_unknown` remains a safety blocker. No SMTP DATA
  was performed in this task.
- Backup: `mail-data/backups/supplier.sqlite3.pre-dedup-20260831.bak`.
- Report: `ai/reports/TASK-MAIL-DUPLICATE-GUARD-20260831-report.md`.
- Commit was not created because the environment denied creation of
  `.git/index.lock`; code/state changes remain in the working tree and push was
  not attempted.

## Last update

- Timestamp UTC: `2026-08-31T07:37:17Z` (`TASK-MAIL-INCOMING-CONTINUATION-20260831` safety stop).
- Project root: `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS`.
- Repository: `edwatikhedwa-tech/supplydesk`.
- Branch: `codex/TASK-STATE-CONTROL-20260830`.
- HEAD at this stage close: `ad3ca8d0c0598fbc82cbc0110c27d6e85bca6d46`; the current
  mail/service and repository changes are local working-tree changes.
- Remote: `origin` → `https://github.com/edwatikhedwa-tech/supplydesk.git`.
- Origin: `https://github.com/edwatikhedwa-tech/supplydesk.git`.
- Upstream: `origin/codex/TASK-STATE-CONTROL-20260830`.
- GitHub branch HEAD at audit: previous remote SHA; local implementation is
  one commit ahead and was intentionally not pushed.
- Repository visibility: `private`.
- Publication: `COMPLETE` for the previously published history; this task's
  implementation commit is local only and was not pushed.
- Working tree at close: `DIRTY`; unrelated tracked changes and broad
  untracked entries remain preserved. No unrelated path was staged.
- Latest verified tests: targeted mail tests `5 OK`, Python compile and diff
  check `PASS`; live HTTP `/messages` `200`, Yandex/Mail.ru IMAP sync `200`,
  and invalid-account error `400`.

## Project

- Project name: `SupplyDesk`.
- Product purpose: procurement workspace with supplier and mail workflows;
  this description is reported by project documentation.
- `ai/inbox/` contains only `.gitkeep`; no product task was created here.

## Current task

- `TASK-INSTRUCTION-CHECK-UX-20260901` — `COMPLETE LOCALLY`.
- The owner-facing response contract is now Russian and factual: it explains
  what was checked, what was not checked, and why, without printing all
  possible status choices at once.
- This is a documentation/state change only. No application, mail, database,
  runtime or external-service action was performed.
- The pre-existing mail/runtime history below remains historical evidence and
  was not rewritten.
- Report: `ai/reports/TASK-INSTRUCTION-CHECK-UX-20260901-report.md`.

- Previous completed task: `TASK-MESSAGES-UX-FIX-20260831` — `COMPLETE`.
- Queue-only request threads are excluded from correspondence and available in
  `Очередь`; unmatched and manual-linked inbox messages have persistent unread
  state; statuses, collapse defaults and narrow layout were updated.
- Report: `ai/reports/TASK-MESSAGES-UX-FIX-20260831-report.md`.
- The worktree remains dirty because unrelated tracked and untracked paths are
  preserved outside the Task-ID commit.

## Last completed task

- `TASK-MESSAGES-AUDIT-20260831` — `COMPLETE`; queue-only visibility,
  unread semantics, grouping and responsive geometry were audited. Report:
  `ai/reports/TASK-MESSAGES-AUDIT-20260831-report.md`.

- `TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831` — `COMPLETE`;
  explicit `body_text`/`body_html` contract, server-side sanitization,
  rich editor coverage, and snapshot preservation were implemented.
  Report: `ai/reports/TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831-report.md`.

- `TASK-MESSAGES-NAV-DEFAULT-20260831` — `COMPLETE`; desktop navigation is
  collapsed on first run while saved user preference remains authoritative.
  Report: `ai/reports/TASK-MESSAGES-NAV-DEFAULT-20260831-report.md`.

- `TASK-MESSAGES-NAV-TOGGLE-20260831` — `COMPLETE`; the blue desktop
  control now toggles the sidebar and reverses the arrow direction. Report:
  `ai/reports/TASK-MESSAGES-NAV-TOGGLE-20260831-report.md`.

- `TASK-MESSAGES-UX-20260831` — `COMPLETE`; `/messages` UX fixes were
  implemented and accepted through real browser checks. Report:
  `ai/reports/TASK-MESSAGES-UX-20260831-report.md`.

- `TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830` — `COMPLETE`,
  `PARTIALLY CONFIRMED`; the existing rich single/thread composer sends HTML
  through a plain-text backend contract. Product code was not changed.

- `TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830` — `COMPLETE` after the
  current documentation/state reconciliation.
- Previous publication task: `TASK-REMOTE-SETUP-SIMPLIFIED` — `COMPLETE`.
- Its publication result is preserved in `ai/CHANGELOG.md`,
  `ai/INTERACTION_LOG.md`, `ai/LAST_HANDOFF.md` and
  `ai/reports/TASK-REMOTE-SETUP-SIMPLIFIED-report.md`.

## Publication status

- `COMPLETE` for the previously published private repository and expected
  branch; those facts were independently confirmed with `gh repo view`,
  `gh api`, `git ls-remote` and local Git metadata.
- Publication commit: `85fb7a2d9ac2f3697f33c7b5f930f44adabf799e`.
- Latest published state-record commit:
  `55db2aa2d8f80cdf69b4970db26cacce669a7e62`.
- Local implementation commits:
  `a7043cc4f30f926dd792ef4aaceedee05300f3e2`,
  `2ba2547383c42ad92b246527739eb2a2a56f8e76` and
  `9c15c6f6dc9cadb989196fb23ebcfd696c3b0e3e`, plus
  `d90bfd46f6ee421d442f2702c04cb9d280e634d9`.
- Push: `NOT RUN`; the remote branch intentionally remains behind this local
  implementation commit.

## Implemented

- `/messages` now exposes manual unlink from a persisted linked thread and
  refreshes the unmatched list/counter after success.
- `EmailRenderer` no longer adds the former `80px` artificial minimum to
  short plain-text mail; the minimum is `24px`.
- Existing remote-image blocking and notice detection were not changed.
- The blue desktop control now owns sidebar expand/collapse; the mobile logo
  keeps its dashboard action.
- Desktop navigation defaults to collapsed when no preference is stored;
  existing stored preference is preserved.
- Outbound mail now has explicit `body_text`/`body_html` fields across bulk,
  single/thread and unmatched-reply flows; HTML is sanitized server-side and
  preserved in idempotency, resend and continuation snapshots.
- Unrelated dirty and untracked paths were preserved and were not staged.

## Runtime

- Local runtime `http://127.0.0.1:8000` remains running after verification;
  Python listener PID `10248` was confirmed.
- Real browser checks used the live local API without route mocks; bulk and reply
  editors were opened and rendered at desktop `1280x720` and mobile
  `390x844`, with no UI send action.
- No SMTP/IMAP, migration, production deployment or PostgreSQL acceptance was
  performed.

## Verified

- Repository, branch, HEAD, origin, upstream and worktree status were checked
  in the current checkout; the local implementation commit and remote-ahead
  boundary were recorded.
- GitHub repository privacy, name, default branch and branch commit were
  checked through `gh`; the remote branch was not changed by this task.
- The task report records the explicit contract, sanitizer behavior, regression
  coverage, smoke commands, screenshots and known verification limits.
- No database migration or supplier identity cleanup was run.
- `/messages` returned HTTP `200`; the authenticated browser rendered request
  list, queue-only detail, delivery-unknown detail and unmatched inbox.
- Read-only SQLite aggregate: 144 request threads, 84 queue-only threads,
  16 inbound messages all read, 41 unmatched inbox messages.
- Portrait/mobile geometry: off-canvas EmptyState was confirmed at 390x844,
  360x800 and 1024x768; screenshots were saved under
  `Temp/messages-audit-20260831/screenshots/`.

## Current priorities

- Current P0: `NONE CONFIRMED`.
- Current `/messages` P1: queue-only threads are displayed as correspondence;
  manual-linked incoming messages do not share the ordinary unread contract.
- Current `/messages` P2: status absent from list rows, all groups expanded by
  default, off-canvas EmptyState on narrow/tablet list layout, and Reply shown
  from queue-only detail.
- Current P1: outbound rich-text contract mismatch is `RESOLVED`; real provider
  mailbox acceptance remains `NOT VERIFIED`. Full-suite helper readiness
  remains `NOT VERIFIED` because the documented helper paths are absent.
- Current P2: PostgreSQL acceptance, real Mail.ru acceptance, missing helper
  scripts, parallel `docs/**` state ownership and broad untracked-worktree
  provenance remain `NOT VERIFIED` or `OPEN` as recorded in deferred findings.

## Not verified

- The following items remain explicitly `NOT VERIFIED` in this closeout:
  production deployment, PostgreSQL acceptance, real Mail.ru acceptance,
  a new live binary CID attachment fixture and collaborator access for other
  agents.
- The current canonical SQLite contains `0` rows in `mail_attachments`; the
  controlled CID fixture was checked in the browser, but a newly ingested
  binary CID attachment was not available for a live end-to-end check.
- Arbitrary secrets outside the documented publication scan patterns.
- Historical authorship/provenance of untracked working-tree paths.
- A live unread visual fixture was unavailable because current inbound unread
  count is zero; the request-list error branch was not forced in the browser.
- Full viewport matrix was not repeated for 1920x1080, 768x1024 and 1640x900.

## Blockers

- No implementation blocker for the audit. The next product iteration is
  blocked only on an explicit lifecycle/visibility decision for queued mail;
  provider mailbox acceptance, missing helper scripts, test isolation and
  parallel `docs/**` state ownership remain open separately.

## Active constraints

- This task was limited to `/messages` frontend UX and its verification
  artifacts.
- Do not change unrelated application code, backend APIs, mail transport,
  migrations, database, production configuration or `docs/**` for this task.
- Do not send email, run migrations, rewrite history, force-push, merge to
  `main`/`master` or push this task without explicit authorization.

## Current next step

- Make the design decision for queue-only visibility and the unified unread
  contract, then authorize a separate implementation task with backend/UI
  tests and live unread fixture.

## Historical / superseded state

- The earlier `TASK-PUBLISH-SAFETY-001` state with absent `origin`, missing
  repository and a blocked publication gate was true at its recorded time and
  is superseded by the successful `TASK-REMOTE-SETUP-SIMPLIFIED` publication.
- Historical blocked sections, product findings and their evidence remain in
  the append-only logs, `ai/DEFERRED_FINDINGS.md` and prior reports. They must
  not be read as the current repository/publication status.
- The separate `docs/**` state snapshot and untracked-worktree provenance
  finding remain recorded; `docs/**` was intentionally not changed.

## Latest implementation closeout — 2026-08-31

`TASK-MAIL-DUPLICATE-PROTECTION-FINAL-20260831` implemented the narrow
recipient-scoped duplicate protection described in the final report. The full
project test discovery is green (`384`, one skipped), the focused mail suite is
green (`224`, one skipped), the local server remains available on port `8000`,
and durable outgoing remains `0`. Live provider acceptance and PostgreSQL stay
not verified. The worktree remains broadly dirty and no isolated commit was
created.
