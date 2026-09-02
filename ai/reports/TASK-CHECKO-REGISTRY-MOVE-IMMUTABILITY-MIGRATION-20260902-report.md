# TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902

`DELIVERY_MODE: PUBLISH`

## Итог

`CHECKO_MOVE: COMPLETE` — [CONFIRMED] `checko_client.py` перенесён в
`backend/integrations/registry/checko_client.py`, все 3 известных consumer
обновлены, поведение не изменилось. Одновременно и минимально обновлён
`supplier_discovery_v2/immutability_check.py`: защита переехала на новый
канонический путь, ни на миг не ослабев. `FINDING-017` закрыт с
доказательствами.

## Цель, контекст и границы

- **Цель:** завершить перенос `checko_client.py`, начатый и приостановленный
  в `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902`, одновременно перенеся
  защиту immutability-guard на новый путь в том же изменении.
- **Контекст:** ветка `audit/frontend-knip-20260902`, preflight HEAD
  `e8ba5b637b163d38d8d4313f4865f1c4a571e2d3`.
- **Ограничения:** без изменения Checko provider-логики; без изменения
  product-логики `supplier_discovery_v2/` за пределами
  `immutability_check.py` и его теста; без реальных provider-вызовов.
- **Готово когда:** новый канонический путь защищён, старый путь не
  протежируется, свежий baseline/verify раунд-трип проходит, disposable-копия
  мутации обнаруживается, все известные consumers обновлены, `FINDING-017`
  закрыт.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `e8ba5b637b163d38d8d4313f4865f1c4a571e2d3` |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] `IDLE` перед стартом |
| Текущее содержимое `checko_client.py` | [CONFIRMED] прочитано целиком, не изменилось со времени прошлой задачи |

## Свежая проверка ссылок

- Импортёры кода: [CONFIRMED] ровно те же три, что ожидалось —
  `supplier_app.py:35`, `scripts/verify_enrichment_live.py:17`,
  `tests/test_enrichment_pipeline.py:9`.
- `supplier_discovery_v2/immutability_check.py:16` — [CONFIRMED] единственная
  path-sensitive зависимость, как и задокументировано в `FINDING-017`.
- `mock.patch`/строковые dotted-path патчи на `checko_client`: [CONFIRMED] не
  найдено. Найден `patch.object(supplier_app, "CheckoClient",
  return_value=fake_checko)` в `tests/test_dashboard.py:264` — патчит атрибут
  `CheckoClient` на уже импортированном объекте модуля `supplier_app`, не
  строковый dotted-path `checko_client...`; после смены строки импорта в
  `supplier_app.py` этот патч продолжает работать без изменений (подтверждено
  прогоном `tests/test_dashboard.py`, `13/13 PASS`, включая
  `test_manual_inn_refreshes_checko_facts_when_key_is_available`).
- `CLAUDE.md`, `docs/architecture/REPOSITORY_LAYOUT.md`, `FINDING-017`:
  [CONFIRMED] прочитаны, обновлены только устаревшие утверждения о
  расположении.

## Перенос `checko_client.py`

- `backend/integrations/registry/checko_client.py` — [CONFIRMED] байт-в-байт
  идентичен прежнему файлу; Git распознал перенос как чистый `rename` (`0`
  изменённых строк в самом файле).
- Корневой `checko_client.py` — [CONFIRMED] удалён. Root wrapper не создан —
  единственные consumers внутренние, конкретного tracked/runtime контракта на
  внешний импорт не обнаружено.
- Обновлены строки импорта: `supplier_app.py:35`,
  `scripts/verify_enrichment_live.py:17` (уже содержал явный `sys.path`
  bootstrap для запуска как самостоятельного скрипта из `scripts/` — не
  тронут, кроме самой строки импорта), `tests/test_enrichment_pipeline.py:9`.
  Больше нигде в реализации ничего не менялось: провайдерская логика
  (`BASE_URL`, endpoints, key rotation, quota handling, timeout/delay, кэш,
  `Company`/`Finances`, `classify_okved`, разбор finance-истории,
  классификация ошибок, имена переменных окружения) идентична исходному
  файлу — проверено побайтовым сравнением через `git diff` (rename, `0`
  строк).

