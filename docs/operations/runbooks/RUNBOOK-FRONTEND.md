---
document_id: RUNBOOK-FRONTEND-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-04
source_commit: 84083130e3a75eb5a6d4fa83957db6760724379b
---

# Runbook: frontend gates

## Gate order

In an approved controlled worktree, use the manifest commands: `npm ci
--no-audit --fund=false`, `npm run typecheck`, `npm run lint`, `npm run
build`, then the public-shell Playwright test. `npm run dev` and every browser
script load `scripts/runtime_guard.py`; the runner checks the manifest
by default and runs these gates only with explicit opt-in.

`npm run dev` defaults to `OWNER_SESSION` and therefore targets the canonical
backend at `http://127.0.0.1:8000`. `npm test` defaults to `AUTOMATED_TEST`
and therefore requires `SAFE_TEST` at `http://127.0.0.1:18000`.
`npm run test:visual` and `npm run lhci` default to `VISUAL_ACCEPTANCE` and
therefore require `LOCAL_CANONICAL`. Before browser acceptance the guard prints
`RUNTIME_PURPOSE`, `RUNTIME_MODE`, `BASE_URL`, `DATABASE_CLASS` and `AUTH_MODE`.
An incompatible purpose/runtime pair is `FAIL + STOP`; there is no silent
fallback to the safe runtime.

## Failure labels

Keep `NPM_MISSING`, `DEPENDENCIES_NOT_INSTALLED`, `INSTALL_FAIL`,
`TYPECHECK_FAIL`, `LINT_FAIL`, `BUILD_FAIL`, `BROWSER_FAIL`,
`ACCESSIBILITY_FAIL` and `OVERFLOW_FAIL` distinct. `NPM_MISSING` means the
toolchain is unavailable; `DEPENDENCIES_NOT_INSTALLED` means the declared
frontend dependencies are absent. A failing script or browser assertion is a
product/test failure. The V1.1 doctor does not edit source or snapshots to make
a gate pass.

The default doctor run validates only the frontend manifest and reports the
typecheck/lint/build/browser checks as not verified. Runtime gates require the
explicit `--run-frontend` or `--run-browser` opt-in and a disposable local
server; no remote browser session is implied.

## Safety and human-in-the-loop browser authentication

Browser acceptance defaults to safe shell/navigation scenarios. Do not log in,
send mail, change requests, or alter provider/database state unless the task
explicitly requires an approved local interactive authentication handoff.

For that handoff, use only a local interactive session: launch a separate
headed Chromium (a visible browser window) with a dedicated Playwright
profile/context. The owner manually signs in in that window; the agent never
asks for a password or token in chat. The owner says `done`, and the agent
continues in the same browser context. Never use the owner's personal Chrome
profile. Keep cookies and authentication state only in the dedicated ignored
or outside-repository state location; never commit or report them.

Remote CI cannot depend on an owner's manual sign-in. CI must use an isolated
test account, a seeded test session or a controlled fixture. `WAITING_FOR_OWNER_LOGIN`
is never a valid CI state.

## Current public-login failure classification

`frontend/tests/frontend-audit.spec.ts` opens `/login` and checks the public
login UI; this scenario does not require authentication. Do not classify its
failure as an auth failure or ask the owner to log in. A timeout at
`page.goto('/login', { waitUntil: 'networkidle' })` first requires diagnosis
of requests, the network-idle wait, background requests, page errors and the
accessibility check. Only after evidence shows that `networkidle` is unstable
may the test owner consider `domcontentloaded` plus a concrete login element;
that is a test change and remains outside this policy-only task.
