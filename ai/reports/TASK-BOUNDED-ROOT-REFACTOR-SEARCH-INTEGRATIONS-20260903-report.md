# TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`SEARCH_INTEGRATIONS_MOVE: COMPLETE` — [CONFIRMED] `web_lookup.py` и
`xmlriver_client.py` перенесены в `backend/integrations/search/`, оба
доказаны как 0-diff pure move (`git diff --cached -M --stat`: `0
insertions(+), 0 deletions(-)`). 6 подтверждённых consumer'ов обновлены на
канонический путь, root-копий не осталось, wrapper'ы не потребовались.
`serp_parser.py` остаётся `DEFER`red (не перенесён) согласно диагностике —
затронута только его внутренняя строка импорта.
`supplier_discovery_v2/xmlriver_subprocess.py` подтверждён незатронутым.
Immutability guard мигрирован для обоих файлов в том же изменении — защита
ни разу не ослаблена.

## Цель, контекст и границы

- **Цель:** перенести SERP/web-lookup интеграции (`web_lookup.py`,
  `xmlriver_client.py`) в `backend/integrations/search/`, обновить только
  подтверждённые consumers, не менять парсинг/API-логику.
- **Контекст:** ветка `audit/frontend-knip-20260902`, продолжение серии
  bounded root refactor (Pass 7) по явной инструкции владельца «продолжи
  рефакторинг!» после отдельного CI-фикса (`почини`).
- **Ограничения:** без изменения XML-парсинга, форматов запросов,
  retry/pagination логики; без реальных сетевых вызовов к XMLRiver; только
  эти два файла плюс их known import-consumers.
- **Готово когда:** обе реализации под `backend/integrations/search/`, root
  отсутствует, все известные imports канонические, immutability guard
  мигрирован и доказан, целевые и regression тесты проходят, документация
  обновлена, валидаторы проходят.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] заблокирован (`TASK-LOCK-022`) перед стартом |
| Текущее содержимое обоих модулей | [CONFIRMED] прочитано целиком перед переносом |

## Свежая проверка ссылок (не только AST)

Полнотекстовый поиск по репозиторию (импорты и строковые/файловые
упоминания) нашёл 6 подтверждённых consumers:

- `supplier_app.py` — `from xmlriver_client import XmlRiverClient` /
  `from web_lookup import WebLookup`.
- `collect_inn.py` — lazy-импорты внутри `if args.web:`.
- `scripts/collect_contacts.py` — lazy-импорты, тот же паттерн.
- `test_extractor.py` — `from web_lookup import WebLookup`.
- `serp_parser.py` — `from xmlriver_client import XmlRiverClient,
  XmlRiverError` (строка 36); сам файл остаётся `DEFER`red по диагностике,
  правится только эта строка импорта — прецедент «beyond imports» уже
  установлен в предыдущих задачах.
- `test_parser.py` — `from xmlriver_client import XmlRiverClient,
  XmlRiverError, XmlRiverTemporaryError` (строка 12); один из 4 корневых
  `DEPRECATED_REVIEW`-тестов — не перенесён/переименован, правится только
  строка импорта.

**Отдельно проверено и подтверждено не затронутым:**
`supplier_discovery_v2/xmlriver_subprocess.py` резолвит
`self.parser_path = Path(__file__).resolve().parents[1] /
"serp_parser.py"` (нетронутый файл) и запускает его через
`subprocess.run(command, cwd=self.parser_path.parent, ...)` = корень
репозитория, поэтому обновлённый внутренний импорт `serp_parser.py`
резолвится штатно при таком способе запуска.

`supplier_discovery_v2/immutability_check.py` protected-paths: [CONFIRMED]
`xmlriver_client.py` и `web_lookup.py` были в плоском кортеже с самого
начала (в отличие от прецедента Checko/`FINDING-017`) — миграция guard'а
обязательна и выполнена в этом же изменении.

`docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`: [CONFIRMED]
проверены и обновлены.

## Перенос

- `backend/integrations/search/web_lookup.py` — [CONFIRMED] `git diff
  --cached -M --stat` показывает `0 insertions(+), 0 deletions(-)`.
- `backend/integrations/search/xmlriver_client.py` — [CONFIRMED] `git diff
  --cached -M --stat` показывает `0 insertions(+), 0 deletions(-)`.
- Корневые `web_lookup.py`/`xmlriver_client.py` — [CONFIRMED] удалены. Root
  wrapper не создан — единственные consumers внутренние, конкретного
  tracked/runtime контракта на внешний импорт не обнаружено.
