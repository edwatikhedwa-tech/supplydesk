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
- Description: application, migration, test, report and artifact changes are
  currently present in the worktree. Their author and exact historical start
  point cannot be proved from the available Git baseline; the earlier wording
  that they definitely predated this task was too strong and is corrected here.
- Severity: `P1`
- Why outside current scope: touching or reconciling them would risk data loss and violate the documentation-only boundary.
- Possible next step: owner-led review and separate commits for those changes.
- Status: `OPEN`

## FINDING-005 — Parallel project-state document system

- ID: `FINDING-005`
- Date: `2026-08-30`
- Source: commit `d949bc6afe0c97135a98662d3a7725f4b46d6c1e` and file inspection.
- Description: `docs/CURRENT_STATE.md`, `docs/DECISIONS.md`,
  `docs/ENGINEERING_CONTRACT.md` and `docs/WORK_LOG.md` form a second state
  system beside `ai/**`. There is no shared version marker or validator rule
  reconciling them. Some claims are historical reports rather than current
  independent evidence.
- Severity: `P2`
- Why outside current scope: the task permits changing only `ai/**`; editing or
  merging `docs/**` would expand scope and could overwrite user work.
- Possible next step: owner decision on one canonical source and an explicit
  migration/linking policy.
- Status: `OPEN`

## FINDING-006 — Current full backend suite is not green

- ID: `FINDING-006`
- Date: `2026-08-30`
- Source: current unittest runs in the reconciliation audit.
- Description: default run returned `344` tests with `41 failures`, `7 errors`
  and `1 skipped`; a process-only outgoing-disable override returned `350`
  tests with the same `41 failures`, `7 errors` and `1 skipped`. A durable or
  loaded outgoing safety gate blocked affected mail tests.
- Severity: `P1`
- Why outside current scope: diagnosing or changing mail safety/application
  behavior would violate the documentation-only boundary.
- Possible next step: separately diagnose the test safety configuration and
  restore an isolated, explicitly controlled full-suite run.
- Status: `OPEN`

## FINDING-007 — Reported outbound rich-text defect

- ID: `FINDING-007`
- Date: `2026-08-30`
- Source: `Documents/28-8/PROJECT_STATUS.md`, P1 mail section.
- Description: the project status reports that editor HTML is escaped as text.
  This was not independently accepted in the current task because the
  outgoing safety gate blocked the relevant full-suite paths.
- Severity: `P1`
- Why outside current scope: implementing or changing MIME/rendering behavior
  is application work and was explicitly prohibited.
- Possible next step: authorize one offline, mock-transport HTML/plain-text
  contract task, keeping Mail.ru and live sending separate.
- Status: `OPEN`

## FINDING-008 — Unattributed `api/index.py` worktree edit

- ID: `FINDING-008`
- Date: `2026-08-30`
- Source: current `git diff -- api/index.py` and file metadata.
- Description: the worktree removes `_APP.queue.start()` from the adapter import
  path. The edit is outside this task, and its author/timing are not verified.
- Severity: `P2`
- Why outside current scope: application code cannot be edited or attributed by
  this reconciliation.
- Possible next step: owner-led review of the diff and its runtime/worker
  implications.
- Status: `OPEN`
