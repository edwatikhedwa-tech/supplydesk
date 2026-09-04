---
task_id: TASK-SUPPLYDESK-SHADCN-MIGRATION-20260904
status: CURRENT
branch: experiment/ui-shadcn-v2
baseline_commit: a610c2ef94638fa19255059932dca0b82b9b3122
---

# SupplyDesk shadcn/ui foundation migration

## Scope

This was an implementation task limited to the frontend component boundary.
The experiment's existing visual direction and presentation-only behavior were
preserved. Backend, API, database, authentication, mail and business logic were
not changed. Pre-existing untracked `runtime/` was preserved and not staged.

The official references used for the migration were the [shadcn/ui Vite
installation guide](https://ui.shadcn.com/docs/installation/vite), [theming
guide](https://ui.shadcn.com/docs/theming), and the current component pages for
[Button](https://ui.shadcn.com/docs/components/base/button), [Dialog](https://ui.shadcn.com/docs/components/base/dialog),
[Sidebar](https://ui.shadcn.com/docs/components/base/sidebar), [Tabs](https://ui.shadcn.com/docs/components/base/tabs),
[Table](https://ui.shadcn.com/docs/components/base/table), [Tooltip](https://ui.shadcn.com/docs/components/base/tooltip),
[Dropdown Menu](https://ui.shadcn.com/docs/components/base/dropdown-menu), and
[Popover](https://ui.shadcn.com/docs/components/base/popover).

## Classification

- Before: `SHADCN_STYLE_ONLY`. The baseline at `a610c2e` had local native
  wrappers and no `components.json`, Radix packages, CVA, `clsx` or
  `tailwind-merge`.
- After: `REAL_SHADCN`. The requested core primitives are local copies of the
  official shadcn component source shape, generated from the official registry
  with the `new-york` style, and use the official Radix-backed implementation
  where that component does so.

This classification is about the foundation of the migrated primitives, not a
claim that every SupplyDesk domain component is an official shadcn component.

## components.json

Path: `frontend/components.json`.

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "iconLibrary": "lucide",
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

The underlying primitive layer is Radix UI: the official `new-york` registry
files import `@radix-ui/react-*` for Checkbox, Dialog, DropdownMenu, Popover,
Separator, Tabs and Tooltip, and `@radix-ui/react-slot` for composable Button
and Sidebar behavior. The generated source also uses CVA and the official
`cn` pattern. `@base-ui/react` is not present or required for this chosen
Radix-backed official path.

## Dependencies added

Direct runtime dependencies added to `frontend/package.json` and lockfile:

| Dependency | Version | Actual role |
|---|---:|---|
| `@radix-ui/react-checkbox` | `^1.3.11` | Checkbox behavior and state |
| `@radix-ui/react-dialog` | `^1.1.23` | Dialog and Sheet behavior |
| `@radix-ui/react-dropdown-menu` | `^2.1.24` | Dropdown menu behavior |
| `@radix-ui/react-popover` | `^1.1.23` | Popover behavior |
| `@radix-ui/react-separator` | `^1.1.15` | Sidebar separator |
| `@radix-ui/react-slot` | `^1.3.3` | `asChild` composition |
| `@radix-ui/react-tabs` | `^1.1.21` | Tabs behavior and ARIA state |
| `@radix-ui/react-tooltip` | `^1.2.16` | Tooltip behavior |
| `class-variance-authority` | `^0.7.1` | Official shadcn variant definitions |
| `clsx` | `^2.1.1` | Conditional class flattening |
| `tailwind-merge` | `^3.6.0` | Tailwind class conflict resolution |

`lucide-react` (`^0.446.0`) was already present and is used by both the
experiment and the generated shadcn files. It was not newly installed in this
task. No `shadcn` package was added to `dependencies`; the official CLI was
invoked as `npx shadcn@4.21.0` to generate the local source. No `@base-ui/react`
package, Radix Accordion package or unrelated UI library was installed.

## Component inventory

Canonical directory: `frontend/src/components/ui/`.

| File | Official shadcn-derived | Custom | Evidence |
|---|---|---|---|
| `badge.tsx` | Yes, adapted | Minor semantic adaptation | Official CVA variants and `cn`; renders `span` to preserve inline/table-cell semantics. |
| `button.tsx` | Yes, adapted | Product compatibility variants | Official `Slot`, CVA, `cn`, `asChild`, focus and disabled classes; `primary`, `danger` and `md` preserve existing callers. |
| `checkbox.tsx` | Yes | No | Official `@radix-ui/react-checkbox` Root/Indicator composition. |
| `dialog.tsx` | Yes, adapted | Overlay token adaptation | Official `@radix-ui/react-dialog` Root/Overlay/Content/Header/Footer/Title/Close composition; overlay color keeps the baseline. |
| `dropdown-menu.tsx` | Yes | No | Official `@radix-ui/react-dropdown-menu` aliases and menu item compositions. |
| `index.ts` | No | Yes, barrel | SupplyDesk export barrel; it points consumers to official local primitives and retained domain compositions. |
| `input.tsx` | Yes | No | Official forward-ref input wrapper using `cn`. |
| `popover.tsx` | Yes | No | Official `@radix-ui/react-popover` Root/Trigger/Content composition. |
| `primitives.tsx` | No | Yes, retained subset | Only SupplyDesk-specific `Textarea`, `Select`, `Radio`, `Switch`, states, `Card`, `Toast` and `TableShell` remain. Migrated duplicate primitives were removed from this file. |
| `separator.tsx` | Yes | No | Official `@radix-ui/react-separator` wrapper, used by Sidebar. |
| `sheet.tsx` | Yes | No | Official shadcn Sheet composition over `@radix-ui/react-dialog`, used by Sidebar. |
| `sidebar.tsx` | Yes | No at foundation layer | Official shadcn Sidebar composition with `Slot`, Sheet, Separator, Tooltip, Input, Skeleton and `use-mobile`. |
| `skeleton.tsx` | Yes | No | Official local loading skeleton wrapper. |
| `StatusBadge.tsx` | No | Yes, domain composition | SupplyDesk status/tone and count compatibility wrapper over official `Badge`. |
| `table.tsx` | Yes | No | Official semantic Table, Header, Body, Row, Head, Cell and Caption wrappers. |
| `tabs.tsx` | Yes | No | Official `@radix-ui/react-tabs` Root/List/Trigger/Content composition. |
| `TextField.tsx` | No | Yes, domain composition | SupplyDesk label/error/icon wrapper; its field is now official `Input`. |
| `tooltip.tsx` | Yes | No | Official `@radix-ui/react-tooltip` Provider/Root/Trigger/Content composition. |

There is no `Accordion` file and no Accordion usage. Decision: `NOT USED`.

## Import proof matrix

| SupplyDesk component | Imported UI primitive | Source file | Underlying library |
|---|---|---|---|
| `V2Button`, `IconButton`, mail/page action buttons | `Button` | `frontend/src/components/ui/button.tsx` | Official shadcn Button; `@radix-ui/react-slot` + CVA |
| `V2Badge`, `StatusBadge` | `Badge` | `frontend/src/components/ui/badge.tsx` | Official shadcn Badge/CVA wrapper |
| `RequestsPage`, `SuppliersPage`, `Messages`, `RequestsList`, `TextField` | `Input` | `frontend/src/components/ui/input.tsx` | Official shadcn Input over native HTML input |
| `RequestsPage`, `SuppliersPage` | `Checkbox` | `frontend/src/components/ui/checkbox.tsx` | `@radix-ui/react-checkbox` |
| `RequestTable`, `RequestsPage`, `SuppliersPage` | `Table`, `TableHeader`, `TableRow`, `TableHead`, `TableBody`, `TableCell` | `frontend/src/components/ui/table.tsx` | Official shadcn semantic HTML table wrappers |
| `MailDetail` in the experiment | `Tooltip`, `TooltipProvider`, `TooltipTrigger`, `TooltipContent` | `frontend/src/components/ui/tooltip.tsx` | `@radix-ui/react-tooltip` |
| `ListToolbar` | `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, radio items | `frontend/src/components/ui/dropdown-menu.tsx` | `@radix-ui/react-dropdown-menu` |
| `RequestsPage` toolbar | `Popover`, `PopoverTrigger`, `PopoverContent` | `frontend/src/components/ui/popover.tsx` | `@radix-ui/react-popover` |
| `EditRequestModal`, request preview, supplier preview | `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`, `DialogClose` | `frontend/src/components/ui/dialog.tsx` | `@radix-ui/react-dialog` |
| Experiment `Sidebar` | `SidebarProvider`, `Sidebar` | `frontend/src/components/ui/sidebar.tsx` | Official shadcn Sidebar; Radix Slot/Dialog/Separator/Tooltip plus local hook |
| `Messages` | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` | `frontend/src/components/ui/tabs.tsx` | `@radix-ui/react-tabs` |
| Accordion consumer | — | — | `NOT PRESENT` |

The official primitives are not inferred from appearance: the source imports,
registry-shaped composition and actual consumers were inspected. A full-tree
search found no remaining imports of the removed custom `Input`, `Checkbox`,
`Dialog`, `DropdownMenu`, `Tooltip` or `Tabs` exports from `primitives.tsx`.

## Removed custom primitives

The old local implementations of `Input`, `Checkbox`, `Dialog`,
`DropdownMenu`, `Tooltip` and `Tabs` were removed from the active primitive
surface and their consumers now use the official local files. Raw experiment
table markup, tabs, checkbox controls, preview dialogs, popover controls and
the ListToolbar dropdown were also replaced by the corresponding official
compositions. `useDialogFocus.ts` remains because the two production mail
composer dialogs still use that product-specific focus behavior; it is not a
replacement for the official Dialog foundation.

## Why they remain custom

The retained `Textarea`, `Select`, `Radio`, `Switch`, state blocks, `Card`,
`Toast` and `TableShell` are SupplyDesk-specific compositions or controls not
required by the migration minimum. `StatusBadge` and `TextField` are domain
wrappers, not competing foundations, because they now compose official Badge
and Input. The experiment's navigation content, mail context, status tones and
fixture-driven layout are product composition and intentionally remain local.
Adding Accordion would have introduced an unused component without a logical
expandable section, so it was correctly not added.

## Why the previous report said “shadcn-style”

That wording was accurate for the baseline commit `a610c2e`: the old UI folder
contained only five custom files, used native HTML elements and custom focus/
class helpers, and had no official config or Radix/CVA/class utility
dependencies. “Without new dependencies” meant those old primitives were
written locally and did not install an official component foundation. It does
not describe the post-migration checkout. This task deliberately added the
official dependencies and config required to make the foundation real.

## Visual baseline preservation

The experiment's existing CSS variables, Tailwind palette and scoped classes
were retained. The new primitives are used as wrappers around the same content
and layout; the only intentional compatibility styling is a narrow tabs-list
override and the dialog overlay token. The old custom dialog focus hook remains
where it is still a production mail requirement. No business or data behavior
was changed.

## Verification

### Browser and accessibility

- Focused command: `node ..\scripts\run_playwright.mjs --purpose
  VISUAL_ACCEPTANCE ui-experiment.spec.ts` from `frontend/`.
- Result: `18 passed, 6 skipped`; all four experiment routes were exercised at
  the required desktop-wide 1440px, desktop-compact 1280px, tablet-landscape
  1024px and mobile-large 390px profiles, with additional profiles in the
  matrix.
- Playwright axe checks reported zero violations on the four route renders.
- Manual interaction check passed: popover opened and closed with Escape,
  dialog focus stayed inside and returned to the opener after close, Radix Tabs
  activated correctly, checkbox state changed, and Tooltip content appeared.
- The first post-migration run exposed missing TabsContent IDs and a Dialog
  title association issue; both were fixed and the final run passed.

### Screenshots and visual comparison

- Before: `frontend/artifacts/ui-shadcn-migration-20260904/before/` — 16 PNGs
  (4 routes × 4 required profiles), captured from the baseline.
- After: `frontend/artifacts/ui-shadcn-migration-20260904/after/` — 32 PNGs
  (the required 16 plus additional matrix profiles).
- Rendered review covered desktop-wide Dashboard, Requests and Messages plus
  mobile-large Suppliers, and the corresponding baseline captures. No
  unacceptable overlap, clipping, overflow or hierarchy drift was found. The
  Messages tabs were adjusted back to the baseline underline treatment after
  the first generated shadcn render introduced a centered pill treatment.

### Automated checks

| Check | Result |
|---|---|
| Workspace guard | PASS |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run lint` | PASS, 0 errors and 8 warnings |
| `npm --prefix frontend run build` | PASS |
| `npm --prefix frontend test` | PASS, 340 passed and 12 skipped |
| `git diff --check` | PASS |
| HTTP `GET /` on `127.0.0.1:8000` | 200 |
| HTTP `GET /api/auth/me` | 200, unauthenticated JSON response |
| HTTP protected `/api/dashboard/summary` | 401, expected without auth |
| HTTP unknown `/api/does-not-exist` | 404, expected error handling |

The canonical server remains listening on port `8000` and serving the built
frontend at closeout. `scripts/audit_toolchain.py` is absent, and the separate
`browser_geometry_audit.mjs` helper is also absent; those checks are
`NOT VERIFIED` and were not replaced by guesswork.

## Final recommendation

Accept the migration as `REAL_SHADCN` for the requested UI foundation. Future
components can be added with the checked-in `frontend/components.json` and
official CLI/registry workflow. Keep the remaining domain compositions local
until a concrete official component requirement exists. No push was performed.
