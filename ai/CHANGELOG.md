# Changelog

This is an append-only chronology. Existing entries must never be deleted or
rewritten.

## 2026-09-01T06:13:09Z — HISTORICAL QUEUE RECONCILIATION COMPLETE — TASK-MAIL-STATUS-RECONCILIATION-20260901

- Applied an allowlisted, evidence-gated and idempotent local reconciliation:
  jobs `49`/`54` became `delivery_unknown`; job `71` was cancelled and its
  campaign target marked `reconciled` because Mail.ru acceptance already
  exists for the exact recipient.
- Created a verified pre-change database backup. Plan, DryRun, Apply and the
  repeated DryRun used zero SMTP calls while durable outgoing and active
  reservations remained zero.
- Request `1059` now has no queued jobs, no duplicate sent recipient and no
  recipient with multiple accepted attempts; the continuation plan is empty.
- Added reconciled acceptance to request facts and explicit Russian contact
  counts to grouped mail status badges.
- Verified full backend discovery (`374` pass, one expected PostgreSQL skip),
  frontend typecheck/lint/build, eight responsive Playwright projects, three
  live rendered widths, SQLite and HTTP/API smoke.

## 2026-09-01T05:53:58Z — HISTORICAL QUEUE RECONCILIATION START — TASK-MAIL-STATUS-RECONCILIATION-20260901

- Owner instructed the agent to complete all remaining tasks from the current
  mail-delivery chain.
- Confirmed three stale queue contradictions without changing data: two
  irreversible disputed transients and one recipient with durable reconciled
  Mail.ru acceptance.
- Scoped the implementation to evidence-gated local reconciliation, request
  fact aggregation, explicit multi-contact badge labels and verification.
- No SMTP, account, credential or unrelated worktree action is allowed.

## 2026-09-01T05:43:31Z — MAIL.RU FINAL CONTINUATION COMPLETE — TASK-MAILRU-FINAL-CONTINUATION-20260831

- Completed thirteen bounded Mail.ru continuation plans: `60` SMTP
  `post_data / 250` acceptances, one permanent pre-DATA recipient rejection,
  and zero unknown outcomes.
- Verified the final continuation is empty, duplicate sent recipients are
  zero, accepted-attempt duplicates are zero, SQLite integrity is `ok`, and
  outgoing is effectively OFF.
- Diagnosed the owner's mixed-status screenshot as an intermediate
  four-contact company card. The last queued contact later completed and the
  live card now shows `Отправлено · 4`.
- Recorded three historical Yandex queue records as a local status-cleanup
  follow-up; none is safe or necessary to send through Mail.ru.

## 2026-08-31T18:58:08Z — MAIL.RU FINAL CONTINUATION START — TASK-MAILRU-FINAL-CONTINUATION-20260831

- Owner explicitly instructed the agent to finish the remaining supplier
  delivery without further confirmation prompts and without duplicate mail.
- Verified the running local server, authenticated API, Mail.ru account `23`,
  durable/effective outgoing OFF, closed account breaker, no cooldown and no
  active pacing reservation.
- A fresh read-only continuation dry-run for campaign `2` returned
  `safe=true`, `61` strictly untouched recipients and zero live sends.
- Created a consistent pre-send SQLite backup with
  `PRAGMA integrity_check=ok`; controlled execution will use fresh bounded
  plans and one transport job at a time.

## 2026-08-31T18:38:35Z — MESSAGES PRIMARY CORRESPONDENCE FILTER — TASK-MESSAGES-PRIMARY-FILTER-20260831

- Changed the default `/messages` correspondence list to show only threads
  with sent outbound mail or a supplier reply; pending outgoing mail remains in
  the separate queue tab.
- Preserved API, database, mail transport, delivery, request-link and queue
  behavior. Direct delivery-unknown thread access remains actionable.
- Verified typecheck, build, lint, focused Playwright regressions and real
  no-route-mock browser checks at `1440x900` and `390x844`.
- Runtime evidence at verification time: correspondence `80`, primary `77`,
  queue `64`, no browser/request errors. Report and screenshots are stored in
  `ai/reports/TASK-MESSAGES-PRIMARY-FILTER-20260831-report.md` and
  `Temp/messages-primary-filter-20260831/`.

## 2026-08-31 — CID IMAGE HEIGHT FIX — TASK-MESSAGES-CID-HEIGHT-FIX-20260831

- Fixed a fast inline-image timing issue in `EmailRenderer` that could leave
  the mail iframe at `24px` and clip a CID image.
- Added a MIME-derived local CID fixture, Storybook coverage and responsive
  Playwright evidence for `390`, `1024`, `1440` and `1640` pixel widths.
- Typecheck, build, lint and the three-case Storybook responsive suite passed.
  The full live no-route-mock suite remains unverified after two 3-minute
  timeout attempts; this is recorded in the task report.
- No external send, SMTP/IMAP, API, queue, status, filter or request-link
  behavior was changed.

## 2026-08-31T17:52:01Z — FRONTEND FIXES AND MAILRU CONTINUATION HOLD — TASK-FRONTEND-MAILRU-CONTINUATION-20260831