## Immutability guard migration (раздел 6)

`supplier_discovery_v2/immutability_check.py` изменён минимально:
`"checko_client.py"` убран из плоского кортежа `protected_paths()` (где он
проверялся как `root / name`), и добавлена отдельная явная проверка нового
пути — тот же паттерн, что уже использовался для `mail/repository.py`:

```python
checko_client = root / "backend" / "integrations" / "registry" / "checko_client.py"
if checko_client.is_file():
    paths.append(checko_client)
```

Ничего другого в файле не тронуто: `_sha256`, `snapshot`, `write_baseline`,
`verify`, `main` и защита остальных 9 файлов + `mail/repository.py` +
`migrations/*.sql` — без изменений. Семантика защиты не ослаблена и не
переосмыслена — только путь одного файла.

## Baseline semantics (раздел 7) — контракт доказан без изменения реального файла

Выполнено ровно по контракту, с временными путями (`tempfile.TemporaryDirectory`),
без коммита сгенерированных baseline-файлов:

1. **Свежий baseline против неизменённого нового дерева → PASS.**
   [CONFIRMED] `write_baseline(REPO_ROOT, tmp_manifest)` затем
   `verify(REPO_ROOT, tmp_manifest)` вернул `[]` (пусто — ничего не
   изменилось) на реальном перенесённом дереве. `protected_paths(REPO_ROOT)`
   содержит `backend/integrations/registry/checko_client.py` и НЕ содержит
   `checko_client.py` — оба факта подтверждены напрямую.
2. **Мутация disposable-копии на новом каноническом пути → обнаружена.**
   [CONFIRMED] Синтетическое дерево создано только в `tempfile` (не копия
   реального файла, не сам проект): файл-заглушка
   `<tmp>/synthetic_root/backend/integrations/registry/checko_client.py`,
   baseline снят, `verify()` → `[]`; после изменения содержимого файла-
   заглушки `verify()` → `['backend/integrations/registry/checko_client.py']`.
   Реальный файл проекта не менялся ни разу.

Оба прогона выполнены вручную перед записью постоянного теста, затем
закреплены как permanent regression test (раздел 8).

## Immutability regression test (раздел 8)

Обновлён `supplier_discovery_v2/tests/test_immutability.py` (переиспользован,
не создан новый harness) — добавлено 2 теста к существующему:

- `test_checko_client_is_protected_at_its_new_canonical_path` —
  `protected_paths(root)` содержит новый путь и не содержит старый корневой.
- `test_disposable_mutation_of_checko_client_is_detected` — синтетический
  tmp-каталог, baseline/verify round-trip, мутация обнаруживается.

`3/3 PASS` (включая уже существовавший `test_snapshot_matches_written_baseline`,
не изменённый).

## Supplier Discovery v2 product logic (раздел 9)

`SUPPLIER_DISCOVERY_V2_PRODUCT_LOGIC_CHANGED: NO` — [CONFIRMED] изменения
ограничены `immutability_check.py:protected_paths()` (1 путь) и его тестом.
`pipeline.py`, `contacts.py`, `matching.py`, `query_planner.py`,
`connectors/`, `direct_site.py`, `xmlriver_subprocess.py`, `storage.py`,
`run.py` не тронуты. Полный набор `supplier_discovery_v2/tests/` (14 тестов:
matching, pipeline_fixture, query_planner, storage, immutability) прошёл
`14/14 PASS`.

## Serverless / startup import contract (раздел 10)

| Проверка | Результат |
|---|---|
| `import backend.integrations.registry.checko_client` | [CONFIRMED] успешно, `CheckoClient`/`Company`/`Finances` доступны |
| `import supplier_app` | [CONFIRMED] успешно |
| `from api.index import handler, _APP` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная офлайн-цепочка `api.index → supplier_app → backend.integrations.registry.checko_client` |
| `python scripts/verify_enrichment_live.py --help` | [CONFIRMED] exit `0`, без сети |

`backend/**` уже подтверждён структурно не исключённым `vercel.json`
(доказательство переиспользовано из `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902`,
`vercel.json`/`api/index.py` не менялись в этой задаче — Vercel не
переаудирован заново).

## Тесты (раздел 11)

