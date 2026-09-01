---
document_id: RUNBOOK-FRONTEND-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: frontend gates

## Gate order

In an approved controlled worktree, use the manifest commands: `npm ci
--no-audit --fund=false`, `npm run typecheck`, `npm run lint`, `npm run
build`, then the public-shell Playwright test. The runner checks the manifest
by default and runs these gates only with explicit opt-in.

## Failure labels

Keep `INSTALL_FAIL`, `TYPECHECK_FAIL`, `LINT_FAIL`, `BUILD_FAIL`,
`BROWSER_FAIL`, `ACCESSIBILITY_FAIL` and `OVERFLOW_FAIL` distinct. A missing
Node installation or `node_modules` is an environment gap; a failing script is
a product/test failure. The V1 doctor does not edit source or snapshots to
make a gate pass.

## Safety

Browser acceptance must use safe shell/navigation scenarios. Do not log in,
send mail, change requests, or alter provider/database state from this
runbook.