- Applied the scoped frontend recommendations and committed them as
  `568391d` (code commit; push not run).
- Verified typecheck/build/lint, `80/80` visual scenarios, live desktop/mobile
  dialog screenshots, `230/230` targeted mail safety tests, doctor DryRun and
  local HTTP smoke with outgoing OFF.
- Read-only canonical preflight identified two and only two untouched queued
  Mail.ru recipients: `support@prometall.ru` and `89087178701@mail.ru`.
- No provider send was started. The exact batch is held for action-time owner
  confirmation; accepted and uncertain historical recipients remain excluded.
- Full backend discovery is not PASS because the system lxml DLL/parser is
  broken and one pre-existing quote-folding assertion fails; this is recorded
  in the task report.

## 2026-08-31T16:45:33Z — REAL-DATA MESSAGES ACCEPTANCE — TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831

- Completed 8 no-route-mock Playwright checks against real `/messages` data:
  manual link, reload persistence, unlink restoration, mobile dialog, queue and
  unread marker.
- Verified `0` console errors, `0` page errors, `0` failed requests and `0`
  unexpected non-2xx responses. Outgoing remained disabled.
- No application code changed. A real binary CID attachment was not present in
  the inspected data; this limitation is recorded in the task report.
- Report and screenshots:
  `ai/reports/TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831-report.md` and
  `Temp/real-data-acceptance-messages-20260831/`.

## 2026-08-31 — PLAIN-LANGUAGE RESPONSE RULE — TASK-COMMUNICATION-RULE-20260831

- Added a project-level rule for concise Russian responses with three opening
  blocks: `Сделано`, `Проблемы и ограничения`, and `Следующий шаг`.
- Technical terms and raw check results must now be explained in user-facing
  language; the instruction-check block remains a final service summary.
- Application code was not changed. Report:
  `ai/reports/TASK-COMMUNICATION-RULE-20260831-report.md`.

## 2026-08-31 — MESSAGES STATUS FILTER — TASK-MESSAGES-STATUS-FILTER-20260831

- Moved visible `Ожидает ответа` from correspondence rows into a top
  client-side filter with counts; stronger accent-blue styling was applied to
  `Ответ получен`.
- No mail transport, queue, API, database, request-link or outbound behavior
  was changed.
- Real no-mock Playwright passed at `390`, `1024`, `1440`, `1640`; live email
  regression passed `1/1`. Report:
  `ai/reports/TASK-MESSAGES-STATUS-FILTER-20260831-report.md`.

## 2026-08-31T13:25:18Z — YANDEX SENT-COPY SEARCH — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- In the authenticated Yandex Mail UI, searched the exact RFC
  `<178792659593.14496.8632352531530487831@yandex.ru>` with the
  `Отправленные` filter.
- Provider UI result: `Таких писем не нашлось`. This classifies the exact RFC
  as `NOT_FOUND` in the selected Sent view, not as proof of external
  non-delivery.
- Yandex `delivery_unknown` row, Mail.ru row, database, campaign and outgoing
  control were not changed. No retry and no SMTP DATA were performed.

## 2026-08-31T13:09:09Z — BROWSER FALLBACK — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Yandex Mail opened in the authenticated browser; its `Отправленные` folder
  is available for read-only verification.
- Mail.ru redirected to VK authentication. The connected browser safety policy
  blocked that protected page, so no bypass or alternate execution path was
  attempted. Manual completion of the Mail.ru/VK login is required.
- No mailbox mutation, database change, campaign change or SMTP operation was
  performed.

## 2026-08-31T12:58:26Z — LOCAL RUNTIME START ATTEMPT — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Attempted to start SupplyDesk on the canonical SQLite and port `8000` with
  `MAIL_OUTGOING_DISABLED=1`.
- The only bundled Python runtime stopped before binding because `nh3` is
  missing; `quotequail` and `bs4` are also absent. No alternate Python,
  accessible WSL distribution or running Docker engine is available.
- No database/mail/campaign state changed. The external TCP restriction and
  unresolved Sent-copy checks remain unchanged.

## 2026-08-31T12:53:28Z — ENVIRONMENT NETWORK FORENSICS — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Reproduced Windows `WinError 10013` / `PermissionError` for both configured
  IMAP endpoints and for unrelated public TCP targets `www.microsoft.com:443`
  and `1.1.1.1:443`.
- `127.0.0.1:8000` returned ordinary connection refusal because no local
  server is listening. Windows Firewall reports `AllowOutbound`; no proxy is
  configured and no explicit enabled outbound block rule was found.
- Root cause boundary: the current execution environment denies external TCP;
  this is not evidence of a Yandex/Mail.ru credential or provider-selection
  failure. Sent-copy lookup remains unverified.
- No mail/database/campaign state changed; outgoing remains OFF and SMTP DATA
  calls remain `0` for this task.

## 2026-08-31T12:46:00Z — READ-ONLY DELIVERY VERIFICATION — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Checked both existing `delivery_unknown` records: Yandex account `1`,
  job `20`/message `28`; Mail.ru account `23`, job `172`/message `190`.
