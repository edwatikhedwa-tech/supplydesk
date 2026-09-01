---
document_id: TASK-DOCUMENTATION-GOVERNANCE-RECONCILIATION-20260901
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# Documentation Governance Reconciliation — Pre-change Audit

## Scope

This is the temporary, pre-change reconciliation record for `TASK-DOCUMENTATION-GOVERNANCE-20260901`. It audits documentation and state files in the governance worktree before any documentation changes. Application code, database files, runtime state, mail data, migrations, and frontend assets are out of scope.

The worktree is based on `control/canonical-baseline-20260901` at `792f441b4b6099533177e7c1d23d6252670f9309`. The product/source HEAD recorded by the canonical baseline is `c076e1be385c3ae6da2716159e1f46fc2fce23d7`.

## Inventory result

- Scoped formats: Markdown, YAML, YML, and JSON.
- Exclusions: `node_modules`, vendor/cache/generated paths, and frontend build output.
- Scoped documents: 124.
- Current-looking by filename or content: 75.
- Root historical/task reports requiring relocation: 11.
- Candidate canonical state files: `ai/CURRENT_STATE.md` and `docs/CURRENT_STATE.md`.
- No application files were changed before this report.

## Classification

| Classification | Meaning | Pre-change examples | Required treatment |
|---|---|---|---|
| `CANONICAL_CURRENT` | The one authoritative current project state | `ai/CURRENT_STATE.md` | Rebuild as a short current snapshot |
| `CURRENT_SUPPORTING` | Current control or product guidance that is not the state source | `PROJECT_MANIFEST.yaml`, `ai/AI_CONTRACT.md`, `ai/WORKFLOW.md`, `docs/ENGINEERING_CONTRACT.md` | Mark ownership and link to canonical state |
| `HISTORICAL` | Superseded chronology or captured past state | `docs/CURRENT_STATE.md`, `docs/WORK_LOG.md`, `Documents/28-8/**` | Mark non-canonical and preserve |
| `AUDIT_EVIDENCE` | Evidence produced by a repository or runtime audit | `ai/audits/2026-09-01-repository-hygiene/**` | Keep a compact canonical pointer; retain evidence remotely |
| `TASK_REPORT` | Result or plan for a completed task | `ai/reports/**`, the 11 root reports | Keep in task-report/history locations, never as current state |
| `PORTFOLIO_FUTURE` | Future/portfolio material without current implementation authority | Portfolio and future-facing documents found by content review | Keep separate from current state and do not use as implementation evidence |
| `ARCHIVE` | Retained material no longer needed in the canonical working branch | Large forensic audit artifacts after remote retention proof | Remove only from this governance branch after remote proof |
| `CONFLICTING` | Two sources make incompatible current claims | Mixed chronology inside the existing AI state/log documents | Resolve by precedence and record the decision |
| `UNKNOWN` | Ownership or currentness cannot be proved | External Neon skill files, `keywords.txt`, root `run_probe.py` in source checkout | Do not delete or promote; leave explicitly flagged |

## Contradictions found

1. `ai/CURRENT_STATE.md` is named canonical but contains historical task chronology and multiple prior “current” snapshots. It is a source-structure conflict, not evidence that the product has multiple runtime states.
2. `docs/CURRENT_STATE.md` has a historical banner and links to `ai/CURRENT_STATE.md`, but its filename can be mistaken for a second current state. It must remain explicitly non-canonical.
3. `ai/ACTIVE_TASK.md`, `ai/LAST_HANDOFF.md`, `ai/DECISIONS.md`, and `ai/DEFERRED_FINDINGS.md` mix current control data with old task chronology. Their current sections need compact replacements; the old content must remain historical evidence.
4. Eleven root reports are dated 2026-08-28/29 and describe completed or captured iterations. Their root placement makes them look operationally current; they must move under `ai/history/2026/08/` with historical metadata.
5. The canonical branch contains a full copy of repository-hygiene forensic artifacts even though the audit branch already retains them. A retention pointer plus selected summaries is sufficient for the working branch; heavy raw artifacts can be removed from this new branch after the remote proof recorded below.

## Remote audit retention proof

Read-only remote checks completed before this reconciliation:

- `refs/heads/audit/repository-hygiene-reports-20260901` resolves to `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.
- The audit commit tree contains `ai/audits/2026-09-01-repository-hygiene/AUDIT_INDEX.md`, `AUDIT_SUMMARY.json`, `FINAL_REPORT.md`, `FUNCTIONAL_BASELINE.md`, and `SECURITY_FINDINGS.md`.
- GitHub Contents API successfully read `AUDIT_INDEX.md` at that branch (size 7983 bytes).
- `control/canonical-baseline-20260901` resolves remotely to `792f441b4b6099533177e7c1d23d6252670f9309`.

The audit branch and its history are not in scope for deletion or rewriting. Any forensic cleanup below applies only to the new documentation-governance branch.

## Unknown review register

The following source-checkout local-only artifacts were inspected separately and are not promoted by this task:

| Path | Classification | Evidence | Action |
|---|---|---|---|
| `.agents/skills/neon/SKILL.md` | `UNKNOWN` / local-only | External Neon skill text; historical Git presence; no current application owner proven | Leave untracked; do not add |
| `keywords.txt` | `UNKNOWN` / local-only | Historical references in old parser documentation; no current canonical runtime owner proven | Leave untracked; do not add |
| `run_probe.py` | `UNKNOWN` / local-only | Predecessor of tracked `supplier_source_tests/run_probe.py`; hashes differ and source-specific logic is missing | Leave untracked; do not delete |

`skills-lock.json` references the Neon skill path, but that lock reference does not prove that the local untracked skill is part of the current product. It remains an explicit review item.

## Reconciliation decision

The governance branch will make `ai/CURRENT_STATE.md` the only canonical current-state document, preserve old state and task chronology in dated history, keep `ai/**` as operational control documentation, keep `docs/**` as product documentation, and use an executable read-only documentation validator to enforce this boundary. No application behavior is changed.

