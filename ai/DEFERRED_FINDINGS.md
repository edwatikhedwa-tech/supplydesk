# Deferred Findings

Agents must not automatically fix these findings while doing another task.

## FINDING-001 — Project status snapshot may be stale

- ID: `FINDING-001`
- Date: `2026-08-30`
- Source: `Documents/28-8/PROJECT_STATUS.md`, Git status and file timestamps.
- Description: the passport calls itself a 28 August snapshot while the working tree and reports contain later changes.
- Severity: `P2`
- Why outside current scope: reconciling product documentation with application code would expand into a product audit.
- Possible next step: run a separate read-only documentation/code reconciliation and update the passport with evidence.
- Status: `OPEN`
## FINDING-002 — No configured Git remote

- ID: `FINDING-002`
- Date: `2026-08-30`
- Source: `git config --get remote.origin.url` returned no value.
- Description: this checkout has no verified `origin`, so push cannot be performed.
- Severity: `P3`
- Why outside current scope: configuring a remote changes external repository state and needs owner direction.
- Possible next step: configure the intended remote through the normal project process, then authorize a push.
- Status: `OPEN`

## FINDING-003 — Standard verification helper scripts are absent

- ID: `FINDING-003`
- Date: `2026-08-30`
- Source: existence checks for `tests/run-tests.ps1` and `scripts/doctor.ps1`.
- Description: the repository does not contain the helper scripts referenced by the verification skill.
- Severity: `P2`
- Why outside current scope: creating project test tooling is not required to build the state contour.
- Possible next step: decide separately whether a maintained project-level verification wrapper is needed.
- Status: `OPEN`

## FINDING-004 — Existing application worktree changes are broad

- ID: `FINDING-004`
- Date: `2026-08-30`
- Source: `git status --short --branch`.
- Description: application, migration, test, report and artifact changes predate this task and are not attributable to this implementation.
- Severity: `P1`
- Why outside current scope: touching or reconciling them would risk data loss and violate the documentation-only boundary.
- Possible next step: owner-led review and separate commits for those changes.
- Status: `OPEN`
