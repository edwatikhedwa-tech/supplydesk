# Changelog

This is an append-only chronology. Existing entries must never be deleted or
rewritten.

## 2026-09-04 — SUPPLYDESK UI MODERNIZATION

- `TASK-SUPPLYDESK-UI-MODERNIZATION-20260904`: audited the frontend stack and
  real routes, then added a local UI foundation with `Button`,
  `StatusBadge`/`Count` and `TextField` primitives without adding shadcn,
  Radix or another dependency.
- Modernized `/messages` into a request-first procurement workspace: calm
  header/search, lightweight section navigation, quiet counters, semantic
  statuses, neutral unmatched preview, separate outbox and a single primary
  reply action. Existing reply, manual-link, metadata and recovery behaviors
  remain available.
- Added current audit/design-system docs and final report. `typecheck`, lint
  (0 errors, 5 pre-existing warnings), build and rendered Playwright/a11y
  matrix pass `88/88`; live CUA list/detail smoke passes at 1280×720.
- Before screenshot remains inline-only and no approved reference image was
  supplied; reference matching is `PARTIAL`. Backend and data were not changed.

## 2026-09-04 — MESSAGES PRODUCT ACCEPTANCE CORRECTION

- `TASK-MESSAGES-PRODUCT-ACCEPTANCE-CORRECTION-20260904`: corrected the
  rejected `/messages` behavior and presentation over commit `c70e6d63`.
- Added a shared repository business predicate so conversation views exclude
  pre-send queue/cancel/failure records while retaining inbound, sent,
  `delivery_unknown`, and post-transport failure/bounce evidence. Durable raw
  mail records are not deleted.
- Corrected detail width, compact request hierarchy, neutral unmatched preview,
  visible metadata controls and bounced status presentation. Existing manual
  linking and inline reply logic remain the source of truth.
- Verified: visibility regression tests `5/5`, metadata tests `2/2`, transport
  status tests `18/18`, the HTML/text rendering regression `1/1`, full
  `test_mail*.py` exit code `0`, frontend typecheck/build, lint with the same
  five unrelated warnings, and source diff checks.
- Live/browser status is `BLOCKED`: canonical port `8000` serves stale code
  (`POST /api/correspondence/metadata` -> `404`), the real pointer drag was
  attempted but did not create a link, and mandatory viewport screenshots are
  unavailable because the CUA browser exposes no viewport capability.

## 2026-09-04 — MESSAGES WORKSPACE REDESIGN + USER METADATA

- `TASK-MESSAGES-WORKSPACE-REDESIGN-20260904`: redesigned `/messages` into a
  procurement workspace with a desktop navigator/detail split, mobile
  list-to-detail behavior in code, global conversation search, request-group
  attention expansion, a three-item unmatched preview, accessible flag and
  priority controls, and shortened presentation-only supplier names.
- Added additive `mail_thread_user_metadata` persistence and
  `POST /api/correspondence/metadata`. The flag and priority are independent,
  scoped to user/workspace/request/supplier, optimistic in the UI, and do not
  alter mail or delivery statuses. Added a safe drag shortcut that only links a
  single exact sender match; ambiguous/domain/unknown cases remain manual.
- Confirmed: targeted backend tests (`6`, all pass), frontend typecheck/build,
  lint with the existing `5` warnings and no errors, migration creation in the
  disposable runtime, and an authenticated canonical-session desktop render.
- `NOT VERIFIED`: authenticated SAFE_TEST browser flow, real drag/drop against
  a disposable seeded correspondence, tablet/mobile screenshot matrix, and
  the absent repository `scripts/audit_toolchain.py`/geometry runner.

## 2026-09-04 — LOGISTICS: LIVE DELLIN KEY CONNECTED, TERM_DAYS FALLBACK FIX

- Owner shared the real `DELLIN_API_KEY` (Dellin registration approved);
  added to the local `.env` only. A real calculation against `api.dellin.ru`
  returned `status: "success"`, `price: 15422.0 RUB` — first genuine
  non-mocked proof the MVP integration works.
- The same live call showed `term_days` came back `None` because
  `_compute_term_days` only checked `orderDates.giveoutFromOspReceiver`,
  absent in this real response. Fixed to fall back through
  `giveoutFromOspReceiver` → `derivalFromOspReceiver` → `arrivalToOspReceiver`;
  re-verified live — `term_days: 2`. Two new tests added; logistics suite
  now `13 tests, all pass`.
- Commercial authorization to use the Dellin API in a paid SaaS product
  remains `NOT VERIFIED` — unaffected by this key.

## 2026-09-03 — RUNTIME MODE ROOT-CAUSE FIX + FULL .ENV RECOVERY

- `TASK-ROOT-CAUSE-RUNTIME-FIX-20260903`: fixed the root cause of a Yandex
  OAuth callback-mismatch — a prior session's "start the server" shortcut
  used the `SAFE_TEST` runtime (port `18000`, credentials always blanked)
  instead of `LOCAL_CANONICAL` (port `8000`, the port actually registered
  with Yandex), without re-checking `PROJECT_MANIFEST.yaml`.
- `DECISION-016`: `PROJECT_MANIFEST.yaml` now names both runtime modes
  explicitly in a new `runtime_modes` block (first source of truth);
  `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md` gives one
  unambiguous start command per mode; `ai/AI_CONTRACT.md` rule 14 now
  requires classifying `RUNTIME_MODE` before any backend start.
- By explicit separate owner authorization, `.env` at the canonical checkout
  root was fully, automatically recovered (byte-for-byte, no manual secret
  selection) from the legacy recovery-only checkout, with the previous
  partial `.env` backed up locally first, two legacy-pointing DB-path
  variables removed, and non-secret `LOCAL_CANONICAL` runtime values set
  explicitly. No secret value was ever printed to chat, logs or a report.
- Verified against a real `LOCAL_CANONICAL` run (`python supplier_app.py`,
  port 8000): root/`auth/me` 200, `/api/auth/yandex/start` redirects with
  `redirect_uri=http://127.0.0.1:8000/oauth/yandex/callback`, matching the
  legacy `YANDEX_REDIRECT_URI` exactly. Port 18000 confirmed not in use.
- Report: [`ai/reports/TASK-ROOT-CAUSE-RUNTIME-FIX-20260903-report.md`](reports/TASK-ROOT-CAUSE-RUNTIME-FIX-20260903-report.md).

## 2026-09-03 — LOGISTICS: DELLIN SHIPPING-COST CALCULATOR MVP

- `TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903`: added a manual shipping-cost
  calculator for one request/one supplier against the Деловые Линии (Dellin)
  public calculator API. New `backend/integrations/logistics/dellin_client.py`,
  `backend/domain/logistics/quote_service.py`, `mail/logistics_quotes.py`
  (`LogisticsQuotesMixin`), `migrations/033_logistics_quotes.sql` (executed
  under explicit one-migration owner authorization), a "Логистика" section in
  `SupplierPanel.tsx`, and `tests/test_logistics_quote.py` (11 tests).
- Dellin's request/response schema was verified against the official
  documentation via the public Wayback Machine archive (`dev.dellin.ru`
  itself blocks direct automated fetches) before writing any code — no field
  was guessed from memory.
- A hard gate blocks calculation until every required field is present; a
  contract/unknown price, provider error or rate limit always resolves to an
  explicit non-success status with a message, never a `0 ₽` price.
- Official suite: `515 tests, failures=0, errors=9 (pre-existing, unchanged),
  skipped=1`. Frontend typecheck/build clean, lint 0 errors/5 warnings (no
  new errors). Manually verified end-to-end against the safe `OFFLINE_TEST`
  runtime in a real browser.
- `NOT VERIFIED`: a real call to `api.dellin.ru` with an actual
  `DELLIN_API_KEY`, and whether commercial use of the Dellin API in a paid
  SaaS product is contractually authorized.
- Report: [`ai/reports/TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903-report.md`](reports/TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903-report.md).

## 2026-09-03 — REFACTOR SERIES CLOSEOUT + ARCHITECTURE PROGRAM PAUSED

- A read-only recovery audit on `integration/current-architecture-governance-20260903`
  @ `a88334deb59f32d43f79afca63f71fc7bf263da0` found `NO_UNFINISHED_REFACTOR_FOUND`:
  every bounded extraction pass reached full close and is already integrated;
  the remaining architecture program has zero commits anywhere in the
  repository — only prose next-step language.
- Owner decision recorded as `DECISION-014`: the current bounded-refactor
  series (`TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903`,
  `TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903`,
  `TASK-BOUNDED-MAIL-REPOSITORY-DB-COMPAT-EXTRACT-20260903`,
  `TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903`,
  `TASK-BOUNDED-SUPPLIER-APP-ROUTE-HELPERS-EXTRACT-20260903`,
  `TASK-BOUNDED-MAIL-REPOSITORY-AUTH-ACCOUNTS-EXTRACT-20260903`,
  `TASK-BOUNDED-MAIL-REPOSITORY-TEMPLATES-EXTRACT-20260903`) is closed. The
  remaining architecture program (campaign lifecycle extraction,
  queue/send-attempt refactor, inbox-reply refactor, `supplier_app.py` mail
  HTTP batch C, dispatch-table conversion, further architecture-enforcement
  changes) is `PAUSED` pending a new direct owner instruction with its own
  Task ID, scope, non-goals, allowed files and acceptance criteria.
- Classifier-selected CI (`33763726815`) on this HEAD is `SUCCESS`. Exact
  suite result: `tests=504, failures=0, errors=9, skipped=1` — the 9 errors
  are the same pre-existing `pwsh`-gap documented across every prior task on
  this line and were **not** fixed here; not in this closeout's scope.
- State-only task: no product code, frontend, backend, test or dependency
  file changed; `ai/DEFERRED_FINDINGS.md` unchanged; `ai/ACTIVE_TASK.md`
  remains `IDLE`.

## 2026-09-03 — COLD-START WORKSPACE HARD GATE

- Added `SESSION_WORKSPACE_HARD_GATE` before all project analysis, including
  read-only tasks. The guard now has one explicit stop outcome:
  `BLOCKED_WRONG_WORKSPACE`.
- Unified the canonical policy pointers in `AGENTS.md`, `CLAUDE.md`,
  `PROJECT_MANIFEST.yaml` and `ai/AI_CONTRACT.md`; added 5 focused governance
  tests, bringing the guard-focused set to `8/8`.
- Updated the legacy checkout's local marker and adapters to point to
  `C:\Users\edwat\SupplyDesk` and stop project work there. Those local safety
  changes were not synchronized or published.
- Codex fresh canary passed in canonical and legacy contexts. Claude fresh
  behavior is `NOT VERIFIED` because both post-fix CLI attempts ended with the
  same API 200 malformed-response error. See the task report.

## 2026-09-03 — CI CAPACITY FIX CONFIRMED + NEW FLAKY TEST FOUND

- The Windows Defender exclusion fix (`6af2af1`) is now `CONFIRMED`, not
  just applied: on the classifier-selected CI run for
  `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903`
  (`33691773114`), `Backend Full` completed the real `462`-test suite twice
  in a row — `18m54s` then `24m0s` on an unmodified rerun — never
  cancelled, well inside the `35`-minute timeout. The earlier dedicated
  `workflow_dispatch profile=FULL` run (`33690006924`) was inconclusive on
  its own: it got cancelled by the branch's concurrency group when this
  push's own CI run started, after running ~19 minutes without hitting the
  timeout or a failure — this later run supersedes it with a clean,
  uninterrupted confirmation.
