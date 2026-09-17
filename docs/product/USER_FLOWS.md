---
document_id: DOC-PRODUCT-USER-FLOWS-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# User Flows

Narrative walkthroughs, verified against actual code (not UI mockups treated as functionality).
Technical/function-level detail lives in [`../technical/DATA_FLOW.md`](../technical/DATA_FLOW.md).

## 1. Authentication

User lands on `/login` → chooses email+password or "Войти через Яндекс" (Google/Mail.ru are
visibly disabled, labeled "Скоро" — honest, not a hidden stub) → session cookie set → every page
load re-checks `/api/auth/me`; an expired session redirects back to login with a visible message.
**Verified real**, single-owner-account model (not general signup).

## 2. Requests

Buyer clicks "Новая заявка", fills name/description/positions → request created in `draft`
status → starts search → status becomes `searching`, progress bar advances as the durable job
queue processes SERP results and enrichment in the background (survives a page reload or a
serverless cold start mid-search) → status becomes `completed` (or `error` with a visible reason
if e.g. XMLRiver credentials are missing). Buyer can filter/sort the supplier table, mark a
supplier irrelevant, blacklist a domain, or add a manual ИНН.

**Not currently possible from this flow:** monitoring or pausing an in-flight *bulk email send*
campaign — that whole surface (`CampaignPage.tsx` in the old frontend) has no v2 equivalent
(`GAP-001`). A buyer who starts a bulk send today cannot pause/stop it from the live UI.

## 3. Suppliers

Discovery → enrichment → contacts → request association, per
[`SUPPLIERS.md`](SUPPLIERS.md)'s detailed model. From the user's perspective: a supplier found
via one request's search becomes visible/reusable across other requests in the same workspace
(the `global_suppliers` card), with registry/finance data attached once resolved. **Known rough
edge, confirmed live:** if a supplier later replies from a personal address (Gmail/Yandex/Mail.ru)
that differs from the company domain the search found, the system can create a *second*,
duplicate supplier card that holds the actual conversation — the enrichment data ends up "stuck"
on the original, unlinked card. This affects roughly 1 in 9 suppliers in the audited local
database. See `GAP-003`/`INV-SUP-002`.

## 4. Messages

Buyer opens Messages, sees threads grouped by request, plus "Письма без заявки" for anything the
system couldn't auto-match. Opening a thread marks it read. Replying, forwarding a link, viewing
inline images — all render through a sanitized HTML pipeline (no raw script/style injection
possible). A thread can be marked `in_progress`/`deferred`/`rejected` (a personal workflow label,
never touches sending/blacklist). A thread with no reply after its SLA window shows
`needs_followup`, offering "Связаться" (record a call result) or "Напомнить" (create a task).
**No message or thread is ever physically deleted** by any user action — only status/visibility
changes.

## 5. AI Assistant

From an open thread, "Открыть ИИ-помощника" lets the buyer ask a question; the assistant answers
using that thread's own message history, optionally extended with other *already-replied*
suppliers on the same request (a UX-level suggestion — the real security boundary is
server-side re-validation of every thread id against workspace+request, not this client filter).
Capped at 10₽/day of spend by default; further questions are refused with a clear "лимит
достигнут" message rather than silently failing.

## 6. Tasks / Calendar

Buyer creates a task (optionally tied to a request/supplier), sets a due date/time and a
reminder channel. **What actually happens at the due time:** if the tab is open, a toast appears
and (if permitted) a desktop notification fires, polled every 45 seconds. If the channel chosen
was "Email" or "Телефон", nothing is sent — email has no send path at all, and the phone option
is explicitly labeled a mock in its own UI copy. The Dashboard shows a real calendar widget with
dots on days that have tasks; clicking a task/day opens the task detail. There is no dedicated
full-page calendar any more (removed 2026-09-17 as unreachable dead code after its own nav link
was already removed).

## 7. Logistics quote

From a request+supplier pair, the buyer can request a one-off Dellin shipping-cost estimate.
Small, self-contained, live-verified against the real Dellin API — not a mock.
