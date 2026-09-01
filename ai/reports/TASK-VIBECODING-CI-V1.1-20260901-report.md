# SupplyDesk VibeCoding CI V1.1

Task ID: `TASK-VIBECODING-CI-V1.1-20260901`

## Result

- STATUS: `PARTIAL` — local implementation and gates pass; the required remote
  FULL run is pending publication of this branch.
- BASE SHA: `9d3e58232230b276396f3bc127e2d937bed8482d`
- FINAL SHA: `NOT_VERIFIED` until the closeout commit is published
- POLICY: `1.1`
- LAST_CORRECTED: `2026-09-01`
- PRODUCT CODE CHANGED: `NO`
- REAL SMTP: `NO`
- REAL IMAP: `NO`
- REAL EMAIL: `NO`
- PRODUCTION DB: `NO`
- PRODUCTION SECRETS: `NO`

The task is classified as `INFRA_CONTROL_CHANGE` and `HIGH` risk because it
changes CI infrastructure. No product behavior, UI, API, database, migrations,
mail data, legacy workspace, quarantine or unrelated dependency was changed.

## CI architecture

One workflow, `.github/workflows/ci.yml`, uses these stable job names:

1. `SupplyDesk / Fast Control`
2. `SupplyDesk / Change Classification`
3. `SupplyDesk / Backend`
4. `SupplyDesk / Frontend`
5. `SupplyDesk / Browser`
6. `SupplyDesk / Full Control`

`FAST` runs first. Relevant expensive jobs wait for its success and run in
parallel where possible. Pushes normally use FAST and classifier-selected jobs;
pull requests run FAST plus relevant full jobs; manual dispatch can choose
`FAST` or `FULL`. Concurrency cancels obsolete runs for the same ref.

The workflow uses clean `windows-latest` runners, `contents: read`, official
GitHub actions with pinned major tags, bounded timeouts, and pip/npm caches.
It does not use `pull_request_target`, production credentials, private `.env`,
local databases, mail data or quarantine.

Immutable action SHA pinning was not introduced in V1.1; the workflow records
this as a limitation for a later security-hardening task.

## Fast and risk model

- FAST target: approximately 1–5 minutes, as an engineering target rather than
  an artificial gate.
- FOCUSED: changed-behavior checks selected locally by the agent.
- FULL: pull request, high-risk, release, uncertain-blast-radius and explicit
  manual acceptance.
- PERIODIC: expensive analysis outside blocking FAST CI.
- Risks: `LOW`, `NORMAL`, `HIGH`.
- 90% FAST/FOCUSED usage is an operational target, not an automated gate.

## Change classifier

`PASS` locally. `scripts/ci/classify_changes.ps1` reads the actual path mapping
from `scripts/ci/change_groups.json` and emits `docs_only`, `backend`,
`frontend`, `browser`, `high_risk`, `control`, `unknown` and `full_required`.
Four classifier tests cover docs-only, normal backend, CI/high-risk and unknown
path cases. No LLM or third-party changed-files action is used.

## Local acceptance

- VibeCoding validator: `PASS`, 34 registry entries.
- Diagnostic/control tests: `34/34 PASS`.
- Documentation validator: `PASS`.
- State validator: `PASS`.
- Traceability validator: `PASS`.
- Doctor Plan: `PASS`, exit `0`.
- `git diff --check`: `PASS`.
- Staging security inspection: `PASS`; protected paths and staged paths are
  both zero.
- Full backend/frontend/browser local acceptance: `NOT_NEEDED` for this CI
  implementation task; the required independent remote FULL run is the
  acceptance evidence for those jobs.

## Remote acceptance

- REMOTE FAST: `NOT_VERIFIED` — pending first workflow run.
- REMOTE BACKEND: `NOT_VERIFIED` — pending first workflow run.
- REMOTE FRONTEND: `NOT_VERIFIED` — pending first workflow run.
- REMOTE BROWSER: `NOT_VERIFIED` — pending first workflow run.
- REMOTE DOCTOR: `NOT_VERIFIED` — pending first workflow run.
- REMOTE RUN VERIFIED: `NO` — workflow must be pushed and manually dispatched
  with `profile=FULL`, then each job conclusion and duration must be recorded.
- BRANCH PROTECTION: `NOT_VERIFIED`; it is not enabled by this task.

GitHub Actions remains `NOT_VERIFIED` in the tool registry until the remote run
passes and its result is independently read. Periodic tools are not part of
blocking CI V1.1.

## CI minute optimizations

- concurrency cancellation removes obsolete in-progress runs;
- clean pip/npm caches avoid rebuilding downloaded packages while preserving
  clean installs;
- changed-path classification avoids irrelevant full jobs on ordinary pushes;
- expensive jobs wait for FAST and run in parallel when selected;
- periodic analysis is not forced into every iteration.

## Next

Run one explicit remote FULL profile, record the workflow/run IDs, commit SHA,
job conclusions and observed durations, then update the registry and closeout
state. Phase 1 tooling remains a separate follow-up: pre-commit, Ruff,
Pyright, Gitleaks and a coverage baseline.
