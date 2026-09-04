# Codex project instructions

This file is the Codex adapter for this repository. The shared rules are in
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md); this file only describes the Codex
entrypoint and links to the state documents.

## Before work

At the start of a new agent session, read, in this order:

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

## Session, task and continuation preflight

At the start of a new agent/Codex session, perform the full bootstrap listed
above once. In a healthy session, reuse that verified context unless the
workspace, Git root, environment, relevant instructions or agent context
changes. Before each new independent task, run only the cheap Task Preflight:
workspace guard, branch, HEAD, working-tree status, active-task/conflict check,
brief classification and required verification profile.

Messages that continue the current task do not start a new task automatically.
For those messages, perform only the action-specific check required next. Do
not repeat the full instruction pack or environment discovery without a
revalidation reason. The canonical policy in `ai/VIBECODING_RULES.md` defines
the three levels and the required exception cases.

## Workspace guard

Before project-specific analysis or execution, including read-only work, enforce
the canonical `SESSION_WORKSPACE_HARD_GATE` from
[`ai/VIBECODING_RULES.md`](ai/VIBECODING_RULES.md). Only after it passes may the
agent read project state, classify the task or select project-analysis tools.
Before any file change, state/report update, backend start, frontend build,
database write, migration, artifact-producing test, commit or push, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
```

The default local root is `C:\Users\edwat\SupplyDesk`. A deliberate Git
worktree or CI checkout must pass its exact absolute root explicitly with
`-ExpectedRoot <absolute path>`. The guard only compares the real Git root; it
never changes directory, branch or files. If it prints
`BLOCKED_WRONG_WORKSPACE`, stop immediately, even when local state files appear
valid.

The legacy root `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS` is
recovery-only. Do not run ordinary coding tasks, the backend, frontend builds
or migrations there, and do not use it to change canonical project state.
Recovery or read-only audit of that root requires an explicit task instruction.

## VibeCoding bootstrap (mandatory)

At the start of a new session, read `PROJECT_MANIFEST.yaml`,
`ai/CURRENT_STATE.md`, `ai/VIBECODING_RULES.md` and
`ai/VIBECODING_TOOL_REGISTRY.yaml`; read `last_corrected` from the canonical
policy. Reuse these files for later tasks in the same healthy session unless
the policy's revalidation exceptions apply. For each new task, classify it and
select only the required checks. Emit the
VibeCoding acknowledgement exactly once in the final response after the task
is completed or stopped; never emit it in intermediate updates. If the policy
is missing, ambiguous or its date is unreadable, use
`VIBECODING POLICY: NOT VERIFIED` exactly once in the final response and do
not modify the project. Detailed rules live only in
[`ai/VIBECODING_RULES.md`](ai/VIBECODING_RULES.md).

## During and after work

- Keep one primary goal and an explicit scope/non-goals boundary.
- Do not change application logic, UI, API, database, migrations or production
  settings for a documentation/state task.
- Do not fix unrelated findings; record them in
  [`ai/DEFERRED_FINDINGS.md`](ai/DEFERRED_FINDINGS.md).
- For substantial work, append [`ai/CHANGELOG.md`](ai/CHANGELOG.md) and
  [`ai/INTERACTION_LOG.md`](ai/INTERACTION_LOG.md); update
  [`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) when project facts change.
  For micro/small tasks, update only documents whose factual content changed.
- Keep documentation current in the same task as the change it describes:
  [`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) is the only current-state source;
  `docs/**` owns product documentation, while `ai/**` owns operational control;
  dated snapshots must be marked `HISTORICAL — NOT CURRENT` and link back to it.
- At stage close, update [`ai/LAST_HANDOFF.md`](ai/LAST_HANDOFF.md), save a
  concise report under [`ai/reports/`](ai/reports/) when traceability requires
  it, and run
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
