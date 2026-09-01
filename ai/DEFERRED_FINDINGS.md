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
- Evidence: The baseline records local environment files in the source checkout; values were not read or copied.
- Impact: Accidental staging or publication could disclose credentials or enable external actions.
- Why deferred: Reading or changing secret-bearing files is outside this task and prohibited without a separately approved security workflow.
- Next verification: Owner performs a value-free `git status`/ignore audit and confirms the protected paths remain untracked and unpublished.

## FINDING-015 — Residual repository-hygiene audit drift

- ID: `FINDING-015`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The retained audit index records remaining `AUDIT-002` through `AUDIT-011` findings.
- Impact: Repository hygiene, tooling, and source-state questions remain visible follow-up work.
- Why deferred: This task only establishes documentation ownership and retention; it must not broaden into cleanup or application repair.
- Next verification: Triage each retained audit finding in a separate task with an explicit allowlist and rollback plan.

