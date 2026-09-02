# TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902

`DELIVERY_MODE: PUBLISH`

## Итог

`LLM_MOVE: COMPLETE` — [CONFIRMED] `llm_fallback.py` и `routerai_client.py`
перенесены в `backend/integrations/llm/`, все 4 подтверждённых consumer'а
обновлены, root-копий не осталось, wrapper'ы не потребовались. Prompts,
schemas, model defaults и provider-логика не изменены — доказано `git diff
-M` (99% и 100% similarity). Обнаружен и задокументирован (не исправлен)
несвязанный pre-existing баг: `collect_inn.py --llm` импортирует
несуществующий `InnLlmExtractor`.

## Цель, контекст и границы

- **Цель:** перенести LLM/provider-транспорт (`llm_fallback.py`,
  `routerai_client.py`) в `backend/integrations/llm/`, обновить только
  подтверждённые consumers, не менять LLM business logic.
- **Контекст:** ветка `audit/frontend-knip-20260902`, preflight HEAD
  `c666c8d2ad758815599ea812e5746df3c84eef7a`.
- **Ограничения:** без изменения prompts/schemas/model selection/RouterAI
  API behavior; без реальных AI/provider вызовов; только эти два файла.
- **Готово когда:** обе реализации под `backend/integrations/llm/`, root
  отсутствует, все известные imports канонические, prompts/schemas/defaults
  структурно доказаны неизменными, offline-цепочка импорта проходит,
  focused-тесты проходят.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `c666c8d2ad758815599ea812e5746df3c84eef7a` |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] `IDLE` перед стартом |
| Текущее содержимое обоих модулей | [CONFIRMED] прочитано целиком перед переносом |

## Свежая проверка ссылок (не только AST)

- `llm_fallback`: [CONFIRMED] `supplier_app.py:51`, `collect_inn.py:217`
  (lazy), `scripts/collect_contacts.py:287` (lazy),
  `benchmarks/benchmark_models.py:172` (lazy) — совпадает с baseline.
  `inn_extractor.py:15` содержит лишь текстовое упоминание в комментарии
  (`см. llm_fallback.py`), не импорт — не требует правки, `inn_extractor.py`
  в списке "не трогать".
- `routerai_client`: [CONFIRMED] `llm_fallback.py` (lazy),
  `benchmarks/benchmark_models.py:173` (lazy) — совпадает с baseline.
- `mock.patch`/`monkeypatch`/строковые dotted-path на любой из модулей:
  [CONFIRMED] не найдено нигде в `tests/`.
- `supplier_discovery_v2/immutability_check.py` protected-paths: [CONFIRMED]
  ни `llm_fallback.py`, ни `routerai_client.py` в списке никогда не было —
  конфликта, аналогичного Checko/FINDING-017, нет.
- `docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`: [CONFIRMED]
  проверены; `CLAUDE.md` уже не содержит их имён (очищено в предыдущей
  задаче), `REPOSITORY_LAYOUT.md` обновлён.

