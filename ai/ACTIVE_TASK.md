---
document_id: TASK-LOCK-004
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
based_on_commit: f13dad6dc2461ef6dc50242f7fc075895f2a4603
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `IDLE`
Started: `2026-09-01`
Scope: `VibeCoding control policy, tool registry, validator and diagnostics`
Allowed files: `AGENTS.md`, `CLAUDE.md`, `PROJECT_MANIFEST.yaml`, `ai/**`,
`tests/diagnostics/test_vibecoding_governance.py`,
`ai/tools/validate_docs.py`; no product/data/runtime changes
Status: `IDLE — TASK-VIBECODING-CONTROL-POLICY-V1-20260901 complete and branch pushed`
Last update: `2026-09-01T19:13:54Z`

## Цель

Создать единую canonical policy VibeCoding V1, factual registry доступных
инструментов и read-only validation для обязательного AI-agent workflow.

## Границы

Product behavior, frontend UI, API, database, migrations, mail data, runtime,
secrets, dependency installation, legacy workspace and quarantine are not
changed.

## Acceptance

VibeCoding validator, diagnostics, documentation/state/traceability validators,
Doctor Plan, diff check and security staging audit must pass. Full product
regression is not required unless runtime or test-runner behavior changes.

## Следующий шаг

Активной задачи нет. Policy V1 опубликована; следующая работа должна
начинаться из canonical checkout с чтения policy и registry.

