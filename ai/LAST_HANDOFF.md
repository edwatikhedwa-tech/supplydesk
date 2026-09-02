---
document_id: HANDOFF-009
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-02
based_on_commit: c666c8d2ad758815599ea812e5746df3c84eef7a
---

# Last Handoff

This handoff records the LLM integrations move (`llm_fallback.py`,
`routerai_client.py`) to `backend/integrations/llm/`, plus one newly
discovered, deferred, unrelated pre-existing bug.

## Цель

Перенести `llm_fallback.py` и `routerai_client.py` в
`backend/integrations/llm/`, обновить только подтверждённые consumers, не
меняя LLM business logic/prompts/schemas/provider behavior.

## Что изменено

- Added `backend/integrations/llm/__init__.py`,
  `backend/integrations/llm/llm_fallback.py`,
  `backend/integrations/llm/routerai_client.py` (git-recognized renames,
  `99%`/`100%` similarity).
- Removed root `llm_fallback.py`/`routerai_client.py`; no compatibility
  wrapper.
- Updated import lines in `supplier_app.py`, `collect_inn.py`,
  `scripts/collect_contacts.py`, `benchmarks/benchmark_models.py`.
- Added `tests/diagnostics/test_llm_integration_move.py` (6 tests) and
  updated `docs/architecture/REPOSITORY_LAYOUT.md`.
- Added `FINDING-018` to `ai/DEFERRED_FINDINGS.md` for a pre-existing,
  unrelated `collect_inn.py --llm` broken-symbol bug found during the fresh
  reference scan.
- Added `ai/reports/TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902-report.md`.

## Что проверено

- Workspace Guard passed before task-lock and before mutation.
- Fresh, non-AST-only reference scan for both modules found nothing beyond
  the known 4 consumers; no immutability-protected-path conflict; no
  mock/patch targets anywhere in `tests/`.
- `git diff -M` proved `100%` similarity for `routerai_client.py` and `99%`
  for `llm_fallback.py` (exactly one line changed: the internal lazy
  RouterAI import) — structural proof that prompts, schemas and
  `DEFAULT_MODEL` are unchanged, not just claimed unchanged.
- `backend.integrations.llm.{llm_fallback,routerai_client}`, `supplier_app`,
  `collect_inn` import cleanly; `python collect_contacts.py --help` /
  `python -m scripts.collect_contacts --help` and `python
  benchmark_models.py --help` / `python -m benchmarks.benchmark_models
  --help` are all exit `0` and byte-identical between old/new invocation;
  `from api.index import handler, _APP` succeeds under
  `SUPPLYDESK_ENV=test`.
- `tests/diagnostics/test_llm_integration_move.py`: `6/6` passed.
  `tests/test_enrichment_pipeline.py` + `tests/test_dashboard.py`: `21/21`
  passed.
- Full `tests/diagnostics` discovery: `52/61` passed; the remaining `9`
  errors are the same pre-existing `pwsh`-missing gap already proven
  unrelated in an earlier task — not re-investigated here.
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py`: all `PASS`. `git diff --check`: `PASS`.
- Staged diff scanned for secret-like literals: only `ROUTERAI_KEY`/
  `ANTHROPIC_API_KEY`/`api_key`/`self.token` identifiers, no values. `0`
  external provider calls.

## Что не прошло

Nothing this task touched failed. `FINDING-018` (`collect_inn.py --llm`
importing a nonexistent `InnLlmExtractor`) is a pre-existing bug this task
found but did not fix, by design.

## Что не проверено

NOT VERIFIED: real Vercel build/deploy (not re-audited; structural
`vercel.json` check reused from earlier tasks, file untouched). NOT
VERIFIED: undocumented external Python-import compatibility for either
moved module.

## Текущее состояние runtime

No runtime was started for this task. No provider call, real mail, or
canonical database write occurred.

## Следующий рациональный шаг

A separate task should fix `FINDING-018` (`collect_inn.py --llm`'s broken
`InnLlmExtractor` import and the `ANTHROPIC_API_KEY`/`ROUTERAI_KEY` message
mismatch) and add offline argument-parsing coverage for `--llm`. Any further
root moves (`supplier_app.py`, `api/index.py`, `serp_parser.py`, and the
rest of the flat root package) each need their own bounded, explicitly-
scoped task.

## Не повторять

Do not use the legacy OneDrive checkout for development, do not output or
save secret values, do not run real mail or live provider calls, do not
modify protected local data, do not fix an unrelated bug discovered during a
structural move task (record it in `ai/DEFERRED_FINDINGS.md` instead), and
do not add a second acknowledgement to an intermediate message.
