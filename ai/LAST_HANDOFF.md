---
document_id: HANDOFF-003
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
based_on_commit: cc3cd3bea7e4f53a2e25a6ba208d7e94b0859e30
---

# Last Handoff

This handoff records the canonical workspace guard V1 implementation. The
publication commit is recorded by Git history, not copied into this metadata.

## Цель

Закрепить техническую защиту от работы Codex/project tooling в неправильном
checkout, остановить подтверждённый legacy backend и сохранить explicit Git
worktree/CI support.

## Что изменено

- Added `scripts/assert_workspace.ps1` with canonical default and exact
  `-ExpectedRoot` override support; it never changes directory, branch or files.
- Integrated the guard into Doctor, bootstrap/recovery, test setup/runner and
  safe-runtime start/stop wrappers; CI supplies `$env:GITHUB_WORKSPACE`.
- Added three focused governance tests covering canonical/default behavior,
  legacy rejection and explicit worktree acceptance/mismatch.
- Replaced local-state placeholders with the confirmed canonical and legacy
  paths; added the durable workspace-boundary decision.
- Confirmed PID 15912 belonged to the legacy OneDrive checkout and stopped only
  that process. No legacy file, database, lock or session file was changed.

## Что проверено

- Canonical workspace guard: `WORKSPACE_GUARD: PASS`, exit `0`.
- Legacy workspace: `BLOCKED_WRONG_WORKSPACE`, exit `1`.
- Explicit matching worktree: `WORKSPACE_GUARD: PASS`; wrong explicit root:
  `BLOCKED_WRONG_WORKSPACE`.
- Governance tests: `3/3 PASS`.
- Doctor, bootstrap, test setup, safe-runtime start/stop `Plan` modes passed;
  no backend/frontend/Playwright process was started.
- PID 15912 was stopped and was absent on post-stop verification.

## Что не прошло

Nothing failed in the focused guard/control scope. Backend, frontend and
Playwright acceptance were intentionally not run; they are `NOT_NEEDED` for
this control-only task and are not evidence about product behavior.

## Что не проверено

NOT VERIFIED: remote CI proof for this new revision, live external providers,
real mail, production database behavior, branch protection and unlisted CI
tools remain outside this task. The guard tests exercise local PowerShell/Git
behavior, not remote runner execution.

## Текущее состояние runtime

No canonical or live runtime was left running. The previously confirmed old
legacy backend PID 15912 is stopped; no test runtime was started in this task.

## Следующий рациональный шаг

Local acceptance and final validators are complete; create the Task-ID commit
on the isolated branch. Leave push unperformed unless explicitly requested.

## Не повторять

Do not use the legacy OneDrive checkout for development, do not run real mail,
do not modify protected local data, do not run backend/frontend/Playwright for
this task, do not force-push, and do not add a second acknowledgement to an
intermediate message.
