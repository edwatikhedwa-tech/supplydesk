---
document_id: TASK-LOCK-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: f2e707ac9988223dc87f242d53df837d70ddca5f
---

# Active Task

Task ID: `TASK-REPRODUCIBLE-TEST-RUNTIME-V1-20260901`
Agent: `Codex`
Mode: `CLOSE`
Started: `2026-09-01`
Scope: `reproducible offline test environment, safe disposable runtime, backend/frontend/browser acceptance and profile-aware diagnostics`
Allowed files: `requirements-test.txt`, `.gitignore`, `tests/run-tests.ps1`, `tests/diagnostics/**`, `scripts/run_test_suite.py`, `scripts/setup_test_env.ps1`, `scripts/start_test_runtime.ps1`, `scripts/stop_test_runtime.ps1`, `scripts/test_runtime_entry.py`, `scripts/diagnostics/**`, `docs/testing/TEST_ENVIRONMENT.md`, `PROJECT_MANIFEST.yaml`, `ai/**`
Status: `READY FOR COMMIT/PUSH — acceptance complete; final normal push remains`
Last update: `2026-09-01T16:08:00Z`

## Цель

Дать чистому checkout воспроизводимую безопасную OFFLINE_TEST-среду без
приватного `.env`, канонической SQLite, реального SMTP/IMAP и реальных писем.

## Границы

Продуктовый код, фронтенд-код, каноническая база, миграции и настройки
production не изменяются. Поддерживаются только отдельный test-venv,
документированные runners/bootstrap, disposable SQLite, безопасный runtime,
диагностика и состояние проекта.

## Acceptance

Нужны фактические проверки backend regression, frontend `npm ci`/typecheck/lint/build,
safe runtime HTTP/API, real-route Playwright, profile-aware Doctor, validators,
git diff check и отдельный commit с Task ID. Реальная почта и внешний live-provider
acceptance остаются запрещёнными.

## Следующий шаг

Создать commit с Task ID, выполнить обычный push отдельной ветки, затем
обновить этот sentinel в `IDLE` и зафиксировать remote SHA.

