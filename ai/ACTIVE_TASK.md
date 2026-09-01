---
document_id: TASK-LOCK-005
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
based_on_commit: 2b860a54e89c062126f872635ea721537c0594dc
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `IMPLEMENT`
Started: `2026-09-02`
Scope: `FAST-first CI performance routing, real-route smoke and remote proof`
Allowed files: `.github/workflows/ci.yml`, `scripts/ci/**`, `ai/**`,
`PROJECT_MANIFEST.yaml`, `tests/diagnostics/**`; no product/data/runtime changes
Status: `IDLE — closed with documented FULL runner limitation`
Last update: `2026-09-01T21:56:03Z`

## Цель

Остановить медленный full-on-push CI, доказать быстрый focused push path,
сохранить полный acceptance path и зафиксировать фактическое ограничение
hosted Windows runner.

## Границы

Product behavior, frontend UI, API, database, migrations, mail data, runtime,
secrets, quarantine and unrelated dependencies are not changed. Planned tools
are not installed.

## Acceptance

Local validators, diagnostics, classifier tests, Doctor Plan, diff check and
security staging audit pass. Remote FAST proof passes on the final routing;
explicit FULL selection is present and its hosted-runner failure is recorded
honestly as NOT_VERIFIED rather than hidden by timeout escalation.

## Следующий шаг

Task is closed after the report/state commit and normal push. A future
Playwright/Axe runner performance investigation requires a separate task; do
not increase timeouts or reuse this task for that work.