| Проверка | Результат |
|---|---|
| `tests.test_enrichment_pipeline` | [CONFIRMED] `8/8 PASS` |
| `tests.test_dashboard` | [CONFIRMED] `13/13 PASS` (включает checko `patch.object` мок) |
| `supplier_discovery_v2.tests.test_immutability` | [CONFIRMED] `3/3 PASS` |
| `supplier_discovery_v2` полный набор | [CONFIRMED] `14/14 PASS` |
| `python -m unittest discover -s tests/diagnostics -v` | `LOCAL_DIAGNOSTICS_PASSED: 52`, `LOCAL_DIAGNOSTICS_ERRORS: 9`, `LOCAL_DIAGNOSTICS_STATUS: PARTIAL_ENVIRONMENT` — те же 9 ошибок `test_change_classifier.py` (`pwsh` недоступен в PATH), уже доказано ранее не связанными с изменениями кода; повторно не расследовалось |
| Checko API вызовы | [CONFIRMED] `0` |
| DaData/XMLRiver/RouterAI/SMTP/IMAP/crawler вызовы | [CONFIRMED] `0` |

## FINDING-017 closeout (раздел 12)

[CONFIRMED] Все условия выполнены: перенос выполнен, новый путь защищён,
self-test проходит, свежий baseline round-trip PASS, disposable-мутация
обнаруживается. `FINDING-017` помечен `Status: RESOLVED` в
`ai/DEFERRED_FINDINGS.md` — не удалён и не переписан, запись сохранена с
добавленными полями `Resolution`/`Resolution report`, по тому же формату,
что уже используется в этом файле для `FINDING-006` (`Status: SUPERSEDED`).
Существующая история (`ai/history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md`,
`status: HISTORICAL`) не редактировалась — это заморённый снапшот вне
объявленного scope этой задачи; ротация в chronicle остаётся отдельной
задачей документационного governance.

## Документация (раздел 13)

- `docs/architecture/REPOSITORY_LAYOUT.md` — [CONFIRMED] обновлено: Checko
  убран из "root composition entrypoints", добавлен в
  `backend/integrations/registry/`; секция "Moves in progress" отражает
  завершение обеих задач вместо "не перенесён".
- `CLAUDE.md` — [CONFIRMED] обновлено: строка `backend/integrations/registry/`
  теперь называет оба адаптера без "pending a separate task"; пример
  `checko_client.py` убран из списка примеров всё ещё-корневых файлов
  (instruction compaction — заменена формулировка, а не добавлен новый
  абзац).

## Валидация

| Проверка | Результат |
|---|---|
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS`, `tool_entries=40` |
| `git diff --check` | [CONFIRMED] exit `0` |
| Сканирование staged diff на секреты | [CONFIRMED] только `CHECKO_KEY`/`self.key`/`self.keys` — код и имена переменных, значений нет |
| Проверенный perimeter (раздел 19 "DO NOT TOUCH") | [CONFIRMED] `dadata_client.py`, `contact_crawler.py`, `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `verify.py`, `llm_fallback.py`, `routerai_client.py`, `web_lookup.py`, `xmlriver_client.py`, `serp_parser.py`, `api/index.py`, `mail/`, `migrations/`, `frontend/`, корневые `test_*.py` — не изменялись (проверено по итоговому `git status`) |

## Change Budget (раздел 18)

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `9` файлов:
`checko_client.py` (удалён), `backend/integrations/registry/checko_client.py`
(rename), `supplier_app.py` (1 строка), `scripts/verify_enrichment_live.py`
(1 строка), `tests/test_enrichment_pipeline.py` (1 строка),
`supplier_discovery_v2/immutability_check.py` (protected_paths),
`supplier_discovery_v2/tests/test_immutability.py` (+2 теста), `CLAUDE.md`,
`docs/architecture/REPOSITORY_LAYOUT.md`. В пределах ожидаемых 8–10.

## Не проверено

- NOT VERIFIED: реальный Vercel build/deploy (не запускался; структурная
  проверка `vercel.json` переиспользована из прошлой задачи и не менялась).
- NOT VERIFIED: недокументированный внешний Python-импорт `checko_client` за
  пределами репозитория.

## Публикация

Commit/push/CI зафиксированы в финальном отчёте ниже. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
