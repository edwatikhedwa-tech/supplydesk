# TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`COLLECT_INN_SPLIT: COMPLETE` — [CONFIRMED] переиспользуемая детерминированная
часть `collect_inn.py` (`INN_URL_HINTS`, `INN_PATHS`, `page_text`,
`extract_for_site`, `extract_legal_ids_for_site`) извлечена в новый модуль
`backend/domain/supplier_enrichment/pipeline.py`. `collect_inn.py` остаётся
на месте в root как явно тонкая CLI-обёртка (argparse, оркестрация
crawl/LLM/web/DaData в `main()`, вывод CSV), импортирующая извлечённые
функции обратно. 4 подтверждённых consumer'а этих конкретных символов
обновлены на канонический путь. Immutability guard дополнен новым путём;
`collect_inn.py` остался защищён на прежнем корневом пути без изменений.

## Цель, контекст и границы

- **Цель:** продолжить bounded root refactor (Pass 9) по явной инструкции
  владельца — выполнить `MOVE_DOMAIN_PACKAGE`-решение диагностики для
  `collect_inn.py`, которое явно требовало разделения («Extract reusable
  pipeline... leave... CLI wrapper»), а не чистого переноса.
- **Контекст:** ветка `claude/zen-goldwasser-022bb1`, продолжение серии из 8
  уже завершённых bounded root refactor passes. Диагностика
  (`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`) явно
  пометила это как `High risk`, требующее «explicit split contract», в
  отличие от всех предыдущих 8 passes, которые были чистыми
  переносами/однострочными правками импорта.
- **Ограничения:** без изменения парсинга/scoring/LLM/web/DaData-логики,
  без сетевых вызовов, без изменения CLI-контракта (`--help`, аргументы,
  вывод). Только эти 5 символов и их known consumers; `write_csv`, `FIELDS`,
  `build_arg_parser`, `collect_hosts`, `main` остаются в `collect_inn.py`
  без изменений по существу.
- **Готово когда:** переиспользуемая часть находится в
  `backend/domain/supplier_enrichment/pipeline.py`, `collect_inn.py`
  импортирует её обратно без дублирования кода, все известные imports
  канонические, immutability guard обновлён и доказан, CLI-поведение
  побайтово не изменилось, целевые и regression тесты проходят,
  документация обновлена.

## Разделение: что ушло, что осталось

**В `backend/domain/supplier_enrichment/pipeline.py` (переиспользуемое, без
CLI и сети):**

- `INN_URL_HINTS`, `INN_PATHS` — константы смещения crawl/scoring;
- `page_text()`;
- `extract_for_site()`;
- `extract_legal_ids_for_site()`.

**Осталось в `collect_inn.py` (CLI-only):**

- `FIELDS`, `write_csv()` — CLI-специфичный вывод, не используется
  `supplier_app.py`;
- `build_arg_parser()`, `collect_hosts()`, `main()` — argparse, оркестрация
  ступеней 1–4, печать отчёта; логика ступеней не менялась, только источник
  импорта детерминированного разбора.

Функции `page_text`/`extract_for_site`/`extract_legal_ids_for_site`
скопированы в новый модуль байт-в-байт (включая существующий комментарий у
`page_text`), затем их дублирующиеся определения в `collect_inn.py` удалены
и заменены импортом — код не переписывался, только перемещён.

## Свежая проверка ссылок (не только AST)

Полнотекстовый поиск по репозиторию для этих 5 символов нашёл 4 реальных
Python-consumer'а помимо самого `collect_inn.py`:

- `supplier_app.py:36-42` — все 5 символов, top-level import;
- `scripts/verify_enrichment_live.py:18-23` — 4 из 5 (`INN_PATHS`,
  `INN_URL_HINTS`, `extract_for_site`, `extract_legal_ids_for_site`;
  `page_text` не используется этим скриптом);