- Now that the suite can finally run to completion instead of being cut off
  by the old timeout, its first full pass surfaced one previously-masked,
  unrelated test failure:
  `tests.test_mail_integrity.MailIntegrityAcceptanceTests.test_35_disabled_wait_preserves_retry_budget_for_real_transport_attempt`
  (`AssertionError: 'sending' != 'queued'`). Read the test
  (`tests/test_mail_integrity.py:874-909`): it polls
  `self.provider.send_calls` until it reaches `1`, then immediately asserts
  the job row's DB `status`, with no synchronization guaranteeing the
  background `MailQueue` worker thread has finished writing the final
  status by that point — a genuine race in the test's own polling logic.
  Confirmed not caused by this branch: it passed clean on an identical
  rerun with zero code changes, and it lives in a module unrelated to the
  search-integrations move. Flagged as a separate, out-of-scope background
  task rather than fixed here.

## 2026-09-03 — BOUNDED ROOT REFACTOR PASS 7: SEARCH INTEGRATIONS

- Moved `web_lookup.py` and `xmlriver_client.py` (both `MOVE_INTEGRATIONS`
  in the root diagnostic) to `backend/integrations/search/`; both are
  0-diff pure moves proven by `git diff --cached -M --stat`.
- Updated 6 confirmed consumers to the canonical import path:
  `supplier_app.py`, `collect_inn.py` (lazy import),
  `scripts/collect_contacts.py` (lazy import), `test_extractor.py`,
  `serp_parser.py` (import line only — the file itself stays `DEFER`red),
  `test_parser.py`. Verified `supplier_discovery_v2/xmlriver_subprocess.py`
  is unaffected (invokes `serp_parser.py` by absolute path via
  `subprocess.run(..., cwd=...)`).
- Migrated `supplier_discovery_v2/immutability_check.py`'s protected-path
  list for both files to their new location in the same change, proven via
  a real-tree baseline round-trip and a disposable synthetic tempfile-tree
  mutation-detection test; the guard was never weakened. Added two new
  permanent tests to `supplier_discovery_v2/tests/test_immutability.py`.
- Regression evidence: official backend suite `462 tests, failures=0,
  errors=9 (pre-existing pwsh gap), skipped=1`; `test_extractor.py`/
  `test_parser.py` both "Все проверки пройдены" exit 0;
  `tests/test_enrichment_pipeline.py` 8/8; full
  `supplier_discovery_v2/tests/` 18/18.

## 2026-09-03 — CI CAPACITY REAL FIX: WINDOWS DEFENDER EXCLUSION FOR BACKEND FULL

- Root-caused the `Backend Full` `CI_INFRA` timeout (previous entry):
  extracted per-test start timestamps from the CI logs of all three prior
  failed attempts and found the slowdown is not uniform across the suite —
  a concentrated set of tests in `tests/test_mail_deliverability.py` and
  `tests/test_mail_integrity.py` (heavy `MailRepository`/SQLite users, each
  creating a `tempfile.TemporaryDirectory()`) individually took 7–60
  seconds on the CI runner versus a sub-second average locally.
- No Windows Defender exclusion existed for the runner's workspace/temp
  paths in `.github/workflows/ci.yml`. Real-time Defender scanning of every
  small SQLite file write/read is a well-documented cause of large
  slowdowns for I/O-heavy suites on GitHub-hosted Windows runners. Added a
  best-effort `Add-MpPreference -ExclusionPath` step (workspace + both temp
  env vars) to the `backend_full` job only, right after the workspace
  guard — a standard, no-risk mitigation on an ephemeral, destroyed-after-job
  VM. No test logic, other job, or timeout changed in this step; the prior
  owner-approved `timeout-minutes: 35` was left as a safety margin, not
  reverted.

## 2026-09-03 — CI CAPACITY FIX: BACKEND FULL TIMEOUT — TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902 (follow-up)

- `SupplyDesk / Backend Full` failed twice in a row on push, both times
  cancelled by its own `timeout-minutes: 25` at `25m10s`
  (`KeyboardInterrupt`/`The operation was canceled`, not an assertion or
  import failure), each time at a different test inside the same slow
  `tests/test_mail_pacing.py` suite. Local evidence with the exact same
  official runner (`scripts/run_test_suite.py --suite full`): `460` tests,
  `failures=0`, `errors=9` (the same pre-existing `pwsh`-gap already proven
  unrelated), `skipped=1`, in `3m46s` — confirming `FAILURE_DOMAIN: CI_INFRA`
  (the 25-minute cap had become too tight for the current suite size on the
  shared Windows runner), not a product regression from the supplier-identity
  move.
- Owner explicitly authorized a minimal, narrow scope extension: raised
  `.github/workflows/ci.yml`'s `backend_full` job `timeout-minutes` from
  `25` to `35` — one line, no other job/timeout/test changed.
- The owner-approved verification (one manual `workflow_dispatch`
  `profile=FULL` run, since the CI-fix push itself was too narrow to
  reclassify `backend_full`) showed the same `KeyboardInterrupt`/"The
  operation was canceled" pattern a third time, now at exactly `35m5s` —
  the new limit, not a logic failure, and again at a different test
  (`tests/test_mail_status_semantics.py`) than either prior attempt. Per
  the owner's explicit stop condition, the timeout was **not** raised
  further. `FULL_CI` / `Backend Full` for this branch remains `FAIL` on a
  `CI_INFRA` basis (confirmed non-product: local `scripts/run_test_suite.py
  --suite full` continues to show `460 tests, failures=0, errors=9
  (pre-existing pwsh-gap), skipped=1` in under 4 minutes). Root cause of
  why the suite now needs more than 35 minutes on the shared Windows
  runner is `NOT VERIFIED` and is out of this task's scope to investigate
  further. The same `workflow_dispatch` run also exercised `Browser Full`,
  which failed independently — this matches the already-recorded,
  unrelated `TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902` limitation
  (root cause not confirmed) and was not investigated further here.

## 2026-09-02 — BOUNDED ROOT REFACTOR: SUPPLIER IDENTITY DOMAIN — TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902

