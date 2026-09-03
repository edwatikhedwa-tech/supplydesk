# TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`PASS_2_COMPLETE` — [CONFIRMED] весь enrichment pipeline (~1000 строк:
`_run_enrichment_retry_loop`, `process_search_step`, `_process_serp_step`,
`_process_enrich_step`, `_job_hosts`, `_enqueue_enrichment_outcome`,
`process_enrichment_retry_step`, `_resume_registry_enrichment`,
`_resume_web_enrichment`, `_resume_finance_enrichment`, `_enrich_suppliers`,
`_enrich_registry_backlog`, `_resolve_missing_inn`, `_resolve_missing_email`,
`_enrich_one`, `_legal_id_context`, `_checko_retry_since`,
`_evidence_items`, `_llm_fill`) и `EnrichmentOutcome` вынесены из
`SupplierApp` в `backend/domain/supplier_enrichment/orchestrator.py` как
`EnrichmentOrchestratorMixin`. `class SupplierApp(EnrichmentOrchestratorMixin)`
композирует его через наследование — методы byte-for-byte идентичны,
поведение не изменилось. `supplier_app.py` уменьшился ещё на ~1000 строк.

## Как выбран безопасный способ переноса

По итогам read-only аудита (Explore-агент) эта часть кода была оценена как
"low-medium risk, самый большой прирост" при условии **mixin-композиции**, а
не переноса с явной передачей зависимостей: все методы уже полагаются на
`self.repository`, `self.service`, `self.llm_budget_rub`,
`self.llm_spent_rub`, `self.llm_spent_day`, `self.enrichment_retry_stop`,
`self.enrichment_retry_interval` — все эти атрибуты остаются в
`SupplierApp.__init__` (не переносился). При mixin-наследовании Python MRO
резолвит `self.xxx` идентично независимо от того, в каком классе физически
определён метод — поэтому перенос механический и не требует передачи
зависимостей явными параметрами.

## Что сделано

1. Создан `backend/domain/supplier_enrichment/orchestrator.py`:
   `EnrichmentOutcome` (dataclass) + `EnrichmentOrchestratorMixin` (19
   методов, включая 4 `@staticmethod`).
2. `ROOT` в новом файле — независимая локальная константа
   (`Path(__file__).resolve().parents[3]`), а не `self.ROOT` — тот же
   паттерн, что уже установлен в `backend/app_config.py`/
   `backend/http_static.py` в Pass 1; единственное место использования
   (`stop_domains.txt` в `_process_serp_step`) сверено построчно.
3. `supplier_app.py`: `class SupplierApp:` → `class SupplierApp
   (EnrichmentOrchestratorMixin):`; методы удалены (`sed` по точным
   границам, проверенным до и после); импорты, использовавшиеся только
   внутри перенесённого блока, удалены (`ContactCrawler`, `SiteResult`,
   `INN_PATHS`, `INN_URL_HINTS`, `extract_for_site`,
   `extract_legal_ids_for_site`, `page_text`, `is_contact_url`,
   `root_domain`, `InnHit`, `LegalIdHit`, `is_requisites_url`,
   `collect_name_hints_from_pages`, `resolve_inn_by_legal_ids`,
   `resolve_inn_by_registry`, `LlmExtractor`, `api_key_present`,
   `registry_owns_site`, `registry_ownership_unknown`, `verify_email`,
   `WebLookup`, `SerpCollector`, `read_lines`, `XmlRiverClient`,
   `EnrichmentOutcome`, `dataclass`, `field`). `CheckoClient` и
   `validate_inn_checksum` остались — используются в `update_supplier_inn`,
   который не переносился (проверено grep построчно ДО удаления).

## Регрессия и фикс (не product-код)

Первый полный прогон дал `failures=1`:
`tests.diagnostics.test_llm_integration_move.LlmIntegrationMoveTests.
test_known_consumers_use_the_canonical_import_path` — тест из более
раннего прохода (`TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902`) буквально
проверял наличие строки `from backend.integrations.llm.llm_fallback
import LlmExtractor, api_key_present` в исходнике `supplier_app.py`. После
переноса эта строка законно переехала в `orchestrator.py`. Это прямая
причинная зависимость данного изменения (сам тест проверяет
местоположение импорта, не бизнес-логику) — обновлён по установленному
паттерну ("known consumers" reference tests), без вопроса владельцу, в
соответствии с явным разрешением на такие causal-зависимые правки.
Перепрогон полного набора — чисто.

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` обоих файлов | [CONFIRMED] синтаксис корректен |
| `supplier_app.SupplierApp.__mro__` | [CONFIRMED] `['SupplierApp', 'EnrichmentOrchestratorMixin', 'object']` |
| `hasattr(SupplierApp, '_enrich_one')`, `process_search_step` | [CONFIRMED] `True` |
| Офлайн импорт `supplier_app`, `api.index.handler` | [CONFIRMED] PASS |
| `tests.test_enrichment_pipeline`, `test_dashboard`, `test_outgoing_safety`, `test_mail_integrity`, `test_mail_integration` (129 тестов) | [CONFIRMED] `OK (skipped=1)` |
| `supplier_discovery_v2.tests.test_immutability` (13 тестов) | [CONFIRMED] `OK` — protected paths не задеты |
| `python scripts/run_test_suite.py` (после фикса теста) | [CONFIRMED] `tests=497; failures=0; errors=9 (baseline); skipped=1` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 4 файла продукта/тестов
(`supplier_app.py`, новый модуль, `tests/diagnostics/test_llm_integration_move.py`,
`CLAUDE.md`) + state-файлы. Причинно-связанный тест обновлён в рамках той
же задачи, не отдельным вопросом.

## Не проверено

- NOT VERIFIED: реальный запуск сервера как процесс.
- NOT VERIFIED: Vercel build/deploy.

## Следующий шаг

Pass 3: routes/auth mixins для `SupplierHandler` — по аудиту это требует
СНАЧАЛА перевода `do_GET`/`do_POST` с линейной if/elif-цепочки (~65
маршрутов) на таблицу диспетчеризации, что само по себе более рискованное
структурное изменение, чем чистое извлечение метода. Затем —
`mail/repository.py` (сначала DB-compat shim, затем mixins по
обязанностям), по тому же аудиту.
