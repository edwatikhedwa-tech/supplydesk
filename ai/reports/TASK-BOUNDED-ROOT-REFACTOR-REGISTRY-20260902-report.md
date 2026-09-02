# TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902

`DELIVERY_MODE: PUBLISH`

## Итог

`BOUNDED_ROOT_REFACTOR: PARTIAL_BY_DESIGN` — [CONFIRMED] `dadata_client.py`
перенесён в `backend/integrations/registry/dadata_client.py`, единственный
известный consumer (`collect_inn.py`, lazy import) обновлён, поведение не
изменилось. `checko_client.py` **не перенесён**: свежая проверка ссылок
нашла операционный контракт вне заявленных границ задачи (см. ниже), и по
собственному разделу задачи "STOP that module and report" перенос этого
модуля приостановлен, а не выполнен молча.

## Цель, контекст и границы

- **Цель:** перенести `checko_client.py` и `dadata_client.py` в
  `backend/integrations/registry/`, обновить только подтверждённые consumers,
  не менять provider-семантику.
- **Контекст:** ветка `audit/frontend-knip-20260902`, preflight HEAD
  `4065242519bb55271d82f65198d27236a33915ba` (предыдущий verified
  `TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902`).
- **Ограничения:** без реальных Checko/DaData вызовов; без изменения
  бизнес-логики/HTTP semantics; не трогать `supplier_discovery_v2/` и
  остальные перечисленные в разделе 17 модули.
- **Готово когда:** оба клиента перенесены и проверены — **или** для модуля,
  где перенос небезопасен без выхода за объявленные границы, зафиксирован
  явный STOP с доказательствами, а второй модуль всё равно доведён до конца.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `4065242519bb55271d82f65198d27236a33915ba` |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] `IDLE` перед стартом |
| Текущее содержимое `checko_client.py`/`dadata_client.py` | [CONFIRMED] прочитано целиком |

## Свежая проверка ссылок (раздел 2)

`import`/`from` в `*.py`:

- `checko_client`: [CONFIRMED] `supplier_app.py:35`,
  `scripts/verify_enrichment_live.py:17`, `tests/test_enrichment_pipeline.py:9`
  — совпадает со списком из диагностики.
- `dadata_client`: [CONFIRMED] только `collect_inn.py:271` (lazy import внутри
  функции) — совпадает со списком из диагностики.
- `mock.patch`/`monkeypatch`/`importlib` на эти модули: [CONFIRMED] не найдено.

**Незапланированная находка:** [CONFIRMED]
`supplier_discovery_v2/immutability_check.py:16` жёстко прописывает
относительный путь `"checko_client.py"` в кортеже `protected_paths()` —
списке файлов, чей SHA-256 сравнивается с ранее записанным baseline
(`protected_manifest.json`, оператор-командой `--write-baseline`/verify из
`supplier_discovery_v2/README.md`). Диагностика `TASK-PYTHON-ROOT-DIAGNOSTIC-20260902`
эту зависимость не называла. `CLAUDE.md` (project layout) тоже прямо называет
`checko_client.py` примером намеренной корневой структуры.

Текущий checkout не содержит закоммиченного/трекаемого
`protected_manifest.json` (не в Git, не в истории), поэтому сейчас ничего не
падает. Но:

1. `protected_paths()` включает кандидата только через `.is_file()` —
   перенос молча убрал бы `checko_client.py` из будущего
   `--write-baseline` снапшота без предупреждения;
2. любой уже существующий вне этого checkout baseline, где
   `checko_client.py` учтён, после переноса вернёт
   `protected_files_changed=checko_client.py` при `verify()` — сравнение
   `expected.get(name) != actual.get(name)` даёт несовпадение, когда ключ
   пропадает из фактического снапшота.

