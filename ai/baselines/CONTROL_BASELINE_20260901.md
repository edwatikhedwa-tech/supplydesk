# SupplyDesk Control Baseline — 2026-09-01

## Identity

- Baseline ID: `supplydesk-control-canonical-baseline-20260901`
- Control branch: `control/canonical-baseline-20260901`
- Reconciliation commit: `58103e4373f82f8ced5735c096a1028d2fbb7843`
- Metadata commit: `f31938622954ad27b9cd1a3e79e797e5e3dae3f6`
- Source HEAD: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`
- Audit branch: `audit/repository-hygiene-reports-20260901`
- Audit commit: `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`
- Repository visibility: private (verified with GitHub CLI)

## Canonical scope

- `ai/CURRENT_STATE.md` is the only current-state document.
- `PROJECT_MANIFEST.yaml` is the reconciled runtime manifest.
- The selective ledger covers 157 classified rows: two modified tracked files,
  154 project-owned untracked rows and one project-owned ignored test fixture.
- Control commit currently contains 331 tracked files: 266 source files, 27
  published audit-report files, 36 promoted project files and two ledger files.
  The 36 promoted project files are separate from the two modified docs.
- `ARCHIVE_LATER=93`, `LOCAL_ONLY=22`, `GENERATED=1` and
  `UNKNOWN_REVIEW=3` are not silently deleted or promoted.

## Functional result

| Gate | Result |
| --- | --- |
| Backend control run | `373 passed, 1 skipped, 0 failed, 0 errors` |
| Published audit comparison | `321 passed, 52 failed, 1 skipped, 0 errors` |
| New backend failures | `0` |
| New backend errors | `0` |
| Clean `npm ci` | PASS |
| Typecheck | PASS |
| Lint | PASS, 8 warnings, 0 errors |
| Production build | PASS |
| Public shell Playwright | `8 passed` across 8 configured viewport projects |
| Published live-route audit | `18/18 PASS`; backend-backed rerun not verified here |
| Knip | NOT VERIFIED; package unavailable without install |
| Source doctor DryRun | PASS |
| Control doctor DryRun | Expected partial: `.env` and DB absent |

The backend result was obtained with the tracked offline fixture
`benchmarks/enrichment_cases.json`. The published audit run used a local
environment that is intentionally not copied into this branch; exact
same-secret-environment parity is therefore not claimed.

## Security and non-goals

- Files deleted: `0`.
- `.env` values were not read or published.
- Database, runtime data, captured mail and real-email fixtures were not
  published.
- No real email or SMTP/IMAP action was performed.
- No migration, canonical database write, application refactor, merge, default
  branch change or force-push was performed.
- The staged security path allowlist and added-line high-signal scan passed.
- Remote branch `control/canonical-baseline-20260901` was pushed without force
  and its ref was verified after the final metadata synchronization.

## Confidence

High confidence in branch identity, source/audit linkage, selective file
allowlist, no-deletion property and static/frontend/public-shell gates.
Medium confidence in backend cross-environment comparison because local env and
DB were intentionally excluded. Live-route regressions are `NOT VERIFIED` in
this worktree, with published audit evidence retained as the prior baseline.
