---
document_id: STATE-001
status: CURRENT
canonical: true
owner: project-control
updated_at: 2026-09-01
source_commit: 9e2acba40a702399653055162fa7101adf6d7486
---

# Current State

This file is the only canonical current-state source for SupplyDesk. It is a
short evidence snapshot, not a task diary. Older snapshots and chronology are
preserved under [`ai/history/`](history/).

## Last update

`2026-09-01T17:59:25Z` — safe cleanup Batch 2 completed its offline acceptance
on the canonical checkout. The new canonical checkout is the development
source of truth; the historical OneDrive checkout is marked
`DO_NOT_USE_FOR_DEVELOPMENT` and its three former unknown items are retained
outside the repository in quarantine.

## Project

- Repository: `edwatikhedwa-tech/supplydesk` (private).
- Verified controlled baseline: `control/reproducible-test-runtime-v1-20260901`
  at `d4d2b2ab2457e3aa103f80120642bff4bc72920f`.
- Cleanup branch: `control/safe-cleanup-batch2-20260901`, based on the verified
  Batch 1 HEAD `847b0979a27da9d38f9cc755309a283ad99df699`.
- Canonical development checkout: `<CANONICAL_WORKSPACE>`.
- Historical legacy checkout: `<LEGACY_WORKSPACE>`, marked
  `LEGACY_WORKSPACE_DO_NOT_DEVELOP_HERE.txt`.
- External retained quarantine: `<QUARANTINE_ROOT>`; it is outside the Git
  repository and is not a source of truth.
- Canonical control baseline: `control/canonical-baseline-20260901` at
  `792f441b4b6099533177e7c1d23d6252670f9309` before this governance branch.
- Documentation governance branch: `control/documentation-governance-20260901`.
- Diagnostic V1 branch: `control/diagnostic-plane-v1-20260901` at
  `98f4a370e2bf223aea6550630ce49ed05f12a8af`.
- Diagnostic V1.1 branch: `control/diagnostic-plane-v1.1-20260901`, created in
  a separate worktree from the V1 HEAD above; verified remote branch resolves
  to `f9b0b66432f9e8650e87e5a89dd27a258a416e38`.
- Reproducible test/runtime branch: `control/reproducible-test-runtime-v1-20260901`,
  pushed at functional commit `09d12018afc4ecb8445f40dc1b717ef078cfae0f` in
  a separate worktree and not merged into the default branch.
- Product behavior is not changed by this control-plane-only task.
- Source of truth after cleanup is the verified remote control branch plus the
  new canonical checkout. The old dirty OneDrive checkout is recovery-only.

## Runtime

- Backend entrypoints recorded by the manifest: `supplier_app.py` and
  `api/index.py`.
- Frontend root: `frontend/`; default URLs are
  `http://127.0.0.1:8000` and `http://127.0.0.1:5173`.
- Canonical database contract remains SQLite at `mail-data/supplier.sqlite3`;
  the safe test profile refuses that path and uses only
  `runtime/test-data/supplier.sqlite3`.
- Safe runtime profile: `OFFLINE_TEST`; it uses the real application routes,
  synthetic credentials, disposable SQLite, disabled outgoing mail and
  loopback-only networking. The process was stopped after acceptance.

## Implemented

- One canonical state file: `ai/CURRENT_STATE.md`.
- Operational control documentation is owned by `ai/**`; product documentation
  is owned by `docs/**`.
- Historical state, handoff, decisions, deferred findings, and root task
  reports are retained under dated `ai/history/` paths.
- Documentation lifecycle and audit retention policies are recorded in
  [`docs/DOCUMENTATION_POLICY.md`](../docs/DOCUMENTATION_POLICY.md) and
  [`ai/AUDIT_POLICY.md`](AUDIT_POLICY.md).
- Diagnostic control plane V1 is catalogued in
  [`docs/product/CAPABILITY_CATALOG.md`](../docs/product/CAPABILITY_CATALOG.md),
  [`docs/requirements/TRACEABILITY_MATRIX.csv`](../docs/requirements/TRACEABILITY_MATRIX.csv),
  and [`scripts/diagnostics/diagnostic_contract.yaml`](../scripts/diagnostics/diagnostic_contract.yaml).
