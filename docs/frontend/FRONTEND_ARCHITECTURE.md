---
document_id: DOC-FRONTEND-ARCHITECTURE-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Frontend Architecture

Supersedes `docs/architecture/COMPONENT_MAP.md`'s `COMP-FRONTEND` row (dated 2026-09-04, only
knows about `frontend/`, doesn't mention `frontend-v2` at all — confirmed stale, see `GAP-011`).

## Which frontend is live (verified, not assumed)

**`frontend-v2/` is the only deployed frontend.** Evidence:
- `vercel.json`: `buildCommand: cd frontend-v2 && npm run build`, `outputDirectory:
  frontend-v2/dist`, and `frontend/**` is explicitly excluded from the serverless bundle.
- No root-level `package.json` — all build orchestration points at `frontend-v2` (both
  `vercel.json` and the local dev launcher `scripts/start_server_and_open.ps1`, whose own code
  comment states frontend-v2 "теперь основной UI, а не... frontend/dist").
- `git log -- frontend/` bottoms out ~2026-09-04; `git log -- frontend-v2/` has near-daily
  commits through today. `frontend/` is frozen, not actively maintained in parallel — it is dead
  code still sitting in the repo, not a live alternative.

## Stack (frontend-v2)

React 19.2.8 + Vite 7.3.6 + Tailwind v4 (via `@tailwindcss/vite`, no PostCSS config needed) +
react-router-dom v7.18.3 (`HashRouter`) + TypeScript ~6.0.2. Component primitives: `radix-ui`
(headless) + `clsx`/`tailwind-merge`. Tables: `@tanstack/react-table` (used in exactly 1 of 6
table implementations — see `UI_INVENTORY.md`). Icons: `lucide-react`, exclusively (41 files,
no competing icon source). Toasts: `react-toastify`. Dates: `date-fns` + `react-day-picker`.
Linter: `oxlint` (not ESLint). Tests: `vitest` + Testing Library (4 unit-test files only, no
e2e/browser/visual coverage — see `GAP-010`).

## Routing (`frontend-v2/src/App.tsx`)

`/` (Dashboard), `/requests`, `/requests/:id`, `/suppliers`, `/suppliers/:id`, `/messages`,
`/blacklist`, `/settings`, `/help`, `*` (404). `/calendar` existed transiently, removed
2026-09-17 as dead/unreachable code (commit `85d7f31`) once its sidebar nav entry had already
been dropped and the Dashboard gained its own real calendar widget.

## Why the app looks inconsistent ("Frankenstein") — root cause, evidence-based

Not a vague impression — three concrete, distinct causes, in order of impact:

1. **Missing shared primitives for 5 of 13 audited UI categories** (Input, Checkbox, Card, Table,
   Tabs) — every page reinvents its own version of each, with visible drift between copies. See
   [`UI_INVENTORY.md`](UI_INVENTORY.md) for the full evidence table. This is the largest
   contributor.
2. **Two frontends with materially different tech stacks coexist in the repo** — React 18 vs 19,
   router v6 vs v7, a full major-version jump on the icon library, Tailwind v3 vs v4 with a
   different theming model, and v2 adding a headless component library (Radix) v1 never had. Any
   code or visual pattern carried over between them would need re-theming, not copy-paste — see
   [`FRONTEND_V1_V2_COMPARISON.md`](FRONTEND_V1_V2_COMPARISON.md).
3. **One screen (`Login.tsx`) is visually foreign to the rest of the app** — literal Tailwind
   colors instead of the shared design tokens, plus a Three.js shader background
   (`MagicRings.tsx`) pulling in the entire `three` package for one decorative element. Reads as
   imported from a different design source (`GAP-008`).

Counterpoint, also evidence-based: `Button`, `Modal`, the toast system, and the
`LoadingState`/`EmptyState`/`ErrorState` trio *are* genuinely centralized and consistently reused
across the app — the inconsistency is real but narrower than "everything is duplicated."

## Known regression vs v1

Campaign monitoring/control (pause/resume/stop an in-flight bulk send, continuation dry-run) —
`frontend/src/pages/CampaignPage.tsx` — has no v2 route or page at all. See `GAP-001`.
