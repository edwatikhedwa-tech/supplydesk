---
document_id: TASK-LOCK-005
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
based_on_commit: 84083130e3a75eb5a6d4fa83957db6760724379b
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `CLOSE`
Started: `2026-09-02`
Scope: `shared architecture/lifecycle contract, browser auth handoff instructions, minimal lifecycle registry; no product/CI/root changes`
Allowed files: `ai/AI_CONTRACT.md`, `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/DECISIONS.md`, `ai/LAST_HANDOFF.md`, `ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`, `ai/reports/`, `docs/architecture/`, `docs/operations/runbooks/RUNBOOK-FRONTEND.md`; no product/data/runtime/CI changes
Status: `IDLE — policy implementation and local checks PASS; same-task PUBLISH gates pending`
Last update: `2026-09-02`

## Цель

Добавить минимальные cross-cutting правила размещения, жизненного цикла
компонентов и безопасной локальной browser-auth handoff в одном
`DELIVERY_MODE: PUBLISH` цикле без изменения product code.

## Границы

Product behavior, frontend UI, API, database schema/data, migrations, mail
data, secret values, quarantine, snapshots, legacy checkout, dependencies,
runtime, CI architecture and Workspace Guard behavior are not changed. Existing
Finding-009 evidence is reused; candidate archives are not reread or altered.
Backend, frontend, Playwright, FULL CI and forbidden audit tools are not run.

## Acceptance

Architecture placement/lifecycle rules, the component registry, browser auth
handoff instructions and public `/login` failure classification are added;
delivery includes one commit, ordinary push, remote SHA confirmation and FAST
CI; product code, current browser tests, CI routing, Knip and root structure
are unchanged.

## Следующий шаг

After successful FAST CI, record publication as complete and keep
`LOCAL_ARCHIVE_SECRET_RETENTION` as a separate deferred security action. Do not
create another closeout task.

