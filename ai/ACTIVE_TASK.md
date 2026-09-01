---
document_id: TASK-LOCK-005
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
based_on_commit: 9d3e58232230b276396f3bc127e2d937bed8482d
---

# Active Task

Task ID: `TASK-VIBECODING-CI-V1.1-20260901`
Agent: `Codex`
Mode: `IMPLEMENT`
Started: `2026-09-01`
Scope: `VibeCoding CI V1.1, change classification and governance updates`
Allowed files: `.github/workflows/ci.yml`, `scripts/ci/**`, `ai/**`,
`PROJECT_MANIFEST.yaml`, `tests/diagnostics/**`; no product/data/runtime changes
Status: `IN_PROGRESS — CI/control-plane implementation`
Last update: `2026-09-01T19:45:15Z`

## Цель

Настроить первый независимый GitHub Actions CI с FAST/FOCUSED/FULL/PERIODIC
профилями и детерминированной классификацией изменений.

## Границы

Product behavior, frontend UI, API, database, migrations, mail data, runtime,
secrets, quarantine and unrelated dependencies are not changed. Planned tools
are not installed.

## Acceptance

Local validators, diagnostics, classifier tests, Doctor Plan, diff check and
security staging audit must pass. One remote manual FULL workflow run must
prove Fast Control, Backend, Frontend, Browser and Full Control/Doctor.

## Следующий шаг

Complete local gates, publish the branch, dispatch one remote FULL run, verify
the remote conclusion and then close the task.

