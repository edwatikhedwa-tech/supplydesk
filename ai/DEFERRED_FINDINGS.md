---
document_id: DEFERRED-FINDINGS-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# Deferred Findings

Only unresolved, accepted-risk, or explicitly superseded findings belong in
this current register. Resolved findings and full chronology are preserved in
[`ai/history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md`](history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md).

## FINDING-018 — `collect_inn.py --llm` imports a nonexistent symbol

- ID: `FINDING-018`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: `TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902`'s fresh reference scan
  found `collect_inn.py:217` does `from llm_fallback import InnLlmExtractor,
  api_key_present` (now `from backend.integrations.llm.llm_fallback import
  InnLlmExtractor, api_key_present`), but `llm_fallback.py` only ever
  defined `LlmExtractor`, never `InnLlmExtractor`. This predates the move —
  confirmed by checking the pre-move file content — and the move preserves
  the identical `ImportError` from the new path. The same code path's error
  message also tells the operator to set `ANTHROPIC_API_KEY`, while the
  actual `api_key_present()` checks `ROUTERAI_KEY`.
- Impact: `python collect_inn.py --llm ...` raises `ImportError` immediately
  when the `--llm` flag is used; the feature is currently non-functional.
  No test exercises this path (env/flag-gated), so nothing else would catch
  it.
- Why deferred: out of scope for a structural move task
  (`AI_CONTRACT.md` rule 5 — do not fix unrelated problems); `collect_inn.py`
  was explicitly limited to an import-line change only.
- Next verification: a separate task confirms whether `InnLlmExtractor` was
  meant to be `LlmExtractor` (or a dedicated INN-only wrapper was dropped
  during earlier work), fixes the symbol reference and the
  `ANTHROPIC_API_KEY`/`ROUTERAI_KEY` message mismatch, and adds a smoke test
  for `--llm` argument parsing that does not require a live key.

## FINDING-003 — Standard helper-script coverage is incomplete

- ID: `FINDING-003`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The canonical baseline documents the tracked operator-tool set but does not establish a complete standard helper-script catalog.
- Impact: Future agents may repeat ad-hoc inspection or use inconsistent commands.
- Why deferred: This task establishes governance; it does not add application or operator behavior.
- Next verification: Compare the required diagnostic control-plane command catalog with tracked scripts in a separately scoped task.

## FINDING-004 — Source checkout has broad pre-existing worktree changes

- ID: `FINDING-004`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical baseline records a dirty source checkout and intentionally isolates governance work in a clean control worktree.
- Impact: Source-side ownership and rollback cannot be inferred from the governance branch.
- Why deferred: Resolving ownership would require user decisions about pre-existing application changes.
- Next verification: Owner reviews source `git status`, tracked/untracked inventory, and the exact allowlist before any cleanup or merge.

## FINDING-006 — Historical published-environment backend failures

- ID: `FINDING-006`
- Severity: `MEDIUM`
- Status: `SUPERSEDED`
- Evidence: The old published audit run recorded failures, while the canonical control baseline recorded `373 passed, 1 skipped, 0 failed, 0 errors` in its controlled run.
- Impact: The old failure count must not be presented as the current control baseline or as proof of an application fix.
- Why deferred: The environments are not equivalent and this task did not rerun live backend acceptance.
- Next verification: Re-run the relevant backend-backed live routes in the approved runtime environment and compare scope explicitly.

## FINDING-008 — Unattributed source-side API edit

- ID: `FINDING-008`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical baseline records an unattributed `api/index.py` worktree edit in the source checkout.
- Impact: Ownership and deployability of the source-side API change are unknown.
- Why deferred: This task forbids application edits and cannot assign ownership to another agent.
- Next verification: Source owner identifies the change, validates it against the source HEAD, and decides whether to keep, revert, or isolate it.

## FINDING-009 — Local credential-bearing environment risk

- ID: `FINDING-009`
- Severity: `P2`
- Status: `OPEN`
- Lifecycle: `DEFERRED_SECURITY_ACTION — LOCAL_ARCHIVE_SECRET_RETENTION`
- Cleanup impact: `CLEANUP_PHASE: COMPLETE` — this deferred security action
  does not keep the recovery/cleanup phase open.
- Evidence: The canonical checkout still has no current operational
  `.env`/`.env.*` files, no tracked operational secret paths and no operational
  `.env` path in Git history. Three unique historical `.env.example` blobs were
  classified as `SAFE_TEMPLATE`. The controlled allowlist review covered 12
  snapshot `.env*` files and 12 quarantine token/auth-named artifacts: 8 were
  `REAL_SECRET_PRESENT`, 4 were `MIXED`, 6 were `EMPTY_OR_NON_SECRET`, 5 were
  `SAFE_TEMPLATE`, and 4 were `UNDETERMINED`.