- Decrypted only the account-specific credentials in memory. Yandex access and
  refresh credentials are present; the stored access-token expiry is in the
  future, so refresh was not attempted. Mail.ru app-password ciphertext is
  present.
- Attempted only read-only IMAP access to `imap.yandex.com:993` and
  `imap.mail.ru:993` over SSL. Both connects failed before authentication with
  local Windows `WinError 10013` / `PermissionError`; Sent-copy status remains
  unverified.
- No database/status/credential/cursor/campaign change and no SMTP module or
  DATA operation. Outgoing remains OFF; campaign `2` remains
  `paused_for_health`.
- Report: `ai/reports/TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831-report.md`.
- Commit attempt: blocked because Git could not create `.git/index.lock`
  (`Permission denied`); no paths were staged. Push was not run.

## 2026-08-31T12:35:07Z — SAFE RECONCILIATION — TASK-MAIL-DUPLICATE-GUARD-20260831

- Cause addressed: continuation safety previously keyed accepted/history checks
  by `supplier_id`, allowing duplicate supplier rows with one mailbox to evade
  the no-repeat gate.
- Code: continuation checks now use normalized recipient email across supplier
  identities, reject duplicate emails within one continuation campaign, detect
  prepared continuation mail across the whole request, and use email-scoped
  answered/delivery history.
- Data safety: after a database backup, exactly `20` queued Yandex jobs for
  request `1059` were marked `cancelled`/`excluded` because Mail.ru had already
  prepared or accepted the same recipient. No rows were deleted.
- Invariants: campaign `2` stayed `paused_for_health`; outgoing stayed OFF;
  Yandex `message 78 / job 70` stayed unchanged; no SMTP DATA was executed.
- Verification: SQLite `PRAGMA integrity_check`=`ok`; active duplicate delivery
  candidates=`0`; Python `py_compile` and `git diff --check`=`PASS`.
- Test limitation: unittest import was blocked because the bundled Python
  runtime lacks required `nh3` and `quotequail` packages.
- Report: `ai/reports/TASK-MAIL-DUPLICATE-GUARD-20260831-report.md`.

## 2026-08-30T16:20:16Z — AUDIT — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `AUDIT`
- Action: inspected repository root, Git branch/commit/status/remote, agent instructions, project state documents, runtime listener and declared commands.
- Files: existing `CLAUDE.md`, `Documents/28-8/PROJECT_STATUS.md`, `Documents/28-8/PROJECT_DOCUMENTATION.md`, `frontend/package.json`, `vercel.json`, source/runtime metadata.
- Result: audit complete; worktree is dirty with pre-existing application changes; no origin configured; local `127.0.0.1:8000` answered 200 for `/` and `/api/auth/me`.
- Evidence: read-only PowerShell/Git inspection recorded in `ai/reports/TASK-STATE-CONTROL-20260830-AUDIT.md`.
- Commit: `7658b1151bab414c867bf87898003586fbcdc8f3` baseline.
- Status: `PASS`

## 2026-08-30T16:20:16Z — DESIGN DECISION — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `DESIGN DECISION`
- Action: selected a repository-local `ai/` control plane, preserved useful `CLAUDE.md` root-hygiene rules, created a Codex branch, and excluded application files.
- Files: branch metadata; no application files.
- Result: scope fixed to state documents, adapters, templates, report and read-only validator.
- Evidence: `ai/WORKFLOW.md` and `ai/DECISIONS.md`.
- Commit: `HEAD` at close.
- Status: `PASS`

## 2026-08-30T16:20:16Z — IMPLEMENT — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `IMPLEMENT`
- Action: created the unified state-document structure and updated root agent adapters.
- Files: `AGENTS.md`, `CLAUDE.md`, `ai/` documentation tree.
- Result: implementation created; validator and final acceptance still pending.
- Evidence: file existence and later validator output.
- Commit: `HEAD` at close.
- Status: `PARTIAL`

## 2026-08-30T16:30:02Z — ACCEPTANCE — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `ACCEPTANCE`
- Action: ran the read-only validator, Python compilation, backend unittest suite, HTTP smoke/error checks and scoped documentation checks.
- Files: `ai/tools/validate_state.py`, `ai/**`, `AGENTS.md`, `CLAUDE.md`.
- Result: validator PASS; compile PASS; 344 tests OK with 1 PostgreSQL skip; `/` 200; `/api/auth/me` 200; invalid API path 404.
- Evidence: command output from this acceptance run; PostgreSQL skip is due to missing configured PostgreSQL URL.
- Commit: `HEAD` at close.
- Status: `PASS`

## 2026-08-30T16:30:02Z — CLOSE — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `CLOSE`
- Action: closed the documentation/state iteration, cleared `ACTIVE_TASK.md` to the idle sentinel, prepared the scoped Task-ID commit and confirmed that no push is possible.
- Files: `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`, `ai/INTERACTION_LOG.md`, `ai/reports/TASK-STATE-CONTROL-20260830-FINAL.md`.
- Result: no application file entered the allowed scope; working tree remains dirty only because of pre-existing user changes plus the pending scoped commit.
- Evidence: scoped `git status`, `git diff --check`, validator PASS and final report.
- Commit: `HEAD` after the scoped commit; exact hash is reported by final `git rev-parse HEAD`.
- Status: `PASS`

