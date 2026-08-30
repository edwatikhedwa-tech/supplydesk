# Current State

## Last update

- Timestamp UTC: `2026-08-30T17:13:31Z` (audit snapshot; close evidence is in the reconciliation report).
- Agent: `Codex`.
- Task ID: `TASK-STATE-RECONCILIATION`.
- Current HEAD: `HEAD` (resolve the exact hash with `git rev-parse HEAD`).
- Parent HEAD at audit start: `d949bc6afe0c97135a98662d3a7725f4b46d6c1e`.
- Branch: `codex/TASK-STATE-CONTROL-20260830`.
- Remote: `origin` is not configured; `git remote -v` returned no entries.
- Working tree: `DIRTY`.
- Audit snapshot counts: `72` tracked modified/deleted paths, `598` untracked paths,
  `0` staged paths, `670` unique uncommitted paths. These counts include
  application, documentation and generated/review artifacts outside `ai/`.
- `PRE-EXISTING STATUS: REPORTED, NOT VERIFIED`: the historical claim of `170`
  pre-existing positions cannot be proved from the available baseline/history.
  Current uncommitted paths were preserved and were not treated as authored by
  this reconciliation task.

## Scope and source reconciliation

- The prior state-control commits are confirmed locally and ordered as:
  `7658b115` baseline → `8a8bc36a` unified AI state → `9ca82f891` final
  verification chronology → `d949bc6a` separate project-state snapshot.
- `8a8bc36a` contains only `AGENTS.md`, `CLAUDE.md` and `ai/**`.
- `9ca82f891` contains only `ai/CHANGELOG.md` and `ai/INTERACTION_LOG.md`.
- `d949bc6a` adds `docs/CURRENT_STATE.md`, `docs/DECISIONS.md`,
  `docs/ENGINEERING_CONTRACT.md` and `docs/WORK_LOG.md`; it does not change
  application code.
- The repository now has two state-document systems: the existing `ai/**`
  control-plane and the later `docs/**` project snapshot. They are not unified
  by a machine-checked link or shared version marker. This is recorded as a
  reconciliation finding; `docs/**` was not changed because the task permits
  only `ai/**` documentation changes.
- The current worktree also contains uncommitted changes to `docs/**` and
  `api/index.py`. Their author and exact historical start point are unknown;
  they remain outside this task's scope.

## Project

- Project name: `SupplyDesk` — confirmed by repository layout and project
  documentation.
- Product purpose: procurement workspace for requests, supplier discovery and
  enrichment, and mail workflows — reported by `Documents/28-8/PROJECT_STATUS.md`.
- No active product task exists in `ai/inbox/`; only `.gitkeep` is present.
- This reconciliation does not create or implement a product task.

## Implemented

- This reconciliation updated only the `ai/**` state documents and added the
  reconciliation report; no product implementation was started.

## Runtime and database checks

- Loopback listener `127.0.0.1:8000` was observed under PID `23324` with a
  Python process. Process ownership beyond that observation is not verified.
- `GET http://127.0.0.1:8000/` returned `200`.
- `GET http://127.0.0.1:8000/api/auth/me` returned `200`.
- `GET http://127.0.0.1:8000/api/requests/1059` returned `401` without an
  authenticated session; this is the negative-path smoke result.
- The canonical SQLite file `mail-data/supplier.sqlite3` exists and was opened
  read-only. No migration or database write was performed.
- Read-only database observations: `PRAGMA integrity_check=ok`, `67` tables,
  `493` suppliers, `171` request-1059 supplier rows, `2` mail accounts,
  `165` mail messages, `42` inbox messages, `1` runtime-control row and
  `149` mail jobs.
- Message statuses observed: `sent=62`, `queued=84`, `failed=2`,
  `delivery_unknown=1`, `received=16`. Providers observed: one `mailru` and
  one `yandex` account row. A row is not proof of live provider acceptance.
- The local `.env` contains the outgoing-mail safety switch reported as
  `MAIL_OUTGOING_DISABLED=1`; no real SMTP/IMAP send was attempted.

## Verification status

- `python ai/tools/validate_state.py`: `PASS` before and after the document
  reconciliation.
- `python -m py_compile ai/tools/validate_state.py`: `PASS`.
- Targeted `test_supplier_identity.py`: `27 tests, OK`.
- Targeted `test_mail_status_semantics.py`: `16 tests, OK`.
- Targeted `test_mailru_mvp.py`: `12 tests, OK`; this uses patched/dummy
  transports and is not live Mail.ru acceptance.
