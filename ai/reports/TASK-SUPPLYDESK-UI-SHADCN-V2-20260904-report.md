---
document_id: REPORT-TASK-SUPPLYDESK-UI-SHADCN-V2-20260904
status: CURRENT
canonical: false
owner: frontend-experiment
updated_at: 2026-09-04
based_on_commit: 878cf70292683fa8d9730ee353af78854746b2b1
---

# TASK — SupplyDesk UI Experiment v2 / shadcn-ui

## Result

`PARTIALLY VERIFIED`: the isolated visual experiment is implemented and
rendered on the requested route family. The experiment is intentionally
presentation-only; production authenticated flows remain outside this task.

## Scope and non-goals

- Branch: `experiment/ui-shadcn-v2`.
- Added only frontend experiment code, its browser acceptance test, and design
  documentation.
- Production backend, API, database, migrations, authentication, business
  logic, mail behavior and production screen semantics were not changed.
- The route is public only because it contains static fixture data and no
  production session or write path; existing production routes remain behind
  `RequireAuth`.

## Implemented

- Added `/experiment/ui-shadcn-v2`, `/requests`, `/suppliers` and `/messages`.
- Added a calm procurement-workbench direction: graphite rail, warm neutral
  canvas, cobalt action color, request-first hierarchy and compact data views.
- Added local shadcn-style primitives in the experiment boundary: buttons,
  badges, icon buttons, filters, table/list states, dialogs, notices and a
  responsive shell. No shadcn or Radix dependency was installed.
- Added semantic CSS variables in the experiment scope for background,
  foreground, card, primary, muted, border, input, ring, sidebar and state
  colors.
- Added presentation states for filtering, preview dialogs, supplier
  selection, empty search results, mobile navigation and presentation-only
  reply feedback.
- Added a split-view email workspace with request, supplier, next-step and
  attachment context.
- Added a design rationale and reference synthesis in
  `docs/experiments/ui-shadcn-v2.md`.

## Verification evidence

- Workspace guard: `PASS`.
- Frontend typecheck: `PASS`.
- Frontend lint: `PASS` with five pre-existing warnings in production files;
  the experiment has zero lint errors.
- Frontend production build: `PASS`.
- Browser matrix: `9 passed, 3 skipped` across desktop-wide 1440px,
  desktop-compact 1280px, tablet-landscape 1024px and mobile-large 390px.
- Browser checks covered route headings, visible geometry, horizontal overflow,
  axe accessibility violations, request preview, supplier search/selection,
  mail tabs/reply notice and mobile drawer navigation.
- Final screenshots were rendered to
  `frontend/artifacts/ui-shadcn-v2-20260904/` for all four routes and all four
  viewport profiles. A visual review fixed the 1024px table compression and
  supplier name/INN spacing before the final run.
- Canonical HTTP smoke: frontend `/login` returned `200`; backend `/health`
  returned `200` during the session. The frontend dev server remained running
  on port `5173` after verification.

## Limitations and unverified items

- A persisted authenticated BEFORE capture for the four production screens was
  not available in the current browser session; before/after transformation
  comparison is therefore `NOT VERIFIED`.
- The experiment uses local fixture data and intentionally does not exercise
  production API, database, auth or mail writes.
- `scripts/audit_toolchain.py --project frontend` was attempted but the helper
  is absent from this checkout; that audit-toolchain result is `NOT VERIFIED`.
- Full existing product Playwright suite and authenticated production flows
  were not rerun because this task is isolated to the experiment route.
- Five existing lint warnings remain outside the experiment files.
- The worktree contained pre-existing modified control-plane files and an
  untracked `runtime/` directory; they were preserved and not staged.

## Rollback

Revert the task commit(s), or remove only the experiment route/import,
`frontend/src/pages/UiExperiment.tsx`,
`frontend/src/styles/ui-experiment.css`, its test and the experiment docs.
No database, mail or production data rollback is required.

## Recommendation

Keep this as an opt-in visual experiment until authenticated production
screens are captured for comparison, real data contracts are mapped, and
product owners validate the request-first and split-view workflows. No
production rollout is implied by this task.
