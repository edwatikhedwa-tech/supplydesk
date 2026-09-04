---
document_id: UI-DESIGN-SYSTEM-20260904
status: CURRENT
canonical: false
owner: product-design
updated_at: 2026-09-04
---

# SupplyDesk UI foundation — 2026-09-04

## Visual identity

SupplyDesk — это не generic admin panel, а спокойный рабочий стол снабженца.
Визуальная система должна помогать сравнивать компании, понимать состояние
переписки и выполнять следующее действие без визуального крика. Узнаваемость
строится на графитовом navigation rail, белых рабочих поверхностях, холодном
синем action color, табличной точности и компактной иерархии «заявка → поставщик
→ коммуникация».

## Product rationale → UI decision → evidence

| Product reason | Principle | Concrete decision | Acceptance evidence |
|---|---|---|---|
| Снабженец сканирует много объектов | Density with hierarchy | компактные строки и спокойные counters | first viewport, long names, 13+ rows |
| Ошибка и ожидание требуют разного действия | Status is semantic | badge только для состояния, действия — кнопки | rendered status/error states |
| Ответ нужно читать в контексте заявки | Context before content | request strip above message history | selected thread screenshot |
| На мобильном важнее чтение и reply | Progressive disclosure | list → full-width detail, no squeezed sidebar | 390×844 and 360×800 screenshots |
| Частые actions должны быть предсказуемыми | Shared controls | Button variants and common focus ring | keyboard/pointer interaction |

## Tokens

Текущая Tailwind palette сохраняется и оформляется как продуктовые роли:

- Canvas: `ink-50` / `#f8fafc`.
- Surface: white.
- Text: `ink-900`, supporting text `ink-500`, quiet `ink-400`.
- Action: `accent-600`/`accent-700`; use only for primary action, active link or
  selected navigation.
- State: emerald for success, amber for attention/waiting, rose for error;
  never use state colors for counters or decoration.
- Borders: `ink-200` for meaningful separation, `ink-100` for internal rhythm.
- Radius: `rounded-lg` controls, `rounded-xl` surfaces, `rounded-2xl` only for
  intentional hero/empty surfaces.
- Spacing: 4, 8, 12, 16, 24, 32 px. New UI must not introduce arbitrary gaps.
- UI font: `Public Sans`, then `Geist`, then the local system UI stack
  (`ui-sans-serif`, `system-ui`, `Segoe UI`); no remote font request is added,
  so the app remains usable offline. Embedded email content keeps its isolated
  sender-controlled font stack as an intentional content exception.
- Screen titles use the shared `page-title` role: `28px` on mobile up to `32px`
  on desktop. The login display title uses `32px` on mobile up to `36px` on
  desktop, matching the reference scale without making dense B2B content
  oversized.
- Primary screen `h1` elements use the local `sd-shimmer-heading` CSS treatment:
  a restrained blue gradient sweep with a `prefers-reduced-motion` static
  fallback. Shimmer is reserved for page titles, not error messages, metadata,
  statuses or mail HTML.

## Primitives

The staged foundation adds local primitives under `frontend/src/components/ui/`
without adding shadcn/Radix or another dependency:

- `Button`: `primary`, `secondary`, `ghost`, `danger`, `link` variants and
  `sm`/`md` sizes; all preserve 40px minimum touch height where appropriate.
- `StatusBadge`: semantic state only (`success`, `info`, `warning`, `danger`,
  `neutral`), with optional dot; no quantity or action labels.
- `Count`: quiet numeric metadata for list headers and tabs.
- `TextField`: consistent search/input surface with label, focus and error hooks.

The current foundation uses these primitives in `/messages` and the main
operational pages. Product-specific status, mail rendering and data-fetching
components remain local where their behavior is domain-specific.

## Design System v1 foundation extension — 2026-09-04

The semantic layer now also exposes canvas/surface/text/border/action/state
roles, 4/8/12/16/24/32 spacing, 6/10/14 radii and shared control height in
`frontend/src/index.css`, with matching Tailwind aliases. The canonical local
inventory is:

`Button`, `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Switch`,
`Badge`/`StatusBadge`, `Tooltip`, `DropdownMenu`, `Dialog`, `Sheet`, `Tabs`,
`Card`, `Skeleton`, `EmptyState`, `ErrorState`, `LoadingState`, `Toast`,
`TableShell`, `TextField`, `Count`, `PageFrame` and `PageIntro`.

The migration intentionally covered shared shell, dashboard, requests,
suppliers, blacklist, settings, new request, edit modal, tables and list
toolbar. No second UI dependency was added, and domain-specific mail states
were not replaced with generic fake data.

## Reference synthesis

References supplied by the owner: Linear, Vercel Dashboard, Stripe Dashboard,
Notion. They are used as problem/category benchmarks, not copied layouts.

| Category/reference | Transferable principle | SupplyDesk adaptation | Deliberate non-copy |
|---|---|---|---|
| Information architecture / Linear | clear object hierarchy and low-noise navigation | request group → supplier row → message detail | no keyboard-first issue tracker clone |
| Data-dense UI / Stripe Dashboard | restrained surfaces and aligned metadata | quiet counters, stable row rhythm, semantic status | no KPI-card wall or finance-specific density |
| Visual system / Vercel Dashboard | strong contrast axis and simple surfaces | graphite rail + white workbench + blue action | no monochrome developer dashboard language |
| Progressive disclosure / Notion | reveal detail in the context of the object | list → full-width reading detail, compact relation strip | no editor canvas or block model |

Synthesis: a procurement-specific split workspace with a quiet information layer,
clear semantic states and one unmistakable action path. The signature is the
request context strip and its consistent transition into supplier communication.

## Acceptance criteria for `/messages`

- The first viewport identifies page, search, section, selected request and
  primary action within seconds.
- Buttons use the shared variants; status badges do not carry counts/actions.
- The detail panel consumes available width without artificial max-width.
- Long company names, long emails, missing company and multiline message content
  do not clip or overlap.
- Search, tabs, selection, reply, manual link and error recovery remain reachable.
- No page-level horizontal overflow at required viewports.
- `PASS`: full rendered QA covers the repository viewport matrix; `PARTIAL` for
  the owner-facing comparison because the before image is inline-only and no
  approved reference image was supplied.
- Any future width not covered by the named Playwright profiles must be marked
  `NOT VERIFIED`, even if the desktop CUA render looks correct.
