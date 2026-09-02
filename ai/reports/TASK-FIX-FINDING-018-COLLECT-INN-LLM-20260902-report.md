# TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902

`DELIVERY_MODE: PUBLISH`

## Итог

`FINDING_018: RESOLVED` — [CONFIRMED] `collect_inn.py --llm` исправлен
через детерминированный RED→FIX→GREEN workflow (методология
`BUG_REPRODUCER` из `ai/AI_CONTRACT.md`, применена напрямую — установленного
`bug-reproducer` SKILL.md в этой Claude Code сессии нет, проверено через
`ListSkills`, ноль результатов). Тем же самым тестом доказан переход из
падения в прохождение. Реальных provider-вызовов не было.

## Цель, контекст и границы

- **Цель:** исправить `FINDING-018` (`collect_inn.py --llm` импортирует
  несуществующий `InnLlmExtractor`, неверное сообщение про
  `ANTHROPIC_API_KEY`), с доказательством через RED→GREEN.
- **Контекст:** ветка `audit/frontend-knip-20260902`, preflight HEAD
  `bb6aaf0e9a2a6aec3835fa17475718792b1cde0e`.
- **Ограничения:** без реальных RouterAI/AI вызовов; без изменения prompts/
  schemas/model selection policy; без архитектурного рефакторинга.
- **Готово когда:** баг детерминированно воспроизведён, минимальный fix
  применён, тот же reproducer стал зелёным, целевые тесты проходят,
  `FINDING-018` закрыт.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `bb6aaf0e9a2a6aec3835fa17475718792b1cde0e` |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] `IDLE` перед стартом |
| Доступность `bug-reproducer` skill | [CONFIRMED] `ListSkills(keywords=["bug","reproducer","bug-reproducer"])` вернул `0` результатов — skill не установлен в этой сессии; использована методология `BUG_REPRODUCER` из `ai/AI_CONTRACT.md` напрямую, отчитана как `TYPE: WORKFLOW`, не `TYPE: SKILL` |

## History / intent check (раздел 3)

[CONFIRMED] `git log --all --oneline -S "InnLlmExtractor" -- collect_inn.py
llm_fallback.py backend/integrations/llm/llm_fallback.py` вернул ровно один
коммит — исходный bulk-import репозитория (`3b8ab7a`). `InnLlmExtractor`
никогда не существовал как реальный класс в отслеживаемой истории; строка
импорта была сломана уже в этом самом первом коммите.

[CONFIRMED] `Documents/28-8/enrichment-and-cache.md:662-665` (существующая
продуктовая документация, написанная независимо от этой задачи) прямо
называет это «известной нестыковкой»: «CLI-флаг `--llm` в `collect_inn.py`
всё ещё ссылается на `InnLlmExtractor`/`ANTHROPIC_API_KEY` — это осталось от
версии до перехода на RouterAI. Веб-конвейер (`_enrich_suppliers`)
использует актуальный `LlmExtractor`/`ROUTERAI_KEY` и этой проблемой не
затронут».

**Результат: `HISTORICAL_INN_LLM_EXTRACTOR: NEVER_EXISTED`** (в
отслеживаемой истории; задокументирован как leftover от pre-RouterAI
версии). Подтверждено Hypothesis B — `LlmExtractor` (уже используемый
корректно в `supplier_app.py`) является предполагаемой текущей реализацией.
Класс из истории не восстанавливался вслепую.

## Gate 1 — предложение воспроизведения (одобрено владельцем)

[CONFIRMED] Одно консолидированное предложение показано и одобрено:
поведенческий reproducer `tests/diagnostics/test_collect_inn_llm_path.py`,
вызывающий реальный `collect_inn.main(["example.test", "--llm"])` с
замоканными только `ContactCrawler`/`load_dotenv` (сеть/`.env` — границы
изоляции), детерминированной HTML без ИНН. Case A: отсутствие
`ROUTERAI_KEY` → ожидание чистого `SystemExit` с упоминанием
`ROUTERAI_KEY`, без `ANTHROPIC_API_KEY`. Case B/C: без `--llm-model` →
захваченная модель равна `DEFAULT_MODEL`, не `None`; с явным
`--llm-model test-model` → передаётся как есть.

## RED proof (раздел 7)

[CONFIRMED] `python -m unittest tests.diagnostics.test_collect_inn_llm_path
-v` на неисправленном коде: `3/3` теста упали с точно предсказанной
причиной:

```
ImportError: cannot import name 'InnLlmExtractor' from
'backend.integrations.llm.llm_fallback'
  File "collect_inn.py", line 217, in main
    from backend.integrations.llm.llm_fallback import InnLlmExtractor, api_key_present
```

Падение произошло на строке импорта — до вызова `api_key_present()` и до
любого сетевого кода. Это не ошибка setup/fixture/сети — ровно
предсказанное поведение `FINDING-018`.

```
BUG_REPRODUCER_STATUS_BEFORE: REPRODUCED
REPRODUCER_BEFORE: RED
FAILURE_REASON: ImportError: cannot import name 'InnLlmExtractor' (collect_inn.py:217)
```