- Current full backend run with the local safety configuration:
  `344 tests`, `41 failures`, `7 errors`, `1 skipped` — `FAIL`.
- A process-only `MAIL_OUTGOING_DISABLED=0` override was also attempted:
  `350 tests`, `41 failures`, `7 errors`, `1 skipped` — `FAIL`. The durable or
  loaded outgoing safety gate still blocked the affected mail tests. No claim
  of a green full suite is valid for this current audit.
- The previous report's `344 tests OK, 1 skipped` is historical
  `REPORTED, NOT VERIFIED` because no persistent execution log was supplied
  and the current rerun failed.
- Frontend `npm --prefix frontend run typecheck`: `PASS`.
- Frontend `npm --prefix frontend run lint`: `PASS` with `8` warnings and no
  errors (dependency/fast-refresh warnings).
- Frontend `npm --prefix frontend run build`: `PASS` with a Vite chunk-size
  warning. Visual screenshot review and full responsive matrix were not run.
- `tests/run-tests.ps1` and `scripts/doctor.ps1` are absent.
- PostgreSQL acceptance, production deployment status and real Mail.ru
  acceptance are `NOT VERIFIED`.

## Verified

- The validator, targeted tests, frontend checks, HTTP smoke and read-only
  SQLite observations listed in this file were actually executed or observed.

## Not verified

- Historical authorship of uncommitted paths, PostgreSQL, production,
  real-provider acceptance and visual/responsive acceptance remain unverified.

## Open directions and priorities

- `P0`: none confirmed by this reconciliation.
- `P1`: outbound rich-text behavior is explicitly reported as unresolved in
  `Documents/28-8/PROJECT_STATUS.md`: editor HTML is escaped as text and rich
  formatting should not be promised until fixed. It was not implemented or
  independently accepted here. Current full-suite failure under the outgoing
  safety gate is also a release-readiness blocker.
- `P2`: real Mail.ru live acceptance is not verified; PostgreSQL acceptance is
  not verified; no central test database-path abort guard was found; the two
  parallel state systems need an owner decision; broad worktree attribution is
  unresolved.
- `P3`: date/time work is reported as already implemented in the historical
  documentation, but no current visual acceptance was run; no active date/time
  blocker is confirmed. No `origin` is configured. Explicit multi-email
  picker and migration-prefix cleanup remain lower-priority reported findings.

## Blockers

- `P0`: none confirmed.
- `P1`: reported outbound rich-text issue and current full-suite failure under
  the outgoing safety gate.
- `P2`: real Mail.ru/PostgreSQL acceptance, test DB guard, parallel state
  systems and worktree provenance remain open.
- `P3`: no configured origin and no current confirmed date/time blocker.

## Recommended next blocker

Choose one bounded product block: **HTML/plain-text outbound mail contract**.

- Why: it is the clearest user-visible P1 reported issue, can be tested offline
  with mocked transport, and does not require credentials, migrations or live
  sending. Mail.ru live acceptance is a separate operational gate requiring
  owner-approved provider access.
- Minimal scope: inspect and, in a separate future task, fix the representation
  of plain text and supported rich HTML for bulk compose and inbox reply;
  add isolated MIME/rendering regression tests and document the exact contract.
- Non-goals: Mail.ru provider integration, PostgreSQL work, migrations, schema
  changes, production deployment, real sends, supplier identity cleanup and
  date/time redesign.
- Definition of Done: plain text is not double-escaped; supported rich HTML is
  sanitized and preserved in the intended MIME part; unsafe markup is removed;
  bulk and reply flows share the documented contract; isolated tests pass with
  transport mocked; no live send occurs; state docs record evidence.
- Acceptance scenarios: literal `<` and `&` in plain text remain literal;
  allowed formatting/link markup survives when rich HTML is supported; unsafe
  tags, event handlers and unsafe URL schemes are removed; inbox reply follows
  the same rule; no external send or database mutation is required for the
  test.
- No implementation was started by this reconciliation.

## Active constraints

- Only `ai/**` documentation and the reconciliation report may be changed by
  this task. Application files, `docs/**`, database, migrations and production
  settings are outside scope.
- Do not run migrations, send mail, publish, configure `origin`, delete,
  reset, clean, checkout or force-push.
- Do not describe unverified history, production state or provider acceptance
  as fact.

## Current next step

The state-control task is ready to close after validator, scoped diff/staging
review and the documentation-only commit. The next product decision is whether
to authorize the separately scoped HTML/plain-text investigation above.
