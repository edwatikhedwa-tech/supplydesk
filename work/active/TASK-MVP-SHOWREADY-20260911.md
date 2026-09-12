# Task: MVP readiness before user presentation

Task ID: TASK-MVP-SHOWREADY-20260911
Status: COMPLETE_WITH_LIMITATIONS
Created: 2026-09-11

## Goal

Bring the existing SupplyDesk MVP to an honestly demonstrable state through
the approved backlog: first close or evidence-check P0 items, then continue
P1/P2 in dependency order. Do not replace working architecture or implement
deferred live telephony.

## Current State

- The canonical product backlog is `docs/product/MVP_BACKLOG.md`.
- The approved UI contract is `docs/product/APPROVED_MVP_INTERFACE.md`.
- `SUP-001` (Checko and supplier card) is DONE locally: a live server-side
  lookup returned registry facts without 401 or key disclosure; an unavailable
  finance report was correctly distinguished from an auth failure. The card
  now discloses Checko risk state. Broader card IA remains SUP-010.
- `SUP-002` is PARTIAL: real authenticated navigation, HTTP and error-path
  checks passed; a fresh logout/login was intentionally not run because it
  would disrupt the owner's working session.
- `SUP-003` is DONE: the reproduced AI-context ambiguity and Checko
  configuration-message leak have neutral, user-safe UI handling.
- `SUP-004` is DONE: financial values now have one compact Russian formatter
  from rubles through trillions; live desktop, tablet and mobile rendering
  confirms the value and sign do not wrap or disappear.
- `SUP-005` is DONE: an existing personal thread note remains discoverable by
  a secondary marker and opens its contextual panel without changing mail.
- `SUP-007` is DONE after source and live UI audit; Messages keeps its
  approved special header while the remaining primary screens share one
  responsive component.
- `SUP-008` is DONE: Dashboard now renders only sections with current work,
  plus one intentional full-empty state; its mobile layout has no horizontal
  overflow.
- `SUP-009` is DONE: Requests, Suppliers, and Blacklist preserve their
  supported search/filter/status behavior and have no horizontal overflow at
  390 px.
- `SUP-010` is DONE: the supplier card presents available identity,
  reliability, interaction and workspace layers without inventing missing
  classification/contact data; its finance chart now exposes a safe
  year-over-year percentage.
- `SUP-011` is DONE: the approved dashboard composition distinguishes system
  attention from user tasks; a full calendar remains correctly gated on the
  later task/reminder data model rather than a UI library.
- `SUP-012` is DONE: request rows show an accessible, secondary count of
  suppliers that have replied, separately from unread-message counts.
- `SUP-013` is PARTIAL: Sidebar fallbacks are explicit and truthful. The
  requested surname-initial format is deliberately not inferred from an
  unstructured display name; it needs a separate consent/scope decision for
  structured profile data.
- `SUP-014` is DONE: the wide sidebar is readable by default and a manual
  collapse/expand choice survives reload using local browser storage.
- `SUP-015` is PARTIAL: every task-creation surface has a concrete,
  recoverable confirmation with the saved title, available deadline, open and
  undo actions. Errors retain entered text. Dashboard open targets the new
  task. The current API has date but no time; a truthful date-only notice is
  therefore used until SUP-017. The forms and compact sidebar were
  visual-checked at 390, 768 and 1440 px without horizontal overflow; no live
  create/delete was performed against the owner's data.
- `SUP-006` is DONE: legacy per-user thread notes remain private; a new
  workspace-scoped note is stored separately and exposes author/create/update
  metadata. The Messages panel has explicit personal/team tabs and temporary
  compatibility with a backend that has not yet reloaded. The canonical
  backend was restarted with outgoing mail forced off; migration 041, both
  tabs and mobile overlay were then read-only verified. Disposable-DB tests
  also prove cross-workspace isolation.
- `SUP-016` is DONE: the Messages context panel now presents a compact,
  read-only activity list of the current thread's latest email, its private or
  workspace note, and active/completed tasks linked to the request or global
  supplier. It reads existing facts only, limits the list to eight entries,
  and orders them by timestamp. A live record showed a related task and email;
  the panel rendered without viewport overflow at 1440, 768 and 390 px.
- `SUP-017` is DONE: additive migration 042 stores task description, local
  date/time plus explicit IANA timezone, priority and a workspace assignee;
  all creation forms and the inline editor support the extended fields.
  Existing date-only tasks remain compatible. Workspace assignees can edit
  content and status, but cannot delete or reassign a task they do not author.
  Unit and visual checks covered the data model, permissions and 1440/768/390px
  layouts without horizontal overflow.
