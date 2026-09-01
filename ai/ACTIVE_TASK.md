---
document_id: TASK-LOCK-004
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
based_on_commit: f13dad6dc2461ef6dc50242f7fc075895f2a4603
---

# Active Task

Task ID: `TASK-VIBECODING-CONTROL-POLICY-V1-20260901`
Agent: `Codex`
Mode: `IMPLEMENT`
Started: `2026-09-01`
Scope: `VibeCoding control policy, tool registry, validator and diagnostics`
Allowed files: `AGENTS.md`, `CLAUDE.md`, `PROJECT_MANIFEST.yaml`, `ai/**`,
`tests/diagnostics/test_vibecoding_governance.py`,
`ai/tools/validate_docs.py`; no product/data/runtime changes
Status: `IN_PROGRESS — governance-only implementation`
Last update: `2026-09-01T19:09:33Z`

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

Complete the governance acceptance, write the report, commit with this Task ID,
push the task branch and verify its remote ref.

