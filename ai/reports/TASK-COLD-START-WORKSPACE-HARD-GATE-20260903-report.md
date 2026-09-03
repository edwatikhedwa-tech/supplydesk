---
document_id: TASK-COLD-START-WORKSPACE-HARD-GATE-20260903-REPORT
status: CURRENT
canonical: false
owner: Codex
updated_at: 2026-09-03
---

# TASK-COLD-START-WORKSPACE-HARD-GATE-20260903

## Решение

`PASS_WITH_LIMITATIONS`: безопасная и полезная работа по hard gate выполнена,
локальные доказательства Codex получены, публикация разрешена. Claude
post-fix cold-start остаётся `NOT VERIFIED` из-за ошибки его CLI-шлюза.

## Причина

- `PRIMARY_ROOT_CAUSE: BOOTSTRAP_GAP` — legacy checkout не содержал указателя
  на каноническую политику и мог начать собственный root-аудит.
- `SECONDARY_ROOT_CAUSE: INSTRUCTION_GAP` — прежняя формулировка gate
  начиналась до мутаций/runtime/build, но не запрещала read-only-анализ.

## Изменение

- `SESSION_WORKSPACE_HARD_GATE` теперь является первым project action, в том
  числе для `READ_ONLY`.
- До успешного gate разрешены только проверка Git root, результат guard,
  канонический указатель и legacy marker. Ошибка означает
  `BLOCKED_WRONG_WORKSPACE` и остановку.
- Физический canonical path стабилен: `C:\Users\edwat\SupplyDesk`.
  Branch — `task-dependent`; для worktree/CI используется явный
  `-ExpectedRoot`.
- Legacy `AGENTS.md`, `CLAUDE.md`, `ai/AI_CONTRACT.md` и marker обновлены
  локально. Это recovery safety boundary, не синхронизация старого checkout.
- Добавлены 5 статических governance tests; всего guard-focused: `8/8`.

## Canary 1

Neutral prompt не называл tools/skills и просил только оценить текущую
структуру проекта.

| Проверка | Результат | Доказательство |
|---|---|---|
| Codex legacy | `PASS` | `assert_workspace.ps1` вернул `BLOCKED_WRONG_WORKSPACE`, child остановился до Git/DB/process/code-rot анализа |
| Codex canonical | `PASS` | guard вернул `WORKSPACE_GUARD: PASS`, child продолжил read-only-аудит и сам выбрал достаточные диагностические средства |
| Claude legacy post-fix | `NOT VERIFIED` | CLI завершился с `API Error: ... empty or malformed response (HTTP 200)`, usable trace отсутствует |
| Claude canonical post-fix | `NOT VERIFIED` | та же API 200 ошибка, usable trace отсутствует |
| Claude legacy pre-fix | `FAIL_REPRODUCED` | фактический trace запустил root audit/subagents вместо hard stop; это был диагностический запуск до local legacy adapter fix |

`LEGACY_CODE_ROT_EXECUTED: NO` в post-fix Codex legacy canary. Canaries 2–4
не запускались. Claude post-fix нельзя честно объявить PASS без usable trace.

## Что проверено

- Workspace guard: canonical `PASS`; arbitrary/legacy root `BLOCKED_WRONG_WORKSPACE`.
- `python -m unittest tests.diagnostics.test_workspace_guard -v`: `8/8 OK`.
- Official `tests/run-tests.ps1 -Diagnostics`: `77/77 OK`, failures `0`,
  errors `0`, skipped `0`.
- `python ai/tools/validate_vibecoding.py`: `PASS`.
- `python ai/tools/validate_docs.py`: `PASS`.
- `python ai/tools/validate_state.py`: `PASS`.
- `python ai/tools/validate_traceability.py`: `PASS`, `21/21`.
- `scripts/doctor.ps1 -Plan`: `PASS`, read-only plan.
- `git diff --check`: `PASS`.
- Product code, UI, API, database, migrations, runtime and mail data: not
  changed by this task.

## Не проверено / ограничения

- Claude behavioral cold-start after the fix: `NOT VERIFIED` because the
  external CLI returned malformed HTTP 200 responses in both contexts.
- Full product test suite, browser smoke test, runtime HTTP/API and FULL CI:
  intentionally not run by task scope.
- The legacy safety files are local outside the canonical Git tree and are not
  included in the published commit. They remain recoverable from the backup
  directory created before editing.

## Rollback

The canonical change is one task-scoped commit; revert that commit if the
policy change must be withdrawn. Restore the legacy files from
`C:\Users\edwat\AppData\Local\Temp\SupplyDesk-cold-start-gate-backup-20260903\legacy`
only after an explicit owner decision. No project file was deleted.

## Delivery

- Candidate implementation commit: `10b7922df966f638839ff93eda7668d319c257a7`
  before closeout amend.
- Final commit hash, remote SHA and FAST/control CI result are verified in the
  owner response after the final commit; this report is committed before the
  one authorized normal push so no second publication is needed.
