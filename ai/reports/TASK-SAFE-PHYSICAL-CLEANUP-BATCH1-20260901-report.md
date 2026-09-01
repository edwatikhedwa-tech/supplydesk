# TASK: SUPPLYDESK SAFE PHYSICAL CLEANUP BATCH 1 — LEGACY WORKSPACE HYGIENE

STATUS: PASS_WITH_LIMITATIONS

Task ID: `TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901`
Verified remote base: `control/reproducible-test-runtime-v1-20260901` at
`d4d2b2ab2457e3aa103f80120642bff4bc72920f`
Audit branch: `audit/repository-hygiene-reports-20260901` at
`b5a454f9b39f3cbf01d640d5b67e4231ca25733a`

PRIMARY CANONICAL WORKSPACE: `<CANONICAL_WORKSPACE>`
LEGACY WORKSPACE: `<LEGACY_WORKSPACE>`
QUARANTINE ROOT: `<QUARANTINE_ROOT>`
LEGACY MARKED DO-NOT-USE: `YES`

## Сделано

- A fresh checkout was created outside the legacy OneDrive directory from the
  verified controlled branch. It was checked out locally as
  `control/safe-cleanup-batch1-20260901`; the required application,
  documentation, diagnostic and offline-runtime paths are present.
- The legacy root received a local-only marker declaring the canonical checkout
  and `DO_NOT_USE_FOR_DEVELOPMENT`. The legacy worktree remains dirty by
  design; no unallowlisted source or user change was removed.
- A before-manifest and after-manifest were created outside both repositories:
  `CLEANUP_BEFORE_MANIFEST.csv` and `CLEANUP_AFTER_MANIFEST.csv`. The after
  manifest includes the marker as an explicit after-only row.
- No `git clean`, `git reset --hard`, broad recursive root deletion or
  unclassified move was executed. An initial broad delete attempt was rejected
  before execution and was replaced with exact allowlisted operations.

## PERMANENTLY DELETED — DELETE_REGENERATABLE

Generated/cache material only: **308 files, 30,228,149 bytes**.

- `frontend/dist/`, `frontend/test-results/`, `frontend/artifacts/`,
  `frontend/storybook-static/`, `frontend/.lighthouseci/`
- `frontend/debug.log`
- `cache/`
- all 11 inventoried `__pycache__/` directories
- `supplier_source_tests/out/latest_summary.md`

Each delete target was verified absent after the operation. The application,
API, frontend source, migrations, tests, scripts and current documentation
were not deleted.

## MOVED TO EXTERNAL QUARANTINE — QUARANTINE_ARCHIVE

Quarantine was retained and no permanent purge was performed.

| Quarantine area | Items | Files | Bytes |
|---|---:|---:|---:|
| `01_REVIEW_PACKAGES/` | 12 packages/archives | 210 | 8,236,960 |
| `02_BACKUP_COPIES/` | 1 source-copy package | 11 | 980,704 |
| `03_OLD_EXPORTS/` | 1 old-export tree | 13 | 38,160,562 |
| `04_HISTORICAL_LOCAL_ONLY/` | `artifacts/`, `Temp/`, `tmp/` | 1,247 | 85,291,334 |
| **Total** | **15 top-level moved entries** | **1,481** | **132,669,560** |

The review package set includes the five named review ZIP containers. The
backup source copy was compared with canonical counterparts; differing hashes
were treated as historical versions, not as instructions to overwrite current
code. The old export tree and local generated/evidence trees remain available
for review and recovery.

## PROTECTED AND LEFT IN LEGACY WORKSPACE

- `.env*` files: **0 deleted**; values were not read or written to this report.
- `mail-data/`, including the canonical SQLite and local mail data: **not
  deleted, not moved, not modified**.
- `runtime/` and `.vercel/`: left in place because ownership/recovery is
  local-only and no stale active lock was proven safe to remove.
- Local SMTP/live-mail evidence and reports: left protected; no contents or
  identities were published.
- The three historical unknown items remain `REVIEW_REQUIRED`: local Neon
  skill, `keywords.txt`, and root `run_probe.py`. Root and
  `supplier_source_tests/run_probe.py` were compared and not merged or
  deleted.

## MANIFEST SUMMARY

The following are sums of manifest rows, including intentionally aggregate
rows for Git status and protected evidence; they are not a claim of unique
filesystem-inode counts.