## 2026-08-30T16:34:45Z — COMMIT — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `CLOSE`
- Action: verified and recorded the scoped documentation commit; preserved pre-existing staged files outside the Task ID.
- Files: `AGENTS.md`, `CLAUDE.md`, `ai/**` only.
- Result: local commit exists; no push attempted because `origin` is absent.
- Evidence: `git rev-parse HEAD`, `git diff-tree --no-commit-id --name-only -r HEAD`, validator PASS.
- Commit: `HEAD` — exact hash reported after this final chronology update.
- Status: `PASS`

## 2026-08-30T17:13:31Z — RECONCILIATION — TASK-STATE-RECONCILIATION

- Agent: `Codex`
- Task ID: `TASK-STATE-RECONCILIATION`
- Mode: `AUDIT → DOCUMENTATION`
- Action: reconciled the prior state-control report with Git history, current
  worktree, the later `docs/**` snapshot, runtime/SQLite observations and
  repeatable verification commands.
- Files: `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`,
  `ai/DEFERRED_FINDINGS.md`, this chronology and the new reconciliation report.
- Result: documentation corrected; no product task created; no application,
  database, migration or production file changed by this task.
- Evidence: commit chain `7658b115 → 8a8bc36a → 9ca82f891 → d949bc6a`;
  current worktree snapshot `72` tracked modified/deleted, `598` untracked,
  `0` staged; targeted tests `27/16/12 OK`; full suite currently `FAIL`.
- Status: `PARTIAL` — state reconciliation complete, but the current full
  backend suite is not green and historical pre-existing attribution is not
  provable.

## 2026-08-30T17:13:31Z — ACCEPTANCE — TASK-STATE-RECONCILIATION

- Agent: `Codex`
- Task ID: `TASK-STATE-RECONCILIATION`
- Mode: `ACCEPTANCE`
- Action: recorded validator, Python compile, targeted tests, full-suite
  failures, frontend checks, HTTP smoke and read-only database evidence.
- Result: validator/compile/targeted/frontend/HTTP checks `PASS`; full backend
  suite `FAIL` because the outgoing safety gate blocked mail tests. No real
  SMTP/IMAP send, migration or database write was performed.
- Historical green backend result `344 OK / 1 skipped` is retained as
  `REPORTED, NOT VERIFIED`, not promoted to current fact.
- Status: `PARTIAL`

## 2026-08-30T17:20:49Z — CLOSE/COMMIT — TASK-STATE-RECONCILIATION

- Agent: `Codex`
- Task ID: `TASK-STATE-RECONCILIATION`
- Action: committed the reconciled state documents and report with subject
  `TASK-STATE-RECONCILIATION: verify shared project state`.
- Files: `ai/**` only; no application path was staged.
- Result: local documentation commit created; `origin` remains absent and no
  push was attempted.
- Status: `PASS` for scope control; current backend full-suite `FAIL` remains
  explicitly recorded as an unresolved finding.

## 2026-08-30T17:28:49Z — AUDIT/SECURITY GATE — TASK-REMOTE-REPOSITORY-PREPARATION

- Agent: `Codex`
- Task ID: `TASK-REMOTE-REPOSITORY-PREPARATION`
- Mode: `AUDIT → SECURITY GATE`
- Action: inspected Git/GitHub CLI state, looked up the expected repository,
  classified the current working tree and scanned for potential secrets without
  printing secret values.
- Evidence: `66 M`, `6 D`, `598 ??`, `0 staged`; `670` unique uncommitted paths;
  GitHub auth `PASS` as `edwatikhedwa-tech`; expected `supplydesk` repository
  not found; five ignored env/credential-risk files present.
- Files: updated `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`,
  `ai/ACTIVE_TASK.md`, this chronology and the preparation report only.
- Result: `BLOCKED`; no application code, `.gitignore`, remote, commit or push
  changed. Potential credentials and unresolved publish set require owner
  action first.

## 2026-08-30T17:31:44Z — ACCEPTANCE — TASK-REMOTE-REPOSITORY-PREPARATION

- Agent: `Codex`
- Task ID: `TASK-REMOTE-REPOSITORY-PREPARATION`
- Action: ran the AI state validator, Python compilation and scoped whitespace
  check after documenting the security gate.
- Result: validator `PASS`, compile `PASS`, `git diff --check -- ai` clean.
- Status: `BLOCKED` remains correct because potential credential files and the
  unresolved publish set were not cleared or approved.

## 2026-08-30T17:38:06Z — AUDIT/ALLOWLIST — TASK-PUBLISH-SAFETY-001

- Agent: `Codex`
- Task ID: `TASK-PUBLISH-SAFETY-001`
- Mode: `AUDIT → SECURITY SCAN → ALLOWLIST`
- Action: inventoried the current worktree, classified 677 paths, checked
  ignored sensitive paths and created a conditional AI-only publish allowlist,
  denylist and security report.
