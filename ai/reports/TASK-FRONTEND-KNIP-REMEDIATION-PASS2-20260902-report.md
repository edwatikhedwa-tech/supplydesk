# TASK-FRONTEND-KNIP-REMEDIATION-PASS2-20260902

## Result

`PASS` — bounded frontend hygiene remediation completed. No product behavior,
backend, API, database, migration, or production-setting changes were made.

Branch: `audit/frontend-knip-20260902`

PASS 1 baseline commit: `4e9fda059aa7fdebbf95864a8c9e1e6c92c06bbc`

## Changes

- Removed confirmed-unused `frontend/src/components/suppliers/RiskFactors.tsx`.
- Removed the eight approved ordinary export surfaces. `STATUS_META` was
  removed because it was unused both externally and locally; its now-unused
  `SupplierMailStatus` export was also reduced to an internal type while the
  type declaration and all internal fields remain intact.
- Removed the `export` modifier from the 18 approved types in
  `frontend/src/lib/types.ts` and from `GlobalSupplierTableView`.
- Removed the direct `lighthouse` devDependency. The nested Lighthouse package
  required by `@lhci/cli` remains intentionally present.
- Added direct `@storybook/react@8.6.15` and `knip@6.34.0` devDependencies.
- Added the local script `npm run knip`.
- Added minimal `frontend/knip.jsonc`: two confirmed manual tooling entries and
  one precise deferred ignore for `playwright.real-email.config.ts`.
- Left `playwright.real-email.config.ts` untouched and did not restore or run
  the missing real-email diagnostic spec.

## Post-remediation findings

Permanent command: `npm run knip -- --no-progress --reporter json`

Result: `issues: []`, exit code `0`.

| Finding | PASS 1 | PASS 2 |
| --- | ---: | ---: |
| Unused files | 4 | 0 |
| Approved ordinary exports | 8 | 0 |
| Approved exported types | 19 | 0 |
| Unused dependencies | 0 | 0 |
| Unused devDependencies | 1 (`lighthouse`) | 0 |
| Unlisted `@storybook/react` imports | 2 | 0 |

`SupplierMailStatus` is also no longer public because the optional dead
`STATUS_META` removal exposed that its public export had no external consumer.

## Verification

- Workspace guard: PASS.
- Clean install: `npm ci --no-audit --fund=false` — PASS; lockfile install
  completed successfully.
- Root dependency graph: direct `lighthouse` absent; `@lhci/cli@0.15.1`,
  `knip@6.34.0`, and `@storybook/react@8.6.15` present.
- LHCI safe smoke: `npx --no-install lhci --version` — PASS (`0.15.1`);
  `npx --no-install lhci autorun --help` — PASS; `lighthouserc.cjs` parsed and
  was auto-discovered with one configured URL. No Lighthouse collection,
  upload, backend, or browser run was performed.
- `npm run typecheck` — PASS.
- `npm run lint` — PASS, 0 errors and 5 existing warnings. No new lint error or
  warning was introduced; three PASS 1 warnings belonged to the removed file.
- `npm run build` — PASS.
- `npm run build-storybook` — PASS. Existing dependency/runtime and large-chunk
  warnings did not fail the build.
- Exact scope checks: `RiskFactors` absent with no frontend references; target
  export modifiers absent; real-email config present and diagnostic spec absent.
- No Playwright, visual, backend, or real-mailbox smoke was run because PASS 2
  explicitly excludes those scenarios and changes no UI behavior.

## Deferred

`REAL_EMAIL_CONFIG: DEFERRED_FINDING` — the config references the missing
`real-email-diagnostic.spec.ts`, has no package script, and concerns external
mailbox diagnostics. It remains unchanged and is suppressed only by the exact
file entry in `knip.jsonc`; no PASS 3 is opened.

## Adoption

`KNIP_PERMANENTLY_INTEGRATED: YES` — it is reproducible after clean install,
uses a small topology-specific config, requires no broad dependency or file
suppression, and reports no remaining issues.

Commit and remote CI are recorded in the final delivery response after the
single Task-ID commit is created.