Обновление `immutability_check.py` для этого — правка внутри
`supplier_discovery_v2/`, а этот каталог прямо в разделе 17 задачи помечен
`DO NOT TOUCH`. Поэтому по разделу 2 этой же задачи ("STOP that module and
report") перенос `checko_client.py` приостановлен, а не выполнен обходом
объявленной границы. Записано как
[`FINDING-017`](../DEFERRED_FINDINGS.md#finding-017--checkoclientpy-move-blocked-by-an-immutability-protected-path-list)
в `ai/DEFERRED_FINDINGS.md`.

## Перенос `dadata_client.py`

- Создан пакет `backend/__init__.py`, `backend/integrations/__init__.py`,
  `backend/integrations/registry/__init__.py` — только эти три файла, без
  generic `utils/`/`services/`.
- `backend/integrations/registry/dadata_client.py` — [CONFIRMED] байт-в-байт
  идентичен прежнему содержимому (Git распознал перенос как чистый `rename`,
  `0` изменённых строк в самом файле); импорт `from inn_extractor import
  InnHit` не тронут, `inn_extractor.py` остаётся в корне.
- Корневой `dadata_client.py` — [CONFIRMED] удалён. Root compatibility
  wrapper не создан: единственный consumer — внутренний lazy import в
  `collect_inn.py`, подтверждённого внешнего/операционного контракта на
  `import dadata_client` не найдено (раздел 7).
- `collect_inn.py:271` — [CONFIRMED] обновлён:
  `from dadata_client import DadataClient` →
  `from backend.integrations.registry.dadata_client import DadataClient`.
  Только строка импорта; остальная реализация `collect_inn.py` не тронута.

## Startup / import contract (раздел 10)

| Проверка | Результат |
|---|---|
| `import backend.integrations.registry.dadata_client` | [CONFIRMED] успешно, `DadataClient` доступен |
| `import collect_inn` | [CONFIRMED] успешно |
| `import supplier_app` | [CONFIRMED] успешно |
| `from api.index import handler, _APP` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная цепочка `api.index → supplier_app → collect_inn → (lazy) backend.integrations.registry.dadata_client` разрешается офлайн, без реальных provider-вызовов |
| `DadataClient("fake-token-for-import-test")` | [CONFIRMED] конструируется без сетевого вызова |

## Serverless / deployment boundary (раздел 11)

`SERVERLESS_PACKAGE_COMPATIBILITY: STRUCTURALLY_CONFIRMED` для части
"`backend/**` не исключён `vercel.json`": [CONFIRMED] `excludeFiles` в
`functions."api/**/*.py"` перечисляет `.env*, .git/**, _archive/**,
frontend/node_modules/**, frontend/src/**, artifacts/**, cache/**, tests/**,
Documents/**, *.png, *.zip, *.rar, *.db, *.sqlite3, mail-data/**` — ни один
паттерн не задевает `backend/`; `git check-ignore` на новые файлы `backend/`
вернул "не игнорируется". `vercel.json`/`api/index.py` не менялись (не
потребовалось).

Часть "трассирует ли билдер Vercel лениво-импортируемый модуль внутри
функции" — `NOT_VERIFIED`: это не проверяется локально без реального Vercel
build/deploy, и это не новый риск от переноса — `dadata_client` был
lazy-import'ом (`DADATA_TOKEN`-gated, внутри функции) уже до переноса, при
прежнем корневом пути. Перенос не ухудшил и не улучшил трассируемость этого
конкретного импорта.

## Regression Test Policy (раздел 13)

Существующие тесты (`tests/test_enrichment_pipeline.py`) не упоминают
`DadataClient`/`dadata` вовсе — покрытия не было ни до, ни после переноса.
`REGRESSION_TEST_ADDED: YES` —
[`tests/diagnostics/test_registry_integration_move.py`](../../tests/diagnostics/test_registry_integration_move.py)
(3 теста): модуль импортируется по новому пути, старый корневой файл
отсутствует, `collect_inn.py` больше не содержит устаревшую строку импорта.
Это не «тест на факт переноса ради теста» — единственный путь вызова
`DadataClient` гейтится `DADATA_TOKEN` и никогда не срабатывает в офлайн
suite, поэтому именно этот тест — единственная защита от молчаливого дрейфа
пути импорта.

## Валидация

| Проверка | Результат |
|---|---|
| `python -m unittest tests.diagnostics.test_registry_integration_move -v` | [CONFIRMED] `3/3 passed` |
| `python -m unittest tests.test_enrichment_pipeline -v` | [CONFIRMED] `8/8 passed` |
| `python -m unittest supplier_discovery_v2.tests.test_immutability -v` | [CONFIRMED] `1/1 passed` — самогенерируемый baseline остаётся самосогласованным независимо от текущего списка файлов |
| `python -m unittest discover -s tests/diagnostics -v` | `LOCAL_DIAGNOSTICS_PASSED: 52`, `LOCAL_DIAGNOSTICS_ERRORS: 9`, `LOCAL_DIAGNOSTICS_STATUS: PARTIAL_ENVIRONMENT` |
| Причина 9 ошибок | [CONFIRMED] `test_change_classifier.py` — отсутствие `pwsh` в PATH этой среды; уже доказано однократно в `TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902` через `git stash` на немодифицированном дереве того же файла; не связано с этой задачей, повторно не расследовалось (раздел 15) |
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS`, `tool_entries=40` |
| `git diff --check` | [CONFIRMED] exit `0` |
| `git check-ignore` на новые `backend/**` файлы | [CONFIRMED] не игнорируются |
| Сканирование staged diff на секреты | [CONFIRMED] только имена переменных (`DADATA_TOKEN`, `self.token`) и код, значений нет |
| Внешние provider-вызовы | [CONFIRMED] `0` |

## Change Budget (раздел 16)

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `9` файлов:
`backend/__init__.py`, `backend/integrations/__init__.py`,
`backend/integrations/registry/__init__.py`,
`backend/integrations/registry/dadata_client.py` (rename),
`dadata_client.py` (удалён), `collect_inn.py` (1 строка),
`tests/diagnostics/test_registry_integration_move.py`,
`docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`. Ни один
несвязанный модуль не тронут; `checko_client.py` и весь список раздела 17
(включая `supplier_discovery_v2/`) не изменялись.

## Не проверено

- NOT VERIFIED: реальный Vercel build/deploy трассировки lazy-import (см.
  выше) — не новый риск, унаследован от прежнего состояния.
- NOT VERIFIED: недокументированный внешний Python-импорт `dadata_client` за
  пределами репозитория.
- `checko_client.py` не перенесён — решение задокументировано как
  `FINDING-017`, не как невыполненная часть плана; требует отдельной задачи,
  которая одновременно затронет `checko_client.py` и
  `supplier_discovery_v2/immutability_check.py`.

## Публикация

Commit/push/CI зафиксированы в финальном отчёте ниже. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
