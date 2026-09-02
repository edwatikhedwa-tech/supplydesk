---
report_id: TASK-FRONTEND-KNIP-AUDIT-20260902
status: CURRENT
task_id: TASK-FRONTEND-KNIP-AUDIT-PASS1-20260902
updated_at: 2026-09-02
branch: audit/frontend-knip-20260902
base_head: adb0848d881ce6f3455475178342fdbb7fcc74f7
delivery_mode: PUBLISH
---

# Frontend Knip comprehensive audit — Pass 1

## Decision

`DECISION_READY_FOR_REMEDIATION: YES`

The current checkout contains a bounded high-confidence remediation set: one
unused frontend file, its two unused named exports, eight unused export
surfaces, nineteen unused exported type surfaces, and one direct unused
`lighthouse` development dependency. Two manual/tooling areas remain protected
from automatic removal: live-email/Lighthouse entrypoints and the incomplete
real-email diagnostic configuration.

No deletion, export removal, dependency removal, package-script change, config
change, Knip installation, CI change, backend start, or Playwright execution was
performed in this pass.

## Scope and evidence

- **CONFIRMED:** canonical workspace is `C:\Users\edwat\SupplyDesk`; branch is
  `audit/frontend-knip-20260902`; starting `HEAD` was
  `adb0848d881ce6f3455475178342fdbb7fcc74f7`; the worktree was clean.
- **CONFIRMED:** workspace guard passed before branch creation and before
  frontend build/Knip/report mutation.
- **CONFIRMED:** audit scope is `frontend/` plus the repository's current
  frontend CI/config references. No `.env` contents, mail data, database,
  legacy checkout or protected local data was read or changed.
- **NOT VERIFIED:** unrecorded operator commands or future/planned imports that
  are not present in the current checkout cannot be proven by static analysis.

## Frontend topology

| Item | Confirmed value |
| --- | --- |
| `FRONTEND_PACKAGE_ROOT` | `frontend/` |
| `PACKAGE_MANAGER` | npm; `frontend/package-lock.json` is present |
| Application entrypoints | `frontend/src/main.tsx` → `frontend/src/App.tsx` |
| Route entrypoints | `Dashboard`, `RequestsList`, `NewRequest`, `Login`, `Messages`, `Suppliers`, `Blacklist`, `Settings`, `NotFound`, `CampaignPage` are lazy-loaded in `frontend/src/App.tsx` |
| Test entrypoints | `npm test`, `test:visual`, `test:storybook-visual`; tracked `frontend/tests/*.spec.ts` |
| Storybook entrypoints | `npm run storybook`, `npm run build-storybook`, `.storybook/main.ts`, `.storybook/preview.ts`, `EmailRenderer.stories.tsx` |
| Tooling entrypoints | Vite, TypeScript, ESLint, Tailwind/PostCSS, Playwright, Storybook, `lhci autorun` |
| `DYNAMIC_IMPORTS_PRESENT` | YES; React `lazy(() => import(...))` route imports are explicit in `App.tsx` |

The normal Playwright config intentionally excludes the live-email test; the
live-email config selects it explicitly. The real-email config selects
`real-email-diagnostic.spec.ts`, but that test file is absent from the current
checkout.

## Baseline health

Commands ran from `frontend/` after a passing workspace guard:

| Check | Result | Evidence |
| --- | --- | --- |
| Typecheck | `PASS` | `npm run typecheck`; `tsc --noEmit -p tsconfig.app.json`; exit `0`, ~5.9s |
| Lint | `PASS_WITH_8_WARNINGS` | `npm run lint`; 0 errors, 8 existing warnings, exit `0`, ~3.7s |
| Production build | `PASS` | `npm run build`; Vite transformed 2,205 modules and emitted lazy route chunks; exit `0`, ~7.0s |
| Playwright | `NOT_NEEDED` | Explicitly excluded by this Pass 1 audit contract |
| Backend/runtime | `NOT_NEEDED` | Explicitly excluded; no backend was started |

The eight lint warnings are pre-existing baseline evidence only: one hook
dependency warning and seven React Fast Refresh export warnings. They were not
changed in this audit.

## Knip execution

- **CONFIRMED:** local `node_modules/.bin/knip` is absent; no permanent Knip
  dependency or config exists.
- **CONFIRMED:** `npx --yes knip@6.34.0 --no-progress --files --exports
  --dependencies --reporter json` completed its analysis in ~4.0s.
- **CONFIRMED:** Knip exited `1` because findings were present; this is an
  analyzer finding signal, not a tool crash. The JSON analysis was readable.
