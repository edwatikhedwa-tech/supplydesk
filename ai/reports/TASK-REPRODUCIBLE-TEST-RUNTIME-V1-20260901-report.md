# TASK: SUPPLYDESK REPRODUCIBLE SAFE TEST & RUNTIME ENVIRONMENT V1

STATUS: PASS_WITH_LIMITATIONS

Branch: `control/reproducible-test-runtime-v1-20260901`
Base: verified V1.1 remote HEAD `f9b0b66432f9e8650e87e5a89dd27a258a416e38`
Scope: reproducible Python test dependencies, official runners, disposable
SQLite, safe `OFFLINE_TEST` runtime, frontend/browser acceptance and
profile-aware diagnostics. Product behavior was out of scope.

## CLEAN CHECKOUT BOOTSTRAP:

PASS. A separate worktree was created from the verified V1.1 remote commit.
`scripts/setup_test_env.ps1 -Plan` was read-only; `-Apply` created only
`.venv-test` and installed `requirements-test.txt`. A clean frontend dependency
bootstrap with `npm ci --no-audit --fund=false` also passed. No global Python,
database, mailbox, Git or private environment file was created or modified by
the setup script.

## PYTHON TEST DEPENDENCIES:

`requirements-test.txt` is the test contract and references `requirements.txt`
for application imports. The audit found no `pytest`, `pytest-cov` or
`coverage` imports in the current Python tests. The official runner therefore
uses the standard-library `unittest` discovery and does not add an unjustified
test framework dependency.

## PYTEST DECLARED:

NO. `pytest` and `pytest-cov` are explicitly documented as `NOT_REQUIRED` for
the current suite; missing pytest is no longer a hidden machine prerequisite.

## OFFICIAL BACKEND RUNNER:

`tests/run-tests.ps1` delegates to `scripts/run_test_suite.py` and supports
safe default/full, quick and diagnostic modes. It never installs packages.
The runner removes inherited provider configuration and blocks all non-loopback
DNS/socket connections; fake provider unit paths remain testable without real
SMTP/IMAP.

## DISPOSABLE DB:

PASS. The safe runtime created and used only
`runtime/test-data/supplier.sqlite3`, applied schema migrations only to that
ignored disposable file, and seeded synthetic fixture data. The runtime marker
reported `database.kind=disposable_sqlite` and `database.canonical=false`.
Canonical `mail-data/supplier.sqlite3` was not opened for mutation.

## PRIVATE .ENV REQUIRED:

NO expected. The safe entrypoint imports `Config`/`SupplierApp` directly and
does not call the production `.env` loader. Synthetic values are supplied by
the process wrapper and no secret values were read or emitted.

## CANONICAL DB REQUIRED:

NO expected. `OFFLINE_TEST` rejects canonical `mail-data` paths before any
database open.

## REAL SMTP/IMAP REQUIRED:

NO. External providers are `fake/blocked`; real transport and email delivery
were not attempted. Negative tests reject real SMTP configuration.

## BACKEND FULL REGRESSION:

PASS. The official full runner completed `411` tests with `0` failures,
`0` errors and `1` skipped. The historical `373 passed, 1 skipped` figure is
retained only as a comparison baseline; the runner reports actual totals and
does not force that count.

## OLD PASS → FAIL:

0. No previously passing test was converted to a failure. The initial attempt
with a globally forced test kill-switch exposed 43 failures and 9 errors in
fake-provider unit paths; the harness was corrected to block real network/mail
while preserving those intentional fake-provider tests, after which the full
run passed.

## FRONTEND CLEAN INSTALL:

PASS. `npm ci --no-audit --fund=false` completed from an absent
`frontend/node_modules` state.

## TYPECHECK:

PASS. `npm run typecheck` exited `0`.

## LINT:

PASS with `0` errors and `8` warnings. The warnings are existing dependency or
React refresh-hygiene warnings; this task did not change frontend source.

## BUILD:

PASS. `npm run build` exited `0`; Vite built the frontend successfully.

## SAFE TEST RUNTIME:

PASS. `scripts/start_test_runtime.ps1 -Apply` started the real application on
`http://127.0.0.1:18000` with marker PID `19636`; the marker was ready and
declared `environment=test`, disposable SQLite, disabled outgoing mail,
fake/blocked providers, loopback-only networking, no private `.env` loading
and no real email. Root/API/error smoke passed, including `200`, `401` and
`404` cases. The process was stopped with the exact marker-aware stop script
after acceptance, so it is not currently running.

