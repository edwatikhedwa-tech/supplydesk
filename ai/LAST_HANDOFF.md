---
document_id: HANDOFF-012
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-02
based_on_commit: 6d8f816af3c7aedd9b097306d39a22a22831c118
---

# Last Handoff

This handoff records the supplier-identity domain move
(`email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `verify.py`
→ `backend/domain/supplier_identity/`), the largest bounded root-refactor
batch so far, including one owner-approved change-budget overage.

## Цель

Перенести `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`,
`verify.py` в `backend/domain/supplier_identity/`, обновить всех
подтверждённых consumers, не меняя бизнес-логику.

## Что изменено

- 4 модуля перенесены (2 чистых переноса, 2 — только импортные строки
  внутри модуля).
- Обновлены 15 внешних consumers (11 из исходного списка задачи + 4
  незапланированных, найденных fresh scan'ом: `web_lookup.py`,
  `mail/repository.py`, `backend/integrations/registry/dadata_client.py`,
  `benchmarks/benchmark_models.py`).
- `supplier_discovery_v2/immutability_check.py`: protected-path список
  мигрирован для 3 уже защищённых файлов; `inn_resolver.py` намеренно не
  добавлен.
- `supplier_discovery_v2/tests/test_immutability.py`: +2 постоянных теста
  (защита на новом пути + disposable-mutation proof).
- `docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`: обновлены (замена
  устаревшего текста, без нового абзаца-политики).
- Добавлен
  `ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902-report.md`.

## Что проверено

- Workspace Guard passed до lock и до мутации.
- Fresh full-tree reference scan (Python-импорты plus literal-упоминания
  имён файлов, не только AST) — 15 реальных consumers, из них 4 не были в
  исходном списке задачи.
- `git diff -M` структурно доказал: `email_extractor.py`/`inn_extractor.py`
  — 0-diff чистые переносы; `inn_resolver.py`/`verify.py` — только
  import-строки, `SEMANTIC_CHANGES: 0`.
- Особый случай `mail/repository.py`: единственная строка импорта
  обновлена (не бизнес-логика) вместо оставления сломанного импорта —
  обоснование зафиксировано в отчёте.
- Offline import chain: все 4 модуля,
  `backend.integrations.{llm.llm_fallback,registry.dadata_client}`,
  `contact_crawler`, `web_lookup`, `collect_inn`, `supplier_app`,
  `mail.repository`, и `api.index` под `SUPPLYDESK_ENV=test` — все `OK`.
- Immutability: свежий baseline на реальном дереве → `[]`; disposable
  synthetic-copy мутация каждого из 3 защищённых путей → обнаружена.
  Закреплено `5/5 PASS` постоянными тестами.
- Поведенческие тесты: `test_extractor.py`/`test_inn.py`/`test_verify.py`
  (custom-скрипты, "Все проверки пройдены", exit `0`);
  `tests.test_enrichment_pipeline` + `tests.test_dashboard` (`21/21`);
  FINDING-018 regression (`3/3`, не задет); полный
  `supplier_discovery_v2/tests/` (`16/16`).
- Полная диагностика: `61/70` passed, `9` ошибок — тот же pre-existing
  `pwsh`-gap. Одна НОВАЯ ошибка (`ModuleNotFoundError: inn_extractor` в
  `benchmarks/benchmark_models.py`) была поймана этим же прогоном,
  исправлена, диагностика перезапущена и вернулась к базовому уровню.
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py`: `PASS`. `git diff --check`: `PASS`.
- Diff отсканирован на секреты: только имена переменных окружения, без
  значений. `0` provider/SMTP/DNS вызовов.

## Что не прошло

Ничего из финально применённого не провалилось. Одна ошибка
(`benchmarks/benchmark_models.py`'s пропущенный импорт) была найдена и
исправлена в рамках этой же задачи до публикации, не является дефектом
финального состояния.

## Что не проверено

NOT VERIFIED: реальный Vercel build/deploy. NOT VERIFIED:
недокументированный внешний Python-импорт любого из 4 модулей.

## Change Budget — превышение, одобренное владельцем

`CHANGE_BUDGET_EXCEEDED: YES` — `24` затронутых файла против явного
порога `>22` из самой задачи. Вся работа была уже применена и полностью
протестирована на момент обнаружения этого факта. Публикация была
приостановлена, владельцу представлены точные доказательства (список 24
файлов, причина — 4 легитимные находки fresh-scan, не расширение
функционального scope), получено явное одобрение продолжить без отката.
Это решение и общее правило для будущих похожих ситуаций сохранены в
памяти сессии (`feedback_change_budget_stop_threshold.md`).

## Текущее состояние runtime

Runtime для этой задачи не запускался. Ни одного provider-вызова, real
mail или записи в canonical database не произошло.

## Следующий рациональный шаг

`backend/{integrations/{registry,llm},domain/supplier_identity}/` теперь
содержат 8 перенесённых модулей. Оставшиеся корневые модули
(`supplier_app.py`, `api/index.py`, `serp_parser.py`, `contact_crawler.py`,
`collect_inn.py`, `web_lookup.py`, и т.д.) требуют отдельных bounded задач
с явными import/subprocess/deployment контрактами.

## Не повторять

Не использовать legacy OneDrive checkout для разработки, не выводить и не
сохранять значения секретов, не запускать реальную почту или live
provider-вызовы, не менять бизнес-логику `mail/` при обновлении единственной
сломанной строки импорта (только импорт), не считать формальное численное
превышение change-budget автоматическим STOP, если превышение вызвано
законными находками того же самого уже согласованного переноса (см.
сохранённую memory-заметку), не добавлять `inn_resolver.py` в immutability
protection только потому что он теперь рядом с защищёнными файлами, и не
добавлять второе подтверждение VibeCoding в промежуточное сообщение.