## Gate 2 — предложение fix'а (одобрено владельцем)

[CONFIRMED] Одно консолидированное предложение показано и одобрено:

1. `from backend.integrations.llm.llm_fallback import InnLlmExtractor,
   api_key_present` → `from backend.integrations.llm.llm_fallback import
   DEFAULT_MODEL, LlmExtractor, api_key_present`.
2. `extractor = InnLlmExtractor(model=args.llm_model)` →
   `extractor = LlmExtractor(model=args.llm_model or DEFAULT_MODEL)` — тот
   же безопасный паттерн, что уже используется в
   `scripts/collect_contacts.py`.
3. Текст сообщения об отсутствии ключа: `"Для --llm нужен ключ
   Anthropic.\nЗадайте ANTHROPIC_API_KEY..."` → `"Для --llm нужен ключ
   RouterAI.\nЗадайте ROUTERAI_KEY..."`.

Владелец одобрил ровно это предложение без изменений (с явным требованием
далее вести переписку только на русском языке).

## Применённый минимальный fix (раздел 10)

`collect_inn.py:217-223` — [CONFIRMED] изменены ровно 3 строки внутри блока
`if args.llm:`. Никакой другой код в файле, `llm_fallback.py`,
`routerai_client.py`, `supplier_app.py` не тронут.

## GREEN proof (раздел 11)

[CONFIRMED] Тот же самый `python -m unittest
tests.diagnostics.test_collect_inn_llm_path -v` после fix'а: `3/3 PASS`.

```
REPRODUCER_AFTER: GREEN
BUG_PROOF_STANDARD: RED_TO_GREEN
FIX_STATUS: FIX_PROVEN
```

## Обновление structural-теста (раздел 9)

[CONFIRMED] `tests/diagnostics/test_llm_integration_move.py` до этой задачи
содержал устаревшее ожидание (`CONSUMERS["collect_inn.py"]` требовал строку
с `InnLlmExtractor` как «правильный» канонический импорт — то есть
благословлял сломанное поведение). Обновлено на `DEFAULT_MODEL,
LlmExtractor, api_key_present`. Поведенческий reproducer (этот файл) —
первичное доказательство бага; structural-тест — вторичное доказательство
пути импорта, дублирования нет (разные утверждения: один проверяет
исходный код построчно, другой — реальное поведение `main()`).

## No live providers (раздел 12)

```
ROUTERAI_CALLS: 0
OPENAI_CALLS: 0
ANTHROPIC_CALLS: 0
GEMINI_CALLS: 0
XMLRIVER_CALLS: 0
CHECKO_CALLS: 0
DADATA_CALLS: 0
```

[CONFIRMED] Ни один тест не использовал реальный ключ; `ROUTERAI_KEY` в
Case B/C — заведомо фиктивная строка `"test-key-not-real"`, а
`LlmExtractor`/`api_key_present` подменены на границе модуля
`backend.integrations.llm.llm_fallback`, поэтому реальный
`RouterAiClient`/OpenAI SDK ни разу не конструировался.

## Валидация

| Проверка | Результат |
|---|---|
| `tests.diagnostics.test_collect_inn_llm_path` | [CONFIRMED] `3/3 PASS` (после fix) |
| `tests.diagnostics.test_llm_integration_move` | [CONFIRMED] `6/6 PASS` (после обновления) |
| `tests.test_enrichment_pipeline` + `tests.test_dashboard` | [CONFIRMED] `21/21 PASS` |
| `python -m unittest discover -s tests/diagnostics -v` | `LOCAL_DIAGNOSTICS_PASSED: 61`, `LOCAL_DIAGNOSTICS_ERRORS: 9`, `LOCAL_DIAGNOSTICS_STATUS: PARTIAL_ENVIRONMENT` — те же 9 ошибок `test_change_classifier.py` (`pwsh` недоступен), доказано ранее не связанными с изменениями кода; повторно не расследовалось |
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `git diff --check` | [CONFIRMED] exit `0` |
| Сканирование staged diff на секреты | [CONFIRMED] только `ROUTERAI_KEY`/`ANTHROPIC_API_KEY`/`api_key_present` — код и текст сообщений, значений нет |

## Change Budget (раздел 14)

Затронуто `3` файла: `collect_inn.py` (3 строки),
`tests/diagnostics/test_collect_inn_llm_path.py` (новый),
`tests/diagnostics/test_llm_integration_move.py` (1 строка). Никакой
архитектурный перенос, `llm_fallback.py`/`routerai_client.py`/
`supplier_app.py`/frontend/mail/database/migrations/
`supplier_discovery_v2`/CI/VibeCoding/skills не тронуты.

## Не проверено

- NOT VERIFIED: реальное поведение с настоящим `ROUTERAI_KEY` и живым
  RouterAI API — запрещено разделом 12 этой задачи.
- NOT VERIFIED: вызов `python collect_inn.py --llm ...` из реального
  терминала оператором (только через `unittest`/`main()` напрямую).

## Публикация

Commit/push/CI зафиксированы в финальном отчёте ниже. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
