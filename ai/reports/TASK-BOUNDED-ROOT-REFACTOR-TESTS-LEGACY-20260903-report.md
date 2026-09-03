# TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`TESTS_LEGACY_CONVERSION: COMPLETE` — [CONFIRMED] 4 корневых ручных
проверочных скрипта (`test_extractor.py`, `test_inn.py`, `test_parser.py`,
`test_verify.py` — кастомные `check()`/`main()`, никогда не входившие в
discovery `scripts/run_test_suite.py`) конвертированы в настоящие
`unittest.TestCase` под `tests/legacy/`. Каждый вызов `check(name, actual,
expected)` стал `self._check(name, actual, expected)` (обёртка
`subTest`+`assertEqual`) — построчное сравнение всех 186 точек вызова по 4
файлам подтвердило точное соответствие 1:1 до удаления корневых файлов.
Раннер не потребовал изменений: рекурсивный `unittest.discover` над
`tests/` уже подхватывает `tests/legacy/` автоматически. Это завершает
многоходовую программу root refactor (Pass 2-11).

## Цель, контекст и границы

- **Цель:** выполнить явное решение владельца — превратить 4 корневых
  ручных проверки в unittest, включить в официальный раннер (а не удалить
  или оставить ручными).
- **Контекст:** ветка `claude/zen-goldwasser-022bb1`, Pass 11 (финальный)
  серии bounded root refactor. Диагностика
  (`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`) явно
  оставила discovery-политику этих 4 файлов на решение владельца
  (`DEPRECATED_REVIEW`). Владельцу задан вопрос через `AskUserQuestion`
  одновременно с вопросом про `serp_parser.py`; ответ — «Превратить в
  unittest».
- **Ограничения:** ни одна содержательная проверка не должна быть потеряна
  или переписана по логике; только механическая конвертация формата
  (`check()` → `self._check()`, свободная функция → метод класса). Без
  изменения тестируемой production-логики.
- **Готово когда:** все 4 файла — настоящие `unittest.TestCase` под
  `tests/`, автоматически обнаруживаются `scripts/run_test_suite.py`,
  1:1-паритет проверок доказан, корневые файлы удалены (других consumers
  нет), полный набор тестов проходит без новых регрессий.

## Свежая проверка ссылок

Полнотекстовый поиск `test_extractor|test_inn\b|test_parser\b|test_verify\b`
по всему репозиторию (кроме самих 4 файлов) не нашёл ни одного внешнего
Python-consumer'а — ни импорта, ни вызова `main()` откуда-либо ещё. Значит,
безопасно полностью удалить корневые копии без совместимой обёртки (в
отличие от Pass 2/10, где документированный `python <file>.py ...`
CLI-контракт требовал сохранения).

Отдельно проверено: `Documents/28-8/README.md` и несколько исторических
`ai/reports/*.md` упоминают `python test_extractor.py` и подобные команды —
это исторические/frozen-evidence документы (`Documents/` явно помечен
«HISTORICAL — NOT CURRENT» диагностикой; `ai/reports/*.md` — append-only
исторические отчёты прошлых задач). Не редактировались, по установленному
прецеденту предыдущих passes.

## Конвертация

Для каждого файла: класс `unittest.TestCase` с методом-хелпером

```python
def _check(self, name: str, actual, expected) -> None:
    with self.subTest(name):
        self.assertEqual(actual, expected, name)
```

и каждая бывшая свободная функция `test_xxx()` стала методом
`def test_xxx(self):`, с телом без изменений кроме `check(` → `self._check(`.
`subTest` сохраняет исходное поведение скриптов (продолжать после
проваленной проверки и показать все проблемы разом), а не останавливаться
на первом `assertEqual`.

| Файл | Класс | Проверок (`check`/`_check`) | Строк |
|---|---|---|---|
| `tests/legacy/test_extractor.py` | `ExtractorTests` | `69` | `12` тестов |
| `tests/legacy/test_inn.py` | `InnExtractorTests` | `46` | `6` тестов |
| `tests/legacy/test_parser.py` | `SerpParserTests` | `38` | `8` тестов |
| `tests/legacy/test_verify.py` | `VerifyTests` | `31` | `3` теста |

`test_parser.py`'s `test_errors()` содержит нетривиальный
`try/except XmlRiverError/XmlRiverTemporaryError` паттерн (проверка «либо
исключение с нужным кодом, либо это провал») — перенесён буквально,
структура `try/except` не переписывалась на `assertRaises`, чтобы не
рисковать скрытым изменением поведения при механической конвертации.

`FakeClient` (не-тестовый helper-класс в `test_parser.py`, подкласс
`XmlRiverClient`) перенесён как есть, module-level, рядом с `TestCase` —
`unittest`'s `TestLoader` не подбирает не-`TestCase` классы, поэтому его
наличие не создаёт лишних тестов.

## Доказательство 1:1-паритета (до удаления корневых файлов)