- Git exposure: `NO`. The real or mixed files are retained in external
  snapshots/quarantine, outside the canonical Git repository. Five paired
  snapshot paths are identical copies across the two baseline containers;
  quarantine production OAuth state files are distinct.
- Impact: Accidental staging or publication could disclose credentials or enable external actions.
- Review result: `SECURITY_REVIEW_REQUIRED` — real and mixed secret-bearing
  material was found in local archive retention, and four binary/image artifacts
  remain `UNDETERMINED`.
- Why deferred: The review did not alter the retained files. No deletion,
  rotation, copying, external transmission or Git history rewrite was
  performed.
- Required action: `KEEP_PROTECTED` until owner approval; then
  `DELETE_AFTER_OWNER_APPROVAL` for unneeded retained copies and
  `ROTATE_CREDENTIAL` only where the owner confirms a credential is current or
  may have been exposed. `HISTORY_REWRITE_REVIEW` is not indicated because Git
  secret exposure is `NO`.
- Next verification: Owner approves retention cleanup and confirms credential
  ownership/validity; separately resolve the four `UNDETERMINED` artifacts.

## FINDING-015 — Residual repository-hygiene audit drift

- ID: `FINDING-015`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The retained audit index records remaining `AUDIT-002` through `AUDIT-011` findings.
- Impact: Repository hygiene, tooling, and source-state questions remain visible follow-up work.
- Why deferred: This task only establishes documentation ownership and retention; it must not broaden into cleanup or application repair.
- Next verification: Triage each retained audit finding in a separate task with an explicit allowlist and rollback plan.

## FINDING-017 — `checko_client.py` move blocked by an immutability protected-path list

- ID: `FINDING-017`
- Severity: `LOW`
- Status: `RESOLVED — checko_client.py moved and the immutability guard migrated
  to the new path in the same change`
- Evidence: `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902`'s fresh reference
  scan found `supplier_discovery_v2/immutability_check.py:16` hardcodes a
  repository-root-relative `"checko_client.py"` entry in its
  `protected_paths()` tuple, used to hash-verify that named files have not
  drifted. No committed/tracked `protected_manifest.json` baseline exists in
  this checkout, so nothing currently breaks, but moving `checko_client.py`
  out of root would silently drop it from future `--write-baseline` snapshots
  (the function guards each candidate with `.is_file()`) and would make any
  externally held baseline report it as `changed` on next `verify()`. This
  was not in the prior `TASK-PYTHON-ROOT-DIAGNOSTIC-20260902` reference list.
  `CLAUDE.md`'s Project layout section also names `checko_client.py` as an
  intentional root example, consistent with this being live structure, not
  an oversight.
- Impact: Moving `checko_client.py` to
  `backend/integrations/registry/checko_client.py` (the diagnostic's
  `MOVE_INTEGRATIONS` recommendation) requires either updating
  `supplier_discovery_v2/immutability_check.py`'s protected-path list or an
  explicit decision that Checko is no longer immutability-protected —
  `supplier_discovery_v2/` is out of scope for a bounded CLI/registry-move
  task, per that task's own "DO NOT TOUCH" boundary.
- Why deferred: The registry-move task moved only `dadata_client.py` (not
  referenced anywhere in `immutability_check.py`) and left `checko_client.py`
  at root rather than silently weakening an existing safety mechanism or
  reaching into a directory explicitly marked out of scope.
- Next verification (superseded by resolution below): a separate task scoped
  to touch both `checko_client.py` and
  `supplier_discovery_v2/immutability_check.py` together.
- Resolution: `TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902`
  moved `checko_client.py` to
  `backend/integrations/registry/checko_client.py` and, in the same change,
  updated `supplier_discovery_v2/immutability_check.py:protected_paths()` to
  protect the new path instead of the old root path. A fresh baseline
  generated against the moved tree verifies clean (`[]`); a disposable
  synthetic copy of the new path, mutated after baselining, is correctly
  reported as changed. `checko_client.py` was never dropped from protection
  at any point in the same commit.
- Resolution report:
  `ai/reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md`

## FINDING-016 — Frontend candidates remain review-required

- ID: `FINDING-016`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: The isolated Knip audit reported `RiskFactors.tsx`, three manual
  Playwright/Lighthouse configuration files and the direct `lighthouse`
  development dependency as candidates.
- Impact: The repository retains a small amount of potentially unused
  frontend/tooling surface; deleting it without owner review could remove a
  manual acceptance path or planned UI component.
- Why deferred: The approved Batch 2 allowlist authorized only the proven
  Python cleanup. No frontend file or dependency was deleted.
- Next verification: Owner approves a separate frontend/dependency allowlist;
  repeat clean install, reference/build analysis and full browser acceptance
  before any deletion.

