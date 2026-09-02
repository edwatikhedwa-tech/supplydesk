# Workflow

The mandatory lifecycle is:

`AUDIT → DESIGN DECISION → IMPLEMENT → ACCEPTANCE → CLOSE → UPDATE STATE → COMMIT`

Skipping a stage requires an explicit `NOT NEEDED` or `BLOCKED` reason in the
handoff.

## Preflight levels

The first step is selected by session state, not repeated by every message:

- A new agent session performs `SESSION PREFLIGHT` once: project identity,
  instructions, policy, relevant state, required environment facts and
  available tools.
- A new independent task in a healthy session performs a cheap `TASK
  PREFLIGHT`: workspace guard, branch, HEAD, status, active-task/conflict,
  classification and verification profile.
- A continuation of the current task performs only the next
  action-specific check.

Revalidate the session only after a workspace or Git-root change, material
environment change, relevant instruction change, explicit context reset or
loss of trustworthy session state. The canonical details and exception cases
are in [`ai/VIBECODING_RULES.md`](VIBECODING_RULES.md).

## AUDIT

Inspect the actual checkout without editing it. Use the existing Session
Preflight or cheap Task Preflight according to session state, then check the
branch, commit, working tree, relevant files, runtime, commands, tests and
known constraints. Read only the relevant state files when the session context
is already trusted. Find the root cause for diagnostic tasks, identify
unknowns, and list the smallest set of affected files.

## DESIGN DECISION

Choose the minimal solution. Record the Task ID, scope, non-goals, risks,
compatibility assumptions, evidence classes and what is deliberately not being
changed. Resolve contradictions explicitly; never choose silently between
conflicting sources.

## IMPLEMENT

Change only the approved scope. Preserve unrelated behaviour, avoid new
dependencies, and use targeted tests. For a state/documentation iteration,
application files, migrations, database data and production settings are
non-goals.

### Documentation freshness rule

Documentation is part of the deliverable, not a later cleanup step. When a
task changes product behaviour, data, providers, deployment, tests, limits or
workflow terminology, update the affected documentation in the same task and
commit. `ai/CURRENT_STATE.md` is the only current-state source. Dated audits
and old snapshots remain useful evidence only when they are explicitly marked
`HISTORICAL — NOT CURRENT` and link to the current state.

## ACCEPTANCE

Independently check the changed artifact at the level of risk. For a web task,
check the intended URL and port, current build, API endpoint, user scenario,
empty/error states, reload, repeated action and regressions. For documentation,
run the read-only state validator, check Markdown links, required sections,
timestamps, secret patterns, instruction references and the Git diff. Record
evidence and limitations.

For documentation changes also verify that no edited document calls an old
number, capability or provider state current; check relative Markdown links,
timestamps, evidence labels and secret patterns. Run the state validator and
`git diff --check` before closeout.

## CLOSE

Write a concise handoff and a detailed report under `ai/reports/`. Append the
substantial action to `CHANGELOG.md` and the interaction to
`INTERACTION_LOG.md`. Set `ACTIVE_TASK.md` to an explicit idle sentinel after
the task is complete. Report failures and blockers; do not hide them behind a
success label.

## UPDATE STATE

Update `CURRENT_STATE.md` with the last confirmed facts, current branch and
working-tree status. Use `NOT VERIFIED` for unknown runtime or external values.
Update `LAST_HANDOFF.md` with exact changed files, evidence, non-goals,
unverified items, rollback and one next rational step.

## COMMIT and push protocol

- One substantial iteration has one Task ID.
- Use a separate branch when possible.
- Stage only files in the approved scope.
- The commit subject contains the Task ID, for example
  `TASK-003: document state contract`.
- Report commit, branch, working-tree status and push status after commit.
- Push only when a configured remote exists and the user has authorized it.
- Never force-push or merge `main`/`master` automatically.
- If a check fails or is blocked, do not merge; preserve the report and name
  the next step.
