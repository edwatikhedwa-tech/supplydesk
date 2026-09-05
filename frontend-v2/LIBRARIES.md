# Libraries used in frontend-v2 — and why

Per the Library Selection rule ("use a library because it solves a real
problem, not because it exists"), every dependency below was added for a
concrete need found while building the four screens, not pre-selected from a
capability list.

| Library | Version | Problem it solves here | Why not the native/simpler alternative |
| --- | --- | --- | --- |
| **React** | 19.2.8 | Component UI, the project's baseline. | — |
| **Vite** | 8.2.2 | Dev server + build for a standalone app. | — |
| **Tailwind CSS v4** (`@tailwindcss/vite`) | 4.3.3 | Tokenized styling without hand-written CSS per component; v4's `@theme` block doubles as the design-token source (colors, fonts) referenced throughout `index.css`. | A hand-rolled CSS-module system would duplicate what `@theme` already gives for free, with no config file needed in v4. |
| **react-router-dom** | 7.18.3 | Client-side routing between the four screens inside one App Shell (`<Outlet/>`). | Needed as soon as there is more than one screen; no lighter well-maintained alternative for this. |
| **@tanstack/react-table** | 8.21.3 (pinned; the installed npm `latest` was a `9.2.4` rewrite with an unfamiliar, differently-shaped API — pinning to the well-documented v8 line was the safer choice for a first slice built without live docs access) | Column-based sorting for the Requests and Suppliers tables (click a header, rows reorder) without hand-writing comparator/state wiring for every column. | A plain `<table>` with `useState` sorting would work for one column but gets messy once every column (name, count, deadline, status) needs its own sort behavior; TanStack keeps that declarative per-column. |
| **react-resizable-panels** | 4.12.3 | The Messages workspace's resizable navigator/conversation split (`Group`/`Panel`/`Separator`) — a real interaction users expect in an email-style workspace. | Hand-rolling drag-to-resize with pointer events for one screen is more code and more edge cases (min/max clamping, cursor state) than one focused dependency. |
| **lucide-react** | 1.41.0 | Icon set matching the restrained, non-decorative visual direction (thin stroke, consistent grid). | Inline SVGs per icon would work but don't scale past a handful; Lucide's tree-shaken imports keep bundle cost proportional to icons actually used. |
| **clsx** | 2.1.1 | Conditional Tailwind class composition (active nav state, selected row, tone variants) without string-concatenation bugs. | Template-literal string building is workable but error-prone once 3+ conditions combine (seen in `Sidebar.tsx`, `Badge.tsx`). |

## Deliberately not used (and why)

- **Radix UI primitives** (`react-dialog`, `react-dropdown-menu`,
  `react-tooltip`) were installed while scoping the Messages future-rail and
  filter dropdowns, then **removed** once the actual first slice needed only
  plain buttons, `title` attributes and inline disclosure — no real dialog,
  dropdown menu or rich tooltip ended up in this version. Keeping unused
  accessible-primitive packages around would be exactly the "npm zoo" the
  skill's decision rule warns against; they are the first thing to bring
  back if Requests/Suppliers gain a real filter dropdown or the Messages
  future-rail gains real Notes/Tasks/AI panels.
- **shadcn/ui** — not installed; its generated-component pattern is a
  starting point for accessible primitives, and this slice didn't yet need
  a dialog/select/combobox complex enough to justify generating one.
- **date-fns / dayjs** — relative-time and deadline-urgency formatting
  (`src/lib/format.ts`) is ~15 lines of `Date` arithmetic; a date library
  would be pure overhead at this scope.
- **Storybook, axe-core, Playwright** — not added to this prototype; the
  Engineering/Visual QA for this slice was done by hand in a real browser
  (see the task's completion report). Worth adding once this becomes more
  than a first visual/interactive slice.

## Fonts (not an npm dependency)

- **Inter** (Google Fonts, self-hosted-by-Google) — the dense UI/data
  typeface (tables, labels, message bodies); chosen for reliable tabular
  figures and a tall x-height at 12–13px.
- **ProcureSans** (`public/fonts/ProcureSans-{Regular,Semibold}.otf`) — an
  existing repo asset (`fonts/ProcureSans-*.otf` at the repository root,
  previously served by the old backend but not referenced by the old
  frontend's CSS) reused here as the product's one distinctive display
  typeface for page titles and the wordmark. This is a typography asset,
  not a visual pattern — using it does not read the old frontend's layout
  or styling.