- `tests/test_enrichment_pipeline.py:10` — 2 из 5 (`extract_for_site`,
  `extract_legal_ids_for_site`);
- `benchmarks/benchmark_models.py:96` — 2 из 5 (`INN_PATHS`,
  `INN_URL_HINTS`), lazy-импорт внутри функции; `benchmark_models.py` имеет
  собственную независимую функцию `page_text()` (строка 81, другая
  реализация через `BeautifulSoup` напрямую) — это НЕ consumer
  `collect_inn.page_text`, ложное совпадение отфильтровано вручную.

Отдельно проверено: упоминания `page_text` в
`backend/integrations/llm/llm_fallback.py` и
`tests/diagnostics/test_collect_inn_llm_path.py` — это имена параметров
несвязанных функций (`build_inn_user_message`, `extract_inn`, фейковый
extractor), не импорты из `collect_inn`/`pipeline` — ложные совпадения
отфильтрованы вручную.

Поиск `collect_inn.<attr>` (module-attribute доступ) и
`patch(...collect_inn...)` не нашёл дополнительных string-based
consumer'ов.

`supplier_discovery_v2/immutability_check.py`: [CONFIRMED] `"collect_inn.py"`
уже был в плоском защищённом кортеже — остаётся там без изменений (файл не
переносится, только его контент осознанно меняется в рамках этой задачи,
что и является целью защиты — предотвратить *непреднамеренный* дрейф, а не
запретить санкционированное изменение).

Четыре корневых `test_*.py` (`test_extractor.py`, `test_inn.py`,
`test_parser.py`, `test_verify.py`) проверены на импорт `collect_inn` —
[CONFIRMED] ни один не импортирует его; оба выполнимых без сети
(`test_extractor.py`, `test_inn.py`) прогнаны напрямую — "Все проверки
пройдены", exit `0`.

## Immutability guard migration

`supplier_discovery_v2/immutability_check.py`'s `protected_paths()`:
[CONFIRMED] добавлен новый явный блок, проверяющий
`root / "backend" / "domain" / "supplier_enrichment" / "pipeline.py"` — по
аналогии с прецедентом Checko/supplier-identity/search-integrations/
contact-crawler блоков, но с одним отличием: `pipeline.py` — новый файл, а
не перенос существующего защищённого пути, поэтому старый путь для него не
существовал и не удаляется. `collect_inn.py` остаётся в исходном плоском
кортеже без изменений. Доказано:

- Baseline round-trip на реальном дереве
  (`test_snapshot_matches_written_baseline`): `write_baseline` → `verify()
  == []`.
- Одноразовое synthetic tempfile-дерево
  (`test_disposable_mutation_of_enrichment_pipeline_module_is_detected`):
  `pipeline.py` помечен как protected на новом пути, мутация обнаруживается;
  реальный файл проекта никогда не мутировался.
- `test_enrichment_pipeline_module_is_protected`: явно проверяет, что и
  `pipeline.py`, и `collect_inn.py` оба присутствуют в защищённом множестве
  одновременно.

`supplier_discovery_v2/tests/test_immutability.py`: `24/24 PASS` (полный
файл, включая 2 новых теста).

## Тесты