- `scripts/doctor.ps1` now delegates to read-only typed checks and emits
  machine-readable evidence outside the repository.
- Diagnostic control plane V1.1 separates test-verification, diagnostic and
  live-acceptance levels; adds semantic TRACE-009..013 validation; maps each
  failure mode to a responsible component and doctor check; and records
  symptom, causes, confirming/excluding checks, confidence and repair
  eligibility.
- V1.1 adds disposable negative fixtures for database, backend, frontend,
  secret-path and machine-output classification, and makes `doctor -Apply` an
  explicit safety block because recovery is not implemented.
- V1 adds `requirements-test.txt`, a standard-library unittest runner,
  PowerShell setup/run wrappers, and a documented clean-checkout bootstrap.
- V1 adds `OFFLINE_TEST` safe runtime start/stop wrappers, an owned runtime
  marker, disposable database enforcement, inherited-provider scrubbing and
  a loopback-only network guard.
- Doctor now has explicit `OFFLINE_TEST`, `LOCAL_CANONICAL` and
  `LIVE_EXTERNAL` profiles; offline checks are separated from live-provider
  acceptance and `-Apply` remains blocked.

## Verified

The following evidence is inherited from earlier control work or was verified
on this task's dedicated branch:

- Official backend full run: `411 tests, 0 failures, 0 errors, 1 skipped`.
- Frontend clean install, typecheck and build passed; lint passed with 8
  warnings.
- Public-shell Playwright acceptance: `8/8` viewport projects passed against
  the safe runtime.
- Published live route acceptance: `18/18 PASS`.
- Safe runtime smoke: root `200`, auth/me `200`, protected APIs `401`, unknown
  API `404`; synthetic login and protected `200` paths passed.
- Safe runtime marker: disposable SQLite, canonical `false`, outgoing mail
  disabled, providers fake/blocked, private `.env` not loaded, real email false.
- Remote audit retention: audit branch resolves to
  `b5a454f9b39f3cbf01d640d5b67e4231ca25733a` and its retained tree includes the
  audit index, summary, final report, functional baseline, and security findings.
- Diagnostic tests: `25 passed` with `python -m unittest discover -s
  tests/diagnostics -v`, including controlled negative fixtures.
- Traceability validator: `PASS`; 21 active requirements, 21/21 behavioral
  test links, 21/21 distinctly diagnosable failure modes, and TRACE-001..013.
- Doctor `-Plan`: exit `0`; full `-DryRun -Profile OFFLINE_TEST` returned
  `WARNING`, exit `0`, with all required checks passing and only the expected
  dirty-worktree warning; `doctor -Apply`: `SAFETY_BLOCK`, exit `3`.
- Dedicated branch was pushed to `origin`; the first DNS attempt failed
  transiently and the immediate retry succeeded.
- Documentation, state and traceability validators: `PASS`; `git diff --check`:
  `PASS`.
- `requirements-test.txt` was installed only into `.venv-test`; no global
  package install, private `.env`, canonical DB or provider connection was
  required.
- Traceability validator now reports `offline_eligible_requirements=21/21` and
  `offline_behaviorally_diagnosable=6/21`; eligibility is not overclaimed as
  behavior proof.
- Physical cleanup Batch 1 deleted only 308 regeneratable/cache files
  (`30,228,149` bytes) and moved 1,481 historical/review files
  (`132,669,560` bytes) to retained external quarantine. No product source,
  `.env`, canonical database or mail data was deleted, moved or modified.
- Cleanup before/after manifests are retained outside the repository; all
  delete and quarantine paths were individually verified after the operation.
- Legacy marker was added locally; the legacy worktree remains intentionally
  dirty.
- Batch 2 moved `.agents/skills/neon/SKILL.md`, `keywords.txt` and root
  `run_probe.py` to external quarantine after reference, process and hash
  checks. No canonical source file, database, environment or mail data was
  physically deleted.
- Batch 2 removed only 18 proven unused Python imports and 2 side-effect-free
  dead bindings in commit `d2ceef3`; product behavior and public surfaces were
  preserved.