- Evidence: `66 M`, `6 D`, `599 ??`, `0 staged`; A=190, B=51, C=15, D=7,
  E=89, F=58, G=253, H=14, I=0 status-listed secret paths; five ignored env
  files remain a security overlay.
- Result: `BLOCKED`; no file was staged, committed, pushed, moved or deleted;
  no repository or origin was created.
- Files: `ai/PUBLISH_ALLOWLIST.md`, `ai/PUBLISH_DENYLIST.md`,
  `ai/PUBLISH_SECURITY_REPORT.md`, task report and current state chronology.

## 2026-08-30T17:43:27Z — ACCEPTANCE — TASK-PUBLISH-SAFETY-001

- Agent: `Codex`
- Task ID: `TASK-PUBLISH-SAFETY-001`
- Action: rechecked allowlist exclusions, AI validator, Python compilation,
  scoped diff formatting, status counts, staging and high-confidence patterns.
- Result: validator `PASS`; `681` unique working-tree paths,
  `0` staged; `origin` absent; env credential-risk overlay remains present.
- Status: `BLOCKED`; no commit, repository creation, remote change or push.

## 2026-08-30T18:06:50Z — PUBLISH — TASK-REMOTE-SETUP-SIMPLIFIED

- Agent: `Codex`
- Task ID: `TASK-REMOTE-SETUP-SIMPLIFIED`
- Mode: `EXCLUSION-FIRST → SECURITY SCAN → COMMIT → PRIVATE REMOTE`
- Action: formed an explicit 218-file publish set, removed excluded paths from
  the new Git snapshot with index-only operations, scanned the staged tree and
  reachable history, created the required commit, created the private GitHub
  repository and pushed the current branch.
- Evidence: staged tree `218` files / `3,053,727` bytes; staged security scan
  `NONE FOUND`; history scan `NONE FOUND` across `28` commits; AI validator
  `PASS`; `git diff --cached --check` `PASS`.
- Commit: `85fb7a2d9ac2f3697f33c7b5f930f44adabf799e`.
- Repository: `https://github.com/edwatikhedwa-tech/supplydesk` (`private`).
- Branch: `codex/TASK-STATE-CONTROL-20260830`; push `PASS`.
- Application code changed by this task: `NO`; pre-existing source changes
  were included only through explicit paths.
- Status: `PASS`

## 2026-08-30T18:31:32Z — STATE RECONCILIATION / CLOSE — TASK-STATE-CLOSEOUT-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CLOSEOUT-20260830`
- Mode: `STATE RECONCILIATION / CLOSE`
- Action: closed the stale active task state after independently confirming the
  private GitHub repository, branch and publication HEAD.
- Result: stale `ACTIVE_TASK` was replaced with the explicit `NONE / IDLE`
  sentinel; `CURRENT_STATE` now has an unambiguous current snapshot and marks
  historical publish BLOCKED material as superseded.
- Application code unchanged; no database action; no email action.
- Files: `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`,
  this chronology, `ai/INTERACTION_LOG.md` and the closeout report.
- Evidence: repository/GitHub audit, state validator, scoped diff check and
  staged-path review.
- Status: `PASS`

## 2026-08-30T18:36:14Z — AUDIT / DESIGN DECISION — TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830`
- Action: rechecked the current private GitHub repository, branch, upstream,
  remote SHA and working-tree boundary after publication.
- Design decision: treat the published private branch as the current authority;
  mark only publication-specific stale blockers as `SUPERSEDED`, while keeping
  product acceptance and residual local credential risk explicitly open.
- Scope: `ai/**` state and chronology only; no application, database, runtime,
  SMTP, IMAP or production-setting action.
- Acceptance before commit: `PASS` — AI validator, scoped diff check,
  append-only log check, explicit staged-path review and secret-like diff scan
  all passed; normal push remains the final transport step.
- Status: `PASS`

## 2026-08-30T18:42:02Z — ACCEPTANCE / CLOSE — TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830`
- Acceptance: `PASS` — Task-ID commit `55db2aa2d8f80cdf69b4970db26cacce669a7e62`
  was pushed; `git ls-remote` and `gh api` matched the remote branch SHA.
- Scope result: only `ai/**` state/report files changed; application, database,
  runtime, SMTP and IMAP actions remained untouched.
- Final repository status: tracked/staged changes `0`; `56` unrelated
  untracked entries preserved.
- Status: `COMPLETE`

## 2026-08-30T18:56:25Z — AUDIT / MAIL CONTENT CONTRACT — TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830

- Agent: `Codex`
- Task ID: `TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830`
- Mode: `AUDIT ONLY`
- Result: `COMPLETE — PARTIALLY CONFIRMED`.
- Evidence: traced bulk, single/thread, unmatched-inbox reply and campaign
  continuation flows; ran `171` relevant backend tests, one continuation
  dry-run test, an isolated temporary-SQLite fake-provider/fake-SMTP MIME
  matrix, frontend typecheck and frontend build.
