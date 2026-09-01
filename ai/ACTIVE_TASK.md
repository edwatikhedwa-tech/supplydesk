---
document_id: TASK-LOCK-002
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: d2ceef3
---

# Active Task

Task ID: `TASK-SAFE-CLEANUP-BATCH2-20260901`
Agent: `Codex`
Mode: `CLOSEOUT`
Started: `2026-09-01`
Scope: `canonical deep hygiene, resolved unknowns, evidence-gated Python cleanup and offline acceptance`
Allowed files: `ai/**` plus the explicitly approved Python hygiene bindings;
physical actions were limited to the three external quarantine moves
Status: `CLOSEOUT — offline acceptance complete; final validators and remote push pending`
Last update: `2026-09-01T20:50:00Z`

## Цель

Провести безопасную глубокую очистку canonical SupplyDesk без потери кода,
секретов, базы или пользовательских mail data; сохранить спорное в quarantine.

## Границы

Продуктовые маршруты, фронтенд UI, каноническая база, миграции и настройки
production не изменяются. Quarantine остаётся вне Git и не удаляется навсегда;
три unknown-review пункта перемещены туда с сохранением hash.

## Acceptance

Проверены reference/process/hash gates, duplicate audit, `.gitignore` matrix,
backend/frontend/browser acceptance, Doctor и security boundary. Финальные
state/report validators и remote ref verification выполняются при closeout.

## Следующий шаг

После closeout активной задачи не будет. Проверка содержимого quarantine и
permanent purge остаются отдельным решением владельца проекта.

