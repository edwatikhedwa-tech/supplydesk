---
document_id: TASK-LOCK-006
status: CURRENT
canonical: false
owner: Codex
updated_at: 2026-09-02
based_on_commit: e7e1873160f26faaa9a6385c1b8b14c6c96a540c
---

# Active Task

Task ID: `TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902`
Agent: `Codex`
Mode: `EXTEND`
Started: `2026-09-02`
Scope: `MagicRings reduced-motion lifecycle, public-shell DOM readiness, scoped Browser Full reduced-motion emulation, local/remote acceptance and state evidence; no auth/backend/worker reduction/Knip changes`
Allowed files: `frontend/src/components/MagicRings.tsx`, `frontend/tests/frontend-audit.spec.ts`, `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`, `ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`, `ai/reports/`; Playwright config, dependencies, database, runtime and unrelated frontend files are protected
Status: `IN_PROGRESS — deterministic readiness and reduced-motion remediation`
Last update: `2026-09-02`

## Цель

Исправить нестабильность Browser Full public shell: убрать readiness-зависимость
от `networkidle`, остановить непрерывный Three.js render loop при
`prefers-reduced-motion: reduce`, сохранить нормальную анимацию и подтвердить
результат локально и на GitHub Actions.

## Границы

Auth handoff, OAuth, backend/API, database/schema/data, migrations, mail data,
secrets, quarantine, legacy checkout, dependencies, workers, Knip, login visual
design and unrelated browser tests are not changed. No test-only product flag,
query parameter or CI-only environment branch is introduced. Browser Full must
remain on four workers.

## Acceptance

Public-shell readiness uses a UI locator; MagicRings supports reduced motion
without continuous RAF scheduling while normal mode remains animated; scoped
Browser Full passes locally and remotely; delivery includes one commit,
ordinary push, remote SHA confirmation, FAST CI and required Browser Full.

## Следующий шаг

After required remote acceptance, record publication as complete, set this
sentinel to IDLE, and keep unrelated deferred security findings unchanged.

