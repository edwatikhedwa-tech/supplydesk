---
document_id: DEFERRED-FINDINGS-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# Deferred Findings

Only unresolved, accepted-risk, or explicitly superseded findings belong in
this current register. Resolved findings and full chronology are preserved in
[`ai/history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md`](history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md).

## FINDING-003 — Standard helper-script coverage is incomplete

- ID: `FINDING-003`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The canonical baseline documents the tracked operator-tool set but does not establish a complete standard helper-script catalog.
- Impact: Future agents may repeat ad-hoc inspection or use inconsistent commands.
- Why deferred: This task establishes governance; it does not add application or operator behavior.
- Next verification: Compare the required diagnostic control-plane command catalog with tracked scripts in a separately scoped task.

## FINDING-004 — Source checkout has broad pre-existing worktree changes

- ID: `FINDING-004`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical baseline records a dirty source checkout and intentionally isolates governance work in a clean control worktree.
- Impact: Source-side ownership and rollback cannot be inferred from the governance branch.
- Why deferred: Resolving ownership would require user decisions about pre-existing application changes.
- Next verification: Owner reviews source `git status`, tracked/untracked inventory, and the exact allowlist before any cleanup or merge.

## FINDING-006 — Historical published-environment backend failures

- ID: `FINDING-006`
- Severity: `MEDIUM`
- Status: `SUPERSEDED`
- Evidence: The old published audit run recorded failures, while the canonical control baseline recorded `373 passed, 1 skipped, 0 failed, 0 errors` in its controlled run.
- Impact: The old failure count must not be presented as the current control baseline or as proof of an application fix.
- Why deferred: The environments are not equivalent and this task did not rerun live backend acceptance.
- Next verification: Re-run the relevant backend-backed live routes in the approved runtime environment and compare scope explicitly.

## FINDING-008 — Unattributed source-side API edit

- ID: `FINDING-008`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical baseline records an unattributed `api/index.py` worktree edit in the source checkout.
- Impact: Ownership and deployability of the source-side API change are unknown.
- Why deferred: This task forbids application edits and cannot assign ownership to another agent.
- Next verification: Source owner identifies the change, validates it against the source HEAD, and decides whether to keep, revert, or isolate it.

## FINDING-009 — Local credential-bearing environment risk

- ID: `FINDING-009`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical value-free review found no current operational
  `.env`/`.env.*` files, no tracked operational secret paths, and no operational
  `.env` path in Git history. Git history contains `.env.example` only; its
  contents were not read. Retained external snapshots contain 12 `.env*`
  filename copies and the retained quarantine contains 12 token/auth-named
  artifact filenames.
- Impact: Accidental staging or publication could disclose credentials or enable external actions.
- Review result: `REVIEW_REQUIRED` — the filename-level retained copies were
  not treated as leaks, but they cannot be classified as safe without a
  separately approved content-level owner review.
- Why deferred: This task is value-free and does not read, copy, rotate, delete
  or move secret-bearing files or retained artifacts.
- Next verification: Owner approves a separate retained-artifact review and
  classifies the 12 snapshot `.env*` names and 12 quarantine token/auth names;
  no Git history rewrite is authorized by this finding review.

## FINDING-015 — Residual repository-hygiene audit drift

- ID: `FINDING-015`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The retained audit index records remaining `AUDIT-002` through `AUDIT-011` findings.
- Impact: Repository hygiene, tooling, and source-state questions remain visible follow-up work.
- Why deferred: This task only establishes documentation ownership and retention; it must not broaden into cleanup or application repair.
- Next verification: Triage each retained audit finding in a separate task with an explicit allowlist and rollback plan.

## FINDING-016 — Frontend candidates remain review-required

- ID: `FINDING-016`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: The isolated Knip audit reported `RiskFactors.tsx`, three manual
  Playwright/Lighthouse configuration files and the direct `lighthouse`
  development dependency as candidates.
- Impact: The repository retains a small amount of potentially unused
  frontend/tooling surface; deleting it without owner review could remove a
  manual acceptance path or planned UI component.
- Why deferred: The approved Batch 2 allowlist authorized only the proven
  Python cleanup. No frontend file or dependency was deleted.
- Next verification: Owner approves a separate frontend/dependency allowlist;
  repeat clean install, reference/build analysis and full browser acceptance
  before any deletion.