- **CONFIRMED:** automatic fix/delete flags were not used and no repository raw
  output file was created.

### Raw finding counts

| Knip category | Raw count |
| --- | ---: |
| Unused files | 4 |
| Unused ordinary exports | 8 |
| Unused exported types | 19 |
| Unused dependencies | 0 |
| Unused devDependencies | 1 |
| Unlisted imports | 2 (`@storybook/react`) |
| Unresolved imports | 0 |
| Duplicate exports | 0 |
| Configuration/entrypoint issues | 0 reported by Knip; manual entrypoint review below |

## Classified findings

### Unused files

| Path | Manual evidence | Classification | Confidence | Expected impact in Pass 2 |
| --- | --- | --- | --- | --- |
| `frontend/src/components/suppliers/RiskFactors.tsx` | Exact repository search found no import, re-export, story, test, route, or dynamic reference. `RiskCell` and `RiskList` occur only in this file. | `CONFIRMED_UNUSED` | `HIGH` for the current checkout | Removing the whole file should not affect current build/runtime references; owner approval is still required for destructive removal because future/planned intent is not statically knowable. |
| `frontend/lighthouserc.cjs` | `frontend/package.json` has `lhci: lhci autorun`; installed `@lhci/cli`/`@lhci/utils` code confirms automatic `lighthouserc.cjs` discovery. | `TOOLING_ENTRYPOINT` | — | Keep; removing it changes LHCI collection/assert/upload behavior. |
| `frontend/playwright.live-email.config.ts` | Explicit `testMatch` selects existing `frontend/tests/live-email-regression.spec.ts`; historical direct invocation is also present in repository evidence. | `TOOLING_ENTRYPOINT` | — | Keep; it is the manual live-email acceptance entrypoint. It was not run because real-mail/runtime execution is outside scope. |
| `frontend/playwright.real-email.config.ts` | Explicit `testMatch` targets missing `frontend/tests/real-email-diagnostic.spec.ts`; no current package script invokes it. The config is real-email-oriented and was not executed. | `REVIEW_REQUIRED` | — | Do not delete in Pass 2 without an owner decision on whether to restore or retire this diagnostic path. |

### Unused ordinary exports

All items below are still used locally where noted; Knip reports their export
surface as unused. The safe Pass 2 action, if approved, is to remove only the
unnecessary `export` modifier (or remove a truly dead constant), not to remove
the containing module.

| File | Exports | Manual evidence | Classification | Confidence |
| --- | --- | --- | --- | --- |
| `frontend/src/lib/utils.ts` | `shortCompanyName`, `isSoleTrader` | Only local calls inside `displaySupplierName`; no external import reference | `CONFIRMED_UNUSED` | `HIGH` |
| `frontend/src/useRequestState.ts` | `STATUS_META` | Only its declaration is present in the current tree; the module and other exports remain used | `CONFIRMED_UNUSED` | `HIGH` |
| `frontend/src/lib/campaign.ts` | `CAMPAIGN_STATUS_META`, `CAMPAIGN_PAUSE_REASONS` | Used by local `campaignStatusMeta`/`campaignPauseReason`; no external import reference | `CONFIRMED_UNUSED` | `HIGH` |
| `frontend/src/components/suppliers/RegistryFinanceRow.tsx` | `companyAgeYears`, `checkoProfileUrl`, `registryNeedsAttention` | Used by sibling exports in the same file; no external import reference | `CONFIRMED_UNUSED` | `HIGH` |

Raw ordinary export total: **8**.

### Unused exported type surfaces

Knip reported these 18 types from `frontend/src/lib/types.ts`: `SupplierResponseStatus`,
`SupplierContact`, `RequestPosition`, `RequestMailMetrics`, `MailDirection`,
`PreflightStatus`, `ExclusionReason`, `RolloutConfig`, `PreviewContract`,
`EstimatedDuration`, `CampaignLimits`, `AccountBudget`, `PacingMetadata`,
`CampaignHealth`, `CampaignExcludedTarget`, `InboxReply`,
`GlobalSupplierHistoryEntry`, and `GlobalSupplierIssue`.

Manual exact-name search found each only in `types.ts`, where the types are used
by other declarations in that same module; no external `src/` or test import was
found. Classification for all 18 is `CONFIRMED_UNUSED`, confidence `HIGH`, with
expected impact limited to the exported type surface if only `export` is
removed. This is an export-contract cleanup, not permission to delete the
underlying type definitions without a separate API-contract review.

Knip also reported `GlobalSupplierTableView` from
`frontend/src/components/suppliers/GlobalSupplierTable.tsx`. It is used by that
file's own props and helper functions and has no external import reference:
`CONFIRMED_UNUSED`, confidence `HIGH`; remove only the export modifier if
approved.

