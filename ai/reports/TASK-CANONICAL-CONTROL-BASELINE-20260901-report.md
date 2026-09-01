# TASK-CANONICAL-CONTROL-BASELINE-20260901

## Status

`PASS_WITH_LIMITATIONS` — the canonical control branch and reproducible
selective working set were created and pushed without deleting files or
publishing local data. Browser live-route rerun, Knip and same-secret-environment
backend parity remain explicitly limited.

## Goal and scope

Create a canonical, reproducible Git control baseline for the actual SupplyDesk
state at source HEAD `c076e1be385c3ae6da2716159e1f46fc2fce23d7`, using the
published repository-hygiene audit as evidence. This task does not refactor or
repair the application, delete files, run migrations, send mail or merge a
branch.

## Done

- Created controlled branch `control/canonical-baseline-20260901` in a
  separate worktree from audit commit
  `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.
- Reconciled the two modified canonical documents and the project-owned working
  set using history, references, runtime/test use, audit evidence and content
  scans. Filename-only classification was not used.
- Tracked current documentation, operator tooling, test code, synthetic visual
  snapshots and the offline enrichment case index required by tracked tests.
- Kept review packages, backup copies, real-mail fixtures, generated output,
  vendor/cache, env files, database files and runtime data out of the branch.
- Added `PROJECT_MANIFEST.yaml`, canonical baseline evidence, doctor gap
  analysis, next-stage boundaries and this report. `ai/CURRENT_STATE.md`
  remains the single current-state source.

## Reconciliation ledger

The initial audit ledger covered 154 project-owned untracked rows plus two
modified tracked files. One additional ignored but project-owned test fixture
was promoted after a tracked-test reference caused a reproducibility error.

| Action | Count | Meaning |
| --- | ---: | --- |
| `TRACK_CANONICAL` | 2 | Current accepted decisions/findings |
| `TRACK_DOCUMENTATION` | 12 | Current evidence without local mail/secret material |
| `TRACK_TOOLING` | 10 | Current operator/runtime tools |
| `TRACK_TEST` | 14 | Browser/test contracts, synthetic snapshots and offline fixture |
| `ARCHIVE_LATER` | 93 | Review/backup copies retained locally, not deleted |
| `LOCAL_ONLY` | 22 | Mail evidence, real-mail diagnostics or secret-adjacent data |
| `GENERATED` | 1 | Generated lookup output |
| `UNKNOWN_REVIEW` | 3 | Owner decision still required |

The classification ledger is
`ai/baselines/CANONICAL_WORKING_SET_CLASSIFICATION_20260901.{csv,json}`.
Project-owned unknowns changed from `62` before reconciliation to `3` after
reconciliation. The audit's protected ignored state remains separate:
`SECRET_LOCAL=6`, `DEPENDENCY_VENDOR=54053`, `CACHE=1301`, `GENERATED=321`,
`DATABASE=17`, `LOCAL_RUNTIME=62`.

## Functional verification

### Backend

The exact command was run in the control worktree with the required ignored
offline fixture added:

`python -m pytest tests -q --tb=short`

Observed result: `373 passed, 1 skipped, 4 subtests passed`; no failures and no
errors. The published audit run was `321 passed, 52 failed, 1 skipped, 0
errors`. Therefore `NEW_FAILURES=0` and `NEW_ERRORS=0` when comparing current
failed IDs against the published failed-ID set. The audit environment included
local env/data not published here, so exact same-secret-environment parity is
`NOT VERIFIED`; the difference is not represented as an application fix.

### Frontend and browser

- `npm ci --no-audit --fund=false`: PASS, 822 packages installed in disposable
  worktree; no lockfile change.
- `npm run typecheck`: PASS.
- `npm run lint`: PASS with 0 errors and 8 existing warnings.
- `npm run build`: PASS.
- Vite smoke server: `http://127.0.0.1:5173`.
- `AUDIT_BASE_URL=http://127.0.0.1:5173 npx playwright test tests/frontend-audit.spec.ts -g
  "public shell" --workers=1`: `8 passed` across the configured viewport
  projects, including overflow and axe checks.
