---
document_id: STATE-001
status: CURRENT
canonical: true
owner: project-control
updated_at: 2026-09-03
based_on_commit: 0efbdaf
---

# Current State

This file is the only canonical current-state source for SupplyDesk. It is a
short evidence snapshot, not a task diary. Older snapshots and chronology are
preserved under [`ai/history/`](history/).

## Last update

`2026-09-03` — `TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903` (Pass 3
of the composition-entrypoint program, batch A of `SupplierHandler`
decomposition): 16 auth/session/OAuth handler methods (`_login`,
`_auth_me`, `_require_session`, `_require_csrf`, `_oauth_start`,
`_oauth_callback`, etc.) moved from `SupplierHandler` into
[`backend/http_auth.py`](../backend/http_auth.py) as `AuthHandlerMixin`;
`class SupplierHandler(AuthHandlerMixin, SimpleHTTPRequestHandler)`
composes it in. `do_GET`/`do_POST`/`do_DELETE` and their route ordering
were deliberately left untouched — no dispatch-table conversion was
attempted (`DISPATCH_TABLE: DEFERRED`, pending batches B/C). `supplier_app.py`:
`1364` → `1185` lines. Recorded `FINDING-020` (no test coverage for
404/SPA-fallback routing, found incidentally, out of this pass's scope
since `do_GET` wasn't touched). Official suite: `497 tests, failures=0,
errors=9` (established baseline), `skipped=1`. The task report is
[`ai/reports/TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903-report.md`](reports/TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-MAIL-REPOSITORY-DB-COMPAT-EXTRACT-20260903`
(Pass 1 of splitting `mail/repository.py` by responsibility, per its own
read-only structural audit): the SQLite/Postgres DB-API compatibility shim
(`ManagedConnection`, `CompatRow`, `_postgres_row_factory`,
`_adapt_postgres_sql`, `PostgresCursor`, `PostgresConnection`,
`_postgres_migration_sql`) moved to
[`mail/db_compat.py`](../mail/db_compat.py); `mail/repository.py` shrank
from `8928` to `8816` lines. No external consumer ever referenced these
names directly (grep-confirmed), so no re-export was needed.
`utc_now`/`iso_now`/`iso_after` deliberately stayed in `mail/repository.py`
— they're generic time helpers, not DB-compat, and `mail/queue.py` plus 3
test files import them directly. Official suite: `497 tests, failures=0,
errors=9` (established baseline), `skipped=1`. The task report is
[`ai/reports/TASK-BOUNDED-MAIL-REPOSITORY-DB-COMPAT-EXTRACT-20260903-report.md`](reports/TASK-BOUNDED-MAIL-REPOSITORY-DB-COMPAT-EXTRACT-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903`
(Pass 2 of the composition-entrypoint program): the ~1000-line enrichment
pipeline (SERP→crawl→registry→web→finance retry stages, `_enrich_one` and
17 related methods) moved from `SupplierApp` into
[`backend/domain/supplier_enrichment/orchestrator.py`](../backend/domain/supplier_enrichment/orchestrator.py)
as `EnrichmentOrchestratorMixin`; `SupplierApp` composes it via
inheritance, so every method still resolves `self.repository`/
`self.service`/`self.llm_*` exactly as before. Fixed one direct causal
regression:
`tests/diagnostics/test_llm_integration_move.py`'s `CONSUMERS` map asserted
the LLM import lived in `supplier_app.py`'s own source text; updated to
point at the new orchestrator module. Official suite: `497 tests,
failures=0, errors=9` (established baseline), `skipped=1`; immutability
guard `13/13 PASS` (protected paths unaffected — this pass moved code
within a file, not a protected root path). The task report is
[`ai/reports/TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903-report.md`](reports/TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903` (Pass 1
of an owner-directed program to turn `supplier_app.py` into a thin
composition entrypoint and split `mail/repository.py` by responsibility,
following two read-only structural audits): `Config`, env-parsing helpers,
`load_dotenv`, `yandex_provider_factory` moved to
[`backend/app_config.py`](../backend/app_config.py); `FRONTEND_DIST`,
`_looks_like_source_path`, `load_fixture_data` moved to
[`backend/http_static.py`](../backend/http_static.py). All names remain
importable from `supplier_app` (re-export), so `api/index.py` and operator
scripts are unaffected. Incidentally found and fixed a local-environment-only
`nh3` DLL load failure (unrelated to this change — reproduced with a bare
`import nh3`) by reinstalling the package (`0.3.6` → `0.3.7`, both satisfy
`requirements.txt`'s `nh3>=0.3,<0.4`); no dependency version change, no
system/security setting touched. Official suite: `497 tests, failures=0,
errors=9` (established baseline), `skipped=1`. `supplier_discovery_v2`
stays an isolated pilot per explicit owner decision; `FINDING-009` stays out
of scope pending a separate owner-approved security task. The task report is
[`ai/reports/TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903-report.md`](reports/TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903-report.md).

`2026-09-03` — `TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903`
fixed `FINDING-019`: `scripts/diagnostics/diagnostic_runner.py`'s
`secret_path_check` called `subprocess.run(..., text=True, ...)` without an
explicit `encoding=` on four `git diff`/`git ls-files` calls; on Windows
this decoded stdout with the locale codepage (`cp1251`) instead of UTF-8,
crashing with `AttributeError` whenever the ambient staged diff contained
Cyrillic text. Fixed by adding `encoding="utf-8", errors="replace"`,
matching this same file's own already-correct `run_process()` helper. Two
more instances of the identical defect (`git_check`'s branch/HEAD lookup)
were found and fixed while verifying. Proven on a real repro, not a
synthetic stand-in: this task's own Cyrillic-heavy documentation changes
were staged alongside the fix, confirmed to break `cp1251` decoding, and
`tests.diagnostics.test_diagnostic_negative_fixtures...test_machine_output_fields_are_present_and_safe`
passed under that exact condition. Official suite: `497 tests, failures=0,
errors=9` (established baseline), `skipped=1`. The task report is
[`ai/reports/TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903-report.md`](reports/TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903` (Pass 11,
final pass of the root refactor program) converted the four root manual
check scripts (`test_extractor.py`, `test_inn.py`, `test_parser.py`,
`test_verify.py` — custom `check()`/`main()` scripts never discovered by
`scripts/run_test_suite.py`) into real `unittest.TestCase`s under
[`tests/legacy/`](../tests/legacy/), per explicit owner decision (asked
alongside the `serp_parser.py` decision — the diagnostic had explicitly
deferred both to the owner). Every `check(name, actual, expected)` call
became `self._check(name, actual, expected)` (a `subTest`+`assertEqual`
wrapper); a line-by-line diff of all 186 call sites across the four files
confirmed exact 1:1 parity before the root files were deleted — no coverage
lost, no assertion logic rewritten. `tests/legacy/` needed no runner change:
`scripts/run_test_suite.py`'s existing recursive `unittest.discover` over
`tests/` picked it up automatically (verified: `tests.legacy.test_extractor`
etc. appear in the official run's verbose output). Incidentally discovered
and deferred (not fixed) `FINDING-019`: a missing `encoding="utf-8"` on
`diagnostic_runner.py`'s `subprocess.run(["git","diff",...])` calls crashes
`secret_path_check` when the ambient staged diff contains Cyrillic text —
confirmed non-blocking for this task (the error was present only while this
task's own large Cyrillic diff was staged-but-uncommitted; it disappeared
on a clean rerun after committing). This closes the multi-pass root
refactor program (Passes 2-11); `supplier_app.py`/`api/index.py` remain the
only intentionally-unmoved root Python, per `KEEP_ROOT`. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903`
(Pass 10) moved `serp_parser.py` to
[`backend/integrations/search/serp_parser.py`](../backend/integrations/search/serp_parser.py),
per explicit owner decision (asked because the diagnostic had flagged this
file as conflicting with `supplier_discovery_v2/xmlriver_subprocess.py`'s
hardcoded subprocess path and the Vercel deployment boundary — a genuine
architectural tension the diagnostic deliberately left to the owner, not a
technical unknown). A thin root `serp_parser.py` compatibility wrapper
(delegating only `main()`, same pattern as `collect_contacts.py`'s) keeps
the documented `python serp_parser.py ...` invocation working — proven
byte-for-byte identical `--help` output against the pre-move commit.
`xmlriver_subprocess.py`'s hardcoded default `parser_path` was updated to
the new canonical location (verified: the default now resolves to an
existing file). The module's own `load_dotenv(Path(__file__).with_name(".env"))`
call — which would have silently started looking for `.env` beside the new
nested path instead of the repo root — was fixed to a `REPO_ROOT`-relative
lookup, reusing the exact pattern Pass 2 already proved for
`collect_contacts.py`. 7 confirmed consumers were updated to the canonical
import path: `supplier_app.py`, `collect_inn.py`,
`scripts/collect_contacts.py`, `benchmarks/benchmark_models.py`,
`backend/integrations/search/web_lookup.py`,
`backend/domain/supplier_identity/email_extractor.py` (lazy import),
`test_parser.py`. `supplier_discovery_v2/immutability_check.py`'s
protected-path list was migrated in the same change; the unprotected root
wrapper carries no logic to drift. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903`
(Pass 9) split `collect_inn.py`'s reusable deterministic ИНН/ОГРН parsing
(`INN_URL_HINTS`, `INN_PATHS`, `page_text`, `extract_for_site`,
`extract_legal_ids_for_site`) into
[`backend/domain/supplier_enrichment/pipeline.py`](../backend/domain/supplier_enrichment/pipeline.py).
`collect_inn.py` stays at root as the thinned CLI (argument parsing, the
crawl/LLM/web/DaData orchestration in `main()`, CSV output), importing the
extracted functions back — verified identical objects (`collect_inn.extract_for_site
is pipeline.extract_for_site`), not copies. This is the first pass in the
series that required an actual code split rather than a pure move or
single-line import edit, per the diagnostic's own `High risk`/"explicit
split contract" classification. 4 confirmed consumers of those specific
symbols were updated (`supplier_app.py`, `scripts/verify_enrichment_live.py`,
`tests/test_enrichment_pipeline.py`, `benchmarks/benchmark_models.py`).
`supplier_discovery_v2/immutability_check.py`'s protected-path list gained
the new `pipeline.py` path; `collect_inn.py` stays protected unchanged at
its root path (the split's deliberate content change does not remove its
own protection). CLI contract unchanged (`collect_inn.py --help` byte-for-byte
identical; `build_arg_parser`/`main` untouched beyond the import source).
The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903-report.md).

`2026-09-03` — `TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903`
moved `contact_crawler.py` to
[`backend/domain/supplier_enrichment/`](../backend/domain/supplier_enrichment/)
(`git diff -M --stat`: `0 insertions(+), 0 deletions(-)`, pure move — its
only internal import was already the canonical
`backend.domain.supplier_identity.email_extractor` path from an earlier
pass). 7 confirmed consumers were updated to the canonical import path:
`supplier_app.py`, `collect_inn.py`, `benchmarks/benchmark_models.py`,
`scripts/verify_enrichment_live.py`, `scripts/collect_contacts.py`,
`tests/test_enrichment_pipeline.py`, `tests/diagnostics/test_collect_inn_llm_path.py`.
`supplier_discovery_v2/immutability_check.py`'s protected-path list was
migrated in the same change, so the existing immutability guard was never
weakened; `supplier_discovery_v2/tests/test_immutability.py` gained 2 new
regression tests (protection-at-new-path + disposable-mutation-detection).
This is Pass 8 of the bounded root-refactor series, done per explicit owner
instruction to continue and finish it. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903-report.md).

`2026-09-03` — Fixed a genuine TOCTOU race in
`tests.test_mail_integrity...test_35_disabled_wait_preserves_retry_budget_for_real_transport_attempt`
(flagged as a separate finding by the prior `CI_INFRA` fix task). Root cause:
`attempts` is bumped by `_record_transport_attempt` and the provider is
called (incrementing `send_calls`) before the worker's `retry_job()` write
flips `mail_jobs.status` back to `'queued'` on the exception path
(`mail/queue.py:239-274`); the test polled only `send_calls >= 1` then
asserted `status` immediately. Reproduced the exact CI failure
deterministically with an injected delay in `retry_job` (RED), then fixed
the test to poll for the final `status == "queued"` too, matching the
existing pattern in `test_32` (GREEN). Test-only change; full suite
(48 passed, 1 skipped) reran clean. Commit `0efbdaf`.

`2026-09-03` — `Backend Full` `CI_INFRA` timeout fix `CONFIRMED`: the
Windows Defender exclusion step (`6af2af1`) was proven on the
classifier-selected CI run for
`TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903`
(`33691773114`) — `Backend Full` completed the real `462`-test suite twice
in a row (`18m54s`, then `24m0s` on an unmodified rerun), never cancelled,
well inside the `35`-minute timeout. Root-cause analysis: per-test
timestamp-delta analysis of the three earlier failed job logs (`gh api
.../actions/jobs/<id>/logs`) showed the slowdown concentrated in
`tests/test_mail_deliverability.py`/`tests/test_mail_integrity.py`
(SQLite/`tempfile`-heavy), matching documented Windows Defender real-time
scanning overhead on GitHub-hosted Windows runners; a best-effort
`Add-MpPreference -ExclusionPath` step (workspace, `RUNNER_TEMP`, `TEMP`)
was added to the `backend_full` job only. The `35`-minute timeout was left
as-is, not raised further. Now that the suite can run to completion, its
first pass surfaced one previously CI_INFRA-masked, unrelated flaky test
(`tests.test_mail_integrity...test_35_disabled_wait_preserves_retry_budget_for_real_transport_attempt`)
— confirmed a genuine race in the test's own polling logic, not a product
regression; flagged as a separate task, not fixed here. See this file's
Blockers section for full detail.

`2026-09-03` — `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903`
moved `web_lookup.py` and `xmlriver_client.py` to
[`backend/integrations/search/`](../backend/integrations/search/)
(`git diff -M --stat`: both `0 insertions(+), 0 deletions(-)` pure moves).
6 confirmed consumers were updated to the canonical import path:
`supplier_app.py`, `collect_inn.py` (lazy import), `scripts/collect_contacts.py`
(lazy import), `test_extractor.py`, `serp_parser.py`, `test_parser.py`.
`serp_parser.py` itself stays `DEFER`red (unmoved) per the diagnostic —
only its one internal import line was touched, matching the established
"beyond imports" precedent from earlier passes.
`supplier_discovery_v2/xmlriver_subprocess.py` was confirmed unaffected: it
invokes the untouched `serp_parser.py` by absolute path via
`subprocess.run(..., cwd=...)`, so `serp_parser.py`'s own updated import
resolves normally at that call site.
`supplier_discovery_v2/immutability_check.py`'s protected-path list was
migrated for both files in the same change, so the existing immutability
guard was never weakened. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903-report.md).

`2026-09-02` — CI capacity follow-up to
`TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902`: `Backend Full`
failed twice at its `25`-minute timeout, then once more at an
owner-approved `35`-minute timeout, all three times cancelled
(`KeyboardInterrupt`) mid-suite rather than failing a test — confirmed
`CI_INFRA`, not a product regression (local full-suite run: `460 tests,
failures=0` in under `4` minutes). Per explicit owner instruction the
timeout was not raised further; the branch's `Backend Full` remains `FAIL`
until a separate task investigates why the suite now exceeds `35` minutes
on the shared runner. `ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902-report.md`
and this file's Blockers section carry the full evidence.

`2026-09-02` — `TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902`
moved `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py` and
`verify.py` to
[`backend/domain/supplier_identity/`](../backend/domain/supplier_identity/)
(`git diff -M`: `email_extractor.py`/`inn_extractor.py` are 0-diff pure
moves; `inn_resolver.py`/`verify.py` changed only their internal import
lines). All 15 confirmed consumers were updated, including 4 not named in
the task's own known-dependency list and found only by a fresh full-tree
scan: `web_lookup.py`, `mail/repository.py`,
`backend/integrations/registry/dadata_client.py`, and
`benchmarks/benchmark_models.py` (the last one initially missed in a
partial check and caught by the full diagnostics run before publish).
`supplier_discovery_v2/immutability_check.py`'s protected-path list was
migrated for the three already-protected files
(`email_extractor.py`/`inn_extractor.py`/`verify.py`); `inn_resolver.py`
was deliberately left unprotected. This task's own `CHANGE_BUDGET_EXCEEDED`
threshold (">22 tracked files") was hit at 24 — the overage was 4
legitimate discovered dependents, not scope creep; work was fully applied
and tested, publish was paused, and the owner explicitly approved
continuing. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902-report.md).

`2026-09-02` — `TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902` made
`bug-reproducer`, `code-rot-cleaner` and `skill-doctor` actually
discoverable by Claude Code (previously only Codex-visible despite a global
`CONFIGURED` registry entry — confirmed by `ListSkills` returning `0`
results before, and the platform's own available-skills listing showing
each one after installation). Installed via the official multi-agent
`skills` CLI (`npx skills@latest`), using the existing Codex installations
or the public `warpdotdev/common-skills` upstream as the single source —
no upstream `SKILL.md` edited, no skill forked or vendored into this
repository, no Codex installation touched. `agent-browser` was confirmed to
already reach both agents equally through its own CLI runtime-loading
mechanism (`agent-browser skills get core --full`), distinct from
`SKILL.md` discovery — no install was needed or applicable there. Added one
compact `REGISTRY_AGENT_VISIBILITY` rule to `ai/AI_CONTRACT.md` so a global
`CONFIGURED` is never read as per-agent proof again, and recorded
per-agent status in `ai/VIBECODING_TOOL_REGISTRY.yaml`'s existing `notes`
fields (no new schema). The task report is
[`ai/reports/TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902-report.md`](reports/TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902-report.md).

`2026-09-02` — `TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902` fixed
`collect_inn.py --llm` (it imported a nonexistent `InnLlmExtractor` symbol
and told operators to set `ANTHROPIC_API_KEY`) using a deterministic
RED→FIX→GREEN bug-workflow — the `bug-reproducer` skill is not installed in
this Claude Code session (`ListSkills` returned zero results), so the
`BUG_REPRODUCER` methodology from `ai/AI_CONTRACT.md` was applied directly
and reported as `TYPE: WORKFLOW`. History (`git log -S`, one match: the
initial bulk-import commit) plus `Documents/28-8/enrichment-and-cache.md`
confirmed `InnLlmExtractor` never existed and is a documented leftover from
the pre-RouterAI version; `LlmExtractor` (already correct in
`supplier_app.py`) is the intended implementation. A new behavioral
reproducer (`tests/diagnostics/test_collect_inn_llm_path.py`) failed with
the exact predicted `ImportError` before the fix and passed after it. Two
owner approval gates were used (reproduction plan, then fix plan) before any
change landed. `FINDING-018` is now `RESOLVED`. The task report is
[`ai/reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md`](reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md).

`2026-09-02` — `TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902` moved
`llm_fallback.py` and `routerai_client.py` to
[`backend/integrations/llm/`](../backend/integrations/llm/) (`git diff -M`
showed `99%`/`100%` similarity — prompts, schemas, `DEFAULT_MODEL` and
provider behavior unchanged). All 4 known consumers (`supplier_app.py`,
`collect_inn.py`, `scripts/collect_contacts.py`,
`benchmarks/benchmark_models.py`) updated; no root wrapper. Discovered and
deferred (not fixed, out of scope) a pre-existing unrelated bug:
`collect_inn.py --llm` imports a nonexistent `InnLlmExtractor` symbol —
recorded as `FINDING-018`. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902-report.md).

`2026-09-02` — `TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902`
completed the deferred `checko_client.py` move: it now lives at
[`backend/integrations/registry/checko_client.py`](../backend/integrations/registry/checko_client.py)
(byte-identical, Git-recognized rename), all 3 known consumers
(`supplier_app.py`, `scripts/verify_enrichment_live.py`,
`tests/test_enrichment_pipeline.py`) updated, no root wrapper. In the same
change, `supplier_discovery_v2/immutability_check.py`'s protected-path list
was migrated to the new location — a fresh baseline generated against the
moved tree verifies clean, and a disposable synthetic copy of the new path,
mutated after baselining, is correctly detected as changed; Checko was never
unprotected at any point in the commit. `FINDING-017` is now `RESOLVED`. The
task report is
[`ai/reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md`](reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md).

`2026-09-02` — `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902` moved
`dadata_client.py` to
[`backend/integrations/registry/dadata_client.py`](../backend/integrations/registry/dadata_client.py)
(no root wrapper; no confirmed external consumer) and updated its one known
consumer, `collect_inn.py`'s lazy import. `checko_client.py` was **not**
moved: a fresh reference scan found
`supplier_discovery_v2/immutability_check.py:16` hardcodes a root-relative
`"checko_client.py"` path in its protected-files hash list, and
`supplier_discovery_v2/` was out of this task's scope to touch. This is
recorded as [`FINDING-017`](DEFERRED_FINDINGS.md) rather than silently
worked around. The full offline import chain (`api.index → supplier_app →
collect_inn → backend.integrations.registry.dadata_client`) was verified
under `SUPPLYDESK_ENV=test`; `backend/**` is structurally confirmed not
excluded by `vercel.json`. The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902-report.md).

`2026-09-02` — `TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902` moved the
implementation of two confirmed `MOVE_SCRIPTS` candidates from the root
diagnostic: `collect_contacts.py` now lives at
[`scripts/collect_contacts.py`](../scripts/collect_contacts.py) and
`benchmark_models.py` now lives at
[`benchmarks/benchmark_models.py`](../benchmarks/benchmark_models.py). The
root files are thin compatibility wrappers; both old (`python
collect_contacts.py ...` / `python benchmark_models.py ...`) and new
canonical (`python -m scripts.collect_contacts ...` / `python -m
benchmarks.benchmark_models ...`) invocations were verified to produce
identical help output and exit codes. Repository-root `.env` lookup and
CWD-relative `results/`/`cache/` paths were preserved. No other root Python
module was moved; no provider call, real mail, or database write occurred.
The task report is
[`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902-report.md).

`2026-09-02` — `TASK-PYTHON-ROOT-DIAGNOSTIC-20260902` completed as a
report-only architecture diagnostic: 20 root Python files and 16 tracked root
directories were reviewed; no product code, files or dependencies changed.
The decision-ready report is committed locally as
[`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`](reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md).
Commit `dc93a181c85c175863a84ddddb1c71c9172a98bb` is published with matching
remote SHA `301934fb0daa1f49cad8c793c9a5acbd30b10152`; FAST Control CI run
`33645377974` passed. Full product suites were skipped by report-only
classification.

`2026-09-02` — Cleanup/recovery phase is complete, VibeCoding V1.3 is locally
verified, and `TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902` is closed with
remote SHA match confirmed, FAST CI `PASS`, and Browser Full `FAIL`. The failure
cause is not confirmed; any browser-runtime fix requires a separate task.
Finding-009 remains `REVIEW_REQUIRED`: no operational env file is present or
tracked in the canonical checkout/history, but retained external snapshot and
quarantine filename copies require separate owner review.

## Project

- Repository: `edwatikhedwa-tech/supplydesk` (private).
- Verified controlled baseline: `control/reproducible-test-runtime-v1-20260901`
  at `d4d2b2ab2457e3aa103f80120642bff4bc72920f`.
- Canonical branch: `control/final-hygiene-acceptance-20260901`, created from
  the verified Batch 2 HEAD `a228321401270b69c9ac2f07f76435e246b6f5c3`.
- Current governance branch: `control/vibecoding-policy-v1-20260901`, created
  from verified canonical HEAD `f13dad6dc2461ef6dc50242f7fc075895f2a4603`.
- Current CI branch: `control/vibecoding-ci-v1.1-20260901`, created from
  verified VibeCoding policy HEAD `9d3e58232230b276396f3bc127e2d937bed8482d`.
- Cleanup Batch 2 branch: `control/safe-cleanup-batch2-20260901`, retained as
  the immediately preceding evidence branch.
- Current task branch: `audit/frontend-knip-20260902`; this task's published
  commit is `dc93a181c85c175863a84ddddb1c71c9172a98bb`.
- Canonical development checkout: `C:\Users\edwat\SupplyDesk`.
- Historical legacy checkout: `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS`, marked
  `LEGACY_WORKSPACE_DO_NOT_DEVELOP_HERE.txt`.
- External retained quarantine: `<QUARANTINE_ROOT>`; it is outside the Git
  repository and is not a source of truth.
- Canonical control baseline: `control/canonical-baseline-20260901` at
  `792f441b4b6099533177e7c1d23d6252670f9309` before this governance branch.
- Documentation governance branch: `control/documentation-governance-20260901`.
- Diagnostic V1 branch: `control/diagnostic-plane-v1-20260901` at
  `98f4a370e2bf223aea6550630ce49ed05f12a8af`.
- Diagnostic V1.1 branch: `control/diagnostic-plane-v1.1-20260901`, created in
  a separate worktree from the V1 HEAD above; verified remote branch resolves
  to `f9b0b66432f9e8650e87e5a89dd27a258a416e38`.
- Reproducible test/runtime branch: `control/reproducible-test-runtime-v1-20260901`,
  pushed at functional commit `09d12018afc4ecb8445f40dc1b717ef078cfae0f` in
  a separate worktree and not merged into the default branch.
- Product behavior is not changed by this control-plane-only task.
- Source of truth after cleanup is the verified remote final-acceptance branch
  plus the new canonical checkout. The old dirty OneDrive checkout is
  recovery-only and is not used for development.

## Runtime

- Backend entrypoints recorded by the manifest: `supplier_app.py` and
  `api/index.py`.
- Frontend root: `frontend/`; default URLs are
  `http://127.0.0.1:8000` and `http://127.0.0.1:5173`.
- Canonical database contract remains SQLite at `mail-data/supplier.sqlite3`;
  the safe test profile refuses that path and uses only
  `runtime/test-data/supplier.sqlite3`.
- Safe runtime profile: `OFFLINE_TEST`; it uses the real application routes,
  synthetic credentials, disposable SQLite, disabled outgoing mail and
  loopback-only networking. The process was stopped after acceptance.

## Implemented

- One canonical state file: `ai/CURRENT_STATE.md`.
- Operational control documentation is owned by `ai/**`; product documentation
  is owned by `docs/**`.
- Historical state, handoff, decisions, deferred findings, and root task
  reports are retained under dated `ai/history/` paths.
- Documentation lifecycle and audit retention policies are recorded in
  [`docs/DOCUMENTATION_POLICY.md`](../docs/DOCUMENTATION_POLICY.md) and
  [`ai/AUDIT_POLICY.md`](AUDIT_POLICY.md).
- Diagnostic control plane V1 is catalogued in
  [`docs/product/CAPABILITY_CATALOG.md`](../docs/product/CAPABILITY_CATALOG.md),
  [`docs/requirements/TRACEABILITY_MATRIX.csv`](../docs/requirements/TRACEABILITY_MATRIX.csv),
  and [`scripts/diagnostics/diagnostic_contract.yaml`](../scripts/diagnostics/diagnostic_contract.yaml).
- `scripts/doctor.ps1` now delegates to read-only typed checks and emits
  machine-readable evidence outside the repository.
- Diagnostic control plane V1.1 separates test-verification, diagnostic and
  live-acceptance levels; adds semantic TRACE-009..013 validation; maps each
  failure mode to a responsible component and doctor check; and records
  symptom, causes, confirming/excluding checks, confidence and repair
  eligibility.
- V1.1 adds disposable negative fixtures for database, backend, frontend,
  secret-path and machine-output classification, and makes `doctor -Apply` an
  explicit safety block because recovery is not implemented.
- V1 adds `requirements-test.txt`, a standard-library unittest runner,
  PowerShell setup/run wrappers, and a documented clean-checkout bootstrap.
- V1 adds `OFFLINE_TEST` safe runtime start/stop wrappers, an owned runtime
  marker, disposable database enforcement, inherited-provider scrubbing and
  a loopback-only network guard.
- Doctor now has explicit `OFFLINE_TEST`, `LOCAL_CANONICAL` and
  `LIVE_EXTERNAL` profiles; offline checks are separated from live-provider
  acceptance and `-Apply` remains blocked.
- VibeCoding Control Policy V1 is canonical at `ai/VIBECODING_RULES.md`; its
  `last_corrected` value is read from that file by the read-only validator.
  Its factual tool inventory is `ai/VIBECODING_TOOL_REGISTRY.yaml` and its
  validator is `ai/tools/validate_vibecoding.py`.
- VibeCoding bootstrap references are present in `AGENTS.md`, `CLAUDE.md`,
  `PROJECT_MANIFEST.yaml` and this AI entrypoint. The documentation validator
  recognizes the separate canonical policy without weakening current-state
  uniqueness.
- VibeCoding Control Policy V1.1 adds FAST, FOCUSED, FULL and PERIODIC profiles,
  LOW/NORMAL/HIGH risk levels and the FAST-first rule. CI implementation is
  tracked in `.github/workflows/ci.yml`; classifier mapping is in
  `scripts/ci/change_groups.json`.
- CI Performance Fix V1 adds risk-based FAST/FOCUSED/FULL/PERIODIC workflow
  routing, a real-route one-viewport Browser Smoke, concurrency cancellation,
  explicit job budgets and a CI Summary. Normal focused pushes do not start
  Backend Full or Browser Full.
- VibeCoding Control Policy V1.3 extends V1.2 with Comprehensive-First,
  Two-Pass, No-Micro-Audit-Chain, Decision-Ready, Deferred Findings,
  Governance Freeze, One-Shot Delivery, Tool Audit Batching and stronger
  report/state minimization and verification-budget semantics. Its validator
  checks these policy markers rather than agent cognition.
- Workspace Guard V1 adds `scripts/assert_workspace.ps1`, which compares the
  real Git root with the canonical local default or an explicit absolute
  `-ExpectedRoot` for CI and intentional worktrees without changing directory,
  branch or files.
- Doctor, bootstrap, recovery, test-environment, test-runner and safe-runtime
  control entry points invoke the workspace guard before their actions; CI
  passes its checkout root explicitly.
- Architecture placement, root-growth, versioned-garbage, component lifecycle,
  deprecation, disabled-feature and temporary-file rules are shared in
  [`ai/AI_CONTRACT.md`](AI_CONTRACT.md), with retained non-active components
  recorded in [`docs/architecture/COMPONENT_LIFECYCLE.md`](../docs/architecture/COMPONENT_LIFECYCLE.md).
- Local human-in-the-loop browser authentication and public `/login` failure
  classification are documented in
  [`RUNBOOK-FRONTEND.md`](../docs/operations/runbooks/RUNBOOK-FRONTEND.md);
  remote CI is explicitly non-interactive.

## Verified

The following evidence is inherited from earlier control work or was verified
on this task's dedicated branch:

- Official backend full run: `412 tests, 0 failures, 0 errors, 1 skipped`.
- Frontend clean install, typecheck and build passed; lint passed with 8
  warnings.
- Public-shell Playwright acceptance: `8/8` viewport projects passed against
  the safe runtime.
- Published live route acceptance: `18/18 PASS`.
- Safe runtime smoke: root `200`, auth/me `200`, protected APIs `401`, unknown
  API `404`; synthetic login and protected `200` paths passed.
- Safe runtime marker: disposable SQLite, canonical `false`, outgoing mail
  disabled, providers fake/blocked, private `.env` not loaded, real email false.
- Remote audit retention: audit branch resolves to
  `b5a454f9b39f3cbf01d640d5b67e4231ca25733a` and its retained tree includes the
  audit index, summary, final report, functional baseline, and security findings.
- Diagnostic tests: `25 passed` with `python -m unittest discover -s
  tests/diagnostics -v`, including controlled negative fixtures.
- Traceability validator: `PASS`; 21 active requirements, 21/21 behavioral
  test links, 21/21 distinctly diagnosable failure modes, and TRACE-001..013.
- Doctor `-Plan`: exit `0`; full `-DryRun -Profile OFFLINE_TEST` returned
  `WARNING`, exit `0`, with all required checks passing and only the expected
  dirty-worktree warning; `doctor -Apply`: `SAFETY_BLOCK`, exit `3`.
- Dedicated branch was pushed to `origin`; the first DNS attempt failed
  transiently and the immediate retry succeeded.
- Documentation, state and traceability validators: `PASS`; `git diff --check`:
  `PASS`.
- `requirements-test.txt` was installed only into `.venv-test`; no global
  package install, private `.env`, canonical DB or provider connection was
  required.
- Traceability validator now reports `offline_eligible_requirements=21/21` and
  `offline_behaviorally_diagnosable=6/21`; eligibility is not overclaimed as
  behavior proof.
- Physical cleanup Batch 1 deleted only 308 regeneratable/cache files
  (`30,228,149` bytes) and moved 1,481 historical/review files
  (`132,669,560` bytes) to retained external quarantine. No product source,
  `.env`, canonical database or mail data was deleted, moved or modified.
- Cleanup before/after manifests are retained outside the repository; all
  delete and quarantine paths were individually verified after the operation.
- Legacy marker was added locally; the legacy worktree remains intentionally
  dirty.
- Batch 2 moved `.agents/skills/neon/SKILL.md`, `keywords.txt` and root
  `run_probe.py` to external quarantine after reference, process and hash
  checks. No canonical source file, database, environment or mail data was
  physically deleted.
- Batch 2 removed only 18 proven unused Python imports and 2 side-effect-free
  dead bindings in commit `d2ceef3`; product behavior and public surfaces were
  preserved.
- Batch 2 duplicate audit found 2 groups / 4 files and deleted none. Both
  groups are retained because their path/package roles differ.
- Batch 2 `.gitignore` audit removed broad JSON/CSV hiding and passed the full
  synthetic matrix; `.env.example` remains ignored under the publish denylist.
- Batch 2 acceptance: backend `412/0/0/1`, diagnostics `26/26`, frontend
  install/typecheck/lint/build PASS, Playwright `8/8`, Doctor Full exit `0`.
- Batch 2 documentation/state/traceability validators and `git diff --check`
  passed; the cleanup report and manifest are retained in the pushed branch.
- Remote `control/safe-cleanup-batch2-20260901` was independently verified to
  match the Batch 2 closeout commit before this acceptance branch was created.
- Final canonical inventory: 390 tracked files, 45 tracked root objects, zero
  unknown canonical files/directories/root objects, zero tracked review/backup
  packages, zero tracked generated artifacts, zero tracked env/secret files and
  zero tracked database files. The two known duplicate groups remain kept by
  path-purpose design.
- Final `.gitignore` matrix kept real `.env`, database and runtime artifacts
  ignored while product JSON/CSV, fixtures and `PROJECT_MANIFEST.yaml` remain
  visible to Git.
- Final offline acceptance on the canonical checkout: backend `412/0/0/1`,
  diagnostics `26/26`, frontend install/typecheck/lint/build PASS, safe HTTP
  `200/200/401/404`, Playwright `8/8` and Doctor Full exit `0`.
- Final branch was pushed normally and `git ls-remote` independently confirmed
  its remote HEAD; no force-push, merge or default-branch change occurred.
- VibeCoding policy validator and four governance diagnostic tests passed; the
  full diagnostic set is `30/30` and the required documentation/state/
  traceability validators also pass.
- The governance commit `1bdda8a` was pushed to
  `origin/control/vibecoding-policy-v1-20260901`; its remote ref was verified
  after normal publication.
- Local V1.1 governance checks and classifier tests were rerun after the
  workflow/validator changes; remote CI execution is verified for the focused
  FAST path.
- Acknowledgement-output governance correction is isolated to the canonical
  policy, `AGENTS.md`, `CLAUDE.md`, its validator and focused governance tests:
  intermediate responses contain no acknowledgement, while the final response
  contains exactly one rendered from canonical `last_corrected`.
- Final-status governance correction adds the canonical aggregation rule that
  required `PASS` plus out-of-scope `NOT_NEEDED` remains final `PASS`; required
  `NOT_VERIFIED` is a real limitation and required `FAIL` remains `FAIL`.
- Remote FAST proof `33562406201` passed in 1m22s on final configuration
  commit `2b860a5`; Full Control passed and Backend Full/Browser Full were
  skipped by deterministic classification.
- Explicit FULL proof `33562558816` ran all required full jobs in parallel;
  Change Classification, Fast Control, Full Control and Frontend passed, but
  Browser Full failed after 11m17s on all eight viewport screenshot/Axe
  scenarios and Backend Full was cancelled after 11m49s without a final test
  total. This is recorded as `CI_PERFORMANCE_FAILURE`, not as a product
  regression.
- Browser Full stability remediation is implemented in `MagicRings` and the
  public-shell test: reduced motion renders one stable WebGL frame without a
  continuous RAF loop, normal mode remains animated, readiness uses
  `domcontentloaded` plus the visible login heading, and the Browser Full
  test emulates `reducedMotion: 'reduce'` only for that public-shell case.
- Local remediation acceptance passed: public shell `1/1` single viewport and
  `8/8` configured viewport projects with `workers: 4`; focused reduced-motion,
  normal-motion, runtime media-query switch and WebGL fallback checks passed;
  frontend typecheck, lint, build, screenshot and Axe checks passed.
- Local final control checks after the routing correction: diagnostics
  `39/39`, official quick runner `50/0/0/0`, VibeCoding/docs/state/traceability
  validators PASS, Doctor Plan PASS, and local real-route Browser Smoke `1/1`.
- `TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902` remote closeout: commit
  `647128ece1196f3400c41ef1fce637eba56574e2` is published with remote SHA
  match `YES`; FAST CI is `PASS`; Browser Full is `FAIL`. The failure cause is
  not confirmed and Browser Full was not rerun during closeout.
- The GitHub Actions registry intentionally remains `NOT_VERIFIED`: FAST is
  proven, but the required full remote acceptance is not green.
- Workspace Guard V1 focused acceptance: canonical default `PASS`, legacy
  default `BLOCKED_WRONG_WORKSPACE`, explicit matching worktree `PASS`, wrong
  explicit root `BLOCKED_WRONG_WORKSPACE`; governance tests `3/3 PASS`.
- Control-tool `Plan` checks for Doctor, bootstrap, test setup, safe runtime
  start/stop and the guard passed without starting backend/frontend/Playwright.
- Confirmed old backend PID `15912` was stopped; the process was verified as
  absent afterwards and no legacy checkout file was changed.
- V1.2 focused governance checks: `14` tests passed and
  `python ai/tools/validate_vibecoding.py` passed with `36` registered tools.
- V1.3 focused governance checks: `16` tests passed; the policy validator
  passed with `36` registered tools; state/docs validators and `git diff
  --check` passed.
- Canonical Finding-009 review: no current operational `.env`/`.env.*` files,
  no tracked operational secret paths and no operational env path in Git
  history. Three unique historical `.env.example` blobs were classified as
  `SAFE_TEMPLATE`.
- Controlled allowlist review covered 27 items: 5 `SAFE_TEMPLATE`, 6
  `EMPTY_OR_NON_SECRET`, 8 `REAL_SECRET_PRESENT`, 4 `MIXED` and 4
  `UNDETERMINED`. Real or mixed material is retained only in external
  snapshots/quarantine; Git exposure is `NO`.
- Five paired snapshot paths are identical copies across the two baseline
  containers. No candidate values were output or saved, and no retained file
  was changed.
- Cleanup/recovery closeout is `CLEANUP_PHASE: COMPLETE` based on the existing
  Batch 1, Batch 2 and final hygiene evidence. Finding-009 remains an open
  `DEFERRED_SECURITY_ACTION — LOCAL_ARCHIVE_SECRET_RETENTION` and is not a
  cleanup blocker.
- Root Python architecture diagnostic: 20 root Python files and 16 tracked
  top-level directories were independently inventoried on the current branch.
  `supplier_app.py` remains the protected root backend entrypoint and
  `api/index.py` remains the protected serverless adapter. No deletion
  candidate was confirmed; 14 future structural move candidates and 4
  deprecated-review root test surfaces are recorded in the dated report.
- Code Rot Cleaner was used in report-only mode with external scratch output;
  Ruff and Vulture were not available without installation and were not added.
- `FINDING-018` fix: `collect_inn.py --llm` now imports `DEFAULT_MODEL,
  LlmExtractor, api_key_present` and constructs
  `LlmExtractor(model=args.llm_model or DEFAULT_MODEL)`; the missing-key
  message names RouterAI/`ROUTERAI_KEY`. Proven `RED→GREEN` with
  `tests/diagnostics/test_collect_inn_llm_path.py` (3/3 PASS, exercises the
  real `collect_inn.main()` path, zero provider calls);
  `tests/diagnostics/test_llm_integration_move.py` updated to stop blessing
  the stale import (6/6 PASS); `tests/test_enrichment_pipeline.py` +
  `tests/test_dashboard.py` (21/21 PASS); diagnostics suite `61/70` PASS
  with the same 9 pre-existing `pwsh`-gap errors as before.
- Bounded root refactor Pass 5 (LLM integrations):
  `backend/integrations/llm/llm_fallback.py` and
  `backend/integrations/llm/routerai_client.py` are now the canonical
  implementations; root copies are gone, no wrapper. `supplier_app`,
  `collect_inn`, `scripts.collect_contacts` and `benchmarks.benchmark_models`
  all import successfully offline; `api.index.handler`/`_APP` import under
  `SUPPLYDESK_ENV=test`. `tests/diagnostics/test_llm_integration_move.py`
  (6/6 PASS) added; `tests/test_enrichment_pipeline.py` +
  `tests/test_dashboard.py` (21/21 PASS); diagnostics suite `52/61` PASS
  with the same 9 pre-existing `pwsh`-gap errors as before.
- Bounded root refactor Pass 4 (Checko + immutability migration):
  `backend/integrations/registry/checko_client.py` is now the canonical
  implementation alongside `dadata_client.py`; the root copy is gone.
  `supplier_discovery_v2/immutability_check.py` protects the new path — the
  guard was migrated, not weakened, in the same commit. `supplier_app`,
  `scripts/verify_enrichment_live.py --help`, and `api.index.handler`/`_APP`
  all import successfully offline under `SUPPLYDESK_ENV=test`.
  `tests/test_dashboard.py`'s `patch.object(supplier_app, "CheckoClient", ...)`
  mock still works unchanged (it patches the module attribute, not a dotted
  import string). New/updated regression coverage:
  `supplier_discovery_v2/tests/test_immutability.py` (3/3 PASS, 2 new
  assertions); `tests/test_enrichment_pipeline.py` (8/8 PASS);
  `tests/test_dashboard.py` (13/13 PASS); full `supplier_discovery_v2/tests`
  (14/14 PASS); diagnostics suite `52/61` PASS with the same 9 pre-existing
  `pwsh`-gap errors as before.
- Bounded root refactor Pass 3 (registry): `backend/integrations/registry/dadata_client.py`
  is the canonical implementation; the root copy is gone and no wrapper was
  needed. `collect_inn.py`'s lazy import, `supplier_app`, and
  `api.index.handler`/`_APP` all import successfully offline under
  `SUPPLYDESK_ENV=test`. `checko_client.py` stays at root — see
  `FINDING-017` in `ai/DEFERRED_FINDINGS.md`. New regression coverage:
  `tests/diagnostics/test_registry_integration_move.py` (3/3 PASS); targeted
  `tests/test_enrichment_pipeline.py` (8/8 PASS); the diagnostics suite
  passed `52/61` with the same 9 pre-existing `pwsh`-gap errors as before.
- Bounded root refactor Pass 7 (search integrations):
  `backend/integrations/search/{web_lookup,xmlriver_client}.py` are now the
  canonical implementations; root copies are gone, no wrapper.
  `supplier_app`, `collect_inn`, `scripts.collect_contacts`, `serp_parser`,
  and `backend.integrations.search.{web_lookup,xmlriver_client}` all import
  successfully offline; `api.index.handler`/`_APP` imports under
  `SUPPLYDESK_ENV=test`. Old vs new CLI invocation (`collect_contacts.py
  --help`, `collect_inn.py --help`) verified byte-identical/exit `0`.
  Behavioral evidence: `test_extractor.py` and `test_parser.py` (custom root
  scripts) both print "Все проверки пройдены" with exit `0`;
  `tests/test_enrichment_pipeline.py` (8/8 PASS);
  `supplier_discovery_v2/tests/` full suite (18/18 PASS, including 2 new
  immutability tests); official backend suite `462 tests, failures=0,
  errors=9` (same pre-existing `pwsh`-gap), `skipped=1`.
- Bounded root refactor Pass 2: `scripts/collect_contacts.py` and
  `benchmarks/benchmark_models.py` are now the single canonical
  implementations; root `collect_contacts.py`/`benchmark_models.py` are
  compatibility wrappers with no duplicated logic. Old and new CLI `--help`
  output is byte-identical, exit codes match, and `.env`-root resolution was
  proven structurally (`REPO_ROOT` equals the repository root from both new
  locations) without reading `.env` contents. The new
  `tests/diagnostics/test_operator_cli_root_compat.py` regression test passed
  `4/4`; the full diagnostics suite passed `49/49` with the 9 remaining
  `test_change_classifier.py` errors reproduced identically on the
  unmodified tree (`pwsh` missing from this environment's `PATH`, unrelated
  to this task); docs/state/vibecoding validators and `git diff --check`
  passed.

- Bounded root refactor Pass 11 (tests/legacy conversion): `tests/legacy/{test_extractor,
  test_inn,test_parser,test_verify}.py` are real `unittest.TestCase`s
  (`ExtractorTests`, `InnExtractorTests`, `SerpParserTests`, `VerifyTests`),
  discovered automatically by `scripts/run_test_suite.py`; root copies are
  gone. `python -m unittest discover -s tests/legacy -v`: `29/29 PASS`.
  Official backend suite: `497 tests, failures=0, errors=9` (same
  pre-existing `pwsh`-gap; confirmed a transient 10th error seen mid-task
  was `FINDING-019`, caused by this task's own uncommitted staged diff, not
  by the new test files — cleared after commit), `skipped=1`.
- Bounded root refactor Pass 10 (serp_parser.py move): `backend/integrations/search/serp_parser.py`
  is now the canonical implementation; root `serp_parser.py` is a thin
  compatibility wrapper. `supplier_app`, `collect_inn`,
  `scripts.collect_contacts`, `benchmarks.benchmark_models`,
  `backend.integrations.search.web_lookup`,
  `backend.domain.supplier_identity.email_extractor`,
  `supplier_discovery_v2.xmlriver_subprocess` all import successfully
  offline; `api.index.handler` imports under `SUPPLYDESK_ENV=test`.
  `XmlRiverSubprocess()`'s default `parser_path` verified to resolve to the
  new file and exist. `serp_parser.py --help` (root wrapper) and `python -m
  backend.integrations.search.serp_parser --help` verified byte-for-byte
  identical to each other and to the pre-move commit.
  `tests/test_enrichment_pipeline.py` +
  `tests/diagnostics/test_collect_inn_llm_path.py` +
  `supplier_discovery_v2/tests/test_immutability.py` (24/24 PASS, including
  2 new immutability tests); `test_parser.py`/`test_extractor.py` (custom
  root scripts, "Все проверки пройдены", exit `0`); official backend suite
  `468 tests, failures=0, errors=9` (same pre-existing `pwsh`-gap),
  `skipped=1`.
- Bounded root refactor Pass 9 (collect_inn.py pipeline/CLI split):
  `backend/domain/supplier_enrichment/pipeline.py` now holds the
  deterministic ИНН/ОГРН parsing extracted from `collect_inn.py`;
  `collect_inn.py` is the thinned CLI, importing the extracted functions
  back (verified as identical objects, not copies). `supplier_app`,
  `scripts.verify_enrichment_live`, `benchmarks.benchmark_models`,
  `tests.test_enrichment_pipeline` all import successfully offline;
  `api.index.handler` imports under `SUPPLYDESK_ENV=test`.
  `tests/test_enrichment_pipeline.py` + `tests/diagnostics/test_collect_inn_llm_path.py`
  + `supplier_discovery_v2/tests/test_immutability.py` (22/22 PASS,
  including 2 new immutability tests); `collect_inn.py --help` byte-for-byte
  unchanged; official backend suite `466 tests, failures=0, errors=9` (same
  pre-existing `pwsh`-gap), `skipped=1`.
- Bounded root refactor Pass 8 (contact_crawler):
  `backend/domain/supplier_enrichment/contact_crawler.py` is now the
  canonical implementation; the root copy is gone, no wrapper.
  `supplier_app`, `collect_inn`, `scripts.collect_contacts`,
  `benchmarks.benchmark_models`, `scripts.verify_enrichment_live` all import
  successfully offline; `api.index.handler` imports under
  `SUPPLYDESK_ENV=test`. `tests/test_enrichment_pipeline.py` +
  `supplier_discovery_v2/tests/test_immutability.py` (17/17 PASS, including
  2 new immutability tests); official backend suite `464 tests, failures=0,
  errors=9` (same pre-existing `pwsh`-gap), `skipped=1`.

## Not verified

- NOT VERIFIED: live external provider routes, real SMTP/IMAP, real email and
  production migration behavior were not exercised by design.
- Full authenticated real-provider workflows remain outside the safe offline
  contract; synthetic login and protected local routes were checked.
- Same-environment parity between the source checkout and the control worktree
  was not re-established.
- `knip` produced frontend candidates; no frontend file or dependency was
  removed because the approved allowlist covered Python cleanup only and
  manual/operator surfaces could not be ruled out.
- Current canonical database rows, mailbox state and provider quotas were not
  inspected or exercised.
- Remote CI proof for this new guard/workflow revision was not run in this
  local-only iteration; CI receives an explicit checkout-root override in the
  committed workflow.
- The root cause of the remote Browser Full `FAIL` for
  `TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902` is `NOT VERIFIED`; no
  Browser Full rerun or browser-runtime remediation belongs to this closeout.
- The local interactive browser auth handoff was not exercised; no personal
  browser, credentials, cookies or authentication state were accessed.
- Current validity, ownership and required retention period for the detected
  local archive credentials are not verified. Four binary/image artifacts
  remain `UNDETERMINED` and require owner-approved follow-up.
- Current validity, ownership and required retention period for local archive
  credentials remain unverified; owner approval is required for any deletion
  or rotation. No archive deletion, movement, rotation or history rewrite was
  authorized.
- The root diagnostic did not run product regression, backend/frontend runtime,
  browser acceptance, live providers, real mail or deployment verification;
  these remain outside its report-only scope.

## Blockers

- The task is closed with remote SHA match `YES`, FAST CI `PASS` and Browser
  Full `FAIL`; the failure cause is not confirmed. A browser-runtime fix must
  be a separate task.
- `Backend Full`'s `CI_INFRA` timeout is `RESOLVED`: the Windows Defender
  exclusion fix (`6af2af1`) was confirmed on the classifier-selected CI run
  for `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903`
  (`33691773114`) — `Backend Full` completed the full `462`-test suite twice
  in a row without being cancelled (`18m54s` then `24m0s`, both well under
  the `35`-minute timeout). The dedicated `workflow_dispatch profile=FULL`
  verification run (`33690006924`) launched earlier was inconclusive on its
  own (cancelled by the branch's concurrency group when the next push
  started its own CI run), but this later run supersedes it with a clean
  confirmation. One new, unrelated, non-blocking finding surfaced now that
  the suite can finally run to completion: the first attempt on
  `33691773114` failed exactly one test,
  `tests.test_mail_integrity.MailIntegrityAcceptanceTests.test_35_disabled_wait_preserves_retry_budget_for_real_transport_attempt`
  (`AssertionError: 'sending' != 'queued'`), which passed clean on an
  unmodified rerun — a genuine race in the test itself (it polls
  `provider.send_calls` then immediately asserts DB `status` with no
  synchronization guaranteeing the background `MailQueue` worker has
  finished writing the final status), not a product regression and not
  caused by this branch's changes. `RESOLVED` on `2026-09-03`: the test now
  also polls for the final `status == "queued"` before asserting (commit
  `0efbdaf`); see this file's Last update entry.
- Product/live-provider follow-up remains bounded by the limitations above and
  the open findings in [`ai/DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md).

## Active constraints

- The completed Browser Full stability task was limited to `MagicRings`
  reduced-motion lifecycle and the scoped public-shell test.
- Do not modify auth handoff/OAuth, backend/API, database, migrations, mail
  data, secrets, Knip, unrelated frontend tests, or the worker count.
- Do not send real email, connect to real SMTP/IMAP, write the canonical
  database, force-push, merge, or change the default branch.
- Keep audit history on the dedicated audit branch; only the documented pointer
  and selected summaries belong in the canonical working branch.
- Do not start the safe runtime from a canonical database or private `.env`;
  use `scripts/start_test_runtime.ps1 -Apply` after the test venv exists.
- Do not use the legacy OneDrive checkout for development. Do not permanently
  purge the external quarantine without a separate owner-approved review.
- Run `scripts/assert_workspace.ps1` before repository mutation, runtime start,
  build, artifact-producing tests, commit or push. Use `-ExpectedRoot` only for
  the exact intentional CI/worktree root.
- Do not treat planned or unverified tools as configured, and do not claim a
  check passed unless its command actually ran.
- CI itself is HIGH risk: for the closed task, remote FAST is `PASS` and
  Browser Full is `FAIL`; the failure cause remains `NOT VERIFIED` on the
  hosted runner.

## Current next step

The bounded root refactor program (Passes 2-11) is complete. Pass 2 (CLI
compatibility), Pass 3 (`dadata_client.py`), Pass 4 (`checko_client.py` +
immutability migration), Pass 5 (LLM integrations), Pass 6 (supplier
identity domain), Pass 7 (search integrations), Pass 8 (`contact_crawler.py`),
Pass 9 (`collect_inn.py` pipeline/CLI split), Pass 10 (`serp_parser.py`
move) and Pass 11 (`tests/legacy/` conversion) are all done; `backend/
{integrations/{registry,llm,search},domain/{supplier_identity,
supplier_enrichment}}/` hold 13 moved/extracted modules, `tests/legacy/`
holds 4 converted test modules, and `FINDING-017`/`FINDING-018` are both
resolved. `supplier_app.py`/`api/index.py` remain `KEEP_ROOT` — the only
intentionally-unmoved root Python, being the protected local and serverless
entrypoints. `FINDING-019` (the `diagnostic_runner.py` subprocess-encoding
bug discovered incidentally during Pass 11) is now also resolved.

Keep the Browser Full `FAIL` and Finding-009 as separate recorded
limitations.

## Canonical references

- Manifest: [`PROJECT_MANIFEST.yaml`](../PROJECT_MANIFEST.yaml).
- Documentation entrypoint: [`docs/README.md`](../docs/README.md).
- Active-task sentinel: [`ai/ACTIVE_TASK.md`](ACTIVE_TASK.md).
- Decisions: [`ai/DECISIONS.md`](DECISIONS.md).
- Deferred findings: [`ai/DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md).
- Latest governance report: [`ai/reports/TASK-DOCUMENTATION-GOVERNANCE-20260901-report.md`](reports/TASK-DOCUMENTATION-GOVERNANCE-20260901-report.md).
- Diagnostic report: [`ai/reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901-report.md`](reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901-report.md).
- Browser Full stability report: [`ai/reports/TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902-report.md`](reports/TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902-report.md).
- Diagnostic V1.1 report: [`ai/reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901-report.md`](reports/TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901-report.md).
- Reproducible test/runtime report: [`ai/reports/TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901-report.md`](reports/TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901-report.md).
- Safe physical cleanup report: [`ai/reports/TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901-report.md`](reports/TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901-report.md).
- Safe cleanup Batch 2 report: [`ai/reports/TASK-SAFE-CLEANUP-BATCH2-20260901-report.md`](reports/TASK-SAFE-CLEANUP-BATCH2-20260901-report.md).
- CI performance fix report: [`ai/reports/TASK-CI-PERFORMANCE-FIX-V1-20260902-report.md`](reports/TASK-CI-PERFORMANCE-FIX-V1-20260902-report.md).
- Workspace guard report: [`ai/reports/TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902-report.md`](reports/TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902-report.md).
- Execution-overhead policy report: [`ai/reports/TASK-VIBECODING-EXECUTION-OVERHEAD-OPTIMIZATION-V1-20260902-report.md`](reports/TASK-VIBECODING-EXECUTION-OVERHEAD-OPTIMIZATION-V1-20260902-report.md).
- Cleanup/VibeCoding V1.3 report: [`ai/reports/TASK-CLEANUP-FINAL-CLOSEOUT-VIBECODING-V1.3-20260902-report.md`](reports/TASK-CLEANUP-FINAL-CLOSEOUT-VIBECODING-V1.3-20260902-report.md).
- Finding-009 review report: [`ai/reports/TASK-FINDING-009-CANONICAL-REVIEW-20260902-report.md`](reports/TASK-FINDING-009-CANONICAL-REVIEW-20260902-report.md).
- Python/root diagnostic report: [`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`](reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md).
- Bounded root refactor (CLI surfaces) report: [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902-report.md).
- Bounded root refactor (registry integrations) report: [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902-report.md).
- Checko registry move + immutability migration report: [`ai/reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md`](reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md).
- LLM integrations move report: [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902-report.md).
- Bounded root refactor Pass 6 (supplier identity domain):
  `backend/domain/supplier_identity/{email_extractor,inn_extractor,
  inn_resolver,verify}.py` are now the canonical implementations; all root
  copies are gone. `supplier_app`, `contact_crawler`, `collect_inn`,
  `web_lookup`, `mail.repository`, and both LLM/registry integration
  modules all import successfully offline; `api.index.handler`/`_APP`
  imports under `SUPPLYDESK_ENV=test`. Behavioral evidence: the three
  custom root test scripts (`test_extractor.py`/`test_inn.py`/
  `test_verify.py`) all print "Все проверки пройдены" with exit `0`;
  `tests/test_enrichment_pipeline.py` + `tests/test_dashboard.py` (21/21
  PASS); the FINDING-018 LLM-path regression (3/3 PASS, unaffected);
  `supplier_discovery_v2/tests/` full suite (16/16 PASS, including 2 new
  immutability tests); diagnostics suite `61/70` PASS with the same 9
  pre-existing `pwsh`-gap errors as before.
- FINDING-018 fix report: [`ai/reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md`](reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md).
- Cross-agent skill availability report: [`ai/reports/TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902-report.md`](reports/TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902-report.md).
- Supplier identity domain move report: [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902-report.md).
- Search integrations move report: [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903-report.md).
- Contact crawler move report (Pass 8): [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903-report.md).
- Collect-inn pipeline/CLI split report (Pass 9): [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903-report.md).
- Serp-parser move report (Pass 10): [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903-report.md).
- Tests/legacy conversion report (Pass 11, final): [`ai/reports/TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903-report.md`](reports/TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903-report.md).
- FINDING-019 fix report: [`ai/reports/TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903-report.md`](reports/TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903-report.md).
- Repository layout map: [`docs/architecture/REPOSITORY_LAYOUT.md`](../docs/architecture/REPOSITORY_LAYOUT.md).
- Canonical duplicate audit: [`ai/reports/CANONICAL_DUPLICATES_BATCH2.md`](reports/CANONICAL_DUPLICATES_BATCH2.md).
- Batch 2 cleanup manifest: [`ai/reports/CLEANUP_BATCH2_MANIFEST.csv`](reports/CLEANUP_BATCH2_MANIFEST.csv).
- Audit pointer: [`ai/audits/2026-09-01-repository-hygiene/README.md`](audits/2026-09-01-repository-hygiene/README.md).

