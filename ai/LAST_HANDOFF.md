---
document_id: HANDOFF-010
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-02
based_on_commit: bb6aaf0e9a2a6aec3835fa17475718792b1cde0e
---

# Last Handoff

This handoff records the RED→FIX→GREEN fix of `FINDING-018`
(`collect_inn.py --llm` importing a nonexistent symbol), using two explicit
owner approval gates and a deterministic behavioral reproducer.

## Цель

Исправить `FINDING-018` с доказательством через RED→GREEN, не меняя
prompts/schemas/model selection policy, без реальных provider-вызовов.

## Что изменено

- `collect_inn.py:217-223` — 3 строки: канонический импорт
  (`DEFAULT_MODEL, LlmExtractor, api_key_present`), безопасный
  default-model fallback (`LlmExtractor(model=args.llm_model or
  DEFAULT_MODEL)`), корректное сообщение про `RouterAI`/`ROUTERAI_KEY`.
- Added `tests/diagnostics/test_collect_inn_llm_path.py` (3 tests) —
  поведенческий reproducer через реальный `collect_inn.main()`.
- Updated `tests/diagnostics/test_llm_integration_move.py` — устаревшее
  ожидание `InnLlmExtractor` заменено на канонический импорт.
- Marked `FINDING-018` `RESOLVED` in `ai/DEFERRED_FINDINGS.md` (с
  историческими доказательствами и resolution report, по тому же формату,
  что уже использован для `FINDING-017`).
- Added `ai/reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md`.

## Что проверено

- Workspace Guard passed before task-lock and before mutation.
- `ListSkills` confirmed no `bug-reproducer` skill is installed in this
  Claude Code session — the `BUG_REPRODUCER` workflow from
  `ai/AI_CONTRACT.md` was applied directly with this session's own tools,
  reported as `TYPE: WORKFLOW`.
- History check: `git log --all -S "InnLlmExtractor"` matches exactly one
  commit (the initial bulk import); `Documents/28-8/enrichment-and-cache.md`
  independently documents it as a leftover from the pre-RouterAI version.
  `LlmExtractor` confirmed as the intended implementation, not guessed.
- Gate 1 (reproduction plan) and Gate 2 (fix plan) each presented as one
  consolidated proposal and explicitly approved by the owner before any file
  changed.
- `tests/diagnostics/test_collect_inn_llm_path.py` failed with the exact
  predicted `ImportError: cannot import name 'InnLlmExtractor'` (at
  `collect_inn.py:217`, before any network-capable code ran) on unfixed
  code, then passed `3/3` on the same test after the fix — RED→GREEN with
  the identical reproducer, `FIX_PROVEN`.
- `tests/diagnostics/test_llm_integration_move.py`: `6/6` passed.
  `tests/test_enrichment_pipeline.py` + `tests/test_dashboard.py`: `21/21`
  passed. Full `tests/diagnostics` discovery: `61/70` passed; the remaining
  `9` errors are the same pre-existing `pwsh`-missing gap already proven
  unrelated in an earlier task.
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`: `PASS`.
  `git diff --check`: `PASS`.
- Staged diff scanned for secret-like literals: only `ROUTERAI_KEY`/
  `ANTHROPIC_API_KEY`/`api_key_present` identifiers and message text, no
  values. `0` external provider calls throughout (RouterAI, OpenAI,
  Anthropic, Gemini, XMLRiver, Checko, DaData).

## Что не прошло

Nothing this task touched failed.

## Что не проверено

NOT VERIFIED: real `ROUTERAI_KEY` / live RouterAI behavior (forbidden by
this task's scope). NOT VERIFIED: manual terminal invocation of
`python collect_inn.py --llm ...` by an operator (only exercised via
`unittest` calling `main()` directly).

## Текущее состояние runtime

No runtime was started for this task. No provider call, real mail, or
canonical database write occurred.

## Следующий рациональный шаг

None required for this finding. Remaining root moves named in the root
diagnostic (`supplier_app.py`, `api/index.py`, `serp_parser.py`, and the
rest of the flat root package) each still need their own bounded,
explicitly-scoped task.

## Не повторять

Do not use the legacy OneDrive checkout for development, do not output or
save secret values, do not run real mail or live provider calls, do not
claim a `bug-reproducer` skill invocation without first confirming via
`ListSkills` (or equivalent) that it is actually installed in the current
session, do not skip either approval gate when a task explicitly structures
itself around them, and do not add a second acknowledgement to an
intermediate message.
