---
document_id: AUDIT-FINAL-REPORT-20260901
status: HISTORICAL
canonical: false
owner: audit
updated_at: 2026-09-01
source_commit: b5a454f9b39f3cbf01d640d5b67e4231ca25733a
---

# SupplyDesk safe snapshot + repository hygiene audit

**STATUS: PARTIAL**
`SNAPSHOT_STATUS: PASS`; сам audit завершён с оговорками по старым backend
FAIL, отсутствующему live-email fixture и частичному Knip.

## A. Lock investigation

- path: `mail-data\\supplier.sqlite3.live-mail.lock`;
- owner process: Python PID 16704, подтверждён runtime manifest и совпадением
  `RuntimeSession` в коде;
- created by: `mail/runtime.py::LiveMailLock.acquire` через `RuntimeSession.start`;
- purpose: эксклюзивная OS-level синхронизация отправляющего runtime;
- classification: `EPHEMERAL_RUNTIME`;
- required for restore: `NO` — файл создаётся/захватывается при запуске.

## B. SQLite

- journal mode: `delete`;
- live DB: `mail-data\\supplier.sqlite3`, WAL/SHM не обнаружены;
- backup method: Python `sqlite3.Connection.backup()`;
- integrity_check: source `ok`, backup `ok`;
- quick_check: source `ok`, backup `ok`;
- logical consistency: PASS — schema objects, metadata и row counts согласованы;
- restore status: PASS для необходимых source/config/database данных.

## C. Snapshot

- source: `<LOCAL_PROJECT_ROOT>`;
- frozen baseline: `<LOCAL_SNAPSHOT_ROOT>\20260901-110706\00_FROZEN_BASELINE`;
- critical files: сохранены; SQLite отдельно логически backed up;
- intentionally excluded: только ephemeral lock;
- regeneratable: lock и подтверждённые generated/cache artifacts;
- failed: нет необъяснённых critical failures;
- status: `PASS`.

## D. Audit workspace

- path: `<LOCAL_SNAPSHOT_ROOT>\20260901-110706\01_AUDIT_WORKSPACE`;
- branch: `audit/repository-hygiene-20260901` (local, not pushed);
- HEAD: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`;
- database: отдельный `mail-data\\audit-runtime.sqlite3`, read-only integrity `ok`;
- runtime: `127.0.0.1:18000`, outgoing disabled, process left running.

## E. Functional baseline

Backend: 321 PASS, 52 FAIL, 0 ERROR, 1 SKIP; exact IDs in
`FUNCTIONAL_BASELINE.md`. Playwright public shell 8/8 PASS, live routes 18/18
PASS; live-email historical fixture not verified. No real email sent.

## F. Repository audit

Current Git counts are FILES unless stated otherwise: 266 tracked, 2 modified
tracked, 0 staged, 709 untracked, 55 319 ignored; 711 status PATH ENTRIES.
Physical inventory is 56 553 FILES including `.git` metadata, 956 758 252 bytes
at final recheck. Project-owned classification: KEEP 356,
ARCHIVE_CANDIDATE 27, UNKNOWN 151; no file received a DELETE or
HIGH_CONFIDENCE_DELETE classification.

## G. Findings

- P0: none proven; environment contents were intentionally not printed or
  copied into reports, so secret values remain `NOT VERIFIED` by design.
- P1: 52 existing backend failures require an isolated controlled follow-up;
  they may affect mail campaign/pacing semantics if reproduced with a provider.
- P2: historical docs have a stale supplier count (493 vs current DB aggregate
  494); frontend `node_modules` has 134 extraneous and 5 invalid top-level
  packages; 39 exact duplicate groups; `.env.example` negation is overridden
  by a later `.env*` rule.
- P3: frontend lint has 8 warnings; generated/cache trees are large and noisy.

## H. Documentation conflicts

`ai/CURRENT_STATE.md` is the intended current state source. `docs/CURRENT_STATE.md`
and dated `Documents/28-8/**` are marked historical/supporting, but their
continued visibility can confuse agents. The concrete stale fact found is the
493/494 supplier count. The read-only state validator also found six absolute
links in one historical report escaping the audit-copy root. No source
documentation was edited because the source project was frozen for this task.

## I. Cleanup plan

Use the small, reversible batches in `CLEANUP_PLAN.md`. Every candidate needs
three independent evidence points and a separate task; nothing was deleted in
this audit.

ORIGINAL PROJECT FILES MODIFIED: NO
ORIGINAL DATABASE MODIFIED: NO
ORIGINAL GIT STATE MODIFIED: NO
FROZEN BASELINE CREATED: YES
SQLITE CONSISTENT BACKUP: PASS
AUDIT WORKSPACE CREATED: YES
FILES DELETED FROM PROJECT: 0
REMOTE PUSH: NO
REAL EMAIL SENT: NO
MIGRATIONS: NO