Построчный `diff` всех точек вызова `check(...)`/`self._check(...)` (после
нормализации префикса и отступов) между каждым оригиналом и его
конвертированной версией:

| Пара | Точек вызова (обе стороны) | `diff` |
|---|---|---|
| `test_extractor.py` ↔ `tests/legacy/test_extractor.py` | `69` | пусто (идентично) |
| `test_inn.py` ↔ `tests/legacy/test_inn.py` | `46` | пусто (идентично) |
| `test_parser.py` ↔ `tests/legacy/test_parser.py` | `38` | пусто (идентично) |
| `test_verify.py` ↔ `tests/legacy/test_verify.py` | `31` | пусто (идентично) |

Ни одна проверка не была потеряна, продублирована или переписана по
существу.

## Тесты

| Проверка | Результат |
|---|---|
| `python -m unittest discover -s tests/legacy -v` | [CONFIRMED] `29/29 PASS` |
| `python scripts/run_test_suite.py` (grep на `legacy`) | [CONFIRMED] все 29 тестов видны под именами `tests.legacy.test_*....` — рекурсивный discovery сработал без изменений в раннере |
| `python scripts/run_test_suite.py` (полный прогон, до коммита) | `tests=497; failures=0; errors=10` — на 1 ошибку больше базовой линии, расследовано ниже |
| `python scripts/run_test_suite.py` (полный прогон, после коммита) | [CONFIRMED] `errors=9` — та же pre-existing `pwsh`-gap база, 10-я ошибка не воспроизводится |

## Расследование 10-й ошибки (не регрессия) — `FINDING-019`

При первом прогоне полного набора (до коммита этой задачи) появилась
ошибка `tests.diagnostics.test_diagnostic_negative_fixtures.
DiagnosticNegativeFixtureTests.test_machine_output_fields_are_present_and_safe`
с traceback `AttributeError: 'NoneType' object has no attribute
'splitlines'` внутри `scripts/diagnostics/diagnostic_runner.py:
scan_staged_literal_diff`, вызванного из `secret_path_check`.

Корневая причина: `secret_path_check` вызывает `subprocess.run(["git",
"diff", "--cached", "--unified=0"], ..., text=True)` **без** явного
`encoding="utf-8"`. На этой Windows-машине `text=True` без `encoding`
декодирует stdout в `cp1251` (кодовая страница локали), а не UTF-8, в
котором Git реально отдаёт diff. Пока в staging area (`git diff --cached`)
этой задачи лежал большой, насыщенный кириллицей неподтверждённый diff (мои
собственные изменения Pass 11 перед коммитом), reader-поток subprocess
падал на `UnicodeDecodeError`, и `.stdout` в итоге оказывался `None`.

Проверено программно: `git diff --cached --unified=0 | decode('cp1251')`
воспроизводимо падает с `UnicodeDecodeError` именно на моём staged diff.
После коммита этой задачи (staging area очистилась) — чистый повторный
прогон вернул `errors=9`, ту же базовую линию, что и во всех предыдущих
Pass. Значит, эта ошибка была артефактом МОЕЙ собственной незакоммиченной
staging area в момент прогона, а не дефектом в содержимом
`tests/legacy/*.py` или в тестируемой production-логике.

Найденный баг реален и не исправлен здесь (вне границ этой задачи —
`AI_CONTRACT.md` rule 5): зафиксирован как `FINDING-019` в
`ai/DEFERRED_FINDINGS.md` — те же 4 непроверенных `subprocess.run(...,
text=True, ...)` вызова в `secret_path_check` (строки 572, 574, 576, 580)
рискуют так же упасть у любого контрибьютора с кириллическим
незакоммиченным diff в момент локального прогона полного набора.

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — затронуто `10` файлов:
`tests/legacy/__init__.py`, `tests/legacy/test_extractor.py`,
`tests/legacy/test_inn.py`, `tests/legacy/test_parser.py`,
`tests/legacy/test_verify.py` (все новые), удалены `test_extractor.py`,
`test_inn.py`, `test_parser.py`, `test_verify.py` (корень),
`docs/architecture/REPOSITORY_LAYOUT.md`, `ai/CURRENT_STATE.md`,
`ai/DEFERRED_FINDINGS.md` (+ `ai/ACTIVE_TASK.md` state-only). В пределах
ожидаемого диапазона согласно причинно-связанной автономной политике
владельца.

## Не проверено

- NOT VERIFIED: `FINDING-019`'s фикс (не применялся — вне границ этой
  задачи).
- NOT VERIFIED: реальный Vercel build/deploy (не требуется — только тесты
  затронуты, production-код не менялся).

## Оставшийся объём root-рефакторинга

Программа bounded root refactor (Pass 2-11) завершена. `supplier_app.py`/
`api/index.py` остаются `KEEP_ROOT` — единственные намеренно не перенесённые
корневые Python-файлы, как защищённые entrypoints.

## Публикация

Commit/push/CI зафиксированы в финальном ответе агента. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
