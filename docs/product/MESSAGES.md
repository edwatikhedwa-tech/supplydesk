---
document_id: DOC-PRODUCT-MESSAGES-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Messages / Mail — Business Rules

Verified 2026-09-17 against `docs/ui/MESSAGES_SCREEN_SPEC.md` (updated 2026-09-11, confirmed
still accurate for everything it covers), `docs/api/messages.md` (accurate but narrow — metadata
routes only), and `docs/domain/SUPPLIER_MODEL.md` §7 (confirmed accurate). This file covers what
those three don't, and states clearly which parts are newly confirmed vs newly found wrong.

## Thread matching (inbound → request/supplier)

`_find_incoming_thread` (`mail/repository.py:2638`): first tries RFC `In-Reply-To`/`References`
header-token overlap against the account's own prior `mail_messages`; falls back to
normalized-subject + exact supplier-email match on `mail_threads`. Bounces are matched
separately (`_find_thread_for_bounce`) by extracting the failed recipient from the bounce body —
never by the bounce's own `From` (mailer-daemon), since that would never match a supplier.

**If neither matches:** the message is inserted into `mail_inbox_messages` with
`status='unmatched'` and stays there — visible in "Письма без заявки" — until a human resolves it
via `attach_inbox_message` (link to an existing supplier) or `manually_link_inbox_message`
(link with no supplier). **Nothing here creates a new `suppliers` row** — that only happens on
the *send* path (see [`SUPPLIERS.md`](SUPPLIERS.md) / `GAP-003`).

## Statuses (all of them)

| Layer | Table/field | Values |
|---|---|---|
| Transport (UI-facing) | `request_supplier_states.status`, mapped | `not_sent`, `sent`, `waiting`, `answered`, `error`, `delivery_unknown` |
| Per-message pipeline | `mail_messages.status` | `queued`, `sending`, `sent`, `failed`, `delivery_unknown`, `received`, `cancelled` |
| Conversation label (per-user) | `mail_thread_status` | `in_progress`, `deferred`, `rejected`, or none |
| Derived, never stored | `needs_followup` | boolean — SLA-elapsed with no reply |
| Unmatched inbox | `mail_inbox_messages.status` | `unmatched`, `matched`, `ignored` |

`conversation_status` never touches sending or blacklist status — confirmed, matches spec.

## Attachments

Outbound: enforced 10 MB/attachment, 20 MB total, stored as BLOB, returned inline in
message-detail API responses. Inbound: parsed the same way (`mail/providers/yandex.py`), stored
in `mail_attachments`. **Gap:** the frontend never reads `message.attachments` for an
already-sent or received message — `MailAttachment[]` is wired only to the composer's own draft.
Real backend capability with no UI surface (`GAP-004`).

## HTML / links / CID

Confirmed matches spec §9: `nh3` (Rust Ammonia) allowlist, `data:` scheme allowed for `<img>`
but stripped from `<a href>`, forced `target="_blank"` + safe `rel` on every link, CSS
property-allowlisted with a regex block on `url()`/`expression()`/`javascript:`/`@import`.
CID inline images are resolved to `data:` URLs at parse time; any residual `cid:` src is stripped
at sanitize time as defense in depth (there is no trusted mailbox base URL to resolve it against
otherwise).

**Not verified:** "links are actually clickable in the rendered UI" is asserted by the sanitizer's
own design but has no Playwright/browser test proving the rendered result — unlike the AI-context
scoping invariant, which does have a dedicated backend test. Flagged as
`IMPLEMENTED / NOT VERIFIED`.

## Unread

No explicit "mark read" endpoint — reading is a side effect of `thread_messages()`/
`inbox_conversation()`, which insert a `mail_message_reads`/`mail_inbox_message_reads` row for
every inbound message the moment the thread is opened. No "mark unread" path exists.

## Physical deletion

**Confirmed: none exists.** The only `DELETE FROM mail_messages`/`mail_threads` statement in the
entire repository is in `scripts/supplier_identity_audit.py` — an offline maintenance script with
no HTTP route. Every user-visible "removal" action (ignore, reject, clear status) is a status or
visibility change, never a row deletion. This matches `INV-MSG-001` below.

## needs_followup and contact resolution

Confirmed exactly matches `docs/domain/SUPPLIER_MODEL.md` §7 — not re-explained here to avoid
duplication. Key facts worth surfacing in this index: default SLA 2 business days (Mon–Fri, no
holiday calendar), per-request override available; contact-priority resolution
(workspace-preferred → cross-tenant preferred → stored fallback) runs through one single
side-effect-free resolver used identically by preview and real send, so what a buyer sees in
preview is guaranteed to be what actually gets used.
