# TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`CONTACT_CRAWLER_MOVE: COMPLETE` — [CONFIRMED] `contact_crawler.py` перенесён
в `backend/domain/supplier_enrichment/contact_crawler.py`, доказан как 0-diff
pure move (`git diff --cached -M --stat`: `0 insertions(+), 0 deletions(-)`).
7 подтверждённых Python-consumers обновлены на канонический путь, root-копии
не осталось, wrapper не потребовался. Immutability guard мигрирован в том же
изменении — защита ни разу не ослаблена.

## Цель, контекст и границы

- **Цель:** продолжить bounded root refactor (Pass 8) по явной инструкции
  владельца («заверши рефакторинг и наведи порядок в архитектуре! используй
  все данные тебе инструменты и инструкции») — перенести
  `contact_crawler.py` в `backend/domain/supplier_enrichment/`, обновить
  только подтверждённых consumers, не менять сетевую/crawling-логику.
- **Контекст:** ветка `claude/zen-goldwasser-022bb1`, продолжение серии из 7
  уже завершённых bounded root refactor passes
  (`ai/CURRENT_STATE.md` / `docs/architecture/REPOSITORY_LAYOUT.md`).
  `TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md` пометил `contact_crawler.py`
  как `MOVE_DOMAIN_PACKAGE` без необходимости разделения файла (в отличие от
  `collect_inn.py`).
- **Ограничения:** без изменения crawling/robots/DNS/PDF-логики, без сетевых
  вызовов; только этот файл плюс его known import-consumers и immutability
  guard.
- **Готово когда:** реализация под `backend/domain/supplier_enrichment/`,
  root отсутствует, все известные imports канонические, immutability guard
  мигрирован и доказан, целевые и regression тесты проходят, документация
  обновлена.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `claude/zen-goldwasser-022bb1`, чистое рабочее дерево перед стартом |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] заблокирован (`TASK-LOCK-024`) перед стартом |
| Текущее содержимое модуля | [CONFIRMED] прочитано целиком перед переносом |

## Свежая проверка ссылок (не только AST)

Полнотекстовый поиск по репозиторию (`.py`-файлы) для строки
`from contact_crawler import` нашёл ровно 7 реальных Python-consumers:

- `supplier_app.py:43`
- `collect_inn.py:29`
- `benchmarks/benchmark_models.py:36`
- `scripts/verify_enrichment_live.py:24`
- `scripts/collect_contacts.py:28`
- `tests/test_enrichment_pipeline.py:11`
- `tests/diagnostics/test_collect_inn_llm_path.py:16`

Собственные импорты `contact_crawler.py` (строки 13-31) — только stdlib,
`requests`, `bs4` и уже перенесённый
`backend.domain.supplier_identity.email_extractor` — внутренняя строка
импорта менять не требовалось.

Поиск по `patch(...contact_crawler...)` / `patch.object(..., "contact_crawler"...)`
и по `import contact_crawler` (bare form)/`contact_crawler.<attr>` не нашёл
дополнительных string-based mock-путей или module-attribute обращений вне
уже найденных 7 файлов.

`supplier_discovery_v2/immutability_check.py` protected-paths: [CONFIRMED]
`"contact_crawler.py"` был в плоском кортеже с самого начала — миграция
guard'а обязательна и выполнена в этом же изменении.

`docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`: [CONFIRMED] проверены
и обновлены.

## Перенос

- `backend/domain/supplier_enrichment/contact_crawler.py` — [CONFIRMED]
  `git diff --cached -M --stat` показывает `0 insertions(+), 0 deletions(-)`.
- Корневой `contact_crawler.py` — [CONFIRMED] удалён (`git mv`). Root wrapper
  не создан — только внутренние Python-consumers, нет CLI-контракта на
  прямой запуск этого файла.
- Обновлены строки импорта: `supplier_app.py`, `collect_inn.py`,
  `benchmarks/benchmark_models.py`, `scripts/verify_enrichment_live.py`,
  `scripts/collect_contacts.py`, `tests/test_enrichment_pipeline.py`,
  `tests/diagnostics/test_collect_inn_llm_path.py`.

## Immutability guard migration

`supplier_discovery_v2/immutability_check.py`'s `protected_paths()`:
[CONFIRMED] `"contact_crawler.py"` удалён из плоского кортежа
`for name in ("serp_parser.py", "supplier_app.py", "collect_inn.py"):`;
добавлен новый явный блок, проверяющий
`root / "backend" / "domain" / "supplier_enrichment" / "contact_crawler.py"`
— по точному прецеденту Checko/supplier-identity/search-integrations
блоков. Доказано двумя способами:

- Baseline round-trip на реальном дереве
  (`test_snapshot_matches_written_baseline`): `write_baseline` → `verify()
  == []`.
- Одноразовое synthetic tempfile-дерево
  (`test_disposable_mutation_of_contact_crawler_is_detected`): файл помечен
  как protected на новом пути, мутация обнаруживается по своему
  относительному пути; реальный файл проекта никогда не мутировался.

`supplier_discovery_v2/tests/test_immutability.py` дополнен двумя тестами по
установленному паттерну (protection-at-new-path +
disposable-mutation-detection), `19/19 PASS` (полный файл).

## Тесты

| Проверка | Результат |
|---|---|
| `python -m unittest tests.test_enrichment_pipeline supplier_discovery_v2.tests.test_immutability -v` | [CONFIRMED] `17/17 PASS`, включая 2 новых immutability-теста |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=464; failures=0; errors=9 (те же pre-existing pwsh-gap, что и во всех предыдущих Pass); skipped=1` |
| Provider/сетевые вызовы | [CONFIRMED] `0` |

## Import contract

| Проверка | Результат |
|---|---|
| `import backend.domain.supplier_enrichment.contact_crawler` | [CONFIRMED] успешно, `ContactCrawler`/`SiteResult` доступны |
| `import supplier_app` | [CONFIRMED] успешно |
| `import collect_inn` | [CONFIRMED] успешно |
| `import scripts.collect_contacts` | [CONFIRMED] успешно |
| `import benchmarks.benchmark_models` | [CONFIRMED] успешно |
| `import scripts.verify_enrichment_live` | [CONFIRMED] успешно |
| `from api.index import handler` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная офлайн-цепочка |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `11` файлов:
`backend/domain/supplier_enrichment/__init__.py`,
`backend/domain/supplier_enrichment/contact_crawler.py` (rename),
`supplier_app.py`, `collect_inn.py`, `benchmarks/benchmark_models.py`,
`scripts/verify_enrichment_live.py`, `scripts/collect_contacts.py`,
`tests/test_enrichment_pipeline.py`,
`tests/diagnostics/test_collect_inn_llm_path.py`,
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
- NOT VERIFIED: недокументированный внешний Python-импорт `contact_crawler`
  за пределами репозитория.

## Оставшийся объём root-рефакторинга (не выполнено в этой задаче)

- `collect_inn.py` — `MOVE_DOMAIN_PACKAGE`, но требует **разделения** файла
  на переиспользуемый pipeline (`backend/domain/supplier_enrichment/`) и
  явную CLI-обёртку — структурное изменение, не чистый перенос; нужна
  отдельная bounded-задача с явным контрактом разделения.
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

## Публикация

Commit/push/CI зафиксированы в финальном ответе агента. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