- Published audit live-route evidence remains `18/18 PASS` at desktop/tablet/
  mobile widths. It was not rerun against a backend in this data-free control
  worktree; `PLAYWRIGHT_LIVE_ROUTE_REGRESSIONS=NOT VERIFIED`.
- `knip`: not available locally or globally; `npm exec --no -- knip --reporter
  json` refused to install it. No dependency or lockfile change was made.

### Doctor and safety

- Source `scripts/doctor.ps1 -DryRun`: PASS, values not printed.
- Control `scripts/doctor.ps1 -DryRun`: expected partial result because `.env`
  and `mail-data/supplier.sqlite3` are intentionally absent; Python/imports and
  port checks ran, and no writes occurred.
- Security staged-path allowlist: PASS.
- High-signal literal scan of added lines: PASS.
- No migration, database write, SMTP/IMAP connection, real email, deletion,
  merge, default-branch change or force-push occurred.

## Plain-language explanation

The result is a clean, reviewable branch that contains only the current code
supporting the documented runtime, its safe tests and operator tools. Private
settings, real mailbox material, local database state and disposable artifacts
stay on the machine. A future operator can review exactly what was promoted,
what was deferred and which checks still need a safe runtime.

## What was not changed

- The source checkout, application behavior, API, database rows, migrations,
  mail settings and external services.
- Review/backup packages and local-only data.
- The default branch and any existing audit branch.

## Risks and limits

- `PROJECT_DOCTOR_SPEC.md` still describes more checks than the current doctor;
  the exact gap is documented in `ai/baselines/DOCTOR_GAP_ANALYSIS.md`.
- Existing backend audit failures remain historical baseline evidence; this task
  does not claim to fix them.
- Same-environment backend parity and backend-backed live-route rerun require a
  sanitized disposable environment and are not verified by this branch alone.
- The three `UNKNOWN_REVIEW` items and 93 archive-later items need an owner
  decision; nothing was deleted to resolve them.

## Exact final fields

`STATUS: PASS_WITH_LIMITATIONS`

`CANONICAL CONTROL BRANCH: control/canonical-baseline-20260901`

`CONTROL COMMITS: 58103e4373f82f8ced5735c096a1028d2fbb7843` (reconciliation),
`58bbde8` (manifest/state/report), `f31938622954ad27b9cd1a3e79e797e5e3dae3f6`
(machine-readable baseline)

`SOURCE HEAD: c076e1be385c3ae6da2716159e1f46fc2fce23d7`

`AUDIT COMMIT: b5a454f9b39f3cbf01d640d5b67e4231ca25733a`

`PROJECT MANIFEST: PROJECT_MANIFEST.yaml`

`CURRENT STATE CANONICAL: ai/CURRENT_STATE.md`

`PROJECT-OWNED UNKNOWN BEFORE: 62`

`PROJECT-OWNED UNKNOWN AFTER: 3`

`BACKEND NEW FAILURES: 0`

`BACKEND NEW ERRORS: 0`

`PLAYWRIGHT REGRESSIONS: NOT VERIFIED for backend-backed live routes; public shell 8 passed`

`FILES DELETED: 0`

`ENV PUBLISHED: NO`

`DATABASE PUBLISHED: NO`

`REAL EMAIL SENT: NO`

`MIGRATIONS: NO`

`SOURCE PROJECT DESTRUCTIVELY MODIFIED: NO`

`REMOTE PUSH: YES — control branch ref verified after final metadata synchronization`

## Next stage

Use `ai/NEXT_STAGES.md` as the bounded follow-up plan. The next safe action is
owner review of this branch and a separately authorized sanitized runtime
verification; implementation and merge are not implied.
