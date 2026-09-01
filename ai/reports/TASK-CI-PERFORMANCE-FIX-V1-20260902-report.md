# TASK-CI-PERFORMANCE-FIX-V1-20260902 — CI performance fix report

## Status

`PASS_WITH_PERFORMANCE_LIMITATION`

The FAST-first architecture and normal-push routing are implemented and
independently exercised on GitHub Actions. The preserved FULL backend/browser
acceptance path remains available, but the current Windows hosted runner does
not complete the existing full suite within the observed performance budget.
This is recorded as `CI_PERFORMANCE_FAILURE`; no timeout inflation was used.

## Scope

Changed only CI/control-plane policy, deterministic change classification,
governance validation, the dedicated real-route browser smoke test, and related
diagnostic fixtures/tests. Product logic, frontend UI, API behavior, database,
migrations, mail data, credentials, environments and runtime state were not
changed.

Placeholders used by policy: `<CANONICAL_WORKSPACE>`, `<LEGACY_WORKSPACE>` and
`<QUARANTINE_ROOT>`. No secret values, database contents, real mail evidence or
absolute private paths are included here.

## Before measurement

The previous push run `33557063917` on the old CI shape showed the failure mode
that motivated this task:

| Job | Observed result |
| --- | --- |
| Fast Control | 57s, PASS |
| Change Classification | 13s, PASS |
| Frontend | 1m54s, PASS |
| Full Control | 14s, PASS |
| Browser | 24m14s, FAIL; 2 failed and 6 passed after 8 viewport tests |
| Backend | 25m13s, cancelled |

The workflow therefore spent roughly 26 minutes of wall-clock time on a
normal push while expensive full jobs were running. Increasing test or job
timeouts would have hidden the problem rather than fixing feedback speed.

## Implemented model

- `FAST`: policy/state/traceability/diagnostics/Git safety in Fast Control and
  deterministic path classification.
- `FOCUSED`: Backend Fast for ordinary backend changes, Frontend for frontend
  changes, and one real-route Browser Smoke viewport for frontend/browser
  changes on a normal push.
- `FULL`: Backend Full, Browser Full, Frontend and Doctor for pull requests,
  high-risk changes, explicit `workflow_dispatch` with `FULL`, and the weekly
  schedule. Full browser keeps the canonical Playwright configuration with
  four workers; `--workers=1` and `--timeout=180000` are not used.
- `CI Summary`: always publishes the selected/skipped jobs and their result
  states.
- Concurrency cancels obsolete runs on the same ref.
- The fast smoke uses the real `/login` route, checks HTTP 200, visible UI,
  the Mail.ru interaction message and page errors, and uses no route mocks.
- Diagnostics are classified as control-plane tests, not backend product
  tests. A regression test prevents `tests/diagnostics/` from routing to
  Backend Full.

## Remote evidence

### Corrective push / remote FAST proof

Run `33562406201` on final configuration commit
`2b860a54e89c062126f872635ea721537c0594dc`:

- Trigger: normal `push`.
- Profile: `FAST`.
- Wall-clock from run creation to CI Summary: 1m22s.
- Fast Control: 54s, PASS.
- Change Classification: 15s, PASS; `risk=HIGH` because the classifier itself
  changed, `backend=false`, `backend_full=false`, `frontend=false`,
  `browser=false`, `browser_full=false`, `doctor_required=true`.
- Full Control: 13s, PASS.
- Backend Fast, Backend Full, Frontend, Browser Smoke and Browser Full: SKIP.
- CI Summary: PASS.

This is the required remote FAST proof that a focused control-plane push does
not start the full backend or full browser suites. URL:
https://github.com/edwatikhedwa-tech/supplydesk/actions/runs/33562406201

### Explicit FULL proof

Run `33562558816` on the same final configuration commit:

- Trigger: explicit `workflow_dispatch`, profile `FULL`.
- Wall-clock from run creation to CI Summary: 13m06s.
- Change Classification: 17s, PASS.
- Fast Control: 1m01s, PASS.
- Full Control: 19s, PASS.
- Frontend: 1m48s, PASS; lint warnings remained warnings, with no errors.
- Browser Full: 11m17s, FAIL. The log reports `Running 8 tests using 4
  workers`; all eight existing viewport scenarios reached 60-second test
  timeouts in screenshot/Axe work. The failure was not repaired by inflating
  timeouts.
- Backend Full: 11m49s, cancelled after the run was stopped. Its output showed
  continued passing tests but no final test total was emitted, so the backend
  full total is `NOT_VERIFIED` for this remote proof.
- Browser Smoke and Backend Fast: SKIP as expected for profile `FULL`.
- CI Summary: PASS as a reporting job; overall workflow was cancelled because
  the required full acceptance jobs were not green.

URL:
https://github.com/edwatikhedwa-tech/supplydesk/actions/runs/33562558816

### Diagnostic architecture run

The first push of the architecture commit, run `33561078177`, was stopped
after the same Windows runner behavior. It also exposed that the broad
`^tests/` mapping treated diagnostic tests as backend changes. That issue was
fixed in `2b860a5`; the corrective FAST proof above confirms the repaired
routing. The diagnostic run is not counted as final acceptance.

## Local verification

- Classifier and governance tests: `12/12 PASS` before the final mapping
  correction; classifier tests: `9/9 PASS` after it.
- Full diagnostics: `39/39 PASS` after the correction.
- Quick official backend runner: `50 tests, 0 failures, 0 errors, 0 skipped`.
- `python ai/tools/validate_vibecoding.py`: PASS.
- `python ai/tools/validate_docs.py`: PASS, GATE-001..009.
- `python ai/tools/validate_state.py`: PASS.
- `python ai/tools/validate_traceability.py`: PASS, 21/21 behavioral links.
- `git diff --check`: PASS.
- `tests/run-tests.ps1 -Quick`: PASS.
- `scripts/doctor.ps1 -Plan`: PASS and read-only.
- Local real-route Browser Smoke: `1 passed` in 1.7s against the disposable
  OFFLINE_TEST runtime; the runtime was stopped afterwards.
- Existing local full public-shell evidence remains `8/8` with the canonical
  four-worker configuration; the hosted Windows runner result is a separate
  performance/environment limitation.

## Performance verdict

`FAST`: PASS. The observed corrective push completed in 1m22s, below the
five-minute initial maximum and with no unrelated full backend/browser job.

`FULL`: PRESERVED but `NOT_VERIFIED` as green on the hosted Windows runner.
The measured 13m06s wall-clock is within the broad high-risk observation
window, but Browser Full failed and Backend Full did not emit a final total.
The concrete bottleneck is existing Playwright screenshot/Axe execution on the
Windows hosted runner, not a missing full-test path.

`TIMEOUT ESCALATION`: STOPPED. No further corrective remote iteration is
authorized by this task. The next investigation should be a separately
scoped runner/browser performance task, not another timeout increase.

`PRODUCT CODE CHANGED`: NO.

`GITHUB ACTIONS REGISTRY`: remains `NOT_VERIFIED` because the required full
remote proof is not green. The workflow file is present and its FAST routing
is independently proven, but policy does not convert a partial result into
`CONFIGURED`.

## Security and rollback

No protected path was staged: `.env*`, `mail-data`, databases, credentials,
real mail fixtures, quarantine contents, runtime state and generated local
artifacts remained outside the change. No force-push, merge or default-branch
change occurred.

Rollback is ordinary Git history: revert the two task commits on this branch
or restore the branch to its pre-task remote commit. Do not alter the legacy
OneDrive checkout or quarantine as part of rollback.

## References

- Workflow: `.github/workflows/ci.yml`
- Classifier: `scripts/ci/classify_changes.ps1`
- Mapping: `scripts/ci/change_groups.json`
- Smoke test: `frontend/tests/fast-browser-smoke.spec.ts`
- Policy: `ai/VIBECODING_RULES.md`
- Registry: `ai/VIBECODING_TOOL_REGISTRY.yaml`