Raw exported type total: **19**.

## Dependency and tooling review

| Package | Manifest role | Why Knip/manual review surfaced it | Evidence and classification |
| --- | --- | --- | --- |
| `three` | dependency | Known review candidate | Direct import at `frontend/src/components/MagicRings.tsx:2`; `THREE.WebGLRenderer`, `Scene`, `ShaderMaterial`, `Mesh`, `Vector2`, and `Color` are used. `USED`; do not remove. |
| `@types/three` | devDependency | Known review candidate | Type support for the direct `three` TypeScript import; `npm run typecheck` passes and package is installed. `TOOLING_ENTRYPOINT`; do not remove without a type-resolution experiment. |
| `recharts` | dependency | Known review candidate | Direct import at `frontend/src/components/suppliers/FinanceTrend.tsx:3`; chart components are rendered, and the production build emits `FinanceTrend` output. `USED`; do not remove. |
| `lighthouse` | devDependency | Knip reported one unused devDependency; no source import, CLI script, or direct configuration use was found | Direct root package is `13.4.1`; `npm explain lighthouse` shows LHCI carries its own nested `12.6.1` copies. Current-repository classification: `CONFIRMED_UNUSED`, confidence `HIGH`, subject to Pass 2 owner approval and special verification. |
| `@lhci/cli` | devDependency | Known review candidate | `frontend/package.json` script `lhci: lhci autorun`; `frontend/lighthouserc.cjs` is auto-discovered by the installed CLI. `TOOLING_ENTRYPOINT`; do not remove. |
| `@storybook/addon-essentials` | devDependency | Known review candidate | Configured in `.storybook/main.ts:6`; `TOOLING_ENTRYPOINT`. |
| `@storybook/addon-a11y` | devDependency | Known review candidate | Configured in `.storybook/main.ts:7`; a11y test mode also appears in `.storybook/preview.ts:11`. `TOOLING_ENTRYPOINT`. |
| `@storybook/addon-interactions` | devDependency | Known review candidate | Configured in `.storybook/main.ts:8`. A configured addon is not classified unused. `TOOLING_ENTRYPOINT`. |
| `@storybook/react-vite` | devDependency | Known review candidate | Framework at `.storybook/main.ts:11`. `TOOLING_ENTRYPOINT`. |
| `storybook` | devDependency | Known review candidate | `storybook` and `build-storybook` scripts in `frontend/package.json`. `TOOLING_ENTRYPOINT`. |
| `@storybook/test` | devDependency | No direct source import, but it is a Storybook peer/tooling package and is present in the configured graph | `npm explain @storybook/test` shows peer-optional use by `@storybook/react`/`@storybook/react-vite` and nested addon copies. `TOOLING_ENTRYPOINT`; direct-manifest necessity is a separate review, not a removal conclusion. |
| `@playwright/test` | devDependency | Known review candidate | Imported by all tracked Playwright configs and test specs. `TOOLING_ENTRYPOINT`; no Playwright execution was required. |
| `@axe-core/playwright` | devDependency | Known review candidate | Imported by `campaign-ui.spec.ts`, `frontend-audit.spec.ts`, and `mailru-ui.spec.ts`. `TOOLING_ENTRYPOINT`; no removal. |

### `lighthouse` dependency impact

- **Why Knip reports it:** the direct root devDependency has no current source
  import and no package script invoking the `lighthouse` binary directly.
- **Repository evidence:** the only current package command is `lhci autorun`;
  LHCI's installed dependency graph contains its own Lighthouse runtime. The
  root `lighthouse@13.4.1` is therefore not needed by the declared LHCI script
  based on current checkout evidence.
- **Removal scope:** `frontend/package.json` and `frontend/package-lock.json`
  would both change; no such change was made.
- **Pass 2 verification:** clean `npm ci`, `npm run typecheck`, `npm run build`,
  and a safe LHCI config/CLI verification are required. Build/typecheck alone
  are insufficient because they do not execute the LHCI toolchain. Running the
  full `lhci` collection also needs its configured runtime target and is not
  part of this audit.

### Unlisted Storybook imports

Knip reported `@storybook/react` as unlisted at
`.storybook/preview.ts:1` and `EmailRenderer.stories.tsx:1`. This is not an
unused import: both are direct type imports used by Storybook entrypoints. The
package is currently supplied transitively by `@storybook/react-vite` according
to `npm explain @storybook/react`. Classification: `TOOLING_ENTRYPOINT` with a
separate manifest-contract review in Pass 2 if direct declaration is desired.