- Finding: the rich single/thread Composer sends `innerHTML` as generic `body`,
  while the backend treats it as plain text and escapes it into the HTML
  alternative. Bulk/new and unmatched-inbox reply remain plain-text input
  flows. No implementation was made pending a plain-only vs explicit-rich
  business decision.
- Scope: only `ai/**` report/state files changed; no product code, migrations,
  tests, `docs/**`, live database, SMTP, IMAP or supplier identity state.
- Report: `ai/reports/TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830-report.md`.
- Push: `NOT RUN`.

## 2026-08-31T06:21:32Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MESSAGES-UX-20260831

- Agent: `Codex`
- Scope: `/messages` frontend UX only.
- Changes: removed the artificial short-mail iframe minimum, added persisted
  manual-link unlink control after reload, and refreshed the unmatched list and
  counter after successful unlink.
- Safety: remote-image blocking/notice detection, API contracts unrelated to
  unlink, queue, statuses, filters, database, migrations, SMTP and IMAP were
  not changed or used.
- Verification: live no-mock audit `81/81 PASS`; live Playwright regression
  `1 passed`; remote image requests `0`; typecheck/build `PASS`; lint `PASS`
  with existing warnings.
- Commit: `a7043cc4f30f926dd792ef4aaceedee05300f3e2`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MESSAGES-UX-20260831-report.md`.

## 2026-08-31T06:36:26Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MESSAGES-NAV-TOGGLE-20260831

- Agent: `Codex`
- Scope: desktop navigation control used on `/messages`; mobile behavior
  preserved.
- Change: the blue logo control now expands/collapses the sidebar and reverses
  the arrow direction; the duplicate separate collapse control was removed.
- Verification: real Playwright click check `PASS` for `248 ↔ 76` px,
  full no-mock `/messages` audit `81/81 PASS`, typecheck/build `PASS`, lint
  `PASS` with existing warnings.
- Commit: `2ba2547383c42ad92b246527739eb2a2a56f8e76`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MESSAGES-NAV-TOGGLE-20260831-report.md`.

## 2026-08-31T06:46:00Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831

- Scope: explicit outbound HTML mode with separate `body_text`/`body_html`
  across bulk, single/thread and unmatched-reply flows.
- Safety: server-side nh3 allowlist sanitization, derived plain alternative,
  escaped personalization, idempotency-aware rich snapshots and preserved
  resend/continuation content.
- Verification: relevant mail suite `286 OK` with one expected skip; targeted
  rich/MIME/HTTP/resend/continuation regressions, compileall, typecheck,
  build, lint and browser desktop/mobile smoke all passed.
- No database, migration, supplier identity cleanup, `--apply`, SMTP/IMAP or
  real email was used.
- Commit: `d90bfd46f6ee421d442f2702c04cb9d280e634d9`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831-report.md`.

## 2026-08-31T06:42:12Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MESSAGES-NAV-DEFAULT-20260831

- Agent: `Codex`
- Scope: desktop navigation default on `/messages`; saved preference and
  mobile behavior preserved.
- Change: when no sidebar preference exists, navigation starts collapsed;
  stored `true`/`false` remains authoritative.
- Verification: fresh-context real Playwright `PASS` (`76 px` default), blue
  click/reload persistence `PASS`, full no-mock `/messages` audit `81/81 PASS`,
  typecheck/build `PASS`, lint `PASS` with existing warnings.
- Commit: `9c15c6f6dc9cadb989196fb23ebcfd696c3b0e3e`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MESSAGES-NAV-DEFAULT-20260831-report.md`.

## 2026-08-31T06:55:58Z — AUDIT / MESSAGES VISIBILITY — TASK-MESSAGES-AUDIT-20260831

- Agent: `Codex`.
- Mode: `REVIEW / AUDIT ONLY`.
- Scope: `/messages` request threads, unmatched inbox, delivery/read states,
  responsive rendering and information architecture.
- Result: `FAIL` for the current information contract; architecture direction
  is sound, but queue-only threads and the manual-linked unread gap are
  confirmed.
- Evidence: live browser at `http://127.0.0.1:8000/messages`, read-only SQLite
  aggregate, desktop/mobile screenshots, DOM geometry, typecheck and lint.
- Findings: `84/144` request threads are queue-only; current inbound unread is
  `0/16`; unmatched inbox contains `41` messages; mobile/tablet off-canvas
  EmptyState and default-expanded groups were confirmed.
- No application code, API, database, migrations, SMTP/IMAP or production
  settings were changed.
- Report: `ai/reports/TASK-MESSAGES-AUDIT-20260831-report.md`.
- Push: `NOT RUN`.

## 2026-08-31T07:32:48Z — IMPLEMENTATION / LIVE QA — TASK-MESSAGES-UX-FIX-20260831

- Agent: `Codex`.
- Scope: `/messages` correspondence visibility, outbox separation, unread
  semantics, statuses, grouping and narrow layout.
- Result: `COMPLETE`; queue-only threads are excluded from correspondence and
  shown in `Очередь`; manual/unmatched inbox read state is persisted and reset
  on open; UI statuses and responsive behavior were corrected.
