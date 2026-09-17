---
document_id: DOC-PRODUCT-MODEL-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Product Model

What SupplyDesk actually is, as verified by this audit — not the aspirational pitch.

## Core loop

1. A buyer creates a **заявка** (request): a name, description, and one or more **positions**
   (line items — e.g. "печь-камин с варочной плитой").
2. The system searches the web for candidate suppliers per position, crawls/enriches them
   (company registry + finance via Checko when configured), and produces a supplier list.
3. The buyer emails suppliers (individually or in bulk) asking for a quote.
4. Replies land as **correspondence**, threaded per request+supplier, and are surfaced in
   Messages. An `AI assistant` can answer questions using that history.
5. The buyer tracks status per supplier (sent/waiting/answered/error), can flag a thread for
   follow-up, create tasks/reminders, and — separately — get a one-off Dellin shipping quote for
   a specific request+supplier.

## Feature areas and their real maturity

| Area | Maturity | Detail |
|---|---|---|
| Requests/positions/search | Mature, durable (survives serverless restarts mid-search) | [`../technical/DATA_FLOW.md`](../technical/DATA_FLOW.md) |
| Suppliers (identity/enrichment) | Mature model, one confirmed live data-integrity gap | [`SUPPLIERS.md`](SUPPLIERS.md) |
| Messages/mail | Mature, careful safety invariants (no physical deletion, hard-bounce suppression, dedup-by-final-recipient) | [`MESSAGES.md`](MESSAGES.md) |
| AI assistant | Real, working, budget-capped, context-scoped correctly | [`AI_ASSISTANT.md`](AI_ASSISTANT.md) |
| Tasks | Real CRUD | in-app reminders work; email/phone reminders are recorded but never delivered |
| Calendar | A Dashboard widget only (full-page version deleted 2026-09-17 as dead code) | real task data, not fixture |
| Campaign monitoring (pause/resume/stop a bulk send) | **Missing from the live UI** — exists only in the retired `frontend/` (v1) | `GAP-001` |
| Logistics quote | Small, real, single-purpose (one request/one supplier, Dellin only) | live-verified against the real API |

## What is explicitly NOT a product invariant yet

- No multi-tenant self-signup — single seeded owner account per deployment.
- No push notifications when the app tab is closed (reminders only fire while a tab is open and
  polling).
- No general file/attachment browsing for received mail (attachments are stored but not surfaced
  in the UI — `GAP-004`).

See [`USER_FLOWS.md`](USER_FLOWS.md) for narrative walkthroughs of each area, and
[`../system/CURRENT_STATE.md`](../system/CURRENT_STATE.md) for the full IMPLEMENTED/PARTIAL/
MOCK/NOT_IMPLEMENTED matrix.
