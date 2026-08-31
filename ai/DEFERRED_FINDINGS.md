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
## FINDING-002 — No configured Git remote (historical blocker)

- ID: `FINDING-002`
- Date: `2026-08-30`
- Source: current `git remote -v`, branch tracking metadata and
  `git ls-remote origin refs/heads/codex/TASK-STATE-CONTROL-20260830`.
- Description: the former no-remote observation is superseded. Current
  checkout has `origin`, the expected upstream branch and a matching remote
  SHA; the repository is private and exists at the confirmed owner/name.
- Severity: `P3`
- Why outside current scope: no further remote mutation is needed for this
  reconciliation; future remote changes still require owner direction.
- Possible next step: none for the current publication gate; preserve the
  evidence in the task report.
- Status: `SUPERSEDED` (current publication gate resolved)

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

## FINDING-007 — Outbound rich-text contract mismatch

- ID: `FINDING-007`
- Date: `2026-08-30`
- Source: `Documents/28-8/PROJECT_STATUS.md`, P1 mail section.
- Description: the project status reported that editor HTML is escaped as
  text. The offline audit independently reproduced this for the existing
  single/thread rich Composer through durable fields and mock-SMTP MIME.
- Severity: `P1`
- Why outside the original audit scope: implementation required a separate
  application change and explicit business choice. That choice is now recorded
  as the explicit rich HTML contract.
- Audit result: `PARTIALLY CONFIRMED` — the bulk/new and unmatched-inbox reply
  paths are plain-text inputs, while the request-thread/single rich Composer
  sends HTML through a plain-text backend field. The system-wide contract is
  mixed/implicit.
- Next step: controlled real-mailbox acceptance remains separate; no further
  code action is required for the contract mismatch.
- Status: `RESOLVED — explicit sanitized rich-HTML contract implemented`
- Report: `ai/reports/TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830-report.md`
- Resolution report:
  `ai/reports/TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831-report.md`

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

## FINDING-009 — Potential credential-bearing env files block remote preparation

- ID: `FINDING-009`
- Date: `2026-08-30`
- Source: filename/path inspection, `git check-ignore`, and path-only secret
  scan; values intentionally not recorded.
- Description: `.env`, `.env.local`, `.env.p0-backup-20260830`,
  `.env.production.local` and `.vercel/.env.preview.local` are present and
  ignored. A high-confidence credential/database-URL pattern was detected in
  `.env.production.local`.
- Severity: `P0`
- Why outside current scope: removing, editing or rotating local credentials
  still requires owner action; this reconciliation does not claim that local
  credential hygiene risk is gone.
- Possible next step: owner-led quarantine/rotation and a fresh approved-set
  security review. Local credential-bearing env files remain present and are
  intentionally not described by value here.
- Status: `SUPERSEDED` (publication gate resolved; residual local security risk
  remains `OPEN`)

## FINDING-010 — Publish set and shared branch are not approved

- ID: `FINDING-010`
- Date: `2026-08-30`
- Source: current Git status and repository lookup.
- Description: the former unapproved-publish-set/shared-branch blocker is
  superseded for the completed publication. The explicit sanitized publish
  set was committed as `85fb7a2d9ac2f3697f33c7b5f930f44adabf799e` and pushed
  to the confirmed private repository and branch. The current worktree still
  contains unrelated untracked paths, which remain outside this task.
- Severity: `P1`
- Why outside current scope: no new publish-set selection or branch mutation is
  authorized by this state reconciliation.
- Possible next step: owner-led review of any future publish set; no action is
  required for the already completed publication.
- Status: `SUPERSEDED` (current publication decision resolved)
