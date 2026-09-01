---
document_id: TASK-LOCK-003
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
based_on_commit: a228321401270b69c9ac2f07f76435e246b6f5c3
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `IDLE`
Started: `2026-09-01`
Scope: `final repository hygiene acceptance and canonical closeout`
Allowed files: `ai/**`, `docs/DOCUMENTATION_POLICY.md` and
`PROJECT_MANIFEST.yaml`; no product/data/runtime changes
Status: `IN PROGRESS — acceptance checks complete; final publication pending`
Last update: `2026-09-01T18:36:54Z`

## Цель

Финально подтвердить состояние canonical SupplyDesk и закрыть большую фазу
repository cleanup без нового массового удаления и без изменения продукта.

## Границы

Продуктовые маршруты, фронтенд UI, каноническая база, миграции, mail data и
настройки production не изменяются. Quarantine остаётся вне Git и не
удаляется навсегда.

## Acceptance

Acceptance evidence записана в финальный report; permanent purge не
выполнять. Перевести sentinel в IDLE только после normal push и remote-ref
verification.

## Следующий шаг

Проверки завершены; выполнить только публикацию документации/report на final
branch, затем перевести sentinel в IDLE.

