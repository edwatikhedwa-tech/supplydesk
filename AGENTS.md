# Codex project instructions

This file is the Codex adapter for this repository. The shared rules are in
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md); this file only describes the Codex
entrypoint and links to the state documents.

## Before work

Read, in this order:

1. [`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md)
2. [`ai/WORKFLOW.md`](ai/WORKFLOW.md)
3. [`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md)
4. [`ai/LAST_HANDOFF.md`](ai/LAST_HANDOFF.md)
5. [`ai/DECISIONS.md`](ai/DECISIONS.md)
6. [`ai/DEFERRED_FINDINGS.md`](ai/DEFERRED_FINDINGS.md)
7. [`ai/ACTIVE_TASK.md`](ai/ACTIVE_TASK.md)

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
- Не выдавай служебный блок проверки инструкций за основной ответ: сначала
  объясни результат обычными словами, затем добавь служебную проверку.

## Required final check

Every response ends with the following block, using truthful values:

```text
[INSTRUCTION CHECK]
Instructions loaded: PASS / NOT VERIFIED / BLOCKED
Current state checked: PASS / NOT NEEDED / BLOCKED
Chronology updated: PASS / NO STATE CHANGE / BLOCKED
Scope respected: PASS / FAIL
Unverified items disclosed: PASS / FAIL
State files updated: PASS / NOT NEEDED / BLOCKED
Commit: HASH / NOT CREATED / NOT NEEDED
Push: YES / NO / NOT NEEDED / BLOCKED
Final compliance: COMPLIANT / NOT COMPLIANT
[/INSTRUCTION CHECK]
```
