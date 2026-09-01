---
document_id: DECISIONS-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# Decisions

This is the concise current decision register. It is not an infinite event
log. Superseded and older decision prose is preserved in
[`ai/history/2026/09/DECISIONS-CHRONICLE-20260901.md`](history/2026/09/DECISIONS-CHRONICLE-20260901.md).

## DECISION-006 — One canonical current-state source

- Decision ID: `DECISION-006`
- Date: `2026-09-01`
- Status: `ACTIVE`
- Context: Multiple state-like files and old snapshots made chronology look current.
- Decision: `ai/CURRENT_STATE.md` is the only canonical current-state source.
- Reason: Agents need one short, evidence-backed state snapshot with explicit limitations.
- Consequences: Other state-like documents must be supporting, historical, task evidence, or explicitly non-canonical.
- Related requirements: `TASK-DOCUMENTATION-GOVERNANCE-20260901`, canonical baseline control contract.
- Related commits: `792f441b4b6099533177e7c1d23d6252670f9309`.

## DECISION-007 — Separate operational control from product documentation

- Decision ID: `DECISION-007`
- Date: `2026-09-01`
- Status: `ACTIVE`
- Context: AI state, task locks, audits, and product explanations were mixed across roots.
- Decision: `ai/**` owns operational control; `docs/**` owns product requirements, architecture, API, data, testing, and operations documentation.
- Reason: The two sets have different freshness, ownership, and evidence rules.
- Consequences: `docs/**` has no independent current-state source; it links to `../ai/CURRENT_STATE.md` when current context is needed.
- Related requirements: `TASK-DOCUMENTATION-GOVERNANCE-20260901`, documentation lifecycle policy.
- Related commits: `792f441b4b6099533177e7c1d23d6252670f9309`.

## DECISION-008 — Keep audit evidence remotely, retain a canonical pointer

- Decision ID: `DECISION-008`
- Date: `2026-09-01`
- Status: `ACTIVE`
- Context: The canonical branch contained a full forensic audit bundle while a dedicated audit branch already retained it.
- Decision: Keep the audit index, summary, final report, important findings, and a remote pointer in the canonical branch; remove only heavy forensic duplicates from this governance branch after remote proof.
- Reason: Reviewers retain traceability without bloating the working control branch.
- Consequences: The audit branch and history remain authoritative for raw evidence; the canonical branch records the exact ref and commit.
- Related requirements: `TASK-DOCUMENTATION-GOVERNANCE-20260901`, `ai/AUDIT_POLICY.md`.
- Related commits: `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.

## DECISION-004 — Correspondence semantics remain explicit

- Decision ID: `DECISION-004`
- Date: `2026-08-30`
- Status: `ACTIVE`
- Context: Requests, contacts, attempts, and provider acceptance are different entities.
- Decision: Documentation must keep those entities and their counts separate.
- Reason: Collapsing them creates unsafe operational claims.
- Consequences: Reports and current state must name the counted entity and evidence source.
- Related requirements: mail and campaign documentation contract.
- Related commits: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`.

## DECISION-005 — Irreversible mail actions require an explicit gate

- Decision ID: `DECISION-005`
- Date: `2026-08-30`
- Status: `ACTIVE`
- Context: Real email, SMTP/IMAP, and production data changes are irreversible or externally visible.
- Decision: No real mail action or destructive data operation is allowed without backup, dry-run, validation, and explicit owner approval.
- Reason: Documentation tasks must not turn into unreviewed external actions.
- Consequences: Live mail claims remain `NOT VERIFIED` unless a separately approved acceptance task records evidence.
- Related requirements: project security and destructive-operation rules.
- Related commits: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`.

