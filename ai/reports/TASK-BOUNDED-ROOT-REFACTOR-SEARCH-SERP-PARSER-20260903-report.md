# TASK-BOUNDED-ROOT-REFACTOR-SEARCH-SERP-PARSER-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`SERP_PARSER_MOVE: COMPLETE` — [CONFIRMED] `serp_parser.py` перенесён в
`backend/integrations/search/serp_parser.py`. Тонкая корневая
CLI-совместимая обёртка (`serp_parser.py`, делегирует только `main()`, по
образцу `collect_contacts.py`) сохраняет документированный вызов `python
serp_parser.py ...` — доказано побайтовым совпадением `--help` с версией до
переноса. Жёстко прошитый subprocess-путь в
`supplier_discovery_v2/xmlriver_subprocess.py` обновлён на канонический.
Собственный вызов `load_dotenv()` внутри перенесённого модуля исправлен на
`REPO_ROOT`-относительный (иначе молча сломался бы на новом вложенном
пути) — по точно проверенному прецеденту `collect_contacts.py` из Pass 2.
7 подтверждённых consumers обновлены. Immutability guard мигрирован.

## Цель, контекст и границы

- **Цель:** выполнить явное решение владельца — перенести `serp_parser.py`
  сейчас, а не оставлять `DEFER`red, обновив жёстко прошитый subprocess-путь
  и подтверждённых consumers.
- **Контекст:** ветка `claude/zen-goldwasser-022bb1`, Pass 10 серии bounded
  root refactor. Диагностика
  (`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`) явно
  пометила этот файл как `DEFER` из-за конфликта с изоляцией
  `supplier_discovery_v2` (жёстко прошитый subprocess-путь) и
  deployment-путём Vercel — предыдущие агенты сознательно оставили это
  владельцу. Владельцу заданы 2 вопроса через `AskUserQuestion`: (1) что
  делать с `serp_parser.py` — ответ «Перенести сейчас»; (2) что делать с
  корневыми `test_*.py` — ответ «Превратить в unittest» (отдельная задача,
  не выполняется в этом изменении).
- **Ограничения:** без изменения XML-парсинга, форматов запроса,
  дедупликации, retry-логики; без реальных сетевых вызовов к XMLRiver;
  только этот файл, его известные consumers и жёстко прошитый subprocess-
  путь.
- **Готово когда:** реализация под `backend/integrations/search/
  serp_parser.py`, корневая обёртка сохраняет CLI-контракт побайтово,
  `xmlriver_subprocess.py` резолвит новый путь, все известные imports
  канонические, immutability guard мигрирован и доказан, целевые и
  regression тесты проходят, документация обновлена.

## Свежая проверка ссылок (не только AST)

Полнотекстовый поиск по репозиторию для `from serp_parser import` /
`import serp_parser` нашёл 7 реальных Python-consumers (сам
`serp_parser.py` содержит переиспользуемые утилиты `host_of`, `read_lines`,
`load_dotenv`, `root_domain_of`, `build_query`, `default_out_path`, не
только CLI-класс `SerpCollector` — это существенно шире, чем у переносов
Pass 3-8):

