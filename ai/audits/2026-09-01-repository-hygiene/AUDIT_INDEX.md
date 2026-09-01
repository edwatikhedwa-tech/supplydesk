# SupplyDesk repository hygiene audit — publication index

## Audit identity

- Audit ID: `repository-hygiene-2026-09-01`
- Date: `2026-09-01` (`Europe/Volgograd`)
- Source repository: `https://github.com/edwatikhedwa-tech/supplydesk.git`
- Remote visibility: `PRIVATE` — independently verified with GitHub CLI before publication
- Source branch: `codex/TASK-STATE-CONTROL-20260830`
- Source HEAD: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`
- Audit report branch: `audit/repository-hygiene-reports-20260901`
- Audit report path: `ai/audits/2026-09-01-repository-hygiene/`
- Source checkout and audit workspace: `LOCAL ONLY` (absolute paths intentionally redacted)

## Remote pointer

```text
Source HEAD: c076e1be385c3ae6da2716159e1f46fc2fce23d7
Audit report branch: audit/repository-hygiene-reports-20260901
Audit status: PARTIAL
Snapshot: PASS
SQLite consistent backup: PASS
```

## Baseline and source state

- Frozen snapshot: `SupplyDesk_Snapshots/20260901-110706` (`LOCAL ONLY`)
- Snapshot status: `PASS`
- Source capture: 56,544 files and 956,748,919 bytes at capture; 266 tracked files, 2 modified tracked files, 0 staged files, 709 untracked paths and 55,319 ignored paths.
- The source checkout contained user changes and local/untracked state. It was not cleaned, reset, or edited for this publication.
- The publication worktree was created from the exact source HEAD above. Its commit diff contains only `ai/audits/**`.

## SQLite evidence

- Database file: `mail-data/supplier.sqlite3` (`LOCAL ONLY`)
- Backup file: `supplier.sqlite3.consistent-backup` (`LOCAL ONLY`, never published)
- Backup method: Python `sqlite3.Connection.backup()` with the source opened read-only
- Source and backup `integrity_check`: `ok`
- Source and backup `quick_check`: `ok`
- Journal mode: `delete`; WAL/SHM/journal sidecars were not present
- Schema, metadata and aggregate row counts: `MATCH`
- Aggregate evidence contains counts for 68 tables; it contains no row contents or credentials.
- SQLite consistency result: `PASS`

## Functional baseline

- Audit status: `PARTIAL`
- Backend: 321 passed, 52 failed, 0 errors, 1 skipped; existing failures are preserved as baseline evidence and were not fixed in this task.
- Public shell Playwright: 8/8 passed.
- Live route Playwright: 18/18 passed at 1440, 1024 and 390 widths.
- API smoke: `/api/auth/me` → 200, protected `/api/requests` → 401, unknown endpoint → 404.
- Historical live-email fixture: `NOT VERIFIED`; no real email was sent.
- Playwright screenshots: 15 files, `LOCAL ONLY`; they may contain application or user data and are not part of this branch.

## Security and privacy boundary

- High-signal P0 secret scan: no proven secret values.
- Environment files, credentials, tokens, cookies, session data, database files, mail data, message bodies, raw logs and screenshots were not published.
- Secret values were not printed or copied. The reports state only statuses, paths/categories and aggregate evidence.
- A contradiction audit found `5` vs `6` local env-like files in the source report set. Exact count and contents are `NOT VERIFIED`; this discrepancy is intentionally preserved here rather than resolved by inference.

## Published reports

All source reports listed below were copied from the external report set. The published copies were sanitized in a separate workspace; originals remain untouched.

| File | Purpose | Classification | Published handling | Source |
|---|---|---|---|---|
| `00_EXECUTIVE_SUMMARY.md` | Executive result and constraints | SANITIZE_REQUIRED | published sanitized | `00_EXECUTIVE_SUMMARY.md` |
| `BASELINE_COMPARE_SUMMARY.json` | Frozen baseline comparison | SANITIZE_REQUIRED | published structured JSON with local paths removed | `BASELINE_COMPARE_SUMMARY.json` |
| `BASELINE_PATH_DIFF.csv` | Single explained baseline path difference | SANITIZE_REQUIRED | published sanitized CSV | `BASELINE_PATH_DIFF.csv` |
| `BASELINE_SIZE_DIFF.csv` | Baseline size comparison | SANITIZE_REQUIRED | published sanitized CSV | `BASELINE_SIZE_DIFF.csv` |
| `CLEANUP_PLAN.md` | Reversible future cleanup batches | SANITIZE_REQUIRED | published sanitized, no cleanup performed | `CLEANUP_PLAN.md` |
| `DEAD_CODE_AUDIT.md` | Ruff/Vulture/Knip leads | SANITIZE_REQUIRED | published sanitized, no deletion approval | `DEAD_CODE_AUDIT.md` |
| `DEPENDENCY_AUDIT.md` | Python/JS dependency findings | SANITIZE_REQUIRED | published sanitized | `DEPENDENCY_AUDIT.md` |
| `DOCUMENTATION_MAP.md` | Documentation ownership and drift map | SANITIZE_REQUIRED | published sanitized | `DOCUMENTATION_MAP.md` |
| `DUPLICATES_REPORT.md` | Exact duplicate groups | SANITIZE_REQUIRED | published sanitized, hashes retained only where part of report evidence | `DUPLICATES_REPORT.md` |
| `FINAL_REPORT.md` | Full structured audit result | SANITIZE_REQUIRED | published sanitized | `FINAL_REPORT.md` |
| `FUNCTIONAL_BASELINE.md` | Backend/browser/API baseline | SANITIZE_REQUIRED | published sanitized, no user content | `FUNCTIONAL_BASELINE.md` |
| `GITIGNORE_RECOMMENDATIONS.md` | Ignore-rule findings | SAFE_TO_PUBLISH | published | `GITIGNORE_RECOMMENDATIONS.md` |
| `INVENTORY_SUMMARY.txt` | Inventory totals and categories | SANITIZE_REQUIRED | published sanitized | `INVENTORY_SUMMARY.txt` |
| `LOCK_INVESTIGATION.md` | Ephemeral runtime lock evidence | SANITIZE_REQUIRED | published sanitized, process identifiers not exposed | `LOCK_INVESTIGATION.md` |
| `PROJECT_DOCTOR_SPEC.md` | Read-only diagnostic specification | SAFE_TO_PUBLISH | published | `PROJECT_DOCTOR_SPEC.md` |
| `PROJECT_INVENTORY.csv` | Paths, sizes, status, categories and recommendations | SANITIZE_REQUIRED | published sanitized CSV; no file contents | `PROJECT_INVENTORY.csv` |
| `PROJECT_MANIFEST_SPEC.md` | Manifest and validation specification | SAFE_TO_PUBLISH | published | `PROJECT_MANIFEST_SPEC.md` |
| `SECURITY_FINDINGS.md` | Secret-safety findings | SANITIZE_REQUIRED | published sanitized; values remain redacted | `SECURITY_FINDINGS.md` |
| `SNAPSHOT_BLOCKER.md` | Resolved snapshot blocker | SANITIZE_REQUIRED | published sanitized | `SNAPSHOT_BLOCKER.md` |
| `SOURCE_STATE_CAPTURE.md` | Read-only source state | SANITIZE_REQUIRED | published sanitized with count discrepancy note | `SOURCE_STATE_CAPTURE.md` |
| `SQLITE_BACKUP_REPORT.json` | SQLite structural and aggregate evidence | SANITIZE_REQUIRED | published structured JSON; paths and hashes redacted, no rows | `SQLITE_BACKUP_REPORT.json` |
| `SQLITE_CONSISTENCY.md` | SQLite backup verification | SANITIZE_REQUIRED | published sanitized | `SQLITE_CONSISTENCY.md` |
| `TOOL_RESULTS.md` | Tool availability and limitations | SANITIZE_REQUIRED | published sanitized | `TOOL_RESULTS.md` |
| `UNTRACKED_FILES_AUDIT.md` | Conservative untracked-file classification | SANITIZE_REQUIRED | published sanitized | `UNTRACKED_FILES_AUDIT.md` |
| `playwright-live-routes.json` | Route-matrix result data | SANITIZE_REQUIRED | published structured JSON with local paths removed | `playwright-live-routes.json` |
| `AUDIT_INDEX.md` | Remote review navigation and boundaries | SAFE_TO_PUBLISH | created for this publication | — |
| `AUDIT_SUMMARY.json` | Machine-readable audit summary | SAFE_TO_PUBLISH | created for this publication | — |

## Local-only source artifacts

The following were reviewed or retained locally and were deliberately not published: raw `*.log` files, coverage outputs, raw `npm-ls`/`pip-list` outputs, `knip.json`, `ruff.json`, `CRITICAL_HASHES.csv`, `playwright-live-email.json`, `BASELINE_FILE_LIST.csv`, `BASELINE_MANIFEST.csv`, `SOURCE_FILE_LIST.csv`, `SOURCE_FILE_LIST.json`, all screenshots and traces, the SQLite backup/database, mail data, env-like files, runtime state, archives, caches, vendor trees and generated artifacts.

## Change boundary

- Application code modified: `NO`
- Source checkout modified: `NO`
- Source database modified: `NO`
- Cleanup/deletion performed: `NO`
- Published branch adds: `ai/audits/**` only
