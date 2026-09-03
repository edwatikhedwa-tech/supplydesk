# TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`FINDING_019_FIX: COMPLETE` — [CONFIRMED] `scripts/diagnostics/
diagnostic_runner.py`'s `secret_path_check` больше не падает
`AttributeError`, когда в staging area лежит diff с кириллицей. Причина —
отсутствие `encoding="utf-8"` у четырёх `subprocess.run(..., text=True)`
вызовов, из-за чего на Windows они декодировались локальной кодовой
страницей (`cp1251`), а не UTF-8, в котором Git реально отдаёт diff.
Исправлено добавлением `encoding="utf-8", errors="replace"` — точно те же
параметры, что уже использует `run_process()` в этом же файле несколькими
строками выше. Заодно исправлены 2 дополнительных экземпляра того же
паттерна (`git_check`'s branch/HEAD lookup), найденные при проверке.

## Цель, контекст и границы

- **Цель:** довести до конца `FINDING-019`, обнаруженный попутно в
  `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903` (Pass 11 root
  refactor) и там же сознательно не исправленный (вне границ той задачи).
- **Контекст:** ветка `claude/zen-goldwasser-022bb1`, отдельная bounded
  задача после закрытия PR #1. Владелец дал общее разрешение «делай как
  считаешь нужным» — фикс минимален, причина доказана, бизнес-поведение не
  меняется, поэтому выполняется сразу, без дополнительного вопроса.
- **Ограничения:** менять только 4 (+2 обнаруженных) `subprocess.run`
  вызова в `scripts/diagnostics/diagnostic_runner.py`; не менять логику
  secret-scan, не менять другие diagnostic-скрипты, не трогать
  production-код.
- **Готово когда:** все затронутые вызовы явно указывают
  `encoding="utf-8", errors="replace"`; воспроизведено, что баг был
  реален; доказано, что фикс устраняет его на реальном кириллическом
  staged diff; полный тестовый набор проходит без регрессий.

## Root cause

`scripts/diagnostics/diagnostic_runner.py` уже содержит корректный паттерн
в `run_process()` (используется, например, `git_value()`):

```python
subprocess.run(
    command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False, env=env,
)
```

Но `secret_path_check` (строки 572, 574, 576, 580) и `git_check`'s
branch/HEAD lookup (строки 133-134) вызывают `subprocess.run(...,
text=True, ...)` напрямую, **без** `encoding=`/`errors=`. Без явного
`encoding`, Python использует `locale.getpreferredencoding()` для
декодирования stdout — на этой Windows-машине это `cp1251`, а не UTF-8, в
котором Git выводит diff. Кириллические байты в UTF-8 не декодируются как
валидный `cp1251` → `UnicodeDecodeError` в internal reader-потоке →
`.stdout` оказывается `None` → `scan_staged_literal_diff` падает на
`None.splitlines()`.

## Исправление

`secret_path_check` (4 вызова, строки 572, 574, 576, 580): добавлен
`encoding="utf-8", errors="replace"` к каждому — для `git diff --cached
--name-only`, `git ls-files`, `git ls-files --others --exclude-standard`,
`git diff --cached --unified=0`.

`git_check` (2 вызова, строки 133-134): тот же фикс для `git branch
--show-current` и `git rev-parse HEAD` — найдены при grep-проверке
оставшихся `text=True` без `encoding=` в этом файле; риск ниже (имена
веток и хеши обычно ASCII), но тот же класс дефекта в том же файле,
исправлен для полноты.

`errors="replace"` (а не `strict`, дефолт) выбран по прецеденту
`run_process()` в этом же файле — не роняет процесс на редком
невалидном байте, заменяет его `�`, что достаточно для secret-scan'а
(ищет строковые паттерны, не байт-в-байт содержимое).

## Проверка бага и фикса на реальном условии

Grep подтвердил: после фикса не осталось ни одного `subprocess.run(...,
text=True, ...)` без `encoding=` в этом файле (единственное совпадение —
внутри самого `run_process()`, где `encoding=` уже стоит на следующей
строке).

Условие бага воспроизведено НЕ синтетической заглушкой, а реальным
рабочим сценарием: кириллические документы этой же задачи (этот отчёт и
обновление `ai/DEFERRED_FINDINGS.md`) застейджены в git index одновременно
с фиксом, и целевой тест запущен под этим реальным staged diff:

| Проверка | Результат |
|---|---|
| `git diff --cached --unified=0 \| decode('cp1251')` до фикса (Pass 11, зафиксировано в отчёте той задачи) | `UnicodeDecodeError` — баг подтверждён реальными данными |
| `python -m unittest tests.diagnostics.test_diagnostic_negative_fixtures.DiagnosticNegativeFixtureTests.test_machine_output_fields_are_present_and_safe` с застейдженным кириллическим diff ЭТОЙ задачи и применённым фиксом | [CONFIRMED] `OK` — не падает |

## Тесты

| Проверка | Результат |
|---|---|
| `python -m unittest tests.diagnostics.test_diagnostic_negative_fixtures -v` | [CONFIRMED] `PASS` |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=497; failures=0; errors=9 (те же pre-existing pwsh-gap); skipped=1` |
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `4` файла:
`scripts/diagnostics/diagnostic_runner.py`, `ai/DEFERRED_FINDINGS.md`,
`ai/CURRENT_STATE.md` (+ `ai/ACTIVE_TASK.md` state-only). Точечный
однострочный фикс на 6 вызовов в одном файле.

## Не проверено

- NOT VERIFIED: реальный Vercel build/deploy (не требуется — только
  diagnostic-инструмент затронут, не production/deployment код).
- NOT VERIFIED: `run_process()`'s `env=None` default передача переменных
  окружения дочернему процессу — не менялась, вне scope.

## Публикация

Commit/push зафиксированы в финальном ответе агента. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
