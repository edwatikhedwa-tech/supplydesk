---
document_id: STATE-001
status: CURRENT
canonical: true
owner: project-control
updated_at: 2026-09-02
based_on_commit: f13dad6dc2461ef6dc50242f7fc075895f2a4603
---

# Current State

This file is the only canonical current-state source for SupplyDesk. It is a
short evidence snapshot, not a task diary. Older snapshots and chronology are
preserved under [`ai/history/`](history/).

## Last update

`2026-09-01T21:56:03Z` — VibeCoding CI performance fix V1 is implemented on
the dedicated branch. Remote FAST routing passed; the explicit FULL proof
reproduced the hosted Windows Browser Full performance failure and was stopped
without timeout escalation.

## Project

- Repository: `edwatikhedwa-tech/supplydesk` (private).
- Verified controlled baseline: `control/reproducible-test-runtime-v1-20260901`
  at `d4d2b2ab2457e3aa103f80120642bff4bc72920f`.
- Canonical branch: `control/final-hygiene-acceptance-20260901`, created from
  the verified Batch 2 HEAD `a228321401270b69c9ac2f07f76435e246b6f5c3`.
- Current governance branch: `control/vibecoding-policy-v1-20260901`, created
  from verified canonical HEAD `f13dad6dc2461ef6dc50242f7fc075895f2a4603`.
- Current CI branch: `control/vibecoding-ci-v1.1-20260901`, created from
  verified VibeCoding policy HEAD `9d3e58232230b276396f3bc127e2d937bed8482d`.
- Cleanup Batch 2 branch: `control/safe-cleanup-batch2-20260901`, retained as
  the immediately preceding evidence branch.
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
- Source of truth after cleanup is the verified remote final-acceptance branch
  plus the new canonical checkout. The old dirty OneDrive checkout is
  recovery-only and is not used for development.

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
- VibeCoding Control Policy V1 is canonical at `ai/VIBECODING_RULES.md` with
  `last_corrected: 2026-09-01`; its factual tool inventory is
  `ai/VIBECODING_TOOL_REGISTRY.yaml` and its read-only validator is
  `ai/tools/validate_vibecoding.py`.
- VibeCoding bootstrap references are present in `AGENTS.md`, `CLAUDE.md`,
  `PROJECT_MANIFEST.yaml` and this AI entrypoint. The documentation validator
  recognizes the separate canonical policy without weakening current-state
  uniqueness.
- VibeCoding Control Policy V1.1 adds FAST, FOCUSED, FULL and PERIODIC profiles,
  LOW/NORMAL/HIGH risk levels and the FAST-first rule. CI implementation is
  tracked in `.github/workflows/ci.yml`; classifier mapping is in
  `scripts/ci/change_groups.json`.
- CI Performance Fix V1 adds risk-based FAST/FOCUSED/FULL/PERIODIC workflow
  routing, a real-route one-viewport Browser Smoke, concurrency cancellation,
  explicit job budgets and a CI Summary. Normal focused pushes do not start
  Backend Full or Browser Full.

## Verified

The following evidence is inherited from earlier control work or was verified
on this task's dedicated branch:

- Official backend full run: `412 tests, 0 failures, 0 errors, 1 skipped`.
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
  match the Batch 2 closeout commit before this acceptance branch was created.
- Final canonical inventory: 390 tracked files, 45 tracked root objects, zero
  unknown canonical files/directories/root objects, zero tracked review/backup
  packages, zero tracked generated artifacts, zero tracked env/secret files and
  zero tracked database files. The two known duplicate groups remain kept by
  path-purpose design.
- Final `.gitignore` matrix kept real `.env`, database and runtime artifacts
  ignored while product JSON/CSV, fixtures and `PROJECT_MANIFEST.yaml` remain
  visible to Git.
- Final offline acceptance on the canonical checkout: backend `412/0/0/1`,
  diagnostics `26/26`, frontend install/typecheck/lint/build PASS, safe HTTP
  `200/200/401/404`, Playwright `8/8` and Doctor Full exit `0`.
- Final branch was pushed normally and `git ls-remote` independently confirmed
  its remote HEAD; no force-push, merge or default-branch change occurred.
- VibeCoding policy validator and four governance diagnostic tests passed; the
  full diagnostic set is `30/30` and the required documentation/state/
  traceability validators also pass.
- The governance commit `1bdda8a` was pushed to
  `origin/control/vibecoding-policy-v1-20260901`; its remote ref was verified
  after normal publication.
- Local V1.1 governance checks and classifier tests were rerun after the
  workflow/validator changes; remote CI execution is verified for the focused
  FAST path.
- Remote FAST proof `33562406201` passed in 1m22s on final configuration
  commit `2b860a5`; Full Control passed and Backend Full/Browser Full were
  skipped by deterministic classification.
- Explicit FULL proof `33562558816` ran all required full jobs in parallel;
  Change Classification, Fast Control, Full Control and Frontend passed, but
  Browser Full failed after 11m17s on all eight viewport screenshot/Axe
  scenarios and Backend Full was cancelled after 11m49s without a final test
  total. This is recorded as `CI_PERFORMANCE_FAILURE`, not as a product
  regression.
- Local final control checks after the routing correction: diagnostics
  `39/39`, official quick runner `50/0/0/0`, VibeCoding/docs/state/traceability
  validators PASS, Doctor Plan PASS, and local real-route Browser Smoke `1/1`.
- The GitHub Actions registry intentionally remains `NOT_VERIFIED`: FAST is
  proven, but the required full remote acceptance is not green.

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
- Do not treat planned or unverified tools as configured, and do not claim a
  check passed unless its command actually ran.
- CI itself is HIGH risk: remote GitHub Actions status must be verified before
  its registry entry can become `CONFIGURED`; the focused path is proven, but
  the full path remains NOT_VERIFIED on the hosted runner.

## Current next step

`TASK-CI-PERFORMANCE-FIX-V1-20260902` is in closeout. The final report records
the remote FAST proof, explicit FULL limitation, selected jobs and rollback;
do not start another timeout or runner iteration in this task.

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
- CI performance fix report: [`ai/reports/TASK-CI-PERFORMANCE-FIX-V1-20260902-report.md`](reports/TASK-CI-PERFORMANCE-FIX-V1-20260902-report.md).
- Canonical duplicate audit: [`ai/reports/CANONICAL_DUPLICATES_BATCH2.md`](reports/CANONICAL_DUPLICATES_BATCH2.md).
- Batch 2 cleanup manifest: [`ai/reports/CLEANUP_BATCH2_MANIFEST.csv`](reports/CLEANUP_BATCH2_MANIFEST.csv).
- Audit pointer: [`ai/audits/2026-09-01-repository-hygiene/README.md`](audits/2026-09-01-repository-hygiene/README.md).