## False positives and indirect uses

- `lighthouserc.cjs` is a Knip file candidate but a confirmed LHCI config
  entrypoint.
- `playwright.live-email.config.ts` is a Knip file candidate but a confirmed
  manual Playwright config entrypoint.
- React lazy route imports in `App.tsx` are dynamic/indirect uses. The passing
  Vite build emitted the lazy page chunks, so route pages were not classified as
  unused.
- Configured Storybook addons, Playwright, axe, `three`, `recharts`, and LHCI
  were not classified unused merely because they lack a normal `src/` import.

## Recommended Pass 2 scope

One bounded remediation batch may include:

1. remove `RiskFactors.tsx` only after the owner accepts the current-checkout
   `CONFIRMED_UNUSED/HIGH` result and the destructive-removal rollback plan;
2. remove the 8 unnecessary ordinary export surfaces and 19 unnecessary type
   export surfaces, preserving all containing modules and runtime behavior;
3. remove the direct `lighthouse` devDependency with its lockfile entry only
   after the clean-install and LHCI-specific verification described above.

Deferred from automatic remediation:

- `playwright.real-email.config.ts` — `REVIEW_REQUIRED` because its selected
  test is absent and the path concerns external mailbox diagnostics;
- `@storybook/react` — unlisted tooling import requiring a manifest decision,
  not a deletion decision;
- any unrecorded manual CLI usage or future/planned component import —
  `NOT VERIFIED` by current-checkout static evidence;
- lint warnings and unrelated frontend findings — outside this audit.

## Verification and safety close

- `PRODUCT_CODE_CHANGED: NO` (no `frontend/src/**` change).
- `FRONTEND_PACKAGE_CHANGED: NO` (no `frontend/package.json` change).
- `LOCKFILE_CHANGED: NO` (no lockfile change).
- `KNIP_PERMANENTLY_INTEGRATED: NO`.
- `PLAYWRIGHT_EXECUTED: NO`, as explicitly required by this Pass 1 contract.
- `BACKEND_STARTED: NO`.
- `SECRET_VALUES_OUTPUT: NO`.
- `FULL_CI: NOT_NEEDED` for this audit report; required remote FAST control CI
  is a publication gate after commit.

## Required delivery fields

```text
FRONTEND_PACKAGE_ROOT: frontend/
PACKAGE_MANAGER: npm
KNIP_VERSION: 6.34.0
BASELINE_TYPECHECK: PASS
BASELINE_BUILD: PASS
BASELINE_LINT: PASS_WITH_8_WARNINGS
KNIP_RUN: PASS_WITH_FINDINGS (exit 1; analysis completed)
UNUSED_FILES_RAW: 4
UNUSED_EXPORTS_RAW: 8 ordinary + 19 exported types
UNUSED_DEPENDENCIES_RAW: 0
UNUSED_DEV_DEPENDENCIES_RAW: lighthouse
CONFIRMED_UNUSED: RiskFactors.tsx; 8 ordinary exports; 19 exported type surfaces; direct lighthouse devDependency
FALSE_POSITIVE: lighthouserc.cjs; playwright.live-email.config.ts; lazy route imports; configured Storybook/Playwright/LHCI tooling
TOOLING_ENTRYPOINT: lighthouserc.cjs; playwright.live-email.config.ts; Storybook configs/addons; Playwright/axe; @lhci/cli; @types/three; @storybook/react unlisted type imports
DYNAMIC_OR_INDIRECT_USE: App.tsx lazy route imports; Storybook/LHCI/Playwright config discovery
REVIEW_REQUIRED: playwright.real-email.config.ts; direct @storybook/react manifest declaration; unrecorded future/manual usage
RISK_FACTORS_TSX: CONFIRMED_UNUSED
THREE: USED; @types/three is tooling/type support
RECHARTS: USED
LIGHTHOUSE: CONFIRMED_UNUSED (direct root devDependency)
LHCI: USED (tooling entrypoint)
HIGH_CONFIDENCE_REMEDIATION_ITEMS: RiskFactors.tsx; 8 ordinary exports; 19 exported type surfaces; direct lighthouse devDependency
DECISION_READY_FOR_REMEDIATION: YES
PRODUCT_CODE_CHANGED: NO
REPORT: ai/reports/TASK-FRONTEND-KNIP-AUDIT-20260902-report.md
COMMIT: pending
PUSH: pending
REMOTE_SHA_MATCH: pending
FAST_CI: pending
FULL_CI: NOT_NEEDED
FINAL_STATUS: PENDING_PUBLISH_GATES
```