- `supplier_app.py:30` — `SerpCollector, read_lines`;
- `collect_inn.py:38` — `host_of, load_dotenv, read_lines`;
- `scripts/collect_contacts.py:30` — `host_of, load_dotenv, read_lines`
  (свой независимый `REPO_ROOT`-based `.env` вызов не затронут — он уже не
  зависел от `serp_parser.py`'s внутреннего `load_dotenv` расположения);
- `benchmarks/benchmark_models.py:38` — `host_of, load_dotenv`;
- `backend/integrations/search/web_lookup.py:25` — `host_of`;
- `backend/domain/supplier_identity/email_extractor.py:271` — lazy-импорт
  `root_domain_of` (уже отмечен диагностикой как «direction smell», не
  устранён этой задачей — вне её границ);
- `test_parser.py:13` — `SerpCollector, build_query, host_of,
  root_domain_of, default_out_path` (один из 4 корневых
  `DEPRECATED_REVIEW`-тестов, который владелец решил конвертировать в
  unittest отдельной задачей — здесь правится только строка импорта).

Проверено и подтверждено: строковое упоминание «serp_parser» в docstring
`backend/integrations/search/xmlriver_client.py:6` — не путь, не импорт, не
требует правки (модуль по-прежнему называется `serp_parser.py`, изменилось
только его расположение).

`vercel.json`: [CONFIRMED] structural check — `functions.excludeFiles` не
исключает `backend/**`; новый путь `backend/integrations/search/
serp_parser.py` попадает в deployment bundle так же, как уже перенесённые
`web_lookup.py`/`xmlriver_client.py` из Pass 7.

## Собственный `.env`-контракт модуля — найденный и исправленный риск

`serp_parser.py`'s `main()` вызывал `load_dotenv(Path(__file__).with_name(".env"))`
— поиск `.env` РЯДОМ СО СКРИПТОМ. На корневом расположении это резолвилось
в `<repo_root>/.env`. После переноса в
`backend/integrations/search/serp_parser.py` это молча начало бы искать
`backend/integrations/search/.env` — несуществующий путь, что привело бы к
тихой потере доступов `XMLRIVER_USER`/`XMLRIVER_KEY` из корневого `.env`
при прямом запуске модуля не через обёртку. Это именно тот
deployment/path-риск, который диагностика предвидела для этого файла.

Исправлено по уже проверенному прецеденту `scripts/collect_contacts.py`
(Pass 2): добавлен `REPO_ROOT = Path(__file__).resolve().parents[3]` и
вызов заменён на `load_dotenv(REPO_ROOT / ".env")`. Проверено
программно: `REPO_ROOT` резолвится ровно в корень репозитория (`==
Path.cwd().resolve()` в тестовом окружении).

## Перенос

- `backend/integrations/search/serp_parser.py` — [CONFIRMED] перенесён
  через `git mv`; единственные правки по существу — новая константа
  `REPO_ROOT` и один изменённый вызов `load_dotenv`; парсинг, дедупликация,
  CLI-аргументы, вывод не менялись.
- Корневой `serp_parser.py` — [CONFIRMED] заменён на тонкую обёртку (11
  строк), делегирующую `main()` из канонического модуля — байт-в-байт
  структура как у `collect_contacts.py`'s wrapper.
- `supplier_discovery_v2/xmlriver_subprocess.py:18` — default `parser_path`
  обновлён на `Path(__file__).resolve().parents[1] / "backend" /
  "integrations" / "search" / "serp_parser.py"`. Явный `parser_path`,
  переданный вызывающим кодом (если есть), не затронут — параметр
  `parser_path` конструктора не менялся.
- Обновлены строки импорта: `supplier_app.py`, `collect_inn.py`,
  `scripts/collect_contacts.py`, `benchmarks/benchmark_models.py`,
  `backend/integrations/search/web_lookup.py`,
  `backend/domain/supplier_identity/email_extractor.py` (lazy),
  `test_parser.py`.

## Immutability guard migration

`supplier_discovery_v2/immutability_check.py`'s `protected_paths()`:
[CONFIRMED] `"serp_parser.py"` удалён из плоского кортежа
`for name in ("supplier_app.py", "collect_inn.py"):`; добавлен новый явный
блок, проверяющий `root / "backend" / "integrations" / "search" /
"serp_parser.py"`. Корневая CLI-обёртка сознательно НЕ добавлена в
защищённый список — она не несёт логики для дрейфа, по тому же принципу,
что и обёртки `collect_contacts.py`/`benchmark_models.py`. Доказано:

- Baseline round-trip на реальном дереве
  (`test_snapshot_matches_written_baseline`): `write_baseline` → `verify()
  == []`.
- Одноразовое synthetic tempfile-дерево
  (`test_disposable_mutation_of_serp_parser_is_detected`): файл помечен как
  protected на новом пути, мутация обнаруживается; реальный файл проекта
  никогда не мутировался.

`supplier_discovery_v2/tests/test_immutability.py`: `26/26 PASS` (полный
файл, включая 2 новых теста).

## Тесты

| Проверка | Результат |
|---|---|
| `python -m unittest tests.test_enrichment_pipeline tests.diagnostics.test_collect_inn_llm_path supplier_discovery_v2.tests.test_immutability -v` | [CONFIRMED] `24/24 PASS` |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=468; failures=0; errors=9 (те же pre-existing pwsh-gap); skipped=1` |
| `python test_parser.py` | [CONFIRMED] "Все проверки пройдены", exit `0` |
| `python test_extractor.py` | [CONFIRMED] "Все проверки пройдены", exit `0` |
| `XmlRiverSubprocess(output_dir=...).parser_path.is_file()` | [CONFIRMED] `True` — резолвится в перенесённый файл |
| `serp_parser.py --help` vs `python -m backend.integrations.search.serp_parser --help` | [CONFIRMED] побайтово идентичны |
| `serp_parser.py --help` (после переноса) vs то же (коммит перед этой задачей) | [CONFIRMED] побайтово идентичны |
| Provider/сетевые вызовы | [CONFIRMED] `0` |

## Import contract

| Проверка | Результат |
|---|---|
| `import backend.integrations.search.serp_parser` | [CONFIRMED] успешно, `REPO_ROOT` разрешён верно |
| `import serp_parser` (корневая обёртка) | [CONFIRMED] `root_wrapper.main is canonical.main` — `True` |
| `import supplier_app` | [CONFIRMED] успешно |
| `import collect_inn` | [CONFIRMED] успешно |
| `import benchmarks.benchmark_models` | [CONFIRMED] успешно |
| `import scripts.collect_contacts` | [CONFIRMED] успешно |
| `import backend.integrations.search.web_lookup` | [CONFIRMED] успешно |
| `email_extractor.root_domain("spb.metall.ru")` | [CONFIRMED] `"metall.ru"` — та же логика через новый путь |
| `import supplier_discovery_v2.xmlriver_subprocess` | [CONFIRMED] успешно |
| `from api.index import handler` под `SUPPLYDESK_ENV=test` | [CONFIRMED] успешно — полная офлайн-цепочка |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `14` файлов:
`backend/integrations/search/serp_parser.py` (rename + `REPO_ROOT` fix),
`serp_parser.py` (new thin wrapper), `supplier_discovery_v2/xmlriver_subprocess.py`,
`supplier_app.py`, `collect_inn.py`, `scripts/collect_contacts.py`,
`benchmarks/benchmark_models.py`,
`backend/integrations/search/web_lookup.py`,
`backend/domain/supplier_identity/email_extractor.py`, `test_parser.py`,
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
- NOT VERIFIED: недокументированный внешний Python-импорт `serp_parser` за
  пределами репозитория.
- NOT VERIFIED: реальный сетевой вызов к XMLRiver из перенесённого модуля
  (не требовался этой задачей — `--dry-run` и офлайн-тесты покрывают
  построение запроса/URL без сети).

## Оставшийся объём root-рефакторинга (не выполнено в этой задаче)

- Корневые `test_*.py` (`test_extractor.py`, `test_inn.py`, `test_parser.py`,
  `test_verify.py`) — владелец решил конвертировать в реальные
  `unittest.TestCase`, включить в официальный раннер. Требует отдельной
  bounded-задачи: выбрать назначение (`tests/` напрямую или
  `tests/legacy/`), убедиться, что содержательные проверки не теряются при
  конвертации, подтвердить discovery в `scripts/run_test_suite.py`.
- `supplier_app.py`/`api/index.py` — `KEEP_ROOT`, защищённые entrypoints, не
  переносятся.

## Публикация

Commit/push/CI зафиксированы в финальном ответе агента. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