| Проверка | Результат |
|---|---|
| `python -m unittest tests.test_enrichment_pipeline tests.diagnostics.test_collect_inn_llm_path supplier_discovery_v2.tests.test_immutability -v` | [CONFIRMED] `22/22 PASS` |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=466; failures=0; errors=9 (те же pre-existing pwsh-gap, что и во всех предыдущих Pass); skipped=1` |
| `python test_extractor.py` | [CONFIRMED] "Все проверки пройдены", exit `0` |
| `python test_inn.py` | [CONFIRMED] "Все проверки пройдены", exit `0` |
| `python collect_inn.py --help` | [CONFIRMED] exit `0`, идентичный набор аргументов и справочный текст (не менялись `build_arg_parser`/`__doc__`) |
| Provider/сетевые вызовы | [CONFIRMED] `0` |

`tests/diagnostics/test_collect_inn_llm_path.py` отдельно ценен здесь: это
поведенческий тест реального `collect_inn.main(["...", "--llm"])`
(добавлен при закрытии `FINDING-018`), и его прохождение доказывает, что
`main()` продолжает корректно вызывать перенесённые
`extract_for_site`/`page_text` через новую цепочку импорта end-to-end, а не
только то, что модуль импортируется.

## Import contract

| Проверка | Результат |
|---|---|
| `import backend.domain.supplier_enrichment.pipeline` | [CONFIRMED] успешно |
| `collect_inn.extract_for_site is pipeline.extract_for_site` | [CONFIRMED] `True` — та же функция, не копия |
| `supplier_app.extract_for_site is pipeline.extract_for_site` | [CONFIRMED] `True` |
| `import collect_inn` | [CONFIRMED] успешно |
| `import supplier_app` | [CONFIRMED] успешно |
| `import scripts.verify_enrichment_live` | [CONFIRMED] успешно |
| `import benchmarks.benchmark_models` | [CONFIRMED] успешно |
| `import tests.test_enrichment_pipeline` | [CONFIRMED] успешно |
| `from api.index import handler` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная офлайн-цепочка |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `11` файлов:
`backend/domain/supplier_enrichment/pipeline.py` (new),
`collect_inn.py`, `supplier_app.py`,
`scripts/verify_enrichment_live.py`, `tests/test_enrichment_pipeline.py`,
`benchmarks/benchmark_models.py`,
`supplier_discovery_v2/immutability_check.py`,
`supplier_discovery_v2/tests/test_immutability.py`,
`docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`,
`ai/CURRENT_STATE.md` (+ `ai/ACTIVE_TASK.md` state-only). В пределах
ожидаемого диапазона согласно причинно-связанной автономной политике
владельца.

## Не проверено

- NOT VERIFIED: реальный Vercel build/deploy (не запускался; переиспользована
  структурная проверка `vercel.json` из предыдущих задач — `backend/**` не
  исключён).
- NOT VERIFIED: недокументированный внешний Python-импорт `collect_inn`'s
  извлечённых символов за пределами репозитория.
- NOT VERIFIED: реальные вызовы LLM/XMLRiver/DaData providers в `main()`
  (не требовались этой задачей — `--llm`/`--web`/DaData ветки покрыты
  моками в `tests/diagnostics/test_collect_inn_llm_path.py` и
  `tests/test_enrichment_pipeline.py`, реальные ключи не использовались).

## Оставшийся объём root-рефакторинга (не выполнено в этой задаче)

- `serp_parser.py` — остаётся `DEFER`red: жёстко прошитый subprocess-путь в
  `supplier_discovery_v2/xmlriver_subprocess.py` и deployment-путь Vercel
  конфликтуют с переносом; требует явного решения владельца по
  subprocess/deployment-контракту перед любым перемещением.
- Корневые `test_*.py` (`test_extractor.py`, `test_inn.py`, `test_parser.py`,
  `test_verify.py`) — `DEPRECATED_REVIEW`, требуют решения владельца о
  discovery-политике (остаться manual / стать unittest / retire), не
  перенос.
- `supplier_app.py`/`api/index.py` — `KEEP_ROOT`, защищённые entrypoints, не
  переносятся.
- Опциональный дальнейший шаг (не авторизован этим изменением): перенос
  тонкого CLI-обёртки `collect_inn.py` в `scripts/collect_inn.py` с root
  compatibility wrapper, по точному прецеденту Pass 2
  (`collect_contacts.py`/`benchmark_models.py`) — диагностика называет это
  целевым расположением, но это отдельное, самостоятельно проверяемое
  решение о переносе файла, не выполненное в рамках этой задачи разделения
  логики.

## Публикация

Commit/push/CI зафиксированы в финальном ответе агента. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
