# frontend-v2 changelog

Append-only log of the decisions implemented while building frontend-v2 on
`experiment/frontend-v2-greenfield-20260905`. Each entry names the commit,
what changed, and why — for bugs, the root cause, not just the symptom.
Verification method throughout: `npx tsc -b --noEmit`, `npm run build`, live
testing against the real LOCAL_CANONICAL backend (`:8000`) via the browser,
and `tests/run-tests.ps1 -Quick` when a backend file changed (baseline:
82/91 passing — the other 9 fail in `test_change_classifier.py` because this
machine has no `pwsh`, unrelated to this work).

## 2026-09-08 — supplier table density, request-table fit, task→company preview, AI-context list highlight

- **Suppliers page rebuilt as a real table** (again): the previous pass used
  a card-per-company layout, which read as flat/dense compared to the
  legacy frontend's table. Rebuilt as an actual `<table>` with the same
  columns as `RequestDetail`'s, and — the specific complaint — profit is
  now bold with a colored trend arrow (▲ green when positive, ▼ red when a
  loss), matching the legacy frontend's treatment instead of plain grey
  text. Revenue is bold black, not muted.
- **`RequestDetail`'s supplier table no longer needs horizontal scroll**:
  `min-width` on an auto-layout table is a floor, not a cap — cell content
  (long emails, badge text) was still pushing real width past 1600px even
  at a 1400px viewport. Switched to `table-fixed` with an explicit
  `<colgroup>` and `truncate`/`min-w-0` on every text cell, and compacted
  the "Переписка"/"Не подходит" actions from labeled buttons to icon-only
  buttons with a tooltip. Verified via `scrollWidth` vs `clientWidth` in the
  live DOM (was 1657 vs 1161, now equal).
- **Ghost-button hover made visible everywhere**: `Button`'s `ghost` variant
  hovered to the exact same background tint (`bg-surface-hover`) that the
  table rows it usually sits in already use on row-hover, so hovering the
  button looked identical to just hovering the row — "which one is
  highlighted?" Changed ghost-hover to shift to the accent tint plus a real
  border, a systemic fix (`components/ui/Button.tsx`), not a per-page patch.
- **Task → inline company preview**: clicking a task's title (when it has a
  linked supplier) expands a compact company card underneath it in place —
  name, ИНН, registry status, contacts, age, response rate — without
  leaving the task list. New shared `TaskSupplierPreview`, used in both the
  Dashboard's `TasksSection` and the Messages right-rail `TasksPanel`.
- **AI "Сравнить с поставщиком" picker reflected in the thread list**: a
  supplier added to the AI's extra context now shows a sparkle icon and a
  tinted left border on its row in the main thread list, so which
  conversations are feeding the AI is visible without opening the picker
  again.
- **`SupplierDetail` (company card)**: the registry-status row was hidden
  behind a `supplier.registry?.status || 'Регион не определён'` fallback —
  there is no region field on this data at all, so that fallback text
  always won even when a real registry status existed. Fixed the label
  (and icon — `MapPin` implied "location", replaced with `ShieldCheck`),
  and added the missing Возраст/Прибыль figures and a Checko link next to
  the ОГРН — the data was already in the API response, just never rendered
  on this page even though the request/supplier list pages already had it.

## 2026-09-08 — thread status/filters, weekly unmatched mail, multi-thread AI context, date picker, richer compose (`839d521`)

- **Messages thread list**: response status is a colored pill ("Ответ"
  green / "Ждём" amber) instead of a bare icon, plus a filter bar
  (Все/Есть ответ/Ждём ответа/Непрочитанные) that filters within each
  request group and auto-expands matching groups.
- **"Новые письма без заявки" → "…за неделю"**: scoped to unread messages
  received in the last 7 days. Reading or ignoring one drops it from the
  list on the next reload — no separate "seen" tracking needed, the
  existing `unread`/`ignored` fields already carry it.
- **AI assistant multi-thread context**: a "Сравнить с поставщиком" picker
  lets the user pull other suppliers' threads on the same request into the
  AI's context, summarized to each one's last message (not a full
  transcript) to keep cost bounded regardless of how many are added.
  Verified live: asking "кто дешевле?" correctly pulled in and cited a
  sibling thread's content by supplier name.
- **Custom `DatePicker`** (popover month grid) replacing the native
  `<input type="date">` everywhere it was used — the browser-chrome picker
  couldn't be styled to match the rest of the UI.