- `SUP-018` is DONE: `/calendar` provides the approved `month`, `week`,
  `agenda`, `upcoming` and `today` views over active dated tasks, with links
  back to the source task and no added calendar dependency. Real owner data,
  the empty-today state and navigation were checked at 1440, 768 and 390px;
  no page overflow was measured.
- `SUP-019` is DONE: task reminders use one provider-neutral record with
  `channel`, local scheduled time, IANA timezone, status, recipient and
  timestamps. In-app and Email can be created, changed, removed and appear in
  the task list/calendar; no delivery process is implied or started.
- `SUP-020` is DONE: phone reminders extend the same record in migration 044.
  Development/test uses a local `PHONE_REMINDER_MOCK_TRIGGERED` status/log
  only; production visibly disables the choice as «Скоро». No phone provider,
  TTS, callback, billing or network integration exists.
- `SUP-021` is PARTIAL: migration 045 stores contact persons only inside the
  workspace, with private/team visibility and author-only mutation. The
  unsaved card/form rendered at desktop, 768 px and 390 px; disposable-DB
  CRUD/isolation passed. No contact was saved into the owner's real data, so a
  live write round-trip remains intentionally unverified.
- `SUP-022` is PARTIAL: CSV-first preview/mapping is available from
  «Поставщики». Confirmed Apply accepts UTF-8 CSV in memory and creates only
  new cards with a valid INN; duplicates are skipped strictly by INN, existing
  cards are never updated or merged, and the audit trail keeps source, line and
  author. The full preview/confirmation UI was rendered with an artificial CSV
  (one create candidate, one INN duplicate and one missing-INN row) at 1280,
  768 and 390 px. Final Apply was intentionally not invoked, so no owner-data
  card was created; non-CSV sources remain intentionally unverified.
- `SUP-023` is PARTIAL: migration 046 stores workspace-only classification
  facts with type, value, source, confidence and optional source URL. The
  supplier card renders them and supports manual labels only; the UI cannot
  claim registry/AI provenance. Focused tests prove source separation, owner
  control and invalid-value rejection. The unsaved form rendered at desktop,
  768 px and 390 px; no label was saved into owner data, and registry/AI
  producer integrations remain deliberately absent.
- `SUP-024` is PARTIAL: the supplier detail and workspace-data mutation paths
  require the current workspace to own the global supplier card. A disposable
  two-workspace regression confirms no cross-card read or contact/
  classification write, including shared-INN companies. A second live browser
  session was not opened, so that visual/API session proof is not claimed.
- `SUP-025` is PARTIAL: the global support mini-chat is the primary channel;
  `/help` has been renamed «Справка», removed from the main sidebar and remains
  available through a secondary link in that window. It is a truthful local FAQ
  with a separate unknown-question state and copy-only manual escalation. It
  does not create a support ticket or call an AI/service. Browser checks covered
  an exact CSV answer and an unsupported WhatsApp-bot question. A full knowledge
  base remains outside the current slice.
- `SUP-026` is DONE as a decision not to add versioning without demonstrated
  need. The existing two-note model remains; a focused multi-member test now
  verifies that a workspace note identifies its last editor, not a stale
  original author. Version history requires separate conflict/recovery/audit
  criteria before implementation.
- `SUP-027` is DONE as an evidence-based non-expansion: separate registry,
  finance, response and per-deal rating facts do not have a valid shared score
  contract. No composite score is shown until weights, provenance, freshness,
  missing-data behavior and an accountable owner are separately approved.
- The Messages AI-context ambiguity was fixed locally and visual-checked;
  it is not a replacement for the wider MVP program.

## Decisions

- Work from highest-priority unverified backlog item; do not create parallel
  feature work merely because a later item is easier.
- Treat Checko official API documentation as the source of truth for endpoint
  and available data claims. Display only supplier-useful facts, with public
  registry data kept distinct from workspace knowledge.
- Do not place API keys, request URLs containing keys, or `.env` contents in
  source, logs, documentation, or this task card.

## Sources

- `docs/product/MVP_BACKLOG.md` (SUP-001..028)
- `docs/product/APPROVED_MVP_INTERFACE.md`
- Checko official API pages: `/integration/api/company`, `/finances`, and
  `/integration/api` (accessed 2026-09-11)

## Next Action

No further authorized P0/P1/P2/P3 implementation item remains. `SUP-028`
real-phone-provider integration is explicitly deferred and must not be started
without a separate provider, cost, consent and production-integration decision.
