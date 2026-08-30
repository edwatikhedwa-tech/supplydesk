# AI project state

This directory is the repository-local control plane for Codex, Claude Code,
ChatGPT Project and Claude Project. The repository files are the source of
truth; an agent's chat history or report is not a substitute for reading the
current files.

## Start here

1. [`AI_CONTRACT.md`](AI_CONTRACT.md) — shared rules and evidence statuses.
2. [`WORKFLOW.md`](WORKFLOW.md) — required task lifecycle.
3. [`CURRENT_STATE.md`](CURRENT_STATE.md) — latest confirmed snapshot.
4. [`LAST_HANDOFF.md`](LAST_HANDOFF.md) — latest transfer note.
5. [`ACTIVE_TASK.md`](ACTIVE_TASK.md) — active-task lock/sentinel.

Supporting records are [`CHANGELOG.md`](CHANGELOG.md),
[`INTERACTION_LOG.md`](INTERACTION_LOG.md), [`DECISIONS.md`](DECISIONS.md),
[`DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md), and reports under
[`reports/`](reports/). Reusable task and acceptance forms are under
[`templates/`](templates/). The ChatGPT and Claude Project adapters are under
[`adapters/`](adapters/).

## Update order

Read state → audit evidence → record a design decision → implement the smallest
allowed change → run acceptance checks → write a report → update state and
handoff → run the validator → commit. The validator is read-only.

## Access boundary

These files do not grant ChatGPT Project or Claude Project access to this
repository. They only define what to do after the relevant files are actually
connected or uploaded.
