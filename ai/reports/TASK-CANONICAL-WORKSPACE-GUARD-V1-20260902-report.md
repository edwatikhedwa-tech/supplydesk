# TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902 — workspace guard report

## Status

`PASS_WITH_LIMITATIONS`

The local workspace boundary, legacy rejection, explicit worktree support and
control-entrypoint integration are implemented and tested. Remote CI proof for
the changed workflow was not run because publication was not requested.

## Scope

Changed only the workspace guard, control/test/runtime wrappers, CI checkout
root propagation, governance instructions, manifest/registry, operational
documentation, state records and focused governance tests. Product logic, UI,
API, database schema/data, migrations, mail data, secrets, environment files,
runtime state, quarantine and legacy checkout files were not changed.

Task ID: `TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902`

`DOC_IMPACT=YES`: the operational contract and current local workspace facts
changed, so `ai/CURRENT_STATE.md`, handoff, decision, report, logs, manifest and
affected runbooks were updated.

## Confirmed preflight and legacy process

- `Get-Location`, `git rev-parse --show-toplevel`, branch, HEAD and
  `git status --short` confirmed `C:\Users\edwat\SupplyDesk` before changes.
- PID `15912` existed as `python.exe`; command-line inspection alone did not
  prove its directory. A read-only process-parameter probe confirmed the
  legacy OneDrive path and not the canonical path.
- `Stop-Process -Id 15912 -Force` stopped only that PID. A post-stop process
  lookup confirmed it was absent. No legacy runtime, SQLite, lock or session
  file was read or changed.

## Workspace policy

- Default local development root: `C:\Users\edwat\SupplyDesk`.
- Legacy root: `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS`;
  recovery-only and not a development checkout.
- Intentional worktrees and CI use the exact absolute
  `scripts/assert_workspace.ps1 -ExpectedRoot <absolute path>` override.
- Arbitrary `SupplyDesk_*` discovery is forbidden.

## Implementation

- `scripts/assert_workspace.ps1` runs `git rev-parse --show-toplevel`,
  normalizes paths, compares with a Windows-safe case policy and exits `0` on
  `WORKSPACE_GUARD: PASS`, or non-zero with `BLOCKED_WRONG_WORKSPACE`,
  `EXPECTED_ROOT` and `ACTUAL_ROOT` on mismatch.
- The guard never changes directory, branch or files.
- Doctor, bootstrap, recovery, test setup, test runner and safe-runtime
  start/stop wrappers invoke it before their work. CI passes
  `$env:GITHUB_WORKSPACE` explicitly so clean hosted checkouts remain usable.
- Agent instructions and the VibeCoding policy require the guard before
  mutation, runtime start, build, artifact-producing test, commit or push.

## Acceptance evidence

| Scenario | Result |
|---|---|
| Canonical default root | `WORKSPACE_GUARD: PASS`, exit `0` |
| Legacy default root | `BLOCKED_WRONG_WORKSPACE`, exit `1` |
| Matching explicit temporary Git checkout | `WORKSPACE_GUARD: PASS`, exit `0` |
| Mismatching explicit root | `BLOCKED_WRONG_WORKSPACE`, exit `1` |
| Doctor `-Plan` | PASS, exit `0` |
| Bootstrap `-Plan` | PASS, exit `0` |
| Test setup `-Plan` | PASS, exit `0` |
| Safe runtime start `-Plan` | PASS, exit `0` |
| Safe runtime stop `-Plan` | PASS, exit `0` |
| Recovery `-Plan` | PASS, exit `0` |
| Test runner invoked from legacy root | `BLOCKED_WRONG_WORKSPACE`, exit `1` before test runner |
| Focused governance tests | `3/3 PASS` |

No backend, frontend or Playwright process was started.

## Verification and limitations

- `python -m unittest tests.diagnostics.test_workspace_guard -v`: `3/3 PASS`.
- `python -m unittest discover -s tests/diagnostics -v`: `49/49 PASS`.
- `python ai/tools/validate_vibecoding.py`: `PASS`, 36 registered tools.
- `python ai/tools/validate_docs.py`: `PASS`, GATE-001..009.
- `python ai/tools/validate_state.py`: `PASS`.
- `python ai/tools/validate_traceability.py`: `PASS`, 21/21 behavioral links.
- `git diff --check`: `PASS`.
- `doctor -Plan`, `bootstrap_supplydesk.ps1 -Plan`, `setup_test_env.ps1 -Plan`,
  `start_test_runtime.ps1 -Plan`, `stop_test_runtime.ps1 -Plan` and
  `recover_supplydesk.ps1 -Plan`: PASS.
- Legacy `doctor.ps1 -Plan`: `BLOCKED_WRONG_WORKSPACE`, exit `1`.
- Legacy `tests/run-tests.ps1 -Diagnostics` was blocked before the official
  runner started.
- The explicit staged-path review found `29` allowed files, no protected or
  product paths, `0` staged secret-literal findings and a clean staged diff.
  The final control-plane suite is complete before commit.
- Backend, frontend and Playwright acceptance: `NOT_NEEDED` for this explicit
  control-only task; this is not product behavior evidence.
- Remote CI execution and branch-protection status: `NOT_VERIFIED`; no push was
  authorized or performed.

## Product and security boundary

`PRODUCT_CODE_CHANGED: NO`. The final diff must remain within the approved
control/docs/tests allowlist. No secret values, `.env` content, database rows,
mail evidence, runtime data or quarantine content is included.

`FINAL_STATUS: PASS_WITH_LIMITATIONS`: all local required checks passed; remote
CI proof for the changed workflow was not run because push was not authorized.

## Rollback

Revert the single Task-ID commit on this branch, or restore the branch to its
pre-task commit after reviewing the diff. Do not delete or modify the legacy
checkout as rollback.

## References

- Guard: `scripts/assert_workspace.ps1`
- CI: `.github/workflows/ci.yml`
- Registry: `ai/VIBECODING_TOOL_REGISTRY.yaml`
- Canonical state: `ai/CURRENT_STATE.md`
