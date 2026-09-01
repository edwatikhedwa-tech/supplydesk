# Supplydesk design direction

> **SUPPORTING DESIGN REFERENCE — NOT CURRENT STATE.** Текущее состояние
> проекта находится в [`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md),
> а правило актуализации — в [`../../docs/DOCUMENTATION_POLICY.md`](../../docs/DOCUMENTATION_POLICY.md).

## Product personality

Supplydesk is an operations workbench for a buyer: calm, precise, and fast to scan. The interface should feel trustworthy and workmanlike, with enough character to avoid looking like a generic admin template.

## Visual direction

- A quiet cool canvas with a graphite navigation rail and cobalt action color.
- White surfaces are reserved for work areas, not every nested grouping.
- Prefer one clear container per task, dividers inside lists, and restrained elevation for dialogs only.
- Use color to communicate state and action priority, not to decorate.

## Typography

- The application shell uses one platform-native UI stack: `-apple-system`/SF on Apple platforms, then Inter, Segoe UI, and the system UI fallback on other platforms. This gives the product an Apple-like rhythm without shipping proprietary SF Pro files.
- The type scale is progressive and tokenized: page titles use a fluid `24–28px` range, display titles use a fluid `28–32px` range, and KPI numbers use a fluid `28–30px` range. Body/UI text remains `14px`, metadata `12px`, and compact captions `11px`.
- Headings use compact, slightly tight tracking and strong contrast with supporting copy; identical semantic roles must use the same family, size, weight, and line-height on every route.
- Metadata and table labels are small but never below 11px; important values stay at 14–16px unless a documented KPI role applies.
- Long company names wrap to two lines in cards and remain readable in tables.

### Progressive typography decision — 27 August 2026

Product/user/task reason → the buyer compares many requests, suppliers, and messages quickly across desktop and narrow screens → keep semantic roles stable while allowing only page titles and metrics to breathe with the viewport → use one platform-native stack plus tokenized fluid title/metric sizes → verify computed styles, row scanability, and overflow at `1640px`, `1024px`, and `390px`.

Reference synthesis:

- Platform-native UI typography: use the operating-system UI family first, with Inter/Segoe UI fallbacks. Adapted here as a practical Apple-like rhythm without copying or bundling proprietary SF Pro files.
- Data-dense workbench typography: keep body/UI at `14px`, metadata at `12px`, and numeric values tabular and stable. Adapted here so the procurement workflow stays scannable while titles scale progressively.
- Deliberate exclusion: no display-sized headings on work surfaces, no arbitrary per-route font families, and no decorative type effects that compete with request status or error recovery.

Acceptance criteria for the rendered slice: all primary route titles share one computed family and `28px` desktop / `24px` mobile bounds; the `/requests` error is a single full-width detail row; the final numeric column has at least `24px` inner gutter; toolbar controls form one centered desktop row; body and table content have no unintended horizontal overflow.

## Spacing and layout

- Base rhythm: 4px increments; common gaps are 8, 12, 16, 20, 28, and 32px.
- Desktop content uses a max width around 1500px with 30–34px gutters.
- Search results use a two-column workbench at wide widths: results first, request context second.
- At medium widths the request context moves above the result list so the next step stays visible.
- At mobile widths controls become a two-column action grid, supplier tables become stacked records, and the navigation becomes a menu.

## Semantic colors

- Cobalt: primary actions and focus.
- Green: confirmed, sent, or complete.
- Amber: needs attention, partial confidence, or in progress.
- Red: destructive or failed states.
- Ink and muted ink carry hierarchy; borders stay quiet.

## Components

- Navigation: compact rail with a single active treatment and readable labels when space allows.
- Command bar: global search plus only the actions relevant to the current workspace.
- Lists and tables: strong first column, restrained row separators, predictable action placement.
- Filters: a single control band; primary bulk action is visually dominant, secondary actions remain quiet.
- Dialogs: bottom-aligned sheets on mobile and centered dialogs on desktop; actions stay reachable.
- Loading/error/empty states: explain what is happening, preserve context, and offer one clear recovery action.

## Interaction principles

- Keep search, filters, selection, and send flows intact.
- Prefer reversible actions and explicit feedback for mail, blacklist, and irrelevant actions.
- Maintain visible focus, semantic buttons/links, and labels for every form control.
- Do not hide essential table information on desktop; on mobile, move secondary fields into the record body rather than clipping them.

## Экран входа — осознанное исключение

Решение владельца проекта от 27 августа 2026 года: экран входа остаётся с
WebGL-кольцами, градиентным фоном и анимацией логотипа. Это единственный экран,
где правила «без декоративных градиентов» и «не превращать рабочий инструмент в
лендинг» намеренно не действуют.

Обоснование: вход — не рабочая поверхность. Снабженец видит его раз в сессию,
данных на нём нет, и «лицо продукта» здесь уместнее плотности. Внутри
приложения правила ниже действуют в полном объёме.

Инженерное условие, при котором исключение не стоит ничего: фон грузится
лениво (`lazy(() => import('@/components/MagicRings'))`), поэтому three.js
(465 КБ) не попадает в общий бандл и не замедляет остальные экраны.

## Do / don't

Do use hierarchy, whitespace, and dividers to guide scanning. Do let content determine row height. Do keep the request context available while reviewing suppliers.

Don't add decorative gradients, extra badges, or a rounded container around every sentence. Don't turn a data-heavy workflow into a landing page. Don't solve mobile by shrinking desktop controls until they become hard to operate.