- Verification: targeted/integration suite `53 OK`, Python compile, frontend
  typecheck/build and lint `PASS`; local HTTP/browser smoke `PASS`; final
  desktop/mobile PNGs reviewed.
- Report: `ai/reports/TASK-MESSAGES-UX-FIX-20260831-report.md`.

## 2026-08-31T07:37:17Z — LIVE ACCEPTANCE / SAFETY STOP — TASK-MAIL-INCOMING-CONTINUATION-20260831

- Incoming IMAP is now independent of the per-account outgoing flag; Yandex
  account 1 and Mail.ru account 23 both passed live read-only sync with
  durable outgoing disabled.
- Continuation queue-gate now permits only explicitly applied continuation
  jobs while the source campaign is `paused_for_health`; ordinary campaign
  jobs remain blocked.
- Mail.ru request 1059 continuation: `17` messages accepted (`250`), one
  Unicode-address job became `delivery_unknown` with `UnicodeEncodeError`
  before SMTP DATA, and outgoing was immediately disabled.
- No automatic retry was started. Two prepared jobs remain queued in the
  stopped batch; later contacts were not prepared or sent.
- Verification: targeted mail tests `5 OK`, Python compile and diff check
  `PASS`, live `/messages` HTTP `200`, Yandex/Mail.ru sync `200`, invalid
  account error `400`, and SQLite integrity `ok`.
- Report: `ai/reports/TASK-MAIL-INCOMING-CONTINUATION-20260831-report.md`.
- Commit: pending at state close; Push: `NOT RUN`.
- Commit: pending at state close; Push: `NOT RUN`.

## 2026-08-31T13:54:22Z — IDN PRE-DATA FIX / DEDUP SAFETY — TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831

- Root cause: Mail.ru job `172` / message `190` reached the old durable gate
  before SMTP envelope serialization and then raised `UnicodeEncodeError` for
  the IDN recipient `info@печнойцентр73.рф`; no SMTP code or DATA evidence
  existed, but the job became `delivery_unknown`.
- Code: moved the durable gate to the provider callback immediately before
  SMTP DATA; converted SMTP envelope domains to IDNA ASCII while preserving
  readable headers; added regressions for IDN and pre-DATA behavior.
- Deduplication: continuation checks remain normalized-recipient scoped across
  suppliers/providers, and duplicate recipient selection is blocked.
- Data: backed up canonical SQLite, reconciled only job `172`/message `190` to
  `failed`/`failed` with `delivery_state=not_sent`; historical attempt `70`
  was preserved. Yandex job `20`/message `28` remains untouched
  `delivery_unknown`.
- Verification: SQLite integrity `ok`, outgoing `0`, no active reservations,
  campaign 2 unchanged, zero pending duplicate recipient groups in request
  `1059`; `py_compile` passed. Full unittests are unavailable because the
  bundled runtime lacks `nh3`, `bs4` and `quotequail`.
- No live SMTP/IMAP, SMTP DATA, account reconnect, credential/cursor change or
  campaign-state change was performed.
- Backup: `mail-data/backups/supplier.sqlite3.pre-idn-reconcile-20260831-165009.bak`.
- Report: `ai/reports/TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831-report.md`.

## 2026-08-31T14:01:13Z — FINAL VERIFICATION — TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831

- Fixed a schema mismatch discovered by the reconciliation smoke test:
  exception class is read from `mail_send_attempt_evidence`, not the attempt
  row itself.
- Isolated provider smoke passed IDN envelope conversion. The reconciliation
  method passed apply and repeat/idempotency checks on disposable DB copies.
- Canonical final state remains integrity `ok`, outgoing `0`, campaign 2
  unchanged, no active reservations, zero pending duplicate groups in request
  `1059`, and exactly one outbound row for `s-kl@yandex.ru`.

## 2026-08-31T14:03:03Z — GIT CLOSEOUT — TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831

- Scoped commit attempt was blocked because Git could not create
  `.git/index.lock` (`Permission denied`). No paths were staged and push was
  not run; unrelated worktree changes were preserved.

## 2026-08-31T14:22:36Z — MAIL.RU REMAINING CONTINUATION LAUNCH — TASK-MAILRU-REMAINING-CONTINUATION-20260831

- Owner authorized sending only previously untouched request-1059 supplier
  contacts through Mail.ru account `23`.
- Read-only preflight confirmed account `23` is connected, outgoing is `0`,
  active reservations are `0`, SQLite integrity is `ok`, and the current
  queued Mail.ru jobs are only `173`/`191` and `174`/`192`.
- The declared requirements installation could not reach PyPI because the
  execution environment denies outbound TCP (`WinError 10013`). Starting the
  project entry point then stopped before HTTP binding with
  `ModuleNotFoundError: nh3`.
- No provider authentication, SMTP DATA, queue mutation, campaign change or
  credential change occurred. The continuation remains blocked until the
  previously working runtime is available.

## 2026-08-31T14:40:00Z — SAFE PROJECT RECOVERY TOOLING — TASK-PROJECT-RECOVERY-20260831