- `files_before`: **2,629**; `bytes_before`: **244,758,730**
- `files_after`: **1,665**; `bytes_after`: **214,523,753**
- `deleted_regeneratable_files`: **308**; `deleted_regeneratable_bytes`:
  **30,228,149**
- `quarantined_files`: **1,481**; `quarantined_bytes`: **132,669,560**
- `keep_local_protected`: **9 manifest rows**
- `review_required`: **11 manifest rows**, including the three unresolved
  unknown items; unknown count before/after: **3 / 3**

Before manifest SHA-256:
`FBE4C1AA5A6F377CB9A6661BFEF34A241D71F50C30D525504DD7127328AF88F4`

After manifest SHA-256:
`DE8977483CE4FA7354AA7EFA548B8900F5AFE1C5C73C62324BA6A3E5D6E04F79`

## REFERENCE SEARCH AFTER QUARANTINE

No active runtime dependency on quarantined names was found in the canonical
checkout. `REVIEW_PACKAGE`, `REVIEW_EXPORT` and `mailru-mvp-backup` occur only
in historical publish allow/deny documentation. The two exact
`SUPPLYDESK_*_REVIEW_*.zip` names have no canonical references. Result:
**ACTIVE_RUNTIME_DEPENDENCY = 0**.

## .gitignore AUDIT

**DEFERRED.** The fixture matrix confirmed that `.env.example` is currently
covered by the broad `.env*` rule and that broad `*.json`/`*.csv` rules hide
potential source/fixture files. No correction was made because a safe outcome
was not fully proven in this physical-cleanup batch.

## CANONICAL ACCEPTANCE

All checks below ran in the new canonical checkout and did not depend on the
legacy workspace:

- Remote verification: `git ls-remote` confirmed controlled HEAD
  `d4d2b2ab2457e3aa103f80120642bff4bc72920f` and retained audit HEAD
  `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.
- Backend full regression: **411 tests, 0 failures, 0 errors, 1 skipped**.
- Diagnostic tests: **25/25 PASS**.
- Frontend: `npm ci` PASS; typecheck PASS; lint PASS with **8 warnings and
  0 errors**; build PASS.
- Safe runtime: disposable SQLite only, outgoing mail disabled, providers
  fake/blocked, loopback-only. Manual smoke: `/` `200`, `/api/auth/me` `200`,
  protected `/api/requests` and `/api/mail/status` `401`, unknown API `404`.
- Real-route Playwright: **8/8 PASS** across the configured viewport projects.
- Doctor `OFFLINE_TEST -Full`: **PASS**, exit `0`; all required checks passed.
- Validators: `validate_docs`, `validate_state`, `validate_traceability` and
  `git diff --check`: **PASS**.
- Safe runtime was stopped with the marker-aware stop script. No canonical
  SupplyDesk runtime remains active on port `18000`.
- Safety evidence: real email `false`, provider connections attempted
  `false`, canonical database written `false`, migrations applied `false`,
  secret values emitted `false`.

## Ограничения и восстановление

- Live Mail.ru/Yandex/SMTP/IMAP behavior, real delivery and production-only
  workflows were not exercised. This task is an offline cleanup and isolation
  gate, not a live-mail acceptance.
- A separate process from another historical baseline worktree was already
  listening on port `5173`; it was not part of this cleanup and was not
  changed. Canonical acceptance used port `18000`.
- Quarantine can be reviewed or restored by an explicit future task using the
  manifests and exact destination paths. Permanent quarantine purge requires a
  separate owner-approved task; it was not performed here.
- Rebuilding the clean checkout, reinstalling dependencies and regenerating
  frontend/cache artifacts are the recovery path for the deleted regeneratable
  material. Historical review and local-only material remains in quarantine.

## SECURITY GATE AND REMOTE REPORT

The cleanup branch contains only the cleanup report and state/log updates; no
quarantine content, `.env`, database, credentials or real mail data is staged.
The legacy marker and quarantine are outside Git. Normal branch push and the
final remote ref were verified after the security gate.

REMOTE REPORT PUSH: `YES` — `origin/control/safe-cleanup-batch1-20260901`
The initial evidence commit and subsequent metadata-only closeout commits were
pushed normally; the final remote ref is independently verified at closeout.
PERMANENT PURGE: `NO`
CANONICAL DB DELETED: `NO`
CANONICAL DB MODIFIED: `NO`
PRODUCT SOURCE DELETED: `0`