**Незапланированная находка:** [CONFIRMED] `collect_inn.py:217` импортирует
`InnLlmExtractor` из `llm_fallback` — символа с таким именем в
`llm_fallback.py` никогда не было (только `LlmExtractor`); это
подтверждено чтением файла до переноса. Тот же код-путь сообщает оператору
про `ANTHROPIC_API_KEY`, тогда как `api_key_present()` фактически проверяет
`ROUTERAI_KEY`. Оба несоответствия — pre-existing, не введены этой задачей;
записаны как [`FINDING-018`](../DEFERRED_FINDINGS.md#finding-018--collect_innpy---llm-imports-a-nonexistent-symbol),
исправление вне scope (`collect_inn.py` ограничен только строкой импорта).

## Перенос

- `backend/integrations/llm/routerai_client.py` — [CONFIRMED] `git diff -M`
  показывает `100%` similarity, `0` изменённых строк.
- `backend/integrations/llm/llm_fallback.py` — [CONFIRMED] `git diff -M`
  показывает `99%` similarity, ровно `1` изменённая строка (внутренний lazy
  import `RouterAiClient` на канонический путь). Ничего в prompts (`INN_SYSTEM_PROMPT`,
  `EMAIL_SYSTEM_PROMPT`), schemas (`INN_SCHEMA`, `EMAIL_SCHEMA`),
  `DEFAULT_MODEL`, `MAX_OUTPUT_TOKENS`, `trim_text`, `parse_inn_answer`,
  `parse_email_answer`, `api_key_present` не изменено.
- Корневые `llm_fallback.py`/`routerai_client.py` — [CONFIRMED] удалены.
  Root wrapper не создан — единственные consumers внутренние, конкретного
  tracked/runtime контракта на внешний импорт не обнаружено.
- Обновлены строки импорта: `supplier_app.py:51`, `collect_inn.py:217`
  (символ `InnLlmExtractor` сохранён как есть — см. FINDING-018),
  `scripts/collect_contacts.py:287`, `benchmarks/benchmark_models.py:172-173`.

## Prompt/Schema integrity (раздел 8)

```
PROMPTS_CHANGED: NO
SCHEMAS_CHANGED: NO
MODEL_DEFAULTS_CHANGED: NO
```

Доказано структурно `git diff -M --stat`: `llm_fallback.py` — `1 file
changed, 1 insertion(+), 1 deletion(-)` (только import), `routerai_client.py`
— `0 insertions(+), 0 deletions(-)`. Дополнительно проверено программно:
`backend.integrations.llm.llm_fallback.DEFAULT_MODEL ==
"mistralai/mistral-nemo"` — совпадает с исходным значением.

## Import contract (раздел 10)

| Проверка | Результат |
|---|---|
| `import backend.integrations.llm.routerai_client` | [CONFIRMED] успешно, `RouterAiClient`/`ModelCatalog` доступны |
| `import backend.integrations.llm.llm_fallback` | [CONFIRMED] успешно, `LlmExtractor`/`DEFAULT_MODEL`/`api_key_present` доступны |
| `import supplier_app` | [CONFIRMED] успешно |
| `import collect_inn` | [CONFIRMED] успешно |
| `import scripts.collect_contacts` (через `python collect_contacts.py --help` и `python -m scripts.collect_contacts --help`) | [CONFIRMED] exit `0` оба, вывод побайтово идентичен (`diff` чисто) |
| `import benchmarks.benchmark_models` (через `python benchmark_models.py --help` и `python -m benchmarks.benchmark_models --help`) | [CONFIRMED] exit `0` оба, вывод побайтово идентичен |
| `from api.index import handler, _APP` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная офлайн-цепочка |

## Mock/patch safety (раздел 11)

[CONFIRMED] Ни одного `mock.patch`/`monkeypatch`/строкового dotted-path,
ссылающегося на `llm_fallback`/`routerai_client`, нигде в `tests/` не
найдено — обновлять нечего.

## Pre-existing broken symbol — доказано не регрессией

[CONFIRMED] `InnLlmExtractor` отсутствовал в `llm_fallback.py` до переноса
(прочитано целиком) и отсутствует в `backend.integrations.llm.llm_fallback`
после переноса — тот же `ImportError`, только с новым путём модуля в
сообщении. Поведение этого уже нерабочего code-path идентично до и после.

## Serverless structural check (раздел 13)

`SERVERLESS_PACKAGE_COMPATIBILITY: STRUCTURALLY_CONFIRMED` — [CONFIRMED]
`git check-ignore` на новые файлы `backend/integrations/llm/**` вернул "не
игнорируется"; `vercel.json` не менялся (переиспользована структурная
проверка `excludeFiles` из предыдущих задач — совпадений с `backend/**`
нет). `supplier_app` транзитивная цепочка проверена офлайн через
`api.index` (см. Import contract).

## Тесты (раздел 12)

Существующего покрытия для `llm_fallback`/`routerai_client` не было
(env/flag-gated пути, офлайн-suite их не задевает) — аналогично прецеденту
`dadata_client.py`. Добавлен
[`tests/diagnostics/test_llm_integration_move.py`](../../tests/diagnostics/test_llm_integration_move.py)
(6 тестов): импортируемость обоих модулей по новому пути, каноничность
lazy-импорта RouterAI внутри `llm_fallback.py`, отсутствие корневых файлов,
каноничность импортов во всех 4 known consumers. Это не «тест на факт
переноса ради теста» — единственная защита от молчаливого дрейфа пути
импорта, который иначе не сработает ни в одном офлайн CI.

`6/6 PASS`. Дополнительно:

| Проверка | Результат |
|---|---|
| `tests.test_enrichment_pipeline` + `tests.test_dashboard` | [CONFIRMED] `21/21 PASS` |
| `python -m unittest discover -s tests/diagnostics -v` | `LOCAL_DIAGNOSTICS_PASSED: 52`, `LOCAL_DIAGNOSTICS_ERRORS: 9`, `LOCAL_DIAGNOSTICS_STATUS: PARTIAL_ENVIRONMENT` — те же 9 ошибок `test_change_classifier.py` (`pwsh` недоступен), доказано ранее не связанными с изменениями кода; повторно не расследовалось |
| Provider/AI вызовы | [CONFIRMED] `0` |

## Валидация

| Проверка | Результат |
|---|---|
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS`, `tool_entries=40` |
| `git diff --check` | [CONFIRMED] exit `0` |
| Сканирование staged diff на секреты | [CONFIRMED] только `ROUTERAI_KEY`/`ANTHROPIC_API_KEY`/`api_key`/`self.token` — имена переменных и код, значений нет |

## Change Budget (раздел 17)

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `9` файлов:
`backend/integrations/llm/__init__.py`,
`backend/integrations/llm/llm_fallback.py` (rename),
`backend/integrations/llm/routerai_client.py` (rename),
`supplier_app.py`, `collect_inn.py`, `scripts/collect_contacts.py`,
`benchmarks/benchmark_models.py`, `tests/diagnostics/test_llm_integration_move.py`,
`docs/architecture/REPOSITORY_LAYOUT.md`. В пределах ожидаемых 10-12.

## Не проверено

- NOT VERIFIED: реальный Vercel build/deploy (не запускался; переиспользована
  структурная проверка `vercel.json` из предыдущих задач).
- NOT VERIFIED: недокументированный внешний Python-импорт `llm_fallback`/
  `routerai_client` за пределами репозитория.
- `FINDING-018` (`InnLlmExtractor`) остаётся открытым — вне scope этой
  задачи.

## Публикация

Commit/push/CI зафиксированы в финальном отчёте ниже. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
