---
document_id: AUDIT-POLICY-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# Audit retention policy

## Purpose

Repository and runtime audits produce two kinds of material: a small review
record needed in the canonical control branch, and potentially large forensic
evidence needed for reproducibility. This policy keeps those responsibilities
separate without deleting audit history.

## Canonical branch retention

The canonical branch keeps:

- `ai/audits/2026-09-01-repository-hygiene/README.md` as the remote pointer;
- `AUDIT_INDEX.md`, `AUDIT_SUMMARY.json`, and `FINAL_REPORT.md`;
- important decision and finding summaries such as `FUNCTIONAL_BASELINE.md`,
  `SECURITY_FINDINGS.md`, and `SQLITE_CONSISTENCY.md` when they are needed for
  current control decisions.

The canonical branch does not need a second copy of every raw inventory,
screenshot, trace, tool output, generated route report, or forensic CSV when
the dedicated audit branch retains them.

## Remote audit retention

- Audit branch: `audit/repository-hygiene-reports-20260901`.
- Audit commit: `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.
- Source HEAD audited: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`.
- The audit branch is not deleted, force-pushed, rewritten, or cleaned by this
  task. Its tree remains the source for raw forensic evidence.

Before removing a heavy duplicate from a new governance branch, verify the
remote ref and the exact path at the retained audit commit. Record the proof in
the reconciliation or final report. If remote retention cannot be proved,
defer removal.

## Lifecycle

Audit evidence uses the normal document lifecycle metadata. The pointer and
selected summaries may be `CURRENT` with `canonical: false`; old evidence is
`HISTORICAL` or `ARCHIVED`. “Archived” means retained at a deliberate remote or
dated location, not deleted.