- Обновлены строки импорта: `supplier_app.py`, `collect_inn.py` (lazy,
  ~строка 251-252), `scripts/collect_contacts.py` (lazy, ~строка 275-276),
  `test_extractor.py`, `serp_parser.py` (строка 36), `test_parser.py`
  (строка 12).

## Immutability guard migration

`supplier_discovery_v2/immutability_check.py`'s `protected_paths()`:
[CONFIRMED] `"xmlriver_client.py"` и `"web_lookup.py"` удалены из плоского
кортежа `for name in ("serp_parser.py", "supplier_app.py",
"contact_crawler.py", "collect_inn.py"):`; добавлен новый явный блок,
проверяющий `root / "backend" / "integrations" / "search" / name` для
`("web_lookup.py", "xmlriver_client.py")` — по точному прецеденту Checko и
supplier-identity блоков. Доказано двумя способами:

- Baseline round-trip на реальном дереве
  (`test_snapshot_matches_written_baseline`): `write_baseline` → `verify()
  == []`.
- Одноразовое synthetic tempfile-дерево
  (`test_disposable_mutation_of_search_integrations_modules_is_detected`):
  оба файла помечены как protected на новом пути, мутация каждого
  индивидуально обнаруживается по своему относительному пути; реальные
  файлы проекта никогда не мутировались.

`supplier_discovery_v2/tests/test_immutability.py` дополнен двумя тестами
по установленному паттерну (protection-at-new-path +
disposable-mutation-detection), `7/7 PASS`.

## Тесты

| Проверка | Результат |
|---|---|
| `python -m unittest supplier_discovery_v2.tests.test_immutability -v` | [CONFIRMED] `7/7 PASS` |
| `python test_extractor.py` | [CONFIRMED] "Все проверки пройдены", exit `0` |
| `python test_parser.py` | [CONFIRMED] "Все проверки пройдены", exit `0` |
| `python scripts/run_test_suite.py --suite full` | [CONFIRMED] `tests=462; failures=0; errors=9 (pre-existing pwsh gap); skipped=1` |
| `python -m unittest tests.test_enrichment_pipeline -v` | [CONFIRMED] `8/8 PASS` |
| `python -m unittest discover -s supplier_discovery_v2/tests -v` | [CONFIRMED] `18/18 PASS` |
| Provider/сетевые вызовы | [CONFIRMED] `0` |

## Import contract

| Проверка | Результат |
|---|---|
| `import backend.integrations.search.web_lookup` | [CONFIRMED] успешно |
| `import backend.integrations.search.xmlriver_client` | [CONFIRMED] успешно |
| `import serp_parser` | [CONFIRMED] успешно |
| `import collect_inn` | [CONFIRMED] успешно |
| `import supplier_app` | [CONFIRMED] успешно |
| `python collect_contacts.py --help` vs `python -m scripts.collect_contacts --help` | [CONFIRMED] exit `0` оба, вывод побайтово идентичен |
| `python collect_inn.py --help` | [CONFIRMED] exit `0` |
| `from api.index import handler, _APP` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная офлайн-цепочка |

## Валидация

| Проверка | Результат |
|---|---|
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS`, `tool_entries=40` |
| `git diff --cached --check` | [CONFIRMED] exit `0` |
| Сканирование staged diff на секреты | [CONFIRMED] совпадений не найдено |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `14` файлов:
`backend/integrations/search/__init__.py`,
`backend/integrations/search/web_lookup.py` (rename),
`backend/integrations/search/xmlriver_client.py` (rename),
`supplier_app.py`, `collect_inn.py`, `scripts/collect_contacts.py`,
`test_extractor.py`, `serp_parser.py`, `test_parser.py`,
`supplier_discovery_v2/immutability_check.py`,
`supplier_discovery_v2/tests/test_immutability.py`,
`docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`,
`ai/CURRENT_STATE.md` (+ `ai/ACTIVE_TASK.md` state-only). В пределах
ожидаемых 12-15 согласно причинно-связанной автономной политике владельца.

## Не проверено

- NOT VERIFIED: реальный Vercel build/deploy (не запускался; переиспользована
  структурная проверка `vercel.json` из предыдущих задач — `backend/**` не
  исключён).
- NOT VERIFIED: недокументированный внешний Python-импорт `web_lookup`/
  `xmlriver_client` за пределами репозитория.
- Отдельный, параллельный CI_INFRA fix (Windows Defender exclusions для
  `Backend Full`, commit `6af2af1`) верифицируется отдельным
  `workflow_dispatch` прогоном — его результат фиксируется отдельно и не
  является частью этой задачи.

## Публикация

Commit/push/CI зафиксированы в финальном отчёте ниже. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
