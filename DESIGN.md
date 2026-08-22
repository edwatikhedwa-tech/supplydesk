# Supplydesk design direction

## Product personality

Supplydesk is an operations workbench for a buyer: calm, precise, and fast to scan. The interface should feel trustworthy and workmanlike, with enough character to avoid looking like a generic admin template.

## Visual direction

- A quiet cool canvas with a graphite navigation rail and cobalt action color.
- White surfaces are reserved for work areas, not every nested grouping.
- Prefer one clear container per task, dividers inside lists, and restrained elevation for dialogs only.
- Use color to communicate state and action priority, not to decorate.

## Typography

- Procure Sans is the product typeface for headings and UI copy.
- Headings use compact, slightly tight tracking and strong contrast with supporting copy.
- Metadata and table labels are small but never below 10px; important values stay at 13–16px.
- Long company names wrap to two lines in cards and remain readable in tables.

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

## Do / don't

Do use hierarchy, whitespace, and dividers to guide scanning. Do let content determine row height. Do keep the request context available while reviewing suppliers.

Don't add decorative gradients, extra badges, or a rounded container around every sentence. Don't turn a data-heavy workflow into a landing page. Don't solve mobile by shrinking desktop controls until they become hard to operate.
