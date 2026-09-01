---
document_id: TASK-LOCK-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: e36942926fc4e9a5c31bdd015b3abdd25480c8fa
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `IDLE`
Started: `2026-09-01`
Scope: `safe physical cleanup Batch 1, legacy workspace isolation, quarantine and acceptance evidence`
Allowed files: `ai/**` only in the Git branch; physical actions were limited to
the explicit external quarantine/delete allowlist
Status: `IDLE — TASK-SAFE-PHYSICAL-CLEANUP-BATCH1-20260901 complete and branch pushed`
Last update: `2026-09-01T19:20:00Z`

## Цель

Создать отдельную canonical-копию, вынести доказанные legacy review/backup/
export artifacts в retained quarantine и удалить только воспроизводимый cache,
не трогая код, `.env`, базу или пользовательские mail data.

## Границы

Продуктовый код, фронтенд-код, каноническая база, миграции и настройки
production не изменяются. Quarantine остаётся вне Git и не удаляется навсегда;
три unknown-review пункта остаются на месте.

## Acceptance

Проверены before/after manifests, physical allowlist, clean canonical checkout,
backend/frontend/browser acceptance, Doctor, validators, reference search и
security boundary. Реальная почта и внешний live-provider acceptance остаются
запрещёнными.

## Следующий шаг

Активной задачи нет. Проверка quarantine и permanent purge остаются отдельным
решением владельца проекта.

