---
document_id: REPOSITORY-LAYOUT-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-04
source_commit: 78484108ed010e152ab0e3e04d2490e8c4137d6c
---

# Структура репозитория

Это краткая карта текущих директорий верхнего уровня, синхронизируемая только после того, как
запланированный рефакторинг корня действительно произошёл. Она документирует то, что существует
сейчас, а не целевую структуру. За поведенческим владением компонентами — см.
[`COMPONENT_MAP.md`](COMPONENT_MAP.md).

| Путь | Содержит |
|---|---|
| точки входа композиции в корне | `supplier_app.py` (точка входа локального backend); `serp_parser.py` (тонкая обёртка для совместимости с CLI, реализация перенесена) и `collect_inn.py` (облегчённый CLI, реализация частично вынесена) всё ещё в корне; четыре корневых теста (`test_extractor.py`, `test_inn.py`, `test_parser.py`, `test_verify.py`) |
| `api/` | `api/index.py` — адаптер Vercel serverless поверх `supplier_app.py` |
| `backend/` | Новая область продуктового кода. `backend/integrations/registry/` — адаптеры провайдеров, вынесенные из плоского пакета в корне (`dadata_client.py`, `checko_client.py`); `backend/integrations/llm/` — транспорт LLM/провайдера, вынесенный из плоского пакета в корне (`llm_fallback.py`, `routerai_client.py`); `backend/integrations/search/` — интеграции SERP/веб-поиска, вынесенные из плоского пакета в корне (`web_lookup.py`, `xmlriver_client.py`, `serp_parser.py`, последний — с тонкой обёрткой для совместимости с CLI в корне); `backend/integrations/logistics/` — клиент калькулятора стоимости доставки Деловых Линий (Dellin) (`dellin_client.py`), новый, не перенос; `backend/domain/supplier_identity/` — продуктовая логика идентичности поставщика, вынесенная из плоского пакета в корне (`email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `verify.py`); `backend/domain/supplier_enrichment/` — логика обогащения поставщиков, вынесенная из плоского пакета в корне: `contact_crawler.py` (перенесён) и `pipeline.py` (извлечён из переиспользуемого разбора ИНН/ОГРН в `collect_inn.py`, общий для `supplier_app.py` и CLI); `backend/domain/logistics/` — `quote_service.py`, бизнес-правило расчёта стоимости доставки (жёсткий gate, кэш, разбор ответа), новый, не перенос |
| `mail/` | Реальная интеграция Yandex IMAP/SMTP и репозиторий почты на SQLite, включая `logistics_quotes.py` (`LogisticsQuotesMixin`, хранение ручных расчётов стоимости доставки) |
| `migrations/` | Версионированный DDL схемы SQL |
| `frontend/` | SPA на React/Vite (TypeScript, Tailwind) |
| `scripts/` | Инструменты оператора/управления, плюс одна перенесённая реализация CLI (`scripts/collect_contacts.py`) с обёрткой совместимости в корне |
| `benchmarks/` | Офлайн-фикстуры (`enrichment_cases.json`) и одна перенесённая реализация CLI (`benchmarks/benchmark_models.py`) с обёрткой совместимости в корне |
| `tests/` | Наборы backend-тестов на unittest, включая `tests/diagnostics/` и `tests/legacy/` (четыре корневых скрипта ручной проверки, преобразованные в настоящие `unittest.TestCase`) |
| `supplier_discovery_v2/` | Изолированный пилот discovery; не импортирует и не изменяет продуктовый код парсера (см. собственный `README.md`) |

## Переносы в процессе

- `TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902`: реализации `collect_contacts.py` и
  `benchmark_models.py` перенесены в `scripts/` и `benchmarks/`; файлы в корне — тонкие обёртки
  совместимости.
- `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902` +
  `TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902`:
  `dadata_client.py` и `checko_client.py` оба перенесены в
  `backend/integrations/registry/`, без обёртки в корне (не подтверждено ни одного внешнего
  потребителя Python-импорта ни для одного из них). Список защищённых путей в
  `supplier_discovery_v2/immutability_check.py` был перенесён на новое расположение Checko в
  том же изменении, что и сам перенос, поэтому существующая защита неизменяемости ни разу не
  ослаблялась.
- `TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902`: `llm_fallback.py` и
  `routerai_client.py` перенесены в `backend/integrations/llm/`, без обёртки
  в корне. `supplier_app.py`, `collect_inn.py`,
  `scripts/collect_contacts.py` и `benchmarks/benchmark_models.py` обновлены
  на канонический путь импорта.
- `TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902`:
  `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py` и `verify.py`
  перенесены в `backend/domain/supplier_identity/`, без обёртки в корне. 14 известных
  потребителей обновлены (`supplier_app.py`, `contact_crawler.py`, `collect_inn.py`,
  `web_lookup.py`, `scripts/collect_contacts.py`, `scripts/verify_enrichment_live.py`,
  `benchmarks/benchmark_models.py`, `backend/integrations/llm/llm_fallback.py`,
  `backend/integrations/registry/dadata_client.py`, `mail/repository.py`, корневые
  тесты и `tests/test_enrichment_pipeline.py`), включая два, не названных в
  исходной диагностике (`web_lookup.py`, `mail/repository.py`), найденных
  свежим полным сканированием дерева, а не предположенных по прежним доказательствам.
  Список защищённых путей в `supplier_discovery_v2/immutability_check.py` был
  перенесён для трёх уже защищённых файлов
  (`email_extractor.py`/`inn_extractor.py`/`verify.py`) в том же изменении;
  `inn_resolver.py` намеренно оставлен незащищённым — он никогда не был
  защищён раньше, и перенос рядом с остальными тремя не является основанием для его добавления.
- `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903`: `web_lookup.py`
  и `xmlriver_client.py` перенесены в `backend/integrations/search/`, без обёртки
  в корне. Оба — чистые переносы с нулевым diff (`git diff -M --stat`). 6 подтверждённых
  потребителей обновлены на канонический путь импорта (`supplier_app.py`,
  `collect_inn.py`, `scripts/collect_contacts.py`, `test_extractor.py`,
  `serp_parser.py`, `test_parser.py`); сам `serp_parser.py` остаётся
  в статусе `DEFER` (не перенесён) согласно диагностике — изменена только одна его
  внутренняя строка импорта. `supplier_discovery_v2/xmlriver_subprocess.py` не затронут:
  он вызывает нетронутый `serp_parser.py` по абсолютному пути через
  `subprocess.run(..., cwd=...)`, поэтому обновлённый импорт самого `serp_parser.py`
  разрешается в этой точке вызова как обычно.
  Список защищённых путей в `supplier_discovery_v2/immutability_check.py` был
  перенесён для обоих файлов в том же изменении, поэтому существующая защита
  неизменяемости ни разу не ослаблялась.
- `TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903`:
  `contact_crawler.py` перенесён в `backend/domain/supplier_enrichment/`, без обёртки
  в корне. Это чистый перенос с нулевым diff (`git diff -M --stat`); его единственный внутренний
  импорт уже указывал на канонический путь `backend.domain.supplier_identity.email_extractor`
  с более раннего прохода. 6 подтверждённых потребителей обновлены на канонический
  путь импорта (`supplier_app.py`, `collect_inn.py`,
  `benchmarks/benchmark_models.py`, `scripts/verify_enrichment_live.py`,
  `scripts/collect_contacts.py`, `tests/test_enrichment_pipeline.py`,
  `tests/diagnostics/test_collect_inn_llm_path.py`).
  Список защищённых путей в `supplier_discovery_v2/immutability_check.py` был
  перенесён в том же изменении, поэтому существующая защита неизменяемости ни разу не ослаблялась.
- `TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903`:
  переиспользуемый детерминированный разбор ИНН/ОГРН из `collect_inn.py` (`INN_URL_HINTS`,
  `INN_PATHS`, `page_text`, `extract_for_site`, `extract_legal_ids_for_site`)
  вынесен в `backend/domain/supplier_enrichment/pipeline.py`;
  `collect_inn.py` остаётся в корне как облегчённый CLI (разбор аргументов, оркестрация
  краулинга/LLM/веб/DaData в `main()` и вывод CSV), импортируя обратно
  вынесенные функции. 4 подтверждённых потребителя этих конкретных
  символов обновлены на канонический путь импорта (`supplier_app.py`,
  `scripts/verify_enrichment_live.py`, `tests/test_enrichment_pipeline.py`,
  `benchmarks/benchmark_models.py`).
  Список защищённых путей в `supplier_discovery_v2/immutability_check.py` получил
  новый путь `pipeline.py` рядом с неизменённой записью корневого `collect_inn.py` —
  намеренное изменение содержимого `collect_inn.py` при разделении не снимает
  его собственную защиту.
- `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903`: `serp_parser.py`
  перенесён в `backend/integrations/search/serp_parser.py`, с тонкой обёрткой совместимости
  `serp_parser.py` в корне (делегирует только `main()`, тот же паттерн, что и обёртка
  `collect_contacts.py`), сохраняя задокументированный вызов
  `python serp_parser.py ...`. По явному решению владельца (диагностика отмечала это
  как конфликт с зашитым путём subprocess в
  `supplier_discovery_v2/xmlriver_subprocess.py` и границей развёртывания Vercel):
  этот зашитый путь по умолчанию `parser_path` был обновлён на новое каноническое расположение,
  а собственный вызов модуля `load_dotenv(Path(__file__).with_name(".env"))` (который
  молча начал бы искать `.env` рядом с новым вложенным путём) был исправлен на поиск
  относительно `REPO_ROOT`, по образцу, уже проверенному в обёртке `collect_contacts.py` на
  Проходе 2. 7 подтверждённых потребителей обновлены на
  канонический путь импорта. Список защищённых путей в
  `supplier_discovery_v2/immutability_check.py` был перенесён в том же изменении;
  незащищённая обёртка в корне не несёт логики, которая могла бы разойтись, — как и обёртки
  `collect_contacts.py` и `benchmark_models.py`.
- `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903`: четыре корневых скрипта ручной
  проверки (`test_extractor.py`, `test_inn.py`, `test_parser.py`,
  `test_verify.py` — скрипты с собственными `check()`/`main()`, никогда не входившие в
  обнаружение `scripts/run_test_suite.py`) преобразованы в настоящие
  `unittest.TestCase` под `tests/legacy/` по явному решению владельца.
  Каждый вызов `check(name, actual, expected)` стал
  `self._check(name, actual, expected)` (тонкая обёртка `subTest`+`assertEqual`),
  проверено построчным diff по каждой точке вызова 1:1 — покрытие не потеряно, ни одно
  утверждение не переписано. Корневые файлы удалены (их не импортировал никакой другой код).
  `tests/legacy/` автоматически подхватывается существующим рекурсивным обнаружением
  `unittest` в `scripts/run_test_suite.py` по `tests/` — изменений в раннере не потребовалось.
- Оставшиеся корневые модули, названные в
  `ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`
  (`supplier_app.py`, `api/index.py`), не перенесены и остаются в статусе `KEEP_ROOT` как
  защищённые точки входа.
