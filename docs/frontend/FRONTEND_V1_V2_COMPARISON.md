---
document_id: DOC-FRONTEND-V1-V2-COMPARISON-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Frontend v1 vs v2 Comparison

See [`FRONTEND_ARCHITECTURE.md`](FRONTEND_ARCHITECTURE.md) for which one is live and why the
combination causes visual inconsistency. This file is the detailed page/library diff.

## Pages/routes

| v1 route | v1 file | v2 route | v2 file | Status |
|---|---|---|---|---|
| `/` | `Dashboard.tsx` | `/` | `Dashboard.tsx` | Both |
| `/requests` | `RequestsList.tsx` | `requests` | `Requests.tsx` | Both (renamed) |
| `/requests/new` | `NewRequest.tsx` (own page) | — | `NewRequestModal` (modal in `Requests.tsx`) | UX pattern change, not a real regression |
| `/requests/:id` | `RequestPage` | `requests/:id` | `RequestDetail.tsx` | Both |
| `/messages` | `Messages.tsx` | `messages` | `Messages.tsx` | Both |
| `/mail/campaigns/:id` | `CampaignPage.tsx` | — | — | **v1-only — real regression, `GAP-001`** |
| `/suppliers` | `Suppliers.tsx` | `suppliers` | `Suppliers.tsx` | Both |
| — | — | `suppliers/:id` | `SupplierDetail.tsx` | v2-only (v1 uses an overlay panel instead) |
| `/blacklist` | `Blacklist.tsx` | `blacklist` | `Blacklist.tsx` | Both |
| `/settings` | `Settings.tsx` | `settings` | `Settings.tsx` | Both |
| `/login` | `Login.tsx` | (gated) | `Login.tsx` | Both |
| `*` | `NotFound.tsx` | `*` | `NotFound.tsx` | Both |
| — | — | `help` | `Help.tsx` | v2-only |

No other v1-only pages found beyond the campaign monitor.

## Library/tooling diff

| Aspect | v1 (`frontend/`) | v2 (`frontend-v2/`) |
|---|---|---|
| React | 18.3.1 | 19.2.8 |
| Router | react-router-dom ^6, `BrowserRouter` | react-router-dom ^7, `HashRouter` |
| Icons | lucide-react ^0.446 | lucide-react ^1.41 (major jump) |
| Styling | Tailwind ^3.4 + PostCSS | Tailwind ^4.3 via Vite plugin |
| Component primitives | hand-rolled | Radix UI (headless) |
| Tables | ad hoc | `@tanstack/react-table` (1 of 6 tables) |
| Toasts | none | `react-toastify` |
| Lint | ESLint 9 | oxlint |
| E2E/visual/a11y | Playwright + Storybook + Applitools Eyes + axe-core + Lighthouse CI | none |

## `RequestDetailExperiment.tsx` — already resolved, no action needed

Existed only transiently in the working tree (never on `experiment/frontend-v2-greenfield-20260905`'s
history until captured on the separate `state/current-20260917-2119` snapshot branch, commit
`dcb0576`). Structural diff against the live `RequestDetail.tsx`:

- **Experiment (577 lines):** one monolithic function, all logic inline (tasks, positions,
  table rows) — no sub-components beyond shared pure helpers.
- **Live `RequestDetail.tsx` (~840 lines):** the more evolved version — decomposed into
  `PositionsRow`, `CommunicationCell`, `PrimaryAction`, `OverflowMenu`, `CompanyCell`,
  `AgeCell`/`RevenueCell`/`ProfitCell`/`RegistryCell`, `SupplierTableRow`/`SupplierMobileRow`,
  `TasksOnRequest`. Also has `RemindersContext` integration, a shared `PageHeader`, trend-arrow
  icons on finance cells, and a dedicated mobile row renderer — none of which exist in the
  Experiment file.

**No UI idea in the Experiment file is missing from the live page.** It reads as an earlier,
less-refactored draft of the same screen, already correctly identified and removed as redundant
scratch work per `ai/ACTIVE_TASK.md`: *"its real functionality already lived correctly in
RequestDetail.tsx."* No migration or salvage action is needed.