## PLAYWRIGHT REAL ROUTES:

PASS. `frontend/tests/frontend-audit.spec.ts -g "public shell" --workers=1`
passed across all `8` configured viewport projects against the safe runtime.
No visual product area was changed in this task, so a separate visual
regression artifact was not required.

## DOCTOR OFFLINE_TEST:

`WARNING`, exit `0`. Full dry-run executed all required checks, including the
411-test backend regression, frontend gates, disposable DB, safe runtime and
real-route Playwright evidence. The only warning was the expected dirty
working tree while this change set was being prepared. Machine evidence was
written outside the repository to the system temporary diagnostics path.

## DOCTOR LIVE_EXTERNAL:

Safety block, exit `3`. Automatic live-provider, external-network and real-mail
acceptance is intentionally not available through Doctor.

## BEHAVIORAL DIAGNOSTIC COVERAGE BEFORE:

0/21 active requirements.

## BEHAVIORAL DIAGNOSTIC COVERAGE AFTER:

6/21 active requirements are now behaviorally or runtime diagnosable offline:
4 `BEHAVIORAL` and 2 `RUNTIME`. All 21 active requirements are offline-eligible,
but eligibility is not claimed as proof for every behavior.

## HIDDEN MACHINE DEPENDENCIES:

No hidden dependency remained after clean bootstrap. The documented
prerequisites are Windows PowerShell, Python 3.11.x, Node/npm and the
Playwright Chromium binary for browser acceptance. Live provider credentials,
private `.env`, canonical database and external network are deliberately not
prerequisites. The 8 lint warnings and live-provider/authenticated real-mail
limitations remain explicit.

## PRODUCT CODE CHANGED:

NO. Only test tooling, diagnostic tooling, documentation, manifest and state
files changed; application, API, frontend source and mail provider code were
not edited.

## CANONICAL DATABASE CHANGED:

NO. The canonical database was not opened for mutation; only the ignored
disposable runtime DB was created and migrated.

## REAL EMAIL:

NO. No real SMTP/IMAP connection or message was attempted.

## MIGRATIONS:

NO production/canonical migrations. Schema migrations ran only against the
ignored disposable test database required by the safe runtime.

## SECRETS PUBLISHED:

NO. No secret values, credentials, cookies or private environment contents were
stored in the repository or emitted by machine-readable diagnostics.

## REMOTE PUSH:

PENDING at report drafting time; the dedicated branch is intended for a normal
non-force push after final validation. No merge or default-branch change is
authorized by this task.

## Проверено

- `python -m py_compile ...`: PASS for changed Python scripts and diagnostics.
- PowerShell parser: PASS for setup, start, stop, doctor and test-runner scripts.
- `python -m unittest discover -s tests\\diagnostics -v`: `25/25` PASS.
- `tests\\run-tests.ps1` full: `411` tests, `0` failures, `0` errors, `1` skipped.
- `npm ci`, `npm run typecheck`, `npm run lint`, `npm run build`: PASS; lint
  has 8 warnings.
- `npx playwright install chromium`: PASS; real-route public-shell: `8/8` PASS.
- HTTP smoke: `/` `200`, `/api/auth/me` `200`, protected endpoints `401`,
  unknown API `404`; synthetic login and protected `200` paths were also
  verified.
- `python ai/tools/validate_docs.py --root .`: PASS.
- `python ai/tools/validate_state.py --root .`: PASS.
- `python ai/tools/validate_traceability.py --root .`: PASS; `TRACE-001..013`.
- `git diff --check`: PASS.
- `scripts/doctor.ps1 -Plan`: exit `0`; `-DryRun -Profile OFFLINE_TEST -Full`:
  overall `WARNING`, exit `0`; `-Apply`: `SAFETY_BLOCK`, exit `3`.

## Не проверено

Live external providers, real SMTP/IMAP, real email delivery, canonical
database mutation and production migration behavior remain intentionally
unverified. No full real-provider authenticated workflow is claimed. The
current suite does not require pytest, so pytest-specific plugin behavior is
not tested.

## Ограничения и уровень уверенности

Уверенность высокая для воспроизводимого offline bootstrap, disposable DB,
network/mail safety gates, current backend suite, frontend gates and browser
public-shell route. Уверенность ограничена для live provider behavior and
production-only delivery paths by deliberate safety boundaries.
