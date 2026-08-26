# Extractable components

## AppTopBar
- Source: `supplier_finder.html`
- Category: `layout`
- Description: Product identity, request context, completion status, and progress toggle.
- Extractable props: `status`, `requestLabel`, `showProgressAction`.
- Hardcoded: brand label, mark, status copy, visual tokens.

## RequestSummary
- Source: `supplier_finder.html`
- Category: `basic`
- Description: Request headline, supply position chips, and confirmed/possible KPI pair.
- Extractable props: `title`, `subtitle`, `positions`, `confirmedCount`, `possibleCount`.
- Hardcoded: semantic color mapping and spacing.

## FilterBar
- Source: `supplier_finder.html`
- Category: `basic`
- Description: Supplier filters and selection/export actions.
- Extractable props: `regions`, `kinds`, `roles`, `selectedCount`, `exportDisabled`.
- Hardcoded: labels and button copy.

## SupplierCard
- Source: `supplier_finder.html`
- Category: `basic`
- Description: Supplier identity, evidence, risks, coverage, and contact actions.
- Extractable props: `supplier`, `verified`, `selected`, `coverage`, `contacts`, `risks`.
- Hardcoded: action labels and semantic status styles.

## ExportDialog
- Source: `supplier_finder.html`
- Category: `basic`
- Description: Selected supplier contact table shown in a modal dialog.
- Extractable props: `rows`, `visible`.
- Hardcoded: table headings and close action.
