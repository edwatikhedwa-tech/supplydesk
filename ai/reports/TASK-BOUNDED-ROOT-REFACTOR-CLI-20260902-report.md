# TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902

`DELIVERY_MODE: PUBLISH`

## Итог

`BOUNDED_ROOT_REFACTOR: COMPLETE` — [CONFIRMED] реализация двух standalone
CLI (`collect_contacts.py`, `benchmark_models.py`) перенесена в семантически
правильные области (`scripts/`, `benchmarks/`) по решению
[`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`](TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md).
Корневые команды сохранены тонкими compatibility wrapper'ами. Остальные
12+ runtime-модулей не тронуты; `supplier_app.py`, `api/index.py`,
`serp_parser.py`, `mail/`, `migrations/`, `supplier_discovery_v2/`, root
`test_*.py` и frontend не изменялись.

## Цель, контекст и границы

- **Цель:** первый маленький bounded implementation batch после диагностики —
  перенос двух подтверждённых `MOVE_SCRIPTS` кандидатов с сохранением CLI
  и `.env`-совместимости.
- **Контекст:** ветка `audit/frontend-knip-20260902`, preflight HEAD
  `d7fa86d2456bd7f59a7a6d055acfc6d20a96bbd5`.
- **Ограничения:** только эти два файла; никаких live provider вызовов,
  никакой canonical database, никакого real mail; scope закрыт по
  диагностическому отчёту.
- **Готово когда:** одна каноническая реализация каждого CLI, оба старых и оба
  новых вызова работают идентично, `.env`-lookup и относительные
  `results/`/`cache/` пути не изменили поведение, focused-проверки прошли и
  публикация подтверждена.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `WORKSPACE_GUARD: PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `d7fa86d2456bd7f59a7a6d055acfc6d20a96bbd5` |
| Рабочее дерево до lock | [CONFIRMED] чистое |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] `IDLE` перед стартом |
| Свежая проверка ссылок | [CONFIRMED] `rg`/`grep` по репозиторию не нашёл Python-импортов `collect_contacts`/`benchmark_models` за пределами их собственных файлов, diagnostic report и state-файлов |
| Текущее содержимое файлов | [CONFIRMED] прочитано целиком перед переносом; сопоставлено с diagnostic report |

## Перенос реализации

- `scripts/collect_contacts.py` — [CONFIRMED] единственная реализация
  operator contact-collection CLI; идентична исходной логике, изменён только
  расчёт корня репозитория для `.env` и текст одного сообщения об ошибке
  (упоминание пути к `.env`).
- `benchmarks/benchmark_models.py` — [CONFIRMED] единственная реализация
  model benchmark CLI; идентична исходной логике, изменён только расчёт
  корня репозитория для `.env` и примеры канонической команды в docstring.
- Корневые `collect_contacts.py` и `benchmark_models.py` — [CONFIRMED] тонкие
  compatibility wrapper'ы (`from scripts.collect_contacts import main` /
  `from benchmarks.benchmark_models import main`, `sys.exit(main())`); бизнес-
  логики не содержат.
- Импортируемые root-модули (`contact_crawler.py`, `email_extractor.py`,
  `inn_extractor.py`, `collect_inn.py`, `serp_parser.py`, `llm_fallback.py`,
  `routerai_client.py`, `web_lookup.py`, `xmlriver_client.py`, `verify.py`) —
  [CONFIRMED] не перемещены и не переименованы.
- `sys.path`-хаки — [CONFIRMED] не потребовались: оба обязательных вызова
  (`python collect_contacts.py ...` и `python -m scripts.collect_contacts ...`,
  аналогично для benchmark) выполняются из корня репозитория, где Python уже
  добавляет корень в `sys.path[0]`.

## ENV_LOOKUP_ROOT_PRESERVED

`ENV_LOOKUP_ROOT_PRESERVED: YES` — [CONFIRMED] структурно, без вывода
содержимого `.env`:

```
scripts.collect_contacts.REPO_ROOT == benchmarks.benchmark_models.REPO_ROOT
    == os.getcwd() == C:\Users\edwat\SupplyDesk
