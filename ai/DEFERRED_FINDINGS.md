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

## FINDING-020 — No test coverage for `SupplierHandler`'s 404/SPA-fallback routing

- ID: `FINDING-020`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: While extracting `AuthHandlerMixin` from `SupplierHandler`
  (`TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903`), a search of the
  official test suite for `404`/unknown-route/SPA-fallback assertions found
  zero matches (`grep -rn "404" tests/*.py` — no results). Login/session/
  CSRF/`auth/me` ARE genuinely covered
  (`tests/test_mail_integrity.py::test_session_renews_on_activity_and_survives_repository_restart`,
  `tests/test_outgoing_safety.py::test_owner_endpoint_requires_csrf_confirmation_and_explicit_owner`,
  etc.), but the "unknown `/api/*` path returns 404" and "non-API path falls
  back to the SPA shell" behaviors in `do_GET`/`send_head`/`_serve_app_shell`
  have no direct regression test.
- Impact: A future change to `do_GET`'s fallthrough logic (e.g. reordering
  branches, changing the final `else`) could silently break the 404/SPA
  contract with no test catching it.
- Why deferred: `do_GET`/`do_POST`/`do_DELETE` and their routing logic were
  explicitly NOT touched by the auth-extraction task that found this — only
  auth-related sub-methods (`_login`, `_require_session`, etc.) were moved.
  Writing a route-matrix test for code that wasn't changed is out of that
  task's scope (`AI_CONTRACT.md` rule 5 — do not fix unrelated problems);
  the owner's own instruction for that task also explicitly said not to
  build a large route matrix without necessity.
- Next verification: A separate task adds a small number of targeted tests
  (unknown `/api/*` → 404, non-API path → SPA shell, source-like path →
  404) the next time `do_GET`'s routing is itself the subject of a change.

## FINDING-019 — `diagnostic_runner.py`'s secret scan crashes on a Cyrillic staged diff

- ID: `FINDING-019`
- Severity: `LOW`
- Status: `RESOLVED — fixed by adding explicit encoding="utf-8", errors="replace"
  to the four affected subprocess.run calls, matching the file's own
  existing correct pattern in run_process()`
- Evidence: `scripts/diagnostics/diagnostic_runner.py:secret_path_check` calls
  `subprocess.run(["git", "diff", "--cached", "--unified=0"], ...,
  capture_output=True, text=True, check=False).stdout` (line 580) without an
  explicit `encoding=`. On this Windows environment, `text=True` decodes
  the subprocess's stdout using the locale's default codepage (`cp1251`),
  not UTF-8 — but `git diff` always emits UTF-8. When the currently staged
  diff (`git diff --cached`) contains Cyrillic text (extremely common in
  this codebase's comments/docstrings/Russian identifiers), the reader
  thread hits `UnicodeDecodeError` internally and `.stdout` ends up `None`;
  `scan_staged_literal_diff` then calls `diff_text.splitlines()` on `None`
  and raises `AttributeError`. Reproduced deterministically during
  `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903` while a large,
  Cyrillic-heavy diff was staged-but-uncommitted:
  `tests.diagnostics.test_diagnostic_negative_fixtures.DiagnosticNegativeFixtureTests.test_machine_output_fields_are_present_and_safe`
  errored with exactly this traceback; the same three `subprocess.run` calls
  in the same function (lines 572, 574, 576, for `git diff --name-only`/
  `git ls-files`/`git ls-files --others`) share the same missing-`encoding`
  pattern and are equally exposed, just less likely to contain Cyrillic
  bytes in a single run.
- Impact: any contributor who runs the full local test suite
  (`scripts/run_test_suite.py`) while they happen to have a Cyrillic-containing
  diff staged-but-not-yet-committed will see this test error, indistinguishable
  at a glance from a real regression, purely because of ambient git index
  state rather than anything in the code under test.
- Why deferred: discovered incidentally while verifying
  `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903`'s regression suite
  (converting root manual test scripts to `unittest.TestCase`s); fixing a
  subprocess-encoding bug in an unrelated diagnostic tool is out of that
  task's scope (`AI_CONTRACT.md` rule 5 — do not fix unrelated problems).
  Confirmed non-blocking for that task: after the task's own changes were
  committed (clearing the git staging area), a clean rerun of
  `scripts/run_test_suite.py` returned to the established `9`-error
  `pwsh`-gap baseline with no `AttributeError`.
- Next verification (superseded by resolution below): a separate task adds
  `encoding="utf-8"` to all four `subprocess.run(..., text=True, ...)` calls
  in `secret_path_check`
  (`scripts/diagnostics/diagnostic_runner.py:572,574,576,580`), then proves
  the fix by staging a disposable Cyrillic-containing change and confirming
  `test_machine_output_fields_are_present_and_safe` passes instead of
  erroring.
- Resolution: `TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903`
  added `encoding="utf-8", errors="replace"` to the four `secret_path_check`
  calls (lines 572, 574, 576, 580) — matching the exact parameters this same
  file's own `run_process()` helper already used correctly a few lines
  above, so this was a real inconsistency, not a new pattern. Also fixed two
  more instances of the identical missing-`encoding` defect found in the
  same file while verifying the fix (`git_check`'s raw `branch`/`head`
  lookups at lines 133-134) — lower practical risk since branch names and
  commit hashes are normally ASCII, but the same root cause. Proven by
  staging this task's own Cyrillic-heavy documentation changes (this file
  and the task report) and confirming
  `test_machine_output_fields_are_present_and_safe` passes with the fix in
  place, where it previously raised `AttributeError` under the same staged
  condition.
