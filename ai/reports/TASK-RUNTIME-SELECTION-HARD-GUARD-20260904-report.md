---
document_id: TASK-RUNTIME-SELECTION-HARD-GUARD-20260904
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
---

# Runtime selection hard guard

## Outcome

`scripts/runtime_guard.py` is the single runtime-selection authority. The
purpose matrix is:

| Purpose | Allowed runtime |
| --- | --- |
| `OWNER_SESSION` | `LOCAL_CANONICAL` / `:8000` |
| `VISUAL_ACCEPTANCE` | `LOCAL_CANONICAL` / `:8000` |
| `SAFE_TEST` | `SAFE_TEST` / `:18000` |
| `AUTOMATED_TEST` | `SAFE_TEST` / `:18000` |
| `OAUTH_CHECK` | `LOCAL_CANONICAL` / `:8000` |
| `MAIL_PROVIDER_CHECK` | `LOCAL_CANONICAL` / `:8000` |

The guard rejects an unknown purpose, a mismatched mode, an unexpected loopback
URL, a wrong database class or a wrong auth class. It prints `FAIL:
RUNTIME_SELECTION_GUARD` and `STOP:` and exits non-zero. SAFE_TEST no longer
chooses another port when `18000` is occupied.

## Guarded command inventory

- Backend: `scripts/start_local_canonical.ps1`,
  `scripts/start_test_runtime.ps1`, `scripts/recover_supplydesk.ps1`,
  `scripts/start_server_and_open.ps1` and `scripts/start_server.bat`.
  `supplier_app.py` also validates its runtime context before starting the
  application.
- Frontend: `npm run dev`, `npm run build` and `npm run preview` use
  `scripts/run_frontend_dev.mjs`; Vite validates its backend proxy target.
- Browser tests: `npm test`, `npm run test:visual`,
  `npm run test:visual:eyes` and `npm run test:storybook-visual` use
  `scripts/run_playwright.mjs`; each Playwright config validates its runtime.
- Visual/performance acceptance: `npm run lhci` uses
  `scripts/run_lhci.mjs` and `frontend/lighthouserc.cjs`; both validate
  `VISUAL_ACCEPTANCE` by default.
- Storybook: `npm run storybook` and `npm run build-storybook` use
  `scripts/run_storybook.mjs`, which validates the isolated `:6006` surface
  under `AUTOMATED_TEST`.
- Doctor and CI: `scripts/diagnostics/diagnostic_runner.py` sets
  `AUTOMATED_TEST` for `OFFLINE_TEST` and `VISUAL_ACCEPTANCE` for
  `LOCAL_CANONICAL`; CI browser jobs explicitly set `AUTOMATED_TEST` and
  `SAFE_TEST`.

## Required browser preamble

Before a guarded browser run the output contains:

```text
RUNTIME_PURPOSE
RUNTIME_MODE
BASE_URL
DATABASE_CLASS
AUTH_MODE
```

The values are printed by the Python guard and are not inferred from a
previously running browser tab.

## Controlled failure

Command:

```powershell
python scripts/runtime_guard.py --surface browser --purpose VISUAL_ACCEPTANCE --mode SAFE_TEST --base-url http://127.0.0.1:18000 --backend-url http://127.0.0.1:18000
```

Observed result: exit code `3`, `FAIL: RUNTIME_SELECTION_GUARD`, and
`STOP: purpose VISUAL_ACCEPTANCE requires LOCAL_CANONICAL, but SAFE_TEST was
selected`.

The same mismatch through `npm run test:visual -- --list` stopped before test
collection. The automated unittest file is
`tests/diagnostics/test_runtime_guard.py` and covers the full matrix plus the
process-level failure.

## SAFE_TEST visual evidence

The disposable runtime was restarted only on `:18000` with its existing
marker-controlled process. A synthetic local login was used only in the
disposable runtime to render the app shell. Reviewed screenshots:

- `runtime/safe-test-badge-1440.png` — `1440×900`.
- `runtime/safe-test-badge-360.png` — `360×800`.

The badge reads `SAFE TEST · DISPOSABLE DATA · PORT 18000`, remains visible,
does not overlap the mobile header or navigation, and has no horizontal
overflow. This evidence validates the SAFE_TEST warning only; it is not
canonical visual acceptance.

## Verification

- Workspace guard: PASS.
- Runtime matrix and controlled-failure unit tests: PASS (`3` tests).
- SAFE_TEST browser smoke: PASS (`2/2`), `AUTOMATED_TEST`.
- Full frontend/browser suite: PASS (`322 passed, 6 skipped`),
  `AUTOMATED_TEST` on all configured desktop/tablet/mobile projects.
- Canonical public-shell browser acceptance: PASS (`1/1`, mobile-small),
  `VISUAL_ACCEPTANCE` against `http://127.0.0.1:8000`.
- Frontend typecheck: PASS.
- Vite node-config typecheck: PASS.
- Frontend lint: PASS with five pre-existing warnings and zero errors.
- Frontend build: PASS.
- Documentation, state, VibeCoding and traceability validators: PASS.
- `git diff --check`: PASS at close after final documentation edits.

## Remaining bypasses / unverified paths

The following paths can still bypass this guard and therefore remain
`NOT VERIFIED` unless separately audited:

1. Direct Python imports or constructors, including serverless
   `api/index.py`, do not pass through `supplier_app.py:main()`.
2. A process already listening on `:8000` can be opened by the convenience
   launcher; the launcher does not prove the existing process's parent command
   or environment.
3. A custom browser runner that does not load the repository Playwright
   configs can avoid the config-level guard.
4. A static server serving an existing `frontend/dist` can avoid Vite's
   frontend proxy guard.
5. A caller can intentionally set a matching purpose/mode and still have an
   application-level configuration problem outside this guard's contract.

These are explicit limitations, not fallback behavior. No OAuth settings,
database schema, backend business logic, provider configuration, `.env`,
canonical mail data or outgoing mail were changed.
