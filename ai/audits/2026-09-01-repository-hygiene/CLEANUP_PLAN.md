# Future cleanup plan — recommendations only

No batch below was executed. Each batch must be a separate task with an exact
allowlist, a before/after manifest, a test command and rollback from the frozen
baseline. `UNKNOWN` is safer than deletion.

## Batch 1 — generated/cache artifacts

- exact paths: `frontend/dist/`, `frontend/test-results/`,
  `frontend/artifacts/`, `artifacts/`, `cache/`, `.pytest_cache/`,
  `.ruff_cache/`, selected `Temp/` outputs;
- evidence: generated/cache classification, ignore rules, reproducibility;
- risk: losing diagnostic screenshots or local evidence;
- verify: `npm run build`, targeted Playwright smoke, backend import check;
- rollback: restore exact paths from `00_FROZEN_BASELINE` or its manifest.

## Batch 2 — obsolete exports/backups

- exact paths: candidates listed in `UNTRACKED_FILES_AUDIT.md`, including
  `mailru-mvp-backup-20260829/`, review-package archives and root export files;
- evidence: names/age/duplicate content only, with owner confirmation still
  required;
- risk: deleting the only historical recovery copy;
- verify: reference search, hash manifest, documented canonical replacement;
- rollback: restore from frozen baseline; prefer dated quarantine first.

## Batch 3 — historical documentation

- exact paths: dated `docs/`, `Documents/28-8/`, old task reports identified in
  `DOCUMENTATION_MAP.md`;
- evidence: explicit historical markers and links to `ai/CURRENT_STATE.md`;
- risk: losing decisions or misleading future agents;
- verify: link check, state validator, documentation contradiction audit;
- rollback: restore from frozen baseline.

## Batch 4 — exact duplicates

- exact paths: the 39 SHA-256 groups in `DUPLICATES_REPORT.md`, one group at a
  time;
- evidence: identical hash plus canonical path plus history/reference proof;
- risk: hidden import, script or archival reference;
- verify: `rg` references, runtime smoke, backend/frontend baseline comparison;
- rollback: restore the removed duplicate from frozen baseline.

## Batch 5 — frontend unused candidates

- exact paths: first review `RiskFactors.tsx` and Knip exports; no automatic
  removal;
- evidence: Knip, reference search, explicit entry-point review, clean install;
- risk: dynamic route/component breakage;
- verify: typecheck, lint, build, Playwright route matrix and screenshots;
- rollback: restore file and package manifest from baseline.

## Batch 6 — Python dead-code candidates

- exact paths: Vulture candidates in `vulture.log`, excluding routes,
  callbacks, decorators and plugin hooks until proven;
- evidence: Vulture + rg/config/template search + runtime/test evidence;
- risk: API or background-job regression;
- verify: focused tests, full baseline comparison, HTTP smoke;
- rollback: restore exact file from baseline.

## Batch 7 — dependencies and ignore rules

- exact paths: only explicitly chosen `frontend/package.json`, lockfile or
  `.gitignore` lines after the prior batches are stable;
- evidence: clean `npm ci`, Knip/Ruff results, dependency usage search;
- risk: build/runtime or secret-tracking regression;
- verify: `npm ci`, typecheck, lint, build, Playwright, `git check-ignore` matrix;
- rollback: restore manifests/rules and lockfile from baseline.

## Batch 8 — doctor/CI guardrails

- exact paths: future `scripts/doctor.ps1` and optional workflow files;
- evidence: this audit's checks and explicit safe defaults;
- risk: CI noise or accidental destructive behavior;
- verify: Plan/DryRun modes, no writes in default mode, test fixture run;
- rollback: revert the isolated commit.