```

`REPO_ROOT = Path(__file__).resolve().parents[1]` — тот же приём, что уже
используется в `scripts/run_test_suite.py:22`. `.env` резолвится в
`REPO_ROOT / ".env"`, то есть в корень репозитория, как и раньше через
`Path(__file__).with_name(".env")` на прежнем месте. Значения `.env` не
читались и не выводились.

## RELATIVE_PATH_BEHAVIOR_PRESERVED

`RELATIVE_PATH_BEHAVIOR_PRESERVED: YES` — [CONFIRMED] `results/` (default
`--out-dir`), `cache/pages`, `cache/ground_truth.json` и `--from-serp`
остались относительными `Path(...)` без привязки к `__file__`; они
по-прежнему резолвятся относительно текущего рабочего каталога процесса, а
не относительно нового расположения модуля. Оба обязательных вызова
выполняются из корня репозитория, поэтому эффективные пути не изменились.
Данные `cache/`/`results/` не перемещались и не создавались.

## Focused Acceptance

| Проверка | Результат |
|---|---|
| `python collect_contacts.py --help` | [CONFIRMED] exit `0` |
| `python -m scripts.collect_contacts --help` | [CONFIRMED] exit `0`; вывод идентичен старому (`diff` без различий) |
| `python benchmark_models.py --help` | [CONFIRMED] exit `0` |
| `python -m benchmarks.benchmark_models --help` | [CONFIRMED] exit `0`; вывод идентичен старому (`diff` без различий) |
| Важные опции сохранены | [CONFIRMED] `--from-serp/--max-pages/--workers/--web/--llm/--verify/--out-dir` (16 вхождений) и `--prepare/--run/--models/--limit/--workers/--max-pages` (12 вхождений) присутствуют в новом help |
| Импорт без ошибок | [CONFIRMED] `importlib.import_module` для `scripts.collect_contacts` и `benchmarks.benchmark_models` прошёл без исключений |
| Exit code без аргументов | [CONFIRMED] старый и новый `collect_contacts` вызов без аргументов оба возвращают exit `1` (ожидаемый `SystemExit`, без сети) |
| Сетевые/provider вызовы | [CONFIRMED] `0` — только `--help` и no-op запуск без `--web`/`--run` |
| Файлы не создаются проверками | [CONFIRMED] `git status --porcelain` после всех help/import-проверок показывает только предполагаемые изменённые/новые файлы задачи |

## Регрессионный тест

`REGRESSION_TEST: ADDED` —
[`tests/diagnostics/test_operator_cli_root_compat.py`](../../tests/diagnostics/test_operator_cli_root_compat.py):
4 теста, защищающих именно два риска из задачи — расчёт `.env`-lookup после
переноса и то, что root wrapper делегирует (`is`) в перенесённую реализацию,
а не форкает вторую копию `main`. Более крупный harness не требовался.

## Валидация

| Проверка | Результат |
|---|---|
| `python -m unittest tests.diagnostics.test_operator_cli_root_compat -v` | [CONFIRMED] `4 passed` |
| `python -m unittest discover -s tests/diagnostics -v` | [CONFIRMED] `49 passed`, `9 errors` в `test_change_classifier.py` |
| Причина `9 errors` | [CONFIRMED] `FileNotFoundError: pwsh` — отсутствие `pwsh` (PowerShell Core) в PATH текущей среды; воспроизведено на `git stash` (немодифицированное дерево) тем же файлом с тем же результатом; не связано с этой задачей и не вызвано переносом |
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS`, `tool_entries=40` |
| `git diff --check` | [CONFIRMED] exit `0` |
| Импорт root-модулей за пределами перенесённых файлов | [CONFIRMED] `rg`/`grep` не нашёл `import collect_contacts`/`import benchmark_models`/`from collect_contacts`/`from benchmark_models` нигде в репозитории |
| Сканирование staged diff на секреты | [CONFIRMED] совпадения — только имена переменных окружения (`XMLRIVER_KEY`, `XMLRIVER_USER`) и идентификаторы кода, значений нет |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — изменено `5` файлов: `collect_contacts.py`,
`benchmark_models.py`, `scripts/collect_contacts.py` (new),
`benchmarks/benchmark_models.py` (new),
`tests/diagnostics/test_operator_cli_root_compat.py` (new). Ни один
несвязанный модуль не тронут.

## Не проверено

- NOT VERIFIED: недокументированный внешний Python-импорт этих двух модулей
  за пределами репозитория — по условию задачи не проверяется и не
  поддерживается сложным compatibility-слоем.
- NOT VERIFIED: `python scripts/collect_contacts.py`/`python
  benchmarks/benchmark_models.py` напрямую (без `-m` и без wrapper) — не
  входит в обязательные вызовы задачи; для этой формы `sys.path[0]` был бы
  `scripts/`/`benchmarks/`, и импорт root-модулей (`contact_crawler` и т.д.)
  потребовал бы отдельного решения, сознательно не добавленного, чтобы не
  вводить лишний `sys.path`-хак.
- NOT VERIFIED: полный `--web`/`--llm`/`--verify`/`--prepare`/`--run` путь с
  реальными provider-вызовами — запрещено разделом "No live provider
  execution" этой задачи.
- Причина `9 errors` в `test_change_classifier.py` (`pwsh` недоступен)
  остаётся отдельным ограничением среды, а не находкой этой задачи.

## Публикация

Commit и push зафиксированы в финальном отчёте ниже (см. блок FINAL REPORT в
ответе агента). `ACTIVE_TASK` возвращён в `IDLE` после публикации.
