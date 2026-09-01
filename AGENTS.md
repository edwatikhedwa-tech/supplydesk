# Codex project instructions

This file is the Codex adapter for this repository. The shared rules are in
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md); this file only describes the Codex
entrypoint and links to the state documents.

## Before work

Read, in this order:

1. [`AGENTS.md`](AGENTS.md) and the shared rules in [`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md)
2. [`PROJECT_MANIFEST.yaml`](PROJECT_MANIFEST.yaml) — repository map and protected boundaries
3. [`docs/DOCUMENTATION_POLICY.md`](docs/DOCUMENTATION_POLICY.md) — document ownership and lifecycle
4. [`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) — the only canonical current-state source
5. [`ai/ACTIVE_TASK.md`](ai/ACTIVE_TASK.md) — active-task lock/sentinel
6. Relevant product documents under [`docs/`](docs/README.md)
7. Relevant [`ai/DECISIONS.md`](ai/DECISIONS.md) and [`ai/DEFERRED_FINDINGS.md`](ai/DEFERRED_FINDINGS.md)
8. [`ai/WORKFLOW.md`](ai/WORKFLOW.md), handoff, task reports, and audit evidence as required

Verify the current branch, commit, working tree, URL, port, database and build
before changing anything. If the task is not sufficiently defined, start with
an AUDIT that makes no changes. Do not trust a previous agent's report without
checking its primary evidence.

## During and after work

- Keep one primary goal and an explicit scope/non-goals boundary.
- Do not change application logic, UI, API, database, migrations or production
  settings for a documentation/state task.
- Do not fix unrelated findings; record them in
  [`ai/DEFERRED_FINDINGS.md`](ai/DEFERRED_FINDINGS.md).
- Update [`ai/CHANGELOG.md`](ai/CHANGELOG.md) after each substantial action,
  [`ai/INTERACTION_LOG.md`](ai/INTERACTION_LOG.md) after each interaction, and
  [`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) when project state changes.
- Keep documentation current in the same task as the change it describes:
  [`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) is the only current-state source;
  `docs/**` owns product documentation, while `ai/**` owns operational control;
  dated snapshots must be marked `HISTORICAL — NOT CURRENT` and link back to it.
- At stage close, update [`ai/LAST_HANDOFF.md`](ai/LAST_HANDOFF.md), save a
  report under [`ai/reports/`](ai/reports/), and run
  `python ai/tools/validate_state.py`.
- Create a commit containing the Task ID when the iteration is complete. Never
  force-push or merge into `main`/`master` automatically. Report the exact
  commit, branch, working-tree status and push status.

## Ответы владельцу проекта

- Для существенной работы отвечай кратко и понятным русским языком.
- В начале ответа используй три коротких блока: `Сделано`, `Проблемы и
  ограничения`, `Следующий шаг`.
- Любой неизбежный технический термин сразу расшифровывай простыми словами.
- Команды, числа, `PASS`/`FAIL`, хеш коммита и английские названия всегда
  сопровождай объяснением, что они означают для пользователя.
- Каждую рекомендацию объясняй по схеме: `что это`, `зачем нужно`, `что будет
  без изменения`, `приоритет/срочность`, `что именно изменится`, `что не
  изменится` и `нужно ли действие заказчика`.
- Не используй без расшифровки слова вроде `чанк`, `lazy loading`, `baseline`,
  `регрессия`, `overflow`, `acceptance`, `P3` и `CI`. Если термин нужен,
  сначала дай его бытовое объяснение, а техническое название укажи в скобках.
- Для пунктов `P0`–`P3` обязательно объясняй влияние на пользователя:
  `P0/P1` — мешает пользоваться или создаёт серьёзный риск, `P2` — заметная
  проблема качества, `P3` — небольшое улучшение без срочности.
- Не называй рекомендацию формулировками `разобраться`, `оптимизировать` или
  `улучшить` без конкретного результата и понятного критерия готовности.
- Не выдавай служебную проверку правил за основной ответ: сначала объясни
  результат обычными словами, затем добавь короткий блок `ПРОВЕРКА ПРАВИЛ`.
- В блоке показывай только фактические значения текущего ответа. Не копируй
  шаблон с вариантами через `/`, не оставляй заполнители и не используй
  непереведённые статусы без короткого пояснения.

## Required final check — понятная проверка правил в конце ответа

Каждый ответ по проекту заканчивай этим блоком, заполняя только один реальный
вариант в каждой строке. Если проверка не выполнялась или заблокирована,
укажи это и коротко объясни причину.

```text
[ПРОВЕРКА ПРАВИЛ]
Правила прочитаны: да — проверка выполнена
Состояние проекта проверено: да — проверка выполнена
Хронология действий: изменений не было — причина не нужна
Границы задачи: соблюдены — выход за scope не обнаружен
Непроверенное явно указано: да — неизвестные пункты перечислены выше
Файлы состояния: обновлены — записи соответствуют этой задаче
Коммит: `хеш` — локальная версия сохранена
Отправка изменений: не выполнялась — публикация не запрашивалась
Итог: правила соблюдены — обязательные проверки выполнены
[/ПРОВЕРКА ПРАВИЛ]
```

В готовом ответе нельзя оставлять варианты через `/`: это только подсказка
для агента, а не текст для владельца проекта. Слова `да`, `нет`, `не
требовалось`, `не проверено` и `заблокировано` должны описывать именно этот
ответ. Для понятности после каждого статуса добавляй короткое объяснение
простыми словами. Хеш коммита указывай только если коммит действительно
создан; если коммита нет, пиши `не создавался — ...`.
