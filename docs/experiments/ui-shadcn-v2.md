---
document_id: UI-EXPERIMENT-SHADCN-V2-20260904
status: CURRENT
canonical: false
owner: product-design
updated_at: 2026-09-04
---

# SupplyDesk UI Experiment v2 — design direction

## Scope

This is an isolated, frontend-only visual experiment. It is reachable under
`/experiment/ui-shadcn-v2/*` and does not replace the production routes. The
experiment uses static, non-sensitive examples so it can be reviewed without
logging into the real workspace. Backend, API contracts, database, auth,
request lifecycle, supplier matching and mail actions are non-goals.

## Product job

The user is a procurement specialist who compares many requests, suppliers and
replies during a long workday. The primary job is to identify what needs
attention, scan structured data quickly, and move from request to supplier to
communication with a clear next step.

The mobile job is narrower: see urgent work, open a request summary, or read a
supplier message without rotating the device. Secondary detail can move behind
progressive disclosure.

## Visual identity

SupplyDesk v2 is a quiet procurement workbench: a warm paper-like canvas,
graphite navigation rail, cobalt action color, and measured blue rule lines
that feel closer to a well-run operations desk than a generic admin dashboard.
The product is recognizable without its logo through a stable left rail,
compact numerical metadata, request-first hierarchy and a conversation surface
that keeps supplier context visible beside the message.

## Visual thesis and rationale

Frequent comparison is the dominant task, so the design uses one shared reading
axis, compact rows and restrained semantic color instead of a grid of loud
cards. Important work is surfaced through a narrow attention panel and stable
status badges; the rest of the canvas stays quiet. The expected evidence is a
first-viewport scan at 1440px and 1024px with no accidental wrapping or
unexplained empty space.

| Product reason | Principle | Concrete decision | Evidence |
|---|---|---|---|
| A buyer scans active work repeatedly | Density with hierarchy | KPI rail + real tables + one attention column | Dashboard screenshot and table geometry |
| Status and action are different concepts | Semantic state | Muted status badges; actions stay in neutral/primary buttons | Requests and suppliers screenshots |
| A reply only makes sense in request context | Context before content | Message detail keeps request strip and context rail visible | Messages screenshot |
| Existing production UI must remain untouched | Isolated comparison | Separate route and `.sd-v2-theme` token scope | Route smoke and Git diff |
| Desktop is the main work surface | Intentional compression | 238px rail, 24px page gutter, 3-column mail workbench | 1440/1280/1024 renders |
| Narrow screens preserve the primary job | Progressive disclosure | Rail becomes top bar; message detail becomes one-column | 390px render and overflow check |

## System decisions

- Semantic CSS variables are scoped to `.sd-v2-theme`: background, foreground,
  card, popover, primary, secondary, muted, accent, destructive, border,
  input, ring, sidebar and radius tokens, plus only `success`, `warning` and
  `info` where product meaning requires them.
- The existing local `Button`, `Badge`/`StatusBadge`, `Input`, `Tabs`, `Table`,
  `Dialog` and `Sheet` patterns remain the conceptual primitive layer. No new
  dependency is added because React/Tailwind/Lucide and local primitives are
  already present.
- Surfaces use 8–12px radius, 1px borders and almost no shadow. Shadow is
  reserved for the mobile drawer and request preview dialog.
- UI text keeps the repository's `Public Sans` → `Geist` → system fallback.
  IDs and counts use tabular numerals; embedded mail copy is not re-rendered as
  production email HTML in this static experiment.
- Motion is limited to drawer/dialog feedback and hover transitions. Reduced
  motion falls back to static states.

## Reference synthesis

| Reference/category | Transferable principle | Adaptation decision | Deliberate non-copy |
|---|---|---|---|
| Existing SupplyDesk / IA | Request → supplier → communication is the product model | Keep that order in nav, dashboard and message context | Do not reuse the production card-heavy composition |
| shadcn theming / visual system | Semantic CSS variables let components change theme without rewrites | Use scoped v2 tokens and local primitives | Do not install the CLI or copy a stock dashboard block |
| Radix accessibility guidance | Native semantics, focus management and keyboard behavior matter | Use real buttons, labels, `role=dialog`, focus-visible rings and Escape | Do not replace interaction semantics with clickable `div`s |
| Data-dense UI | Stable axes make comparison fast | Keep table headers and values aligned; reserve the last-column gutter | Do not collapse requests/suppliers into oversized tiles |
| Split-view communication workspace | List/detail/context is the right reading model | Use navigator + message surface + context rail | Do not put email body inside a tiny card inside a giant card |

## Deliberate exclusions

No gradients, glassmorphism, decorative charts, new business fields, AI
backend, supplier scoring, new filters, new API calls, or production route
replacement. The v2 route is a reviewable presentation layer and not a second
source of truth for operational data.

## First-render acceptance criteria

1. All four experiment routes render at `1440×900`, `1280×800` and
   `1024×768` without page-level horizontal overflow.
2. Requests and suppliers remain readable as structured tables with aligned
   headers, semantic status and deliberate action columns.
3. Messages reads as a workbench, with list, selected message, request context,
   attachments and a clear reply next step visible in one desktop frame.
4. At `390×844`, the primary job remains available: navigation can open, the
   requests/suppliers tables become stacked records, and message reading is
   full-width.
5. Search, status tabs, message selection, mobile navigation and request
   preview dialog have visible feedback and keyboard-reachable controls.
6. `npm run typecheck`, `npm run lint`, `npm run build`, `git diff --check` and
   a real browser smoke test pass. Any unavailable authenticated BEFORE screen
   is reported as `NOT VERIFIED`, not inferred.