- Batch 2 duplicate audit found 2 groups / 4 files and deleted none. Both
  groups are retained because their path/package roles differ.
- Batch 2 `.gitignore` audit removed broad JSON/CSV hiding and passed the full
  synthetic matrix; `.env.example` remains ignored under the publish denylist.
- Batch 2 acceptance: backend `412/0/0/1`, diagnostics `26/26`, frontend
  install/typecheck/lint/build PASS, Playwright `8/8`, Doctor Full exit `0`.
- Batch 2 documentation/state/traceability validators and `git diff --check`
  passed; the cleanup report and manifest are retained in the pushed branch.
- Remote `control/safe-cleanup-batch2-20260901` was independently verified to
  match the final closeout commit.

## Not verified

- NOT VERIFIED: live external provider routes, real SMTP/IMAP, real email and
  production migration behavior were not exercised by design.
- Full authenticated real-provider workflows remain outside the safe offline
  contract; synthetic login and protected local routes were checked.
- Same-environment parity between the source checkout and the control worktree
  was not re-established.
- `knip` produced frontend candidates; no frontend file or dependency was
  removed because the approved allowlist covered Python cleanup only and
  manual/operator surfaces could not be ruled out.
- Current canonical database rows, mailbox state and provider quotas were not
  inspected or exercised.

## Blockers

- No reproducible-test-runtime blocker remains for the offline scope.
- Product/live-provider follow-up remains bounded by the limitations above and
  the open findings in [`ai/DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md).

## Active constraints

- Do not modify application logic, UI, API, database, migrations, runtime
  state, mail data, or production settings in this cleanup branch.
- Do not send real email, connect to real SMTP/IMAP, write the canonical
  database, force-push, merge, or change the default branch.
- Keep audit history on the dedicated audit branch; only the documented pointer
  and selected summaries belong in the canonical working branch.
- Do not start the safe runtime from a canonical database or private `.env`;
  use `scripts/start_test_runtime.ps1 -Apply` after the test venv exists.
- Do not use the legacy OneDrive checkout for development. Do not permanently
  purge the external quarantine without a separate owner-approved review.

## Current next step

`TASK-SAFE-CLEANUP-BATCH2-20260901` is complete and its cleanup report,
manifest and state closeout are pushed on the dedicated control branch.
Permanent quarantine purge remains forbidden.

## Canonical references

- Manifest: [`PROJECT_MANIFEST.yaml`](../PROJECT_MANIFEST.yaml).
- Documentation entrypoint: [`docs/README.md`](../docs/README.md).
- Active-task sentinel: [`ai/ACTIVE_TASK.md`](ACTIVE_TASK.md).
- Decisions: [`ai/DECISIONS.md`](DECISIONS.md).
- Deferred findings: [`ai/DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md).
- Latest governance report: [`ai/reports/TASK-DOCUMENTATION-GOVERNANCE-20260901-report.md`](reports/TASK-DOCUMENTATION-GOVERNANCE-20260901-report.md).
- Diagnostic report: [`ai/reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901-report.md`](reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901-report.md).
- Diagnostic V1.1 report: [`ai/reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901-report.md`](reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901-report.md).
- Reproducible test/runtime report: [`ai/reports/TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901-report.md`](reports/TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901-report.md).
- Safe physical cleanup report: [`ai/reports/TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901-report.md`](reports/TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901-report.md).
- Safe cleanup Batch 2 report: [`ai/reports/TASK-SAFE-CLEANUP-BATCH2-20260901-report.md`](reports/TASK-SAFE-CLEANUP-BATCH2-20260901-report.md).
- Canonical duplicate audit: [`ai/reports/CANONICAL_DUPLICATES_BATCH2.md`](reports/CANONICAL_DUPLICATES_BATCH2.md).
- Batch 2 cleanup manifest: [`ai/reports/CLEANUP_BATCH2_MANIFEST.csv`](reports/CLEANUP_BATCH2_MANIFEST.csv).
- Audit pointer: [`ai/audits/2026-09-01-repository-hygiene/README.md`](audits/2026-09-01-repository-hygiene/README.md).

