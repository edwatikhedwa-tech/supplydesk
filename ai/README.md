---
document_id: AI-README-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# AI project state

This directory is the repository-local control plane for Codex, Claude Code,
ChatGPT Project and Claude Project. The repository files are the source of
truth; an agent's chat history or report is not a substitute for reading the
current files.
Before any mutation or runtime/artifact action, run
`scripts/assert_workspace.ps1`; use `-ExpectedRoot` only for an exact
intentional worktree or CI checkout.

## Start here

Use this order for every task:

1. Repository [`AGENTS.md`](../AGENTS.md) — entrypoint and non-negotiable boundaries.
2. [`PROJECT_MANIFEST.yaml`](../PROJECT_MANIFEST.yaml) — repository map and protected paths.
3. [`CURRENT_STATE.md`](CURRENT_STATE.md) — the only canonical current-state snapshot.
4. [`VIBECODING_RULES.md`](VIBECODING_RULES.md) — the canonical AI-agent policy.
5. [`VIBECODING_TOOL_REGISTRY.yaml`](VIBECODING_TOOL_REGISTRY.yaml) — factual tool availability.
6. [`ACTIVE_TASK.md`](ACTIVE_TASK.md) — active-task lock/sentinel.
7. Relevant product documentation from [`docs/README.md`](../docs/README.md).
8. Relevant [`DECISIONS.md`](DECISIONS.md) and [`DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md).
9. Relevant dated task reports and audit evidence under [`reports/`](reports/) and [`audits/`](audits/).

Before acting, also read [`AI_CONTRACT.md`](AI_CONTRACT.md) and
[`WORKFLOW.md`](WORKFLOW.md) for evidence vocabulary and the required task
lifecycle. Read [`LAST_HANDOFF.md`](LAST_HANDOFF.md) when taking over an
unfinished or recently closed task.

The documentation freshness rule is [`../docs/DOCUMENTATION_POLICY.md`](../docs/DOCUMENTATION_POLICY.md):
update the canonical state and affected feature documentation in the same task,
and mark old snapshots as historical.

Supporting records are [`CHANGELOG.md`](CHANGELOG.md),
[`INTERACTION_LOG.md`](INTERACTION_LOG.md), [`DECISIONS.md`](DECISIONS.md),
[`DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md), and reports under
[`reports/`](reports/). Reusable task and acceptance forms are under
[`templates/`](templates/). The ChatGPT and Claude Project adapters are under
[`adapters/`](adapters/).

## Diagnostic read order

For a diagnostic or repair task, read only the relevant slice in this order:

1. [`AGENTS.md`](../AGENTS.md)
2. [`PROJECT_MANIFEST.yaml`](../PROJECT_MANIFEST.yaml)
3. [`CURRENT_STATE.md`](CURRENT_STATE.md)
4. The relevant requirement in [`docs/requirements/requirements.yaml`](../docs/requirements/requirements.yaml)
5. Its row in [`docs/requirements/TRACEABILITY_MATRIX.csv`](../docs/requirements/TRACEABILITY_MATRIX.csv)
6. The linked test in [`docs/testing/TEST_CATALOG.yaml`](../docs/testing/TEST_CATALOG.yaml)
7. The linked failure mode in [`docs/operations/failure_modes.yaml`](../docs/operations/failure_modes.yaml)
8. The linked runbook under [`docs/operations/runbooks/`](../docs/operations/runbooks/)

Do not use historical reports as a substitute for the current state.

## Update order

Read the start sequence → audit evidence → record a durable decision when
needed → implement the smallest allowed change → run acceptance checks → write
a report → update state and handoff → run the validators → commit. The
validators are read-only.

## Access boundary

These files do not grant ChatGPT Project or Claude Project access to this
repository. They only define what to do after the relevant files are actually
connected or uploaded.
