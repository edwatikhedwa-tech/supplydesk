# TASK-DIAGNOSTIC-CONTROL-PLANE-V1-20260901

STATUS: PASS_WITH_LIMITATIONS

Scope: a separate worktree and branch from governance HEAD
`6687fa4289d8f65c47a34e8b7124e113cb3201e6`. `DOC_IMPACT=YES` for the
operational/product documentation contract; application behavior, frontend
source, API, database, migrations and mail transport were not changed.

## A Capabilities

TOTAL `19` / CONFIRMED `17` / PARTIAL `2` / NOT VERIFIED `0`.

The capability map is evidence-backed by routes, component files and existing
tests. The two partial entries are database/runtime-dependent capability
surfaces whose current local environment was not available to this worktree.

## B Requirements

ACTIVE `21` / DRAFT `1` / SAFETY `7` / OPERATIONAL `3`.

There are 12 functional active requirements. `REQ-DIAG-003` is operational
and DRAFT; it is not accepted as a product contract.

## C Traceability

- Requirements with automatic capability linkage: `21/21` active.
- Critical active requirements with a verification path: `11/11`.
- Active requirements linked to a diagnostic check: `21/21`.
- Active requirements with test evidence: `21/21`.
- Active requirements linked to a business rule: `14/21`.
- Validator: `python ai/tools/validate_traceability.py --root .` → `PASS`,
  `TRACE-001..008 PASS`, 22 matrix rows.

Unknown links fail the validator; active requirements must be `ACCEPTED`, and
the DRAFT repair requirement cannot satisfy an active contract gate.

## D Tests

- Backend inherited control baseline: `373 passed, 1 skipped, 0 failed, 0
  errors`.
- Current backend regression: `python -m pytest tests -q --tb=short` could not
  start because this environment has no `pytest`; `tests/run-tests.ps1` is
  absent. Current backend result is `NOT VERIFIED`, not a product pass.
- Old PASS→FAIL: `0` and new errors: `0` are inherited comparison evidence;
  no current rerun was available to establish a new comparison.
- New diagnostic tests: `12 passed` with
  `python -m unittest discover -s tests/diagnostics -v`.
- Frontend inherited baseline: `npm ci`, typecheck and build PASS; lint PASS
  with 8 warnings. Current frontend gates were not rerun in this worktree.
- Browser inherited public shell: `8 passed`; current browser acceptance was
  not rerun. No UI source changed, so visual screenshot acceptance was not
  applicable to this control-plane task.

## E Doctor

- Before: existing doctor coverage was approximately `30%` by the task brief;
  this value was not treated as a measured current metric.
- After: `10/10` DOC contracts are present in
  `scripts/diagnostics/diagnostic_contract.yaml` and implemented by the
  runner. The observed DryRun result was: `4 PASS`, `1 WARNING` (dirty
  worktree), `2 ENVIRONMENT_GAP` (database and HTTP), and `3 NOT VERIFIED`
  (frontend gates, backend suite and browser were opt-in).
- `scripts/doctor.ps1 -Plan` → exit `0`.
- `scripts/doctor.ps1 -DryRun` → exit `2` (`NOT_VERIFIED`) and wrote only
  external machine output to
  `C:\Users\edwat\AppData\Local\Temp\supplydesk-diagnostics\latest-doctor.json`.
- `-Apply` was not executed. In V1 it is a compatibility label that delegates
  to the same read-only runner; it does not mutate state.
- Exit contract: `0` pass/warning, `1` product failure, `2` environment gap or
  incomplete evidence, `3` safety blocker, `4` internal diagnostic error.

## F Failure modes

Catalogued `19/19`; with a diagnostic check `19/19`; with a runbook `19/19`;
automatic recovery allowed `0/19`; human approval required `19/19`.

Frontend failures remain distinct as `INSTALL_FAIL`, `TYPECHECK_FAIL`,
`LINT_FAIL`, `BUILD_FAIL`, `BROWSER_FAIL`, `ACCESSIBILITY_FAIL` and
`OVERFLOW_FAIL`. Database absence is an environment gap. Provider/migration/
production mutation is a safety block.

## G Runbooks

- `docs/operations/runbooks/RUNBOOK-DATABASE.md`
- `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`
- `docs/operations/runbooks/RUNBOOK-FRONTEND.md`
- `docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md`
- `docs/operations/runbooks/RUNBOOK-MAIL-PROVIDER.md`
- `docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md`

## H Repair foundation

Foundation contract: `YES` — `ai/repair-agent/REPAIR_AGENT_CONTRACT.md`.
Repair agent implementation: `NO`. Autonomous repair: `NO`.

## I Safety

REAL EMAIL `NO`; DB MIGRATION `NO`; CANONICAL DB WRITE `NO`; APP LOGIC `NO`;
SECRETS `NO`; FORCE PUSH `NO`; MERGE `NO`.

The runner uses standard-library static checks and read-only SQLite access. It
does not instantiate `MailRepository`, open SMTP/IMAP, call provider adapters,
read secret values or write diagnostic output inside the repository by default.

## Verification commands

```text
python -m unittest discover -s tests/diagnostics -v                 PASS (12)
python ai/tools/validate_docs.py --root .                          PASS
python ai/tools/validate_state.py --root .                         PASS
python ai/tools/validate_traceability.py --root .                  PASS
git diff --check                                                     PASS
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1 -Plan PASS (0)
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1 -DryRun NOT VERIFIED (2)
python -m pytest tests -q --tb=short                            ENVIRONMENT GAP
```

## Commits and publication

Logical commits before final state close:

- `0f4572c` — capability, requirement, business-rule and operations model.
- `0c7417c` — diagnostic runner, contracts, tests, doctor and traceability.

Final state/report commit and remote branch verification are recorded after
the close gate. No merge or default-branch change is performed automatically.