- **BulkComposeModal**: recipients are removable chips instead of a plain
  comma-separated string; attachments are supported end-to-end (client-side
  base64 via `FileReader`, 10 MB/file and 20 MB total caps matching the
  legacy composer's own limits) and wired to the existing
  `preflightBulk`/`sendMailBulk` endpoints, which already accepted an
  `attachments` array — the old frontend just never sent one.

## 2026-09-08 — supplier card open from request rows, Checko URL fix, right-rail tasks, AI chat persistence (`3979396`)

- **Request → supplier card navigation**: the company name in
  `RequestDetail`'s supplier table is now a link to `/suppliers/{id}` when
  `global_supplier_id` is set. Required adding that field to
  `RequestSupplierRow` (it existed in the API response but wasn't typed).
- **Checko links fixed**: Checko splits organisations and sole traders onto
  different paths — `/company/{ОГРН}` (13 digits) vs
  `/entrepreneur/{ОГРНИП}` (15 digits); `/company/{ОГРНИП}` 404s. `checkoUrl()`
  now picks the path from the digit length. Also swapped the generic lucide
  "flame" icon for Checko's real icon (copied from `frontend/src/assets`).
- **Right-rail "Задачи" wired up**: was a permanently-disabled placeholder.
  New `TasksPanel` shows/adds/completes tasks scoped to the open thread.
  This surfaced a real id-space bug: `mail_threads.supplier_id` is the
  request-scoped `suppliers.id`, but `tasks.supplier_id` references
  `global_suppliers` — `list_threads()` never exposed the global id, so a
  naive wire-up 400'd with "Поставщик не найден". Fixed by adding
  `global_supplier_id` to `list_threads()` (backend: `mail/repository.py`,
  joining `global_supplier_links` in both branches of the `UNION ALL`).
  The panel now shows a clear "card not confirmed yet" message instead of a
  broken add form when a thread's supplier isn't linked.
- **AI chat persistence**: conversation history is saved to `localStorage`
  per conversation (`thread-{id}` / `unmatched-{id}`) and survives a page
  reload. Switching threads remounts the panel (`key` tied to the
  conversation id) so one thread's history never bleeds into another's.
- **"Игнорировать" confirm made unmissable**: turned into a full-width
  danger-colored banner. The underlying ignore/reload pipeline was already
  verified correct end-to-end (DB status, API response, list reload); this
  was a precaution against the two-step confirm being misread as one step,
  not evidence of a data bug.

## 2026-09-08 — bulk-compose from the request screen, full-column tables, top search bar (`4020ea1`, `daeb0fe`, `b573e53`)

- **Real "Написать" bulk-compose**: row-select checkboxes in
  `RequestDetail`'s supplier table, wired to the same
  `/api/mail/deliverability/preflight` and `/api/mail/send-bulk` endpoints
  the legacy frontend's `Composer.tsx` already uses — not a new pipeline.
  Live-verified the preflight correctly blocked a test send to two
  already-contacted suppliers (real duplicate-recipient guard, not a stub).
- **Fixed the actual "ШАЛЕ shows Не отправлено" bug**: `RequestSupplierRow`
  read a field named `mail_status_raw`, which the backend never sends (it
  pops that key and sends `mail_status` instead) — the `??` fallback
  silently defaulted every row to "not sent" regardless of real status.
  Root-caused by tracing the field from `mail/repository.py` through to the
  frontend type instead of guessing from the UI.
- **Full-column supplier/request tables**: age (from `registry.registered_at`),
  revenue/profit (`registry`/`finances`, already returned by the backend but
  never rendered), ЕГРЮЛ status, copy-to-clipboard email/ИНН, site links —
  ported from the legacy frontend's table, minus the specialization column
  (explicitly dropped per the approved concept doc).
- **AI assistant grounded in real messages**: context sent to the model was
  only the request/supplier title strings, so it once invented a fake
  requirement from the request's internal test name ("глубокий поиск").
  Now sends the full thread transcript (budgeted to ~3500 chars, newest
  messages kept if truncated).
- **Top search bar**: moved out of the collapsed left sidebar into a bar
  shared by every screen; selecting a message search result deep-links to
  the exact message and highlights the matched text.

## 2026-09-08 — Tasks feature, same-day deadline bug (`147c936`)

- New `tasks` entity (`migrations/037_tasks.sql`, `mail/tasks.py`
  `TasksMixin`): list/create/set-done/delete, scoped to workspace+user,
  optionally linked to a request and/or a global supplier.
- Dashboard "Мои задачи" section (grouped Просрочено/Сегодня/Скоро) and a
  reusable `QuickAddTaskButton` wired into `RequestDetail` and
  `SupplierDetail` page headers.
- **Fixed `daysFromToday()`**: it compared a deadline anchored at midnight
  against the exact current time, so anything due "today" read as overdue
  by one day the moment any time had passed since midnight — caught live
  while testing a same-day task. Now compares calendar days; this also
  fixed the same false-"Просрочено" badge on Requests' deadline tags.

## 2026-09-05 to 2026-09-07 — greenfield foundation (`eeeaf07` … `953100f`)

- App shell, routing (Dashboard/Requests/Suppliers/Messages), connected to
  the real backend (`7216252` dropped the fixture-data prototype).
- Dogfooding pass fixed a batch of real bugs found by using the app as a
  buyer would: dead "New Request" button, CSRF token desync (added a
  one-time self-heal/retry in `lib/api.ts`'s `request()` on the exact 403
  "CSRF-проверка не пройдена" message), Dellin logistics quotes rejecting
  every request (`quote_service.py` hardcoded same-day pickup; Dellin
  requires `today + 1`), message bodies overflowing the layout on long
  unbroken URLs (missing `break-words`), `response_rate` off by a factor of
  100 (backend sends 0–100, `formatPercent()` expects 0–1), Yandex OAuth
  only completing on `127.0.0.1`, never `localhost` (session cookie is
  host-scoped, not a code bug — documented as a dev-environment gotcha).
  (`6a3c6f1`)
- Company names abbreviate their legal form (ООО/ЗАО/…) instead of showing
  the full "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ".
  Message bubbles redesigned from an alternating chat-bubble layout back to
  full-width text after direct negative feedback on readability.
  Unread indicators upsized from a barely-visible 6px dot to numbered
  badges. Real (not stub) thread Notes and AI-assistant panels.
- Suppliers list dropped the category-chip column per the approved concept
  doc's explicit instruction (§5.1). (`d9f6786`)
- Request rows made clickable; new `RequestDetail` page. (`faa1ed3`)
- New `SupplierDetail` (global картотека card) page; fixed the
  `response_rate` scale bug at its second call site. (`953100f`)

## Known gaps, not yet addressed

- Settings screen (concept doc §11 — mail accounts, templates).
- Ассортимент/Документы sections on the supplier card (§9) — the concept
  doc itself marks these as non-priority for now.
- Automatic КП (commercial-proposal) detection (§3) — also explicitly
  deferred by the concept doc.