- Resolution report:
  `ai/reports/TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903-report.md`

## FINDING-018 — `collect_inn.py --llm` imports a nonexistent symbol

- ID: `FINDING-018`
- Severity: `LOW`
- Status: `RESOLVED — fixed with a RED-to-GREEN bug-workflow proof; see resolution below`
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
- Next verification (superseded by resolution below): a separate task
  confirms whether `InnLlmExtractor` was meant to be `LlmExtractor`, fixes
  the symbol reference and the `ANTHROPIC_API_KEY`/`ROUTERAI_KEY` mismatch,
  and adds coverage for `--llm` that does not require a live key.
- History/intent check: `git log --all -S InnLlmExtractor` shows exactly one
  matching commit — the repository's initial bulk import — meaning
  `InnLlmExtractor` was never a real class anywhere in this repo's tracked
  history. `Documents/28-8/enrichment-and-cache.md` (existing product
  documentation, written independently of this finding) already recorded it
  as "осталось от версии до перехода на RouterAI" (a leftover from the
  pre-RouterAI version) and confirmed the web pipeline's own
  `_enrich_suppliers` already correctly uses `LlmExtractor`/`ROUTERAI_KEY`.
  So `LlmExtractor` is confirmed as the intended current implementation, not
  a guess.
- Resolution: `TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902` reproduced the
  bug deterministically (a behavioral reproducer calling the real
  `collect_inn.main(["...", "--llm"])` failed with the exact predicted
  `ImportError: cannot import name 'InnLlmExtractor'`, before any
  network-capable code ran), then applied the minimal fix: `collect_inn.py`
  now imports `DEFAULT_MODEL, LlmExtractor, api_key_present`, constructs
  `LlmExtractor(model=args.llm_model or DEFAULT_MODEL)` (matching the
  existing safe pattern in `scripts/collect_contacts.py`, so `--llm-model`
  never resolves to `None`), and the missing-key message now names RouterAI
  and `ROUTERAI_KEY`. The same reproducer then passed (`GREEN`) —
  `FIX_PROVEN`. No prompts, schemas, `DEFAULT_MODEL` value, or provider
  behavior changed; `0` external provider calls throughout.
- Resolution report:
  `ai/reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md`

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

