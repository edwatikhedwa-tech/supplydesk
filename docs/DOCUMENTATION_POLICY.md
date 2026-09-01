---
document_id: DOCUMENTATION-POLICY-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# Documentation policy

## Purpose

This policy defines which repository documents are operational control, which
are product documentation, how documents age, and what must be updated when a
task changes a source of truth.

## Ownership boundary

- `ai/**` is the operational control plane: current state, active-task lock,
  handoff, decisions, deferred findings, audits, task reports, and later
  incident records.
- `docs/**` is product documentation: product context, requirements,
  architecture, data, API, testing, and operations.
- `ai/CURRENT_STATE.md` is the only canonical current-state source. `docs/**`
  must not create a second current-state file or duplicate live counts.
- `PROJECT_MANIFEST.yaml` is the compact project map and points to these
  boundaries; it does not replace the current state or product documents.

## Lifecycle

Every important operational or product document has a small metadata block with
`document_id`, `status`, `canonical`, `owner`, `updated_at`, and a commit
anchor. Historical or immutable records may use `source_commit`; current state
and handoff documents should use `based_on_commit` for the functional baseline
they describe. The commit that publishes the document is already authoritative
in Git history, so current documents must not pretend that their own publication
commit is the functional source commit.
The allowed lifecycle statuses are:

- `DRAFT` — proposed and not authoritative.
- `CURRENT` — maintained for the present process or product contract.
- `SUPERSEDED` — replaced by a newer document, with the replacement linked.
- `HISTORICAL` — retained chronology or evidence; never current authority.
- `ARCHIVED` — deliberately retained at a dated or remote location and not
  part of the active working set.

`canonical: true` is reserved for the one `ai/CURRENT_STATE.md` file. A policy,
index, task lock, decision register, audit pointer, or product document may be
`CURRENT` while remaining `canonical: false`.

## Naming and placement

- Use stable descriptive names for current documents and date/task IDs for
  reports, audits, and preserved chronology.
- Put operational records under `ai/`; put product explanations under the
  relevant `docs/` domain directory.
- Put superseded chronology under `ai/history/YYYY/MM/` or the dedicated remote
  audit branch. Do not leave dated task reports at repository root when they
  are not project entrypoints.
- A historical file must state `status: HISTORICAL` (or `ARCHIVED` where
  appropriate), `canonical: false`, and link to current authority when a local
  link is practical.

## Current-state precedence

When documents disagree, use this order: current code/schema/runtime evidence;
`ai/CURRENT_STATE.md`; current decisions/deferred findings and handoff; current
domain documentation; historical reports and audits. A historical report can
prove what was observed then, but cannot prove that the same fact is true now.
Unverified values must be labeled `NOT VERIFIED`.

## Update rules

If a task changes application/API/frontend behavior, database schema or
migrations, runtime/deployment, test contracts, user workflow, or a current
operational fact, the task must check documentation impact and update the
affected current documents in the same task. At minimum:

- record `DOC_IMPACT=YES` or `DOC_IMPACT=NO` in the task report;
- update `ai/CURRENT_STATE.md` when current project facts change;
- update the relevant `docs/**` contract when product behavior or requirements
  change;
- update `ai/DECISIONS.md` when a durable design/control choice is made;
- update `ai/DEFERRED_FINDINGS.md` when unresolved risk or verification debt is
  created or closed;
- add append-only entries to `ai/CHANGELOG.md` and `ai/INTERACTION_LOG.md` for
  substantial work;
- retain evidence in a dated task report or audit pointer.

For a documentation-only task, `DOC_IMPACT=NO` is valid when the change only
clarifies ownership, lifecycle, placement, or historical labeling and does not
alter a product contract.

## Task documentation definition of done

A task may close only when all applicable items are true:

- `CODE PASS`: changed code is formatted/checked, or `N/A` for documentation-only work;
- `TESTS PASS`: relevant tests or validators pass, or the report states exactly what was not rerun and why;
- `DOC_IMPACT=YES/NO` is explicit;
- relevant product and operational documents are updated or the report records why no update is needed;
- `ai/CURRENT_STATE.md` is current when project facts changed;
- durable choices are in `ai/DECISIONS.md`;
- unresolved verification debt is in `ai/DEFERRED_FINDINGS.md`;
- task/audit traceability identifies source commit, changed scope, evidence, and limitations;
- links, metadata, secrets, and forbidden application/data changes are checked.

Cosmetic wording or formatting alone is not a reason to rewrite unrelated
documents. The goal is truthful, navigable, reversible documentation.

## Audit retention

Keep a compact audit pointer and important summaries in the canonical branch.
Keep large forensic inventories, raw logs, screenshots, traces, and generated
tool output on the dedicated audit branch after verifying its exact ref and
commit. Never delete or rewrite that branch as part of documentation cleanup.
See [`ai/AUDIT_POLICY.md`](../ai/AUDIT_POLICY.md).

## Acceptance and rollback

Before closing, run `python ai/tools/validate_docs.py`,
`python ai/tools/validate_state.py`, and `git diff --check`; reread changed
documents and inspect the changed-file allowlist. A documentation change is
reversible by reverting its task commit(s); audit history, application code,
database, mail data, and migrations are not modified by this policy.
