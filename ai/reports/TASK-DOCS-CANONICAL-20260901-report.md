# Documentation canonicalization report — 2026-09-01

Task ID: TASK-DOCS-CANONICAL-20260901
Mode: documentation reconciliation and process rule
Status: COMPLETE LOCALLY
Date: 2026-09-01, Europe/Volgograd

## Goal

Remove ambiguity between current-state documents and historical audit records, and
make documentation freshness a permanent project rule without changing product
logic or data.

## Canonical decision

The only current-state source is ai/CURRENT_STATE.md. Current facts must be
verified against code, schema, runtime, read-only database data or tests.
Documents in docs/ and Documents/28-8/ are supporting architecture, decisions,
procedures or historical audits. They cannot override the canonical state.

A historical snapshot is retained when useful, but its header must say
HISTORICAL — NOT CURRENT and link to ai/CURRENT_STATE.md.

## Changes made

- Added docs/DOCUMENTATION_POLICY.md with source priority, same-task update rule,
  evidence vocabulary, link/secret/state acceptance checks and rollback.
- Added the freshness rule to AGENTS.md, ai/AI_CONTRACT.md,
  ai/WORKFLOW.md and docs/ENGINEERING_CONTRACT.md.
- Recorded the decision in ai/DECISIONS.md.
- Marked docs/CURRENT_STATE.md and docs/DECISIONS.md as supporting/historical;
  preserved their old contents for traceability.
- Added a current-state reconciliation entry to docs/WORK_LOG.md.
- Marked the Documents/28-8 catalog and all of its existing Markdown entry
  points as historical/supporting or procedure-reference documents; updated
  their navigation to the canonical state.
- Updated ai/README.md and Documents/28-8/INDEX.md so a new agent starts at the
  canonical state and policy.
- Kept application code, frontend code, API, database rows, migrations, mail
  settings, deployment configuration and external services unchanged.
- Created reversible backups in Temp/20260901-docs-canonical/.

## Reconciled facts

The current read-only snapshot recorded in ai/CURRENT_STATE.md is authoritative.
For request 1059 it records 171 relevant supplier links and outbound statuses
sent=125, failed=4, delivery_unknown=2, cancelled=82, queued=0, with outgoing
disabled. Older values in docs/WORK_LOG.md and docs/CURRENT_STATE.md are now
explicitly historical and cannot be mistaken for current counts.

## Acceptance evidence

- Current branch and HEAD checked before edits.
- Existing worktree changes inventoried and preserved; unrelated files were not
  staged.
- State files were backed up before modification.
- 116 relative navigation links in changed documentation were checked.
- The state validator passed.
- git diff --check passed.
- Changed-document secret-pattern review found no new credentials, tokens,
  cookies, authorization headers or environment values.
- No application/build/runtime test was required because this iteration changes
  documentation and process rules only; the previously verified runtime remained
  unchanged.

## Not verified

- Provider delivery, PostgreSQL/Neon deployment and Vercel production health were
  not rerun because they are outside this documentation-only scope.
- This task does not claim that old historical test results or provider evidence
  have become current; those remain labelled by date and evidence status.
- The pre-existing broad dirty worktree remains and was not cleaned.

## Rollback

Revert the commit for this Task ID, or restore the backups from
Temp/20260901-docs-canonical/. No application or data rollback is required.