- Added non-destructive `scripts/doctor.ps1` with explicit Plan/DryRun/Apply
  modes for Python, configuration, database-file and port checks.
- Added `scripts/bootstrap_supplydesk.ps1` to create a project `.venv` and
  install only declared requirements after explicit Apply.
- Added `scripts/recover_supplydesk.ps1` to force outgoing OFF and keep the
  server running only after an HTTP `200` smoke-test.
- Parse, Plan and DryRun checks passed. Apply stopped before `.venv` creation
  because the current `py.exe` reports no installed Python.
- No deletion, move, database write, campaign change, credential change,
  SMTP login or SMTP DATA occurred. Project cleanup is deferred until after a
  writable Git checkpoint and inventory.

## 2026-08-31T14:52:34Z — RECOVERY APPLY RETRY — TASK-PROJECT-RECOVERY-20260831

- Owner requested immediate server startup and execution of the pending
  Mail.ru continuation.
- Bootstrap `-Apply` was retried. It stopped before creating `.venv` because
  `py.exe` reports no installed Python in the current execution environment.
- No server, SMTP authentication, SMTP DATA, database write, queue mutation,
  campaign change or credential change occurred. Outgoing remains OFF.

## 2026-08-31T14:56:05Z — RUNTIME RECOVERY BLOCKER CONFIRMED — TASK-PROJECT-RECOVERY-20260831

- User requested installation of all missing dependencies and immediate
  execution.
- No local wheel cache or usable alternate runtime was found. The current
  isolated environment cannot execute the available Windows Python or reach
  package indexes.
- The remaining action is external to this environment: run the documented
  bootstrap in ordinary Windows PowerShell. No application, database, queue,
  campaign, credential or outgoing state was changed.

## 2026-08-31T15:01:57Z — SERVER STARTED WITH OUTGOING OFF — TASK-PROJECT-RECOVERY-20260831

- Rechecked the environment: system Python `3.11.7` and all declared
  requirement imports are available; doctor DryRun exited `0`.
- Started `supplier_app.py` directly as PID `23584` on `127.0.0.1:8000` with
  `MAIL_OUTGOING_DISABLED=1` and left it running after verification.
- Root and `/api/auth/me` returned `200`; unauthenticated mail API returned
  `401`; unknown API returned `404`.
- Read-only SQLite remained healthy with durable outgoing `0`. No mail,
  queue, campaign, account, credential or cleanup state changed.

## 2026-08-31 — DUPLICATE RECIPIENT PROTECTION IMPLEMENTED — TASK-MAIL-DUPLICATE-PROTECTION-FINAL-20260831

- Added recipient-scoped durable guards and cross-provider active-delivery
  blocking; continuation now supersedes only untouched source jobs and records
  `resend_of_message_id`.
- Corrected pre-DATA provider-attempt accounting while preserving zero attempts
  for local message/recipient encoding failures.
- Verified `384` discovered tests and `224` focused mail tests (`1` skipped in
  each run), doctor DryRun, compileall, diff check and local HTTP smoke.
- No live send, migration, credential/account change or canonical database
  write was performed. See the final report in `ai/reports/`.
## 2026-08-31 — MESSAGES AUDIT REPAIR — TASK-MESSAGES-AUDIT-REPAIR-20260831

- Fixed reply-editor focus, operational-attention group visibility and the
  stale outbound metric expectation identified by the `56/80` legacy audit.
- Full route-mocked frontend audit passed `80/80`; live no-mock email
  regression passed `1/1` across the required HTML/plain/CID/remote/no-image/
  long-mail cases and widths `390/1024/1440/1640`.
- Typecheck, lint and build passed. Lint reported `0` errors and `8` existing
  warnings outside the changed files.
- No SMTP/IMAP, send, queue, database, request-link or production action was
  performed. Outgoing remains disabled. Report and screenshots are recorded
  in `ai/reports/` and `Temp/task-messages-audit-repair-20260831/`.

## 2026-08-31T18:08:46Z — EXACT MAILRU CONTINUATION SENT — TASK-FRONTEND-MAILRU-CONTINUATION-20260831

- После action-time подтверждения отправлены только существующие jobs `173` и
  `174` через Mail.ru account `23`, по одной попытке на job.
- Оба письма приняты провайдером (`post_data`, SMTP `250`), локальные статусы
  `sent`, sent-copy сохранён; новых jobs/messages и дублей не создано.
- Yandex queue не трогалась, неопределённый Unicode-домен не повторялся.
- Durable outgoing switch возвращён в `0`; активных reservations нет, SQLite
  integrity check `ok`. Send-only процессы остановлены.

## 2026-08-31T18:28:01Z — LOCAL SERVER STARTED WITH OUTGOING OFF — TASK-SERVER-START-20260831

- Запущен `supplier_app.py` на `127.0.0.1:8000`; процесс оставлен работающим.
- Установлен процессный `MAIL_OUTGOING_DISABLED=1`, durable outgoing switch
  подтверждён как `0`; отправка из очереди невозможна.
- HTTP smoke: root `200`, auth/me `200`, protected API `401`, unknown API `404`.
