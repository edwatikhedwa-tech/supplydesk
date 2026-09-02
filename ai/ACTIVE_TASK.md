---
document_id: TASK-LOCK-005
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
based_on_commit: cc3cd3bea7e4f53a2e25a6ba208d7e94b0859e30
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `CLOSE`
Started: `2026-09-02`
Scope: `canonical workspace guard, control-tooling integration and governance tests`
Allowed files: `scripts/**`, `tests/run-tests.ps1`, `tests/diagnostics/**`,
`.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `ai/**`,
`PROJECT_MANIFEST.yaml`, `docs/architecture/**`, `docs/operations/**`,
`docs/testing/**`; no product/data/runtime changes
Status: `IDLE — closed with remote CI proof not verified`
Last update: `2026-09-02T08:34:24Z`

## Цель

Защитить Codex/project tooling от работы в неправильном checkout, сохранить
explicit Git worktree/CI support и остановить подтверждённый legacy backend.

## Границы

Product behavior, frontend UI, API, database schema/data, migrations, mail
data, secrets, quarantine and unrelated dependencies are not changed. Backend,
frontend and Playwright acceptance are not run.

## Acceptance

Canonical and legacy guard cases, explicit worktree cases, control-tooling
integration, state/documentation validators and Git safety checks pass. The
confirmed PID 15912 is stopped without touching legacy files.

## Следующий шаг

Local guard/governance acceptance is complete. Commit the closeout state on the
task branch; push remains an explicit owner action.