- Moved `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, and
  `verify.py` to `backend/domain/supplier_identity/`. `git diff -M`
  confirmed `email_extractor.py`/`inn_extractor.py` as 0-diff pure moves;
  `inn_resolver.py`/`verify.py` changed only their internal import lines
  (2 module-level imports each). No extraction, scoring, validation,
  checksum, registry-ownership, or SMTP/MX semantics changed.
- Updated all 15 confirmed consumers, including 4 not named in the task's
  own known-dependency list and found only by a fresh full-tree scan:
  `web_lookup.py`, `mail/repository.py` (a single import line — the rest
  of the mail domain's business logic was not touched),
  `backend/integrations/registry/dadata_client.py`, and
  `benchmarks/benchmark_models.py` (initially missed in a partial check,
  caught by the full diagnostics run before publish).
- Migrated `supplier_discovery_v2/immutability_check.py`'s protected-path
  list for the three already-protected files
  (`email_extractor.py`/`inn_extractor.py`/`verify.py`) to their new
  canonical location; `inn_resolver.py` was deliberately left unprotected
  — it was never protected before, and sitting beside the other three is
  not evidence for adding it. Proved with a fresh baseline round-trip and
  a disposable synthetic-copy mutation test for all three paths, added as
  permanent regression coverage.
- This task's own numeric `CHANGE_BUDGET_EXCEEDED` threshold (">22 tracked
  files") was hit at 24. All work was fully applied and tested first; the
  publish step (commit/push) was paused, concrete evidence was presented,
  and the owner explicitly approved continuing without a rollback, since
  the overage was 4 legitimate discovered dependents rather than scope
  creep into an unrelated subsystem.

## 2026-09-02 — CROSS-AGENT SKILL AVAILABILITY — TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902

- Made `bug-reproducer`, `code-rot-cleaner`, and `skill-doctor` actually
  discoverable by Claude Code, not just Codex, using the official
  multi-agent `skills` CLI (`npx skills@latest`). `bug-reproducer` and
  `code-rot-cleaner` were installed for Claude Code from the existing local
  Codex source (`Source: local` — no known public upstream); `skill-doctor`
  was installed for Claude Code from its real public upstream
  (`warpdotdev/common-skills`) via the same officially supported
  `-a claude-code` multi-agent flag. Existing Codex installations were left
  untouched; no upstream `SKILL.md` was edited, forked, or vendored into
  this repository.
- Confirmed `agent-browser` already reaches both agents equally through its
  own CLI runtime-loading mechanism (`agent-browser skills get core
  --full`), distinct from the `SKILL.md` file-discovery mechanism used by
  the other three — no installation was needed or applicable there.
- Added one compact `REGISTRY_AGENT_VISIBILITY` rule to
  `ai/AI_CONTRACT.md`: a global `CONFIGURED` in
  `ai/VIBECODING_TOOL_REGISTRY.yaml` records that a tool/skill is known
  installed somewhere locally, not that the current agent/session can
  invoke it — verify current-agent discovery once per session before first
  use. Recorded per-agent status in the registry's existing `notes` fields
  for the 4 affected entries; no new schema field was added (the
  registry's regex-based validator would not parse a nested mapping
  safely).

## 2026-09-02 — FIX FINDING-018 — TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902

- Fixed `collect_inn.py --llm`: it imported a nonexistent `InnLlmExtractor`
  symbol and told operators to set `ANTHROPIC_API_KEY`. `git log -S` (one
  match: the initial bulk-import commit) plus existing product documentation
  (`Documents/28-8/enrichment-and-cache.md`) confirmed `InnLlmExtractor`
  never existed and is a documented leftover from the pre-RouterAI version —
  `LlmExtractor` is the intended implementation, already used correctly in
  `supplier_app.py`.
- Used a deterministic RED→FIX→GREEN bug-workflow with two owner approval
  gates (reproduction plan, then fix plan). The installed `bug-reproducer`
  skill is not available in this Claude Code session (`ListSkills` returned
  zero results), so the `BUG_REPRODUCER` methodology from
  `ai/AI_CONTRACT.md` was applied directly with this session's own tools and
  reported as `TYPE: WORKFLOW`, not `TYPE: SKILL`.
- Added `tests/diagnostics/test_collect_inn_llm_path.py`, which exercises
  the real `collect_inn.main()` CLI path with only the crawler/dotenv
  boundaries stubbed. It failed with the exact predicted `ImportError`
  before the fix and passed after it — zero live provider calls throughout.
- Fix: `collect_inn.py` now imports `DEFAULT_MODEL, LlmExtractor,
  api_key_present`, constructs `LlmExtractor(model=args.llm_model or
  DEFAULT_MODEL)` (matching the existing safe pattern in
  `scripts/collect_contacts.py`), and its missing-key message now names
  RouterAI/`ROUTERAI_KEY`. No prompts, schemas, `DEFAULT_MODEL` value, or
  provider behavior changed. `FINDING-018` is now `RESOLVED`.

## 2026-09-02 — BOUNDED ROOT REFACTOR: LLM INTEGRATIONS — TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902

- Moved `llm_fallback.py` and `routerai_client.py` to
  `backend/integrations/llm/`. `git diff -M` confirmed `100%`/`99%`
  similarity (the only change: one internal lazy import updated to the
  canonical path); prompts, schemas, `DEFAULT_MODEL` and RouterAI request/
  response behavior are unchanged. Updated the 4 known consumers
  (`supplier_app.py`, `collect_inn.py`, `scripts/collect_contacts.py`,
  `benchmarks/benchmark_models.py`); no root compatibility wrapper.
- Discovered and deferred (not fixed — out of this task's scope) a
  pre-existing, unrelated bug: `collect_inn.py --llm` imports a nonexistent
  `InnLlmExtractor` symbol from `llm_fallback`, and its error text names the
  wrong environment variable. Recorded as `FINDING-018`; the move preserves
  the identical failure mode.
- Added `tests/diagnostics/test_llm_integration_move.py` (6 tests) — no
  prior coverage existed for either module since both are only reached
  through env/flag-gated lazy imports offline suites never trigger.

## 2026-09-02 — SKILL DOCTOR SD-001 APPLIED — CLAUDE.md instruction-check pointer fix

- The first Skill Doctor review (read-only, no repository changes) found
  that `CLAUDE.md`'s closing instruction pointed at
  `ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md` for "the instruction-check
  block," but that file is the Claude-Project (chat UI) adapter and defines
  no such block — the real rule is `ai/AI_CONTRACT.md`'s
  `TOOL_USAGE_REPORTING`.
- Applied SD-001 only: `CLAUDE.md` now points directly at
  `ai/AI_CONTRACT.md`'s `TOOL_USAGE_REPORTING` rule for the
  `[ИНСТРУМЕНТЫ И SKILLS]` block, plus the canonical VibeCoding
  acknowledgement requirement. No format was copied into `CLAUDE.md`.
- SD-002 (a proposed `MOVE_REFERENCE_SCAN_RULE` in `ai/AI_CONTRACT.md`) was
  rejected as a duplicate: existing `rg`-based reference/import/route/config
  search expectations and `CODE_ROT_AUTHORITY`'s reference/import/string/
  config search already cover this; the missed literal `"checko_client.py"`
  path in an earlier diagnostic was incomplete execution of an existing
  rule, not a proven instruction gap. `ai/AI_CONTRACT.md` and
  `ai/VIBECODING_RULES.md` were not changed.

## 2026-09-02 — CHECKO REGISTRY MOVE + IMMUTABILITY GUARD MIGRATION — TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902

- Completed the deferred `checko_client.py` move: it now lives at
  `backend/integrations/registry/checko_client.py` (byte-identical), with
  `supplier_app.py`, `scripts/verify_enrichment_live.py`, and
  `tests/test_enrichment_pipeline.py` updated to the canonical import path.
  No root wrapper — no confirmed external consumer of the old path.
- In the same change, migrated
  `supplier_discovery_v2/immutability_check.py`'s protected-path entry from
  the root `checko_client.py` to the new location, so the existing
  immutability guard was never weakened. Proved this with a fresh baseline
  round-trip against the moved tree (clean) and a disposable synthetic-copy
  mutation of the new path (correctly detected as changed), both via
  temporary paths only — no real project file was mutated to test this.
- Added 2 tests to the existing `supplier_discovery_v2/tests/test_immutability.py`
  instead of a new harness. `FINDING-017` is now `RESOLVED`.

## 2026-09-02 — BOUNDED ROOT REFACTOR: REGISTRY INTEGRATIONS — TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902

- Moved `dadata_client.py` to `backend/integrations/registry/dadata_client.py`
  (new `backend/` product-code area) and updated its one known consumer,
  `collect_inn.py`'s lazy import. No root compatibility wrapper: no confirmed
  external consumer of the root import path was found.
- `checko_client.py` was intentionally **not** moved: a fresh reference scan
  found `supplier_discovery_v2/immutability_check.py:16` hardcodes a
  root-relative `"checko_client.py"` path in its protected-files hash list,
  and updating it would require touching `supplier_discovery_v2/`, which was
  out of this task's declared scope. Recorded as `FINDING-017` in
  `ai/DEFERRED_FINDINGS.md` for a follow-up task.
- Verified the full offline import chain
  (`api.index → supplier_app → collect_inn → backend.integrations.registry.dadata_client`)
  under `SUPPLYDESK_ENV=test`, with no live provider calls. Added
  `tests/diagnostics/test_registry_integration_move.py` (3 tests) and
  `docs/architecture/REPOSITORY_LAYOUT.md`.

## 2026-09-02 — BOUNDED ROOT REFACTOR: MANUAL CLI SURFACES — TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902

- Moved the `collect_contacts.py` implementation to `scripts/collect_contacts.py`
  and the `benchmark_models.py` implementation to `benchmarks/benchmark_models.py`,
  per the `MOVE_SCRIPTS` decisions in
  `ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`.
- Root `collect_contacts.py` and `benchmark_models.py` are now thin
  compatibility wrappers that delegate to the moved implementations; no
  business logic was duplicated.
- Repository-root `.env` lookup was preserved with an explicit
  `Path(__file__).resolve().parents[1]` calculation (matching the existing
  convention in `scripts/run_test_suite.py`); relative `results/`/`cache/`
  paths were left CWD-relative and unchanged.
- Added `tests/diagnostics/test_operator_cli_root_compat.py` (4 tests) to
  guard the `.env`-root regression and wrapper-delegation risk. No other
  root Python module was moved; product behavior did not change.

## 2026-09-02 — CANONICAL LOCAL SECRET HYGIENE REVIEW — TASK-CANONICAL-LOCAL-SECRET-HYGIENE-REVIEW-FINAL-20260902

- Repeated the local credential hygiene review in the canonical
  `C:\Users\edwat\SupplyDesk` checkout using filenames and Git metadata only.
- No current operational env files, tracked operational secret paths or
  operational env paths in Git history were found; `.env.example` remains
  history-only and content-unverified.
- Retained snapshot/quarantine filename copies were found, so `FINDING-009`
  remains `REVIEW_REQUIRED`. No secret values, files, quarantine contents or
  Git history were changed.

## 2026-09-02T09:14:44Z — VIBECODING EXECUTION OVERHEAD OPTIMIZATION V1 — TASK-VIBECODING-EXECUTION-OVERHEAD-OPTIMIZATION-V1-20260902

- Added canonical VibeCoding V1.2 semantics for Session Preflight, Task
  Preflight and Continuation/Action checks with explicit revalidation reasons.
- Added lazy skill loading, verification budgets, Repeat-Error Rule, Change
  Budget, scope-based state updates, parallel-work preparation and status-noise
  control; aligned the shared AI contract, adapters and workflow.
- Added semantic validator markers and focused governance coverage; `14` tests
  and the VibeCoding validator passed. No product/runtime/database behavior
  changed; backend/frontend/Playwright were not needed.

## 2026-09-02T05:35:37Z — VIBECODING FINAL STATUS SEMANTICS FIX — TASK-VIBECODING-FINAL-STATUS-SEMANTICS-FIX-20260902

- Added canonical final-status semantics: `NOT_NEEDED` is not a limitation;
  required `NOT_VERIFIED` produces `PASS_WITH_LIMITATIONS`; required `FAIL`
  produces `FAIL`.
- Added a minimal pure-governance evaluator and focused A–D tests, including a
  governance-only task with product acceptance classified as `NOT_NEEDED`.
- No product code, CI architecture, backend/frontend/browser behavior or
  external service was changed or executed.

## 2026-09-01T22:16:53Z — VIBECODING ACKNOWLEDGEMENT OUTPUT FIX — TASK-VIBECODING-ACKNOWLEDGEMENT-OUTPUT-FIX-20260902

- Replaced the old response-prefix instruction with a final-response-only
  acknowledgement contract in the canonical VibeCoding policy and both
  instruction adapters.
- Extended `ai/tools/validate_vibecoding.py` to require the final-only and
  intermediate-prohibition markers, reject stale prefix instructions and reject
  hardcoded acknowledgement dates outside canonical `last_corrected`.
- Added focused negative governance fixtures for missing final semantics, stale
  intermediate prefix behavior and embedded dates.
- No product code, CI workflow, database, environment, mail data or frontend
  behavior changed; backend/frontend/Playwright acceptance was intentionally not
  run because this task is governance-only.

## 2026-09-01T15:50:00Z — OPEN / SAFE TEST RUNTIME — TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901

- Независимо подтверждён remote HEAD V1.1 и создан отдельный worktree/branch
  `control/reproducible-test-runtime-v1-20260901`; исходный checkout не менялся.
- Проведён audit тестов: текущий backend/discovery/diagnostic набор использует
  `unittest`; `pytest` и `pytest-cov` не доказаны и не добавлялись.
- Добавлены отдельный `requirements-test.txt`, официальный offline runner,
  bootstrap test-venv, safe runtime entrypoint/start/stop и profile-aware Doctor.
- Проверено: diagnostic suite `25 PASS`; затем официальный полный runner
  `411 tests, 0 failures, 0 errors, 1 skipped`; frontend clean `npm ci`,
  typecheck, lint с 8 предупреждениями и build прошли; Playwright Chromium
  установлен отдельно.
- Safe runtime поднят на disposable SQLite в `OFFLINE_TEST`; HTTP smoke и
  real-route public-shell acceptance `8 passed`; real mail/provider access не
  выполнялся.

## 2026-09-01T07:11:12Z — АУДИТ СИСТЕМЫ И ФРОНТЕНДА — TASK-SYSTEM-FRONT-AUDIT-20260901

- Изучены state-документы, `docs/**`, `Documents/28-8/**`, журналы, исходники,
  deployment config, read-only SQLite и runtime.
- Сохранён аудит с доказательствами и критериями исправления: обнаружены
  расхождение источников состояния, production `/tmp` fallback без fail-closed
  проверки, невоспроизводимый backend test gate, неоднозначная mail metric,
  composer accessibility issue, красный Storybook visual gate и security gaps.
- Проверены HTTP/runtime/database и frontend gates; outgoing оставлен выключенным.
- Application code, frontend code, API, database rows, migrations, mail settings
  и внешние сервисы не менялись. State backups сохранены в
  `Temp/20260901-system-front-audit/`.
- Report: `ai/reports/TASK-SYSTEM-FRONT-AUDIT-20260901-report.md`.

## 2026-09-01T06:38:31Z — ПОНЯТНАЯ ПРОВЕРКА ПРАВИЛ — TASK-INSTRUCTION-CHECK-UX-20260901

- Заменён непонятный английский шаблон `[INSTRUCTION CHECK]` с несколькими
  вариантами через `/` на русскую проверку `[ПРОВЕРКА ПРАВИЛ]`.
- В готовом ответе теперь должны быть только фактические значения и короткое
  объяснение простыми словами; пустые варианты и необъяснённые статусы
  запрещены.
- Основные правила изменены в `AGENTS.md` и `ai/AI_CONTRACT.md`; обязательные
  state-документы и отчёт обновлены отдельно для сохранения истории.
  Код, база, сервер, письма и пользовательские рабочие файлы не менялись.
- Перед правкой сохранены резервные копии инструкций во временной папке;
  проверены state-валидатор и итоговый diff.

## 2026-09-01T06:13:09Z — HISTORICAL QUEUE RECONCILIATION COMPLETE — TASK-MAIL-STATUS-RECONCILIATION-20260901

- Applied an allowlisted, evidence-gated and idempotent local reconciliation:
  jobs `49`/`54` became `delivery_unknown`; job `71` was cancelled and its
  campaign target marked `reconciled` because Mail.ru acceptance already
  exists for the exact recipient.
- Created a verified pre-change database backup. Plan, DryRun, Apply and the
  repeated DryRun used zero SMTP calls while durable outgoing and active
  reservations remained zero.
- Request `1059` now has no queued jobs, no duplicate sent recipient and no
  recipient with multiple accepted attempts; the continuation plan is empty.
- Added reconciled acceptance to request facts and explicit Russian contact
  counts to grouped mail status badges.
- Verified full backend discovery (`374` pass, one expected PostgreSQL skip),
  frontend typecheck/lint/build, eight responsive Playwright projects, three
  live rendered widths, SQLite and HTTP/API smoke.

## 2026-09-01T05:53:58Z — HISTORICAL QUEUE RECONCILIATION START — TASK-MAIL-STATUS-RECONCILIATION-20260901

- Owner instructed the agent to complete all remaining tasks from the current
  mail-delivery chain.
- Confirmed three stale queue contradictions without changing data: two
  irreversible disputed transients and one recipient with durable reconciled
  Mail.ru acceptance.
- Scoped the implementation to evidence-gated local reconciliation, request
  fact aggregation, explicit multi-contact badge labels and verification.
- No SMTP, account, credential or unrelated worktree action is allowed.

## 2026-09-01T05:43:31Z — MAIL.RU FINAL CONTINUATION COMPLETE — TASK-MAILRU-FINAL-CONTINUATION-20260831

- Completed thirteen bounded Mail.ru continuation plans: `60` SMTP
  `post_data / 250` acceptances, one permanent pre-DATA recipient rejection,
  and zero unknown outcomes.
- Verified the final continuation is empty, duplicate sent recipients are
  zero, accepted-attempt duplicates are zero, SQLite integrity is `ok`, and
  outgoing is effectively OFF.
- Diagnosed the owner's mixed-status screenshot as an intermediate
  four-contact company card. The last queued contact later completed and the
  live card now shows `Отправлено · 4`.
- Recorded three historical Yandex queue records as a local status-cleanup
  follow-up; none is safe or necessary to send through Mail.ru.

## 2026-08-31T18:58:08Z — MAIL.RU FINAL CONTINUATION START — TASK-MAILRU-FINAL-CONTINUATION-20260831

- Owner explicitly instructed the agent to finish the remaining supplier
  delivery without further confirmation prompts and without duplicate mail.
- Verified the running local server, authenticated API, Mail.ru account `23`,
  durable/effective outgoing OFF, closed account breaker, no cooldown and no
  active pacing reservation.
- A fresh read-only continuation dry-run for campaign `2` returned
  `safe=true`, `61` strictly untouched recipients and zero live sends.
- Created a consistent pre-send SQLite backup with
  `PRAGMA integrity_check=ok`; controlled execution will use fresh bounded
  plans and one transport job at a time.

## 2026-08-31T18:38:35Z — MESSAGES PRIMARY CORRESPONDENCE FILTER — TASK-MESSAGES-PRIMARY-FILTER-20260831

- Changed the default `/messages` correspondence list to show only threads
  with sent outbound mail or a supplier reply; pending outgoing mail remains in
  the separate queue tab.
- Preserved API, database, mail transport, delivery, request-link and queue
  behavior. Direct delivery-unknown thread access remains actionable.
- Verified typecheck, build, lint, focused Playwright regressions and real
  no-route-mock browser checks at `1440x900` and `390x844`.
- Runtime evidence at verification time: correspondence `80`, primary `77`,
  queue `64`, no browser/request errors. Report and screenshots are stored in
  `ai/reports/TASK-MESSAGES-PRIMARY-FILTER-20260831-report.md` and
  `Temp/messages-primary-filter-20260831/`.

## 2026-08-31 — CID IMAGE HEIGHT FIX — TASK-MESSAGES-CID-HEIGHT-FIX-20260831

- Fixed a fast inline-image timing issue in `EmailRenderer` that could leave
  the mail iframe at `24px` and clip a CID image.
- Added a MIME-derived local CID fixture, Storybook coverage and responsive
  Playwright evidence for `390`, `1024`, `1440` and `1640` pixel widths.
- Typecheck, build, lint and the three-case Storybook responsive suite passed.
  The full live no-route-mock suite remains unverified after two 3-minute
  timeout attempts; this is recorded in the task report.
- No external send, SMTP/IMAP, API, queue, status, filter or request-link
  behavior was changed.

## 2026-08-31T17:52:01Z — FRONTEND FIXES AND MAILRU CONTINUATION HOLD — TASK-FRONTEND-MAILRU-CONTINUATION-20260831

- Applied the scoped frontend recommendations and committed them as
  `568391d` (code commit; push not run).
- Verified typecheck/build/lint, `80/80` visual scenarios, live desktop/mobile
  dialog screenshots, `230/230` targeted mail safety tests, doctor DryRun and
  local HTTP smoke with outgoing OFF.
- Read-only canonical preflight identified two and only two untouched queued
  Mail.ru recipients: `support@prometall.ru` and `89087178701@mail.ru`.
- No provider send was started. The exact batch is held for action-time owner
  confirmation; accepted and uncertain historical recipients remain excluded.
- Full backend discovery is not PASS because the system lxml DLL/parser is
  broken and one pre-existing quote-folding assertion fails; this is recorded
  in the task report.

## 2026-08-31T16:45:33Z — REAL-DATA MESSAGES ACCEPTANCE — TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831

- Completed 8 no-route-mock Playwright checks against real `/messages` data:
  manual link, reload persistence, unlink restoration, mobile dialog, queue and
  unread marker.
- Verified `0` console errors, `0` page errors, `0` failed requests and `0`
  unexpected non-2xx responses. Outgoing remained disabled.
- No application code changed. A real binary CID attachment was not present in
  the inspected data; this limitation is recorded in the task report.
- Report and screenshots:
  `ai/reports/TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831-report.md` and
  `Temp/real-data-acceptance-messages-20260831/`.

## 2026-08-31 — PLAIN-LANGUAGE RESPONSE RULE — TASK-COMMUNICATION-RULE-20260831

- Added a project-level rule for concise Russian responses with three opening
  blocks: `Сделано`, `Проблемы и ограничения`, and `Следующий шаг`.
- Technical terms and raw check results must now be explained in user-facing
  language; the instruction-check block remains a final service summary.
- Application code was not changed. Report:
  `ai/reports/TASK-COMMUNICATION-RULE-20260831-report.md`.

## 2026-08-31 — MESSAGES STATUS FILTER — TASK-MESSAGES-STATUS-FILTER-20260831

- Moved visible `Ожидает ответа` from correspondence rows into a top
  client-side filter with counts; stronger accent-blue styling was applied to
  `Ответ получен`.
- No mail transport, queue, API, database, request-link or outbound behavior
  was changed.
- Real no-mock Playwright passed at `390`, `1024`, `1440`, `1640`; live email
  regression passed `1/1`. Report:
  `ai/reports/TASK-MESSAGES-STATUS-FILTER-20260831-report.md`.

## 2026-08-31T13:25:18Z — YANDEX SENT-COPY SEARCH — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- In the authenticated Yandex Mail UI, searched the exact RFC
  `<178792659593.14496.8632352531530487831@yandex.ru>` with the
  `Отправленные` filter.
- Provider UI result: `Таких писем не нашлось`. This classifies the exact RFC
  as `NOT_FOUND` in the selected Sent view, not as proof of external
  non-delivery.
- Yandex `delivery_unknown` row, Mail.ru row, database, campaign and outgoing
  control were not changed. No retry and no SMTP DATA were performed.

## 2026-08-31T13:09:09Z — BROWSER FALLBACK — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Yandex Mail opened in the authenticated browser; its `Отправленные` folder
  is available for read-only verification.
- Mail.ru redirected to VK authentication. The connected browser safety policy
  blocked that protected page, so no bypass or alternate execution path was
  attempted. Manual completion of the Mail.ru/VK login is required.
- No mailbox mutation, database change, campaign change or SMTP operation was
  performed.

## 2026-08-31T12:58:26Z — LOCAL RUNTIME START ATTEMPT — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Attempted to start SupplyDesk on the canonical SQLite and port `8000` with
  `MAIL_OUTGOING_DISABLED=1`.
- The only bundled Python runtime stopped before binding because `nh3` is
  missing; `quotequail` and `bs4` are also absent. No alternate Python,
  accessible WSL distribution or running Docker engine is available.
- No database/mail/campaign state changed. The external TCP restriction and
  unresolved Sent-copy checks remain unchanged.

## 2026-08-31T12:53:28Z — ENVIRONMENT NETWORK FORENSICS — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Reproduced Windows `WinError 10013` / `PermissionError` for both configured
  IMAP endpoints and for unrelated public TCP targets `www.microsoft.com:443`
  and `1.1.1.1:443`.
- `127.0.0.1:8000` returned ordinary connection refusal because no local
  server is listening. Windows Firewall reports `AllowOutbound`; no proxy is
  configured and no explicit enabled outbound block rule was found.
- Root cause boundary: the current execution environment denies external TCP;
  this is not evidence of a Yandex/Mail.ru credential or provider-selection
  failure. Sent-copy lookup remains unverified.
- No mail/database/campaign state changed; outgoing remains OFF and SMTP DATA
  calls remain `0` for this task.

## 2026-08-31T12:46:00Z — READ-ONLY DELIVERY VERIFICATION — TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831

- Checked both existing `delivery_unknown` records: Yandex account `1`,
  job `20`/message `28`; Mail.ru account `23`, job `172`/message `190`.
- Decrypted only the account-specific credentials in memory. Yandex access and
  refresh credentials are present; the stored access-token expiry is in the
  future, so refresh was not attempted. Mail.ru app-password ciphertext is
  present.
- Attempted only read-only IMAP access to `imap.yandex.com:993` and
  `imap.mail.ru:993` over SSL. Both connects failed before authentication with
  local Windows `WinError 10013` / `PermissionError`; Sent-copy status remains
  unverified.
- No database/status/credential/cursor/campaign change and no SMTP module or
  DATA operation. Outgoing remains OFF; campaign `2` remains
  `paused_for_health`.
- Report: `ai/reports/TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831-report.md`.
- Commit attempt: blocked because Git could not create `.git/index.lock`
  (`Permission denied`); no paths were staged. Push was not run.

## 2026-08-31T12:35:07Z — SAFE RECONCILIATION — TASK-MAIL-DUPLICATE-GUARD-20260831

- Cause addressed: continuation safety previously keyed accepted/history checks
  by `supplier_id`, allowing duplicate supplier rows with one mailbox to evade
  the no-repeat gate.
- Code: continuation checks now use normalized recipient email across supplier
  identities, reject duplicate emails within one continuation campaign, detect
  prepared continuation mail across the whole request, and use email-scoped
  answered/delivery history.
- Data safety: after a database backup, exactly `20` queued Yandex jobs for
  request `1059` were marked `cancelled`/`excluded` because Mail.ru had already
  prepared or accepted the same recipient. No rows were deleted.
- Invariants: campaign `2` stayed `paused_for_health`; outgoing stayed OFF;
  Yandex `message 78 / job 70` stayed unchanged; no SMTP DATA was executed.
- Verification: SQLite `PRAGMA integrity_check`=`ok`; active duplicate delivery
  candidates=`0`; Python `py_compile` and `git diff --check`=`PASS`.
- Test limitation: unittest import was blocked because the bundled Python
  runtime lacks required `nh3` and `quotequail` packages.
- Report: `ai/reports/TASK-MAIL-DUPLICATE-GUARD-20260831-report.md`.

## 2026-08-30T16:20:16Z — AUDIT — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `AUDIT`
- Action: inspected repository root, Git branch/commit/status/remote, agent instructions, project state documents, runtime listener and declared commands.
- Files: existing `CLAUDE.md`, `Documents/28-8/PROJECT_STATUS.md`, `Documents/28-8/PROJECT_DOCUMENTATION.md`, `frontend/package.json`, `vercel.json`, source/runtime metadata.
- Result: audit complete; worktree is dirty with pre-existing application changes; no origin configured; local `127.0.0.1:8000` answered 200 for `/` and `/api/auth/me`.
- Evidence: read-only PowerShell/Git inspection recorded in `ai/reports/TASK-STATE-CONTROL-20260830-AUDIT.md`.
- Commit: `7658b1151bab414c867bf87898003586fbcdc8f3` baseline.
- Status: `PASS`

## 2026-08-30T16:20:16Z — DESIGN DECISION — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `DESIGN DECISION`
- Action: selected a repository-local `ai/` control plane, preserved useful `CLAUDE.md` root-hygiene rules, created a Codex branch, and excluded application files.
- Files: branch metadata; no application files.
- Result: scope fixed to state documents, adapters, templates, report and read-only validator.
- Evidence: `ai/WORKFLOW.md` and `ai/DECISIONS.md`.
- Commit: `HEAD` at close.
- Status: `PASS`

## 2026-08-30T16:20:16Z — IMPLEMENT — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `IMPLEMENT`
- Action: created the unified state-document structure and updated root agent adapters.
- Files: `AGENTS.md`, `CLAUDE.md`, `ai/` documentation tree.
- Result: implementation created; validator and final acceptance still pending.
- Evidence: file existence and later validator output.
- Commit: `HEAD` at close.
- Status: `PARTIAL`

## 2026-08-30T16:30:02Z — ACCEPTANCE — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `ACCEPTANCE`
- Action: ran the read-only validator, Python compilation, backend unittest suite, HTTP smoke/error checks and scoped documentation checks.
- Files: `ai/tools/validate_state.py`, `ai/**`, `AGENTS.md`, `CLAUDE.md`.
- Result: validator PASS; compile PASS; 344 tests OK with 1 PostgreSQL skip; `/` 200; `/api/auth/me` 200; invalid API path 404.
- Evidence: command output from this acceptance run; PostgreSQL skip is due to missing configured PostgreSQL URL.
- Commit: `HEAD` at close.
- Status: `PASS`

## 2026-08-30T16:30:02Z — CLOSE — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `CLOSE`
- Action: closed the documentation/state iteration, cleared `ACTIVE_TASK.md` to the idle sentinel, prepared the scoped Task-ID commit and confirmed that no push is possible.
- Files: `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`, `ai/INTERACTION_LOG.md`, `ai/reports/TASK-STATE-CONTROL-20260830-FINAL.md`.
- Result: no application file entered the allowed scope; working tree remains dirty only because of pre-existing user changes plus the pending scoped commit.
- Evidence: scoped `git status`, `git diff --check`, validator PASS and final report.
- Commit: `HEAD` after the scoped commit; exact hash is reported by final `git rev-parse HEAD`.
- Status: `PASS`

## 2026-08-30T16:34:45Z — COMMIT — TASK-STATE-CONTROL-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CONTROL-20260830`
- Mode: `CLOSE`
- Action: verified and recorded the scoped documentation commit; preserved pre-existing staged files outside the Task ID.
- Files: `AGENTS.md`, `CLAUDE.md`, `ai/**` only.
- Result: local commit exists; no push attempted because `origin` is absent.
- Evidence: `git rev-parse HEAD`, `git diff-tree --no-commit-id --name-only -r HEAD`, validator PASS.
- Commit: `HEAD` — exact hash reported after this final chronology update.
- Status: `PASS`

## 2026-08-30T17:13:31Z — RECONCILIATION — TASK-STATE-RECONCILIATION

- Agent: `Codex`
- Task ID: `TASK-STATE-RECONCILIATION`
- Mode: `AUDIT → DOCUMENTATION`
- Action: reconciled the prior state-control report with Git history, current
  worktree, the later `docs/**` snapshot, runtime/SQLite observations and
  repeatable verification commands.
- Files: `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`,
  `ai/DEFERRED_FINDINGS.md`, this chronology and the new reconciliation report.
- Result: documentation corrected; no product task created; no application,
  database, migration or production file changed by this task.
- Evidence: commit chain `7658b115 → 8a8bc36a → 9ca82f891 → d949bc6a`;
  current worktree snapshot `72` tracked modified/deleted, `598` untracked,
  `0` staged; targeted tests `27/16/12 OK`; full suite currently `FAIL`.
- Status: `PARTIAL` — state reconciliation complete, but the current full
  backend suite is not green and historical pre-existing attribution is not
  provable.

## 2026-08-30T17:13:31Z — ACCEPTANCE — TASK-STATE-RECONCILIATION

- Agent: `Codex`
- Task ID: `TASK-STATE-RECONCILIATION`
- Mode: `ACCEPTANCE`
- Action: recorded validator, Python compile, targeted tests, full-suite
  failures, frontend checks, HTTP smoke and read-only database evidence.
- Result: validator/compile/targeted/frontend/HTTP checks `PASS`; full backend
  suite `FAIL` because the outgoing safety gate blocked mail tests. No real
  SMTP/IMAP send, migration or database write was performed.
- Historical green backend result `344 OK / 1 skipped` is retained as
  `REPORTED, NOT VERIFIED`, not promoted to current fact.
- Status: `PARTIAL`

## 2026-08-30T17:20:49Z — CLOSE/COMMIT — TASK-STATE-RECONCILIATION

- Agent: `Codex`
- Task ID: `TASK-STATE-RECONCILIATION`
- Action: committed the reconciled state documents and report with subject
  `TASK-STATE-RECONCILIATION: verify shared project state`.
- Files: `ai/**` only; no application path was staged.
- Result: local documentation commit created; `origin` remains absent and no
  push was attempted.
- Status: `PASS` for scope control; current backend full-suite `FAIL` remains
  explicitly recorded as an unresolved finding.

## 2026-08-30T17:28:49Z — AUDIT/SECURITY GATE — TASK-REMOTE-REPOSITORY-PREPARATION

- Agent: `Codex`
- Task ID: `TASK-REMOTE-REPOSITORY-PREPARATION`
- Mode: `AUDIT → SECURITY GATE`
- Action: inspected Git/GitHub CLI state, looked up the expected repository,
  classified the current working tree and scanned for potential secrets without
  printing secret values.
- Evidence: `66 M`, `6 D`, `598 ??`, `0 staged`; `670` unique uncommitted paths;
  GitHub auth `PASS` as `edwatikhedwa-tech`; expected `supplydesk` repository
  not found; five ignored env/credential-risk files present.
- Files: updated `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`,
  `ai/ACTIVE_TASK.md`, this chronology and the preparation report only.
- Result: `BLOCKED`; no application code, `.gitignore`, remote, commit or push
  changed. Potential credentials and unresolved publish set require owner
  action first.

## 2026-08-30T17:31:44Z — ACCEPTANCE — TASK-REMOTE-REPOSITORY-PREPARATION

- Agent: `Codex`
- Task ID: `TASK-REMOTE-REPOSITORY-PREPARATION`
- Action: ran the AI state validator, Python compilation and scoped whitespace
  check after documenting the security gate.
- Result: validator `PASS`, compile `PASS`, `git diff --check -- ai` clean.
- Status: `BLOCKED` remains correct because potential credential files and the
  unresolved publish set were not cleared or approved.

## 2026-08-30T17:38:06Z — AUDIT/ALLOWLIST — TASK-PUBLISH-SAFETY-001

- Agent: `Codex`
- Task ID: `TASK-PUBLISH-SAFETY-001`
- Mode: `AUDIT → SECURITY SCAN → ALLOWLIST`
- Action: inventoried the current worktree, classified 677 paths, checked
  ignored sensitive paths and created a conditional AI-only publish allowlist,
  denylist and security report.
- Evidence: `66 M`, `6 D`, `599 ??`, `0 staged`; A=190, B=51, C=15, D=7,
  E=89, F=58, G=253, H=14, I=0 status-listed secret paths; five ignored env
  files remain a security overlay.
- Result: `BLOCKED`; no file was staged, committed, pushed, moved or deleted;
  no repository or origin was created.
- Files: `ai/PUBLISH_ALLOWLIST.md`, `ai/PUBLISH_DENYLIST.md`,
  `ai/PUBLISH_SECURITY_REPORT.md`, task report and current state chronology.

## 2026-08-30T17:43:27Z — ACCEPTANCE — TASK-PUBLISH-SAFETY-001

- Agent: `Codex`
- Task ID: `TASK-PUBLISH-SAFETY-001`
- Action: rechecked allowlist exclusions, AI validator, Python compilation,
  scoped diff formatting, status counts, staging and high-confidence patterns.
- Result: validator `PASS`; `681` unique working-tree paths,
  `0` staged; `origin` absent; env credential-risk overlay remains present.
- Status: `BLOCKED`; no commit, repository creation, remote change or push.

## 2026-08-30T18:06:50Z — PUBLISH — TASK-REMOTE-SETUP-SIMPLIFIED

- Agent: `Codex`
- Task ID: `TASK-REMOTE-SETUP-SIMPLIFIED`
- Mode: `EXCLUSION-FIRST → SECURITY SCAN → COMMIT → PRIVATE REMOTE`
- Action: formed an explicit 218-file publish set, removed excluded paths from
  the new Git snapshot with index-only operations, scanned the staged tree and
  reachable history, created the required commit, created the private GitHub
  repository and pushed the current branch.
- Evidence: staged tree `218` files / `3,053,727` bytes; staged security scan
  `NONE FOUND`; history scan `NONE FOUND` across `28` commits; AI validator
  `PASS`; `git diff --cached --check` `PASS`.
- Commit: `85fb7a2d9ac2f3697f33c7b5f930f44adabf799e`.
- Repository: `https://github.com/edwatikhedwa-tech/supplydesk` (`private`).
- Branch: `codex/TASK-STATE-CONTROL-20260830`; push `PASS`.
- Application code changed by this task: `NO`; pre-existing source changes
  were included only through explicit paths.
- Status: `PASS`

## 2026-08-30T18:31:32Z — STATE RECONCILIATION / CLOSE — TASK-STATE-CLOSEOUT-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-CLOSEOUT-20260830`
- Mode: `STATE RECONCILIATION / CLOSE`
- Action: closed the stale active task state after independently confirming the
  private GitHub repository, branch and publication HEAD.
- Result: stale `ACTIVE_TASK` was replaced with the explicit `NONE / IDLE`
  sentinel; `CURRENT_STATE` now has an unambiguous current snapshot and marks
  historical publish BLOCKED material as superseded.
- Application code unchanged; no database action; no email action.
- Files: `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`,
  this chronology, `ai/INTERACTION_LOG.md` and the closeout report.
- Evidence: repository/GitHub audit, state validator, scoped diff check and
  staged-path review.
- Status: `PASS`

## 2026-08-30T18:36:14Z — AUDIT / DESIGN DECISION — TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830`
- Action: rechecked the current private GitHub repository, branch, upstream,
  remote SHA and working-tree boundary after publication.
- Design decision: treat the published private branch as the current authority;
  mark only publication-specific stale blockers as `SUPERSEDED`, while keeping
  product acceptance and residual local credential risk explicitly open.
- Scope: `ai/**` state and chronology only; no application, database, runtime,
  SMTP, IMAP or production-setting action.
- Acceptance before commit: `PASS` — AI validator, scoped diff check,
  append-only log check, explicit staged-path review and secret-like diff scan
  all passed; normal push remains the final transport step.
- Status: `PASS`

## 2026-08-30T18:42:02Z — ACCEPTANCE / CLOSE — TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830

- Agent: `Codex`
- Task ID: `TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830`
- Acceptance: `PASS` — Task-ID commit `55db2aa2d8f80cdf69b4970db26cacce669a7e62`
  was pushed; `git ls-remote` and `gh api` matched the remote branch SHA.
- Scope result: only `ai/**` state/report files changed; application, database,
  runtime, SMTP and IMAP actions remained untouched.
- Final repository status: tracked/staged changes `0`; `56` unrelated
  untracked entries preserved.
- Status: `COMPLETE`

## 2026-08-30T18:56:25Z — AUDIT / MAIL CONTENT CONTRACT — TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830

- Agent: `Codex`
- Task ID: `TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830`
- Mode: `AUDIT ONLY`
- Result: `COMPLETE — PARTIALLY CONFIRMED`.
- Evidence: traced bulk, single/thread, unmatched-inbox reply and campaign
  continuation flows; ran `171` relevant backend tests, one continuation
  dry-run test, an isolated temporary-SQLite fake-provider/fake-SMTP MIME
  matrix, frontend typecheck and frontend build.
- Finding: the rich single/thread Composer sends `innerHTML` as generic `body`,
  while the backend treats it as plain text and escapes it into the HTML
  alternative. Bulk/new and unmatched-inbox reply remain plain-text input
  flows. No implementation was made pending a plain-only vs explicit-rich
  business decision.
- Scope: only `ai/**` report/state files changed; no product code, migrations,
  tests, `docs/**`, live database, SMTP, IMAP or supplier identity state.
- Report: `ai/reports/TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830-report.md`.
- Push: `NOT RUN`.

## 2026-08-31T06:21:32Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MESSAGES-UX-20260831

- Agent: `Codex`
- Scope: `/messages` frontend UX only.
- Changes: removed the artificial short-mail iframe minimum, added persisted
  manual-link unlink control after reload, and refreshed the unmatched list and
  counter after successful unlink.
- Safety: remote-image blocking/notice detection, API contracts unrelated to
  unlink, queue, statuses, filters, database, migrations, SMTP and IMAP were
  not changed or used.
- Verification: live no-mock audit `81/81 PASS`; live Playwright regression
  `1 passed`; remote image requests `0`; typecheck/build `PASS`; lint `PASS`
  with existing warnings.
- Commit: `a7043cc4f30f926dd792ef4aaceedee05300f3e2`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MESSAGES-UX-20260831-report.md`.

## 2026-08-31T06:36:26Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MESSAGES-NAV-TOGGLE-20260831

- Agent: `Codex`
- Scope: desktop navigation control used on `/messages`; mobile behavior
  preserved.
- Change: the blue logo control now expands/collapses the sidebar and reverses
  the arrow direction; the duplicate separate collapse control was removed.
- Verification: real Playwright click check `PASS` for `248 ↔ 76` px,
  full no-mock `/messages` audit `81/81 PASS`, typecheck/build `PASS`, lint
  `PASS` with existing warnings.
- Commit: `2ba2547383c42ad92b246527739eb2a2a56f8e76`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MESSAGES-NAV-TOGGLE-20260831-report.md`.

## 2026-08-31T06:46:00Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831

- Scope: explicit outbound HTML mode with separate `body_text`/`body_html`
  across bulk, single/thread and unmatched-reply flows.
- Safety: server-side nh3 allowlist sanitization, derived plain alternative,
  escaped personalization, idempotency-aware rich snapshots and preserved
  resend/continuation content.
- Verification: relevant mail suite `286 OK` with one expected skip; targeted
  rich/MIME/HTTP/resend/continuation regressions, compileall, typecheck,
  build, lint and browser desktop/mobile smoke all passed.
- No database, migration, supplier identity cleanup, `--apply`, SMTP/IMAP or
  real email was used.
- Commit: `d90bfd46f6ee421d442f2702c04cb9d280e634d9`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831-report.md`.

## 2026-08-31T06:42:12Z — IMPLEMENTATION / LIVE ACCEPTANCE — TASK-MESSAGES-NAV-DEFAULT-20260831

- Agent: `Codex`
- Scope: desktop navigation default on `/messages`; saved preference and
  mobile behavior preserved.
- Change: when no sidebar preference exists, navigation starts collapsed;
  stored `true`/`false` remains authoritative.
- Verification: fresh-context real Playwright `PASS` (`76 px` default), blue
  click/reload persistence `PASS`, full no-mock `/messages` audit `81/81 PASS`,
  typecheck/build `PASS`, lint `PASS` with existing warnings.
- Commit: `9c15c6f6dc9cadb989196fb23ebcfd696c3b0e3e`.
- Push: `NOT RUN`.
- Report: `ai/reports/TASK-MESSAGES-NAV-DEFAULT-20260831-report.md`.

## 2026-08-31T06:55:58Z — AUDIT / MESSAGES VISIBILITY — TASK-MESSAGES-AUDIT-20260831

- Agent: `Codex`.
- Mode: `REVIEW / AUDIT ONLY`.
- Scope: `/messages` request threads, unmatched inbox, delivery/read states,
  responsive rendering and information architecture.
- Result: `FAIL` for the current information contract; architecture direction
  is sound, but queue-only threads and the manual-linked unread gap are
  confirmed.
- Evidence: live browser at `http://127.0.0.1:8000/messages`, read-only SQLite
  aggregate, desktop/mobile screenshots, DOM geometry, typecheck and lint.
- Findings: `84/144` request threads are queue-only; current inbound unread is
  `0/16`; unmatched inbox contains `41` messages; mobile/tablet off-canvas
  EmptyState and default-expanded groups were confirmed.
- No application code, API, database, migrations, SMTP/IMAP or production
  settings were changed.
- Report: `ai/reports/TASK-MESSAGES-AUDIT-20260831-report.md`.
- Push: `NOT RUN`.

## 2026-08-31T07:32:48Z — IMPLEMENTATION / LIVE QA — TASK-MESSAGES-UX-FIX-20260831

- Agent: `Codex`.
- Scope: `/messages` correspondence visibility, outbox separation, unread
  semantics, statuses, grouping and narrow layout.
- Result: `COMPLETE`; queue-only threads are excluded from correspondence and
  shown in `Очередь`; manual/unmatched inbox read state is persisted and reset
  on open; UI statuses and responsive behavior were corrected.
- Verification: targeted/integration suite `53 OK`, Python compile, frontend
  typecheck/build and lint `PASS`; local HTTP/browser smoke `PASS`; final
  desktop/mobile PNGs reviewed.
- Report: `ai/reports/TASK-MESSAGES-UX-FIX-20260831-report.md`.

## 2026-08-31T07:37:17Z — LIVE ACCEPTANCE / SAFETY STOP — TASK-MAIL-INCOMING-CONTINUATION-20260831

- Incoming IMAP is now independent of the per-account outgoing flag; Yandex
  account 1 and Mail.ru account 23 both passed live read-only sync with
  durable outgoing disabled.
- Continuation queue-gate now permits only explicitly applied continuation
  jobs while the source campaign is `paused_for_health`; ordinary campaign
  jobs remain blocked.
- Mail.ru request 1059 continuation: `17` messages accepted (`250`), one
  Unicode-address job became `delivery_unknown` with `UnicodeEncodeError`
  before SMTP DATA, and outgoing was immediately disabled.
- No automatic retry was started. Two prepared jobs remain queued in the
  stopped batch; later contacts were not prepared or sent.
- Verification: targeted mail tests `5 OK`, Python compile and diff check
  `PASS`, live `/messages` HTTP `200`, Yandex/Mail.ru sync `200`, invalid
  account error `400`, and SQLite integrity `ok`.
- Report: `ai/reports/TASK-MAIL-INCOMING-CONTINUATION-20260831-report.md`.
- Commit: pending at state close; Push: `NOT RUN`.
- Commit: pending at state close; Push: `NOT RUN`.

## 2026-08-31T13:54:22Z — IDN PRE-DATA FIX / DEDUP SAFETY — TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831

- Root cause: Mail.ru job `172` / message `190` reached the old durable gate
  before SMTP envelope serialization and then raised `UnicodeEncodeError` for
  the IDN recipient `info@печнойцентр73.рф`; no SMTP code or DATA evidence
  existed, but the job became `delivery_unknown`.
- Code: moved the durable gate to the provider callback immediately before
  SMTP DATA; converted SMTP envelope domains to IDNA ASCII while preserving
  readable headers; added regressions for IDN and pre-DATA behavior.
- Deduplication: continuation checks remain normalized-recipient scoped across
  suppliers/providers, and duplicate recipient selection is blocked.
- Data: backed up canonical SQLite, reconciled only job `172`/message `190` to
  `failed`/`failed` with `delivery_state=not_sent`; historical attempt `70`
  was preserved. Yandex job `20`/message `28` remains untouched
  `delivery_unknown`.
- Verification: SQLite integrity `ok`, outgoing `0`, no active reservations,
  campaign 2 unchanged, zero pending duplicate recipient groups in request
  `1059`; `py_compile` passed. Full unittests are unavailable because the
  bundled runtime lacks `nh3`, `bs4` and `quotequail`.
- No live SMTP/IMAP, SMTP DATA, account reconnect, credential/cursor change or
  campaign-state change was performed.
- Backup: `mail-data/backups/supplier.sqlite3.pre-idn-reconcile-20260831-165009.bak`.
- Report: `ai/reports/TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831-report.md`.

## 2026-08-31T14:01:13Z — FINAL VERIFICATION — TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831

- Fixed a schema mismatch discovered by the reconciliation smoke test:
  exception class is read from `mail_send_attempt_evidence`, not the attempt
  row itself.
- Isolated provider smoke passed IDN envelope conversion. The reconciliation
  method passed apply and repeat/idempotency checks on disposable DB copies.
- Canonical final state remains integrity `ok`, outgoing `0`, campaign 2
  unchanged, no active reservations, zero pending duplicate groups in request
  `1059`, and exactly one outbound row for `s-kl@yandex.ru`.

## 2026-08-31T14:03:03Z — GIT CLOSEOUT — TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831

- Scoped commit attempt was blocked because Git could not create
  `.git/index.lock` (`Permission denied`). No paths were staged and push was
  not run; unrelated worktree changes were preserved.

## 2026-08-31T14:22:36Z — MAIL.RU REMAINING CONTINUATION LAUNCH — TASK-MAILRU-REMAINING-CONTINUATION-20260831

- Owner authorized sending only previously untouched request-1059 supplier
  contacts through Mail.ru account `23`.
- Read-only preflight confirmed account `23` is connected, outgoing is `0`,
  active reservations are `0`, SQLite integrity is `ok`, and the current
  queued Mail.ru jobs are only `173`/`191` and `174`/`192`.
- The declared requirements installation could not reach PyPI because the
  execution environment denies outbound TCP (`WinError 10013`). Starting the
  project entry point then stopped before HTTP binding with
  `ModuleNotFoundError: nh3`.
- No provider authentication, SMTP DATA, queue mutation, campaign change or
  credential change occurred. The continuation remains blocked until the
  previously working runtime is available.

## 2026-08-31T14:40:00Z — SAFE PROJECT RECOVERY TOOLING — TASK-PROJECT-RECOVERY-20260831

- Added non-destructive `scripts/doctor.ps1` with explicit Plan/DryRun/Apply
  modes for Python, configuration, database-file and port checks.
- Added `scripts/bootstrap_supplydesk.ps1` to create a project `.venv` and
  install only declared requirements after explicit Apply.
- Added `scripts/recover_supplydesk.ps1` to force outgoing OFF and keep the
  server running only after an HTTP `200` smoke-test.
- Parse, Plan and DryRun checks passed. Apply stopped before `.venv` creation
  because the current `py.exe` reports no installed Python.
- No deletion, move, database write, campaign change, credential change,
  SMTP login or SMTP DATA occurred. Project cleanup is deferred until after a
  writable Git checkpoint and inventory.

## 2026-08-31T14:52:34Z — RECOVERY APPLY RETRY — TASK-PROJECT-RECOVERY-20260831

- Owner requested immediate server startup and execution of the pending
  Mail.ru continuation.
- Bootstrap `-Apply` was retried. It stopped before creating `.venv` because
  `py.exe` reports no installed Python in the current execution environment.
- No server, SMTP authentication, SMTP DATA, database write, queue mutation,
  campaign change or credential change occurred. Outgoing remains OFF.

## 2026-08-31T14:56:05Z — RUNTIME RECOVERY BLOCKER CONFIRMED — TASK-PROJECT-RECOVERY-20260831

- User requested installation of all missing dependencies and immediate
  execution.
- No local wheel cache or usable alternate runtime was found. The current
  isolated environment cannot execute the available Windows Python or reach
  package indexes.
- The remaining action is external to this environment: run the documented
  bootstrap in ordinary Windows PowerShell. No application, database, queue,
  campaign, credential or outgoing state was changed.

## 2026-08-31T15:01:57Z — SERVER STARTED WITH OUTGOING OFF — TASK-PROJECT-RECOVERY-20260831

- Rechecked the environment: system Python `3.11.7` and all declared
  requirement imports are available; doctor DryRun exited `0`.
- Started `supplier_app.py` directly as PID `23584` on `127.0.0.1:8000` with
  `MAIL_OUTGOING_DISABLED=1` and left it running after verification.
- Root and `/api/auth/me` returned `200`; unauthenticated mail API returned
  `401`; unknown API returned `404`.
- Read-only SQLite remained healthy with durable outgoing `0`. No mail,
  queue, campaign, account, credential or cleanup state changed.

## 2026-08-31 — DUPLICATE RECIPIENT PROTECTION IMPLEMENTED — TASK-MAIL-DUPLICATE-PROTECTION-FINAL-20260831

- Added recipient-scoped durable guards and cross-provider active-delivery
  blocking; continuation now supersedes only untouched source jobs and records
  `resend_of_message_id`.
- Corrected pre-DATA provider-attempt accounting while preserving zero attempts
  for local message/recipient encoding failures.
- Verified `384` discovered tests and `224` focused mail tests (`1` skipped in
  each run), doctor DryRun, compileall, diff check and local HTTP smoke.
- No live send, migration, credential/account change or canonical database
  write was performed. See the final report in `ai/reports/`.
## 2026-08-31 — MESSAGES AUDIT REPAIR — TASK-MESSAGES-AUDIT-REPAIR-20260831

- Fixed reply-editor focus, operational-attention group visibility and the
  stale outbound metric expectation identified by the `56/80` legacy audit.
- Full route-mocked frontend audit passed `80/80`; live no-mock email
  regression passed `1/1` across the required HTML/plain/CID/remote/no-image/
  long-mail cases and widths `390/1024/1440/1640`.
- Typecheck, lint and build passed. Lint reported `0` errors and `8` existing
  warnings outside the changed files.
- No SMTP/IMAP, send, queue, database, request-link or production action was
  performed. Outgoing remains disabled. Report and screenshots are recorded
  in `ai/reports/` and `Temp/task-messages-audit-repair-20260831/`.

## 2026-08-31T18:08:46Z — EXACT MAILRU CONTINUATION SENT — TASK-FRONTEND-MAILRU-CONTINUATION-20260831

- После action-time подтверждения отправлены только существующие jobs `173` и
  `174` через Mail.ru account `23`, по одной попытке на job.
- Оба письма приняты провайдером (`post_data`, SMTP `250`), локальные статусы
  `sent`, sent-copy сохранён; новых jobs/messages и дублей не создано.
- Yandex queue не трогалась, неопределённый Unicode-домен не повторялся.
- Durable outgoing switch возвращён в `0`; активных reservations нет, SQLite
  integrity check `ok`. Send-only процессы остановлены.

## 2026-08-31T18:28:01Z — LOCAL SERVER STARTED WITH OUTGOING OFF — TASK-SERVER-START-20260831

- Запущен `supplier_app.py` на `127.0.0.1:8000`; процесс оставлен работающим.
- Установлен процессный `MAIL_OUTGOING_DISABLED=1`, durable outgoing switch
  подтверждён как `0`; отправка из очереди невозможна.
- HTTP smoke: root `200`, auth/me `200`, protected API `401`, unknown API `404`.

## 2026-09-01T07:27:56Z — CANONICAL DOCUMENTATION — TASK-DOCS-CANONICAL-20260901

- Установлен единый current-state source: `ai/CURRENT_STATE.md`.
- Добавлен `docs/DOCUMENTATION_POLICY.md` с обязательным правилом: изменённый
  факт и документация обновляются в одной задаче и одном коммите.
- Старые snapshots в `docs/**` и `Documents/28-8/**` помечены
  `HISTORICAL — NOT CURRENT`, сохранены и связаны с canonical state.
- Обновлены AGENTS, AI contract, workflow, decisions, navigation и
  documentation state; `FINDING-001` и `FINDING-005` закрыты.
- Acceptance: 116 relative Markdown links, secret-pattern scan, state validator
  и `git diff --check` прошли. Application code, data, mail and deployment не
  менялись. Backup: `Temp/20260901-docs-canonical/`.

## 2026-09-01T13:34:05Z — TASK-DOCUMENTATION-GOVERNANCE-20260901

- Reconciled state-like documentation and made `ai/CURRENT_STATE.md` the only
  canonical current-state source.
- Moved the 11 root historical/task reports and superseded AI chronology under
  dated `ai/history/` paths; no historical content was deleted.
- Added the `ai/**` versus `docs/**` ownership boundary, lifecycle metadata,
  audit retention policy, documentation indexes, and read-only documentation
  validator. `DOC_IMPACT=NO` for product behavior; application code and data
  remain unchanged.

## 2026-09-01T14:00:00Z — TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901

- Task ID: `TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901`; Status: IN PROGRESS.
- Created evidence-based capability, requirement, business-rule, component,
  test and traceability catalogs without changing product behavior.
- Added a standard-library read-only diagnostic runner, a ten-check contract,
  synthetic disposable diagnostic tests, failure modes, runbooks, incident
  schema and sandbox-only repair-agent contract.
- Expanded `scripts/doctor.ps1` while preserving Plan/DryRun/Apply; no Apply,
  migration, canonical database write, provider connection or real email was
  performed.

## 2026-09-01T14:58:07Z — TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901

- Task ID: `TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901`; Status: IN PROGRESS.
- Hardened traceability semantics, diagnostic evidence levels, failure-mode
  discrimination and frontend/runtime classifications.
- Added controlled negative fixtures with redacted secret evidence and made
  `doctor -Apply` an explicit safety block; no product code, database, mail,
  migration or provider state was changed.

## 2026-09-01T15:02:50Z — TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901 COMPLETE

- Task ID: `TASK-DIAGNOSTIC-CONTROL-PLANE-V1.1-20260901`; Status: COMPLETE.
- Validators, 19 diagnostic tests, doctor Plan/DryRun/Apply and allowlist
  checks passed with documented environment/live limitations.
- Commit `f2e707ac9988223dc87f242d53df837d70ddca5f` was pushed to the
  dedicated remote branch; no merge, product-code change, database write,
  migration, provider connection or real email action occurred.

## 2026-09-01T16:05:00Z — TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901 COMPLETE

- Added the reproducible test contract, official unittest runner, PowerShell
  setup/full/diagnostic wrappers and clean-checkout documentation.
- Added the safe `OFFLINE_TEST` runtime with disposable SQLite, synthetic
  configuration, disabled outgoing mail, fake/blocked providers and
  loopback-only networking; canonical DB and private `.env` remain forbidden.
- Verified `411` backend tests (`0` failures, `0` errors, `1` skipped), `25`
  diagnostic tests, frontend install/typecheck/lint/build, `8/8` real-route
  Playwright viewports, validators, safe HTTP smoke and Doctor profile gates.
- No product source, canonical database, migrations, provider state or real
  email action was changed or performed. Final branch push remains the next
  closeout action.

## 2026-09-01T16:12:07Z — TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901 PUSHED

- Functional commit `09d12018afc4ecb8445f40dc1b717ef078cfae0f` was pushed to
  `origin/control/reproducible-test-runtime-v1-20260901` and the remote ref
  was verified.
- Task sentinel is now `IDLE`; no merge, force-push, default-branch change,
  product-code change, canonical database write or real email action occurred.

## 2026-09-01T19:10:00Z — TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901

- Created a separate canonical checkout and marked the legacy OneDrive
  checkout `DO_NOT_USE_FOR_DEVELOPMENT` with a local-only marker.
- Deleted only 308 verified regeneratable/cache files (`30,228,149` bytes).
- Moved 1,481 review, backup, old-export and historical-local files
  (`132,669,560` bytes) to retained external quarantine; permanent purge was
  not performed.
- Preserved `.env*`, canonical database, `mail-data`, runtime, credentials,
  local mail evidence, product source and the three unknown-review items.
- Verified 411 backend tests, 25 diagnostics, frontend gates, 8/8 Playwright,
  safe HTTP smoke, Doctor OFFLINE_TEST Full, validators and diff check.
- Evidence commit `26e779c` was pushed normally to the dedicated cleanup branch
  after one transient DNS failure; the remote ref was verified. No merge or
  permanent quarantine purge was performed.

## 2026-09-01T20:55:00Z — TASK-SAFE-CLEANUP-BATCH2-20260901

- Created `control/safe-cleanup-batch2-20260901` from the verified Batch 1
  control HEAD and kept the legacy OneDrive checkout out of development.
- Corrected the broad `.gitignore` rules in commit `0585275`; the synthetic
  matrix passed and no secret/data path was exposed for staging.
- Moved the three resolved legacy unknown items to retained external quarantine
  (`43,845` bytes) after reference, process and SHA-256 checks.
- Removed only 18 proven unused Python imports and 2 side-effect-free dead
  bindings in separate commit `d2ceef3`; duplicate groups and frontend review
  candidates were kept.
- Full offline acceptance passed: `412` backend tests with `0` failures and
  `1` expected skip, `26/26` diagnostics, frontend gates, `8/8` Playwright and
  Doctor Full exit `0`. Final state/report validation and remote push remain
  closeout actions.

## 2026-09-01T17:59:25Z — TASK-SAFE-CLEANUP-BATCH2-20260901 CLOSEOUT

- Documentation, state and traceability validators passed; the cleanup report,
  duplicate audit and manifest contain no secrets, quarantine content or
  personal absolute paths.
- The dedicated branch was pushed normally and its remote ref was independently
  compared with the local closeout commit. No merge, force-push or default
  branch change occurred.
- `ACTIVE_TASK` is now `IDLE`; retained quarantine and permanent-purge review
  remain separate owner decisions.

## 2026-09-01T18:36:54Z — TASK-FINAL-REPOSITORY-HYGIENE-ACCEPTANCE-20260901

- Created `control/final-hygiene-acceptance-20260901` from verified Batch 2
  HEAD `a228321401270b69c9ac2f07f76435e246b6f5c3`.
- Replaced fragile current-state `source_commit` metadata with a stable
  `based_on_commit` contract; Git history remains the publication authority.
- Added the lightweight canonical inventory, quarantine disposition
  recommendation and final hygiene acceptance report.
- Confirmed 390 tracked files, 45 tracked root objects, zero canonical unknown
  objects, zero tracked sensitive/generated categories and two intentionally
  retained duplicate groups.
- Re-ran final offline acceptance: backend `412/0/0/1`, diagnostics `26/26`,
  frontend clean gates, safe HTTP `200/200/401/404`, Playwright `8/8` and
  Doctor Full exit `0`. No product/data/mail changes or quarantine purge.

## 2026-09-01T18:39:44Z — TASK-FINAL-REPOSITORY-HYGIENE-20260901 CLOSEOUT

- Final acceptance documentation was pushed normally to
  `origin/control/final-hygiene-acceptance-20260901`; `git ls-remote` confirmed
  the remote HEAD. The first DNS failure was transient and the retry passed.
- `ACTIVE_TASK` is now `IDLE`; the canonical checkout and final remote branch
  are the source of truth. No force-push, merge, product/data/mail change or
  quarantine purge occurred.

## 2026-09-01T19:09:33Z — TASK-VIBECODING-CONTROL-POLICY-V1-20260901

- Created the canonical VibeCoding V1 policy, factual tool registry and
  read-only governance validator with disposable negative/positive tests.
- Added minimal policy bootstrap references to `AGENTS.md`, `CLAUDE.md`,
  `PROJECT_MANIFEST.yaml` and the AI state entrypoint.
- No product behavior, UI, API, database, mail data, runtime, dependency or
  quarantine changes were made. Acceptance and remote publication remain open.

## 2026-09-01T19:45:15Z — TASK-VIBECODING-CI-V1.1-20260901

- Audited the existing SupplyDesk commands and real path structure; no
  duplicate test runner was introduced.
- Started a dedicated CI governance branch and added the V1.1 profile/risk
  model, deterministic path mapping/classifier and single Windows-first
  workflow. Remote execution and closeout remain pending.

## 2026-09-02T21:56:03Z — TASK-CI-PERFORMANCE-FIX-V1-20260902

- Reworked CI into FAST/FOCUSED/FULL/PERIODIC routing with a one-viewport real
  route browser smoke and an always-on CI Summary.
- Remote FAST proof `33562406201` passed in 1m22s; normal focused routing
  skipped Backend Full and Browser Full.
- Explicit FULL proof `33562558816` preserved all full jobs but reproduced the
  hosted Windows Browser Full screenshot/Axe timeout and the slow Backend Full
  path; both limitations are recorded without timeout escalation.
- Corrected `tests/diagnostics/` classification so control tests do not trigger
  Backend Full. No product/data/mail/secrets/runtime changes occurred.

## 2026-09-01T19:13:54Z — TASK-VIBECODING-CONTROL-POLICY-V1-20260901 CLOSEOUT

- VibeCoding validator, 30 diagnostic tests, documentation/state/traceability
  validators, Doctor Plan, diff check and staging security audit passed.
- Commit `1bdda8a` was pushed normally to
  `origin/control/vibecoding-policy-v1-20260901`; the remote ref was verified.
- `ACTIVE_TASK` is now `IDLE`. No product/data/runtime change, dependency
  installation, external provider action or quarantine change occurred.

## 2026-09-02T08:30:55Z — TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902

Task ID: `TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902`
Status: `PASS_WITH_LIMITATIONS`

- Reconfirmed the canonical Git root and branch before implementation; the
  working tree was clean. Confirmed PID 15912's process directory metadata
  matched the legacy OneDrive checkout and stopped only that PID.
- Added `scripts/assert_workspace.ps1` with canonical default, exact
  `-ExpectedRoot` worktree/CI override, path normalization and non-zero mismatch
  exit. No automatic directory, branch or file changes are performed.
- Integrated the guard into control/runtime/test wrappers and CI checkout jobs;
  updated agent instructions, manifest, registry, decision register and
  operational documentation.
- Guard cases and control `Plan` modes passed. Backend, frontend and Playwright
  were not run by explicit scope. No product code, database, mail data, env,
  quarantine or legacy checkout files were changed.

## 2026-09-02 — TASK-FINDING-009-CONTENT-REVIEW-20260902

Task ID: `TASK-FINDING-009-CONTENT-REVIEW-20260902`
Status: `PASS_WITH_LIMITATIONS`

- Completed the exact allowlisted controlled content review without outputting
  or saving secret values. Three historical `.env.example` blobs were safe
  templates; retained snapshots/quarantine contained real or mixed material.
- Classified 27 review items: 5 `SAFE_TEMPLATE`, 6 `EMPTY_OR_NON_SECRET`, 8
  `REAL_SECRET_PRESENT`, 4 `MIXED` and 4 `UNDETERMINED`.
- Confirmed `GIT_SECRET_EXPOSURE=NO` and `LOCAL_ARCHIVE_SECRET_RETENTION=YES`.
  No product, runtime, quarantine or snapshot file was changed; no deletion,
  rotation or Git history rewrite was performed.

## 2026-09-02 — TASK-CLEANUP-FINAL-CLOSEOUT-VIBECODING-V1.3-20260902

Task ID: `TASK-CLEANUP-FINAL-CLOSEOUT-VIBECODING-V1.3-20260902`
Status: `DELIVERY_MODE: PUBLISH`

- Formally separated `CLEANUP_PHASE: COMPLETE` from the open
  `DEFERRED_SECURITY_ACTION — LOCAL_ARCHIVE_SECRET_RETENTION` Finding-009.
- Delivered the VibeCoding V1.3 policy rules for comprehensive-first audits,
  two-pass execution, deferred findings, governance freeze, one-shot delivery,
  tool-audit batching and minimized state/report duplication.
- Focused governance tests (`16`), the policy validator (`36` tools), state and
  documentation validators, Workspace Guard and `git diff --check` passed.
  Product code and protected local archives were not changed.

## 2026-09-02T11:37:47Z — TASK-ARCHITECTURE-HYGIENE-LIFECYCLE-AUTH-HANDOFF-20260902

Task ID: `TASK-ARCHITECTURE-HYGIENE-LIFECYCLE-AUTH-HANDOFF-20260902`
Status: `DELIVERY_MODE: PUBLISH`

- Added the shared architecture placement, root-growth, component lifecycle,
  deprecation, disabled-feature, temporary-file and architecture-change rules.
- Added `docs/architecture/COMPONENT_LIFECYCLE.md` with the first deferred
  manual real-email configuration record and a reusable row template.
- Added local-only human browser auth handoff and public `/login` failure
  classification to the frontend runbook; CI remains non-interactive.
- No product, current browser test, CI, Knip, Python, root, runtime, database,
  mail or secret-bearing file was changed.
- Local documentation/state/VibeCoding validators, 16 focused governance tests,
  architecture allowlist checks and diff check passed. Publication gates remain
  the ordinary push, remote SHA and FAST CI proof.

## 2026-09-02 — TASK-PYTHON-ROOT-DIAGNOSTIC-20260902

Status: `PASS_WITH_LIMITATIONS` — `DELIVERY_MODE: PUBLISH_REPORT_ONLY`

- Completed one read-only Python/root architecture diagnostic on the current
  checkout: 20 root Python files and 16 tracked top-level directories reviewed.
- Confirmed `supplier_app.py` as the protected local backend entrypoint and
  `api/index.py` as the Vercel adapter; root move safety is `NO` for the app.
- Built a 107-file AST/import map with 243 local edges and no statically
  resolved cycles; manually checked string, script, subprocess, docs and
  deployment references.
- Used Code Rot Cleaner in external report-only mode. No file deletion, move,
  import rewrite, dependency change, runtime start or product test occurred.
- Created and published commit `dc93a181c85c175863a84ddddb1c71c9172a98bb`
  containing the report and control-plane updates. Remote SHA matches, and FAST
  Control CI run `33645377974` passed; product suites were skipped by the
  report-only classifier.
- Ruff/Vulture were not available without installation and remain outside this
  diagnostic.

## 2026-09-03 — TASK-DEFAULT-AGENT-OPERATING-MODEL-20260903

Task ID: `TASK-DEFAULT-AGENT-OPERATING-MODEL-20260903`
Status: `PASS_WITH_LIMITATIONS` — `DELIVERY_MODE: PUBLISH`

- Added one canonical default project operating model to `ai/VIBECODING_RULES.md`
  and a compatibility pointer in `ai/AI_CONTRACT.md`; adapters and the factual
  registry were kept unchanged.
- Replaced the old file-count change-budget stop with the causal-scope model:
  `<=125%`, `125–150%` internal review and `>150%` stop only for a broken causal
  chain or a new category/subsystem.
- Added static validator coverage and two focused governance cases; policy,
  docs/state validators and `18/18` governance tests passed.
- Created candidate commit `2678370f`. Neutral Claude and Codex child launches
  were attempted without tool/skill names in their prompts, but neither returned
  a usable child trace; no tracked product file changed and no canary was
  simulated as proof.
- Product code, backend, frontend, browser, database, mail and provider state
  were not changed. Final publication and CI evidence remain in the closeout
  response because this report was prepared before the one allowed push.
