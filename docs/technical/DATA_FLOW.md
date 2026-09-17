---
document_id: DOC-TECH-DATA-FLOW-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Data Flow

Technical (function/route-level) trace of the flows described narratively in
[`../product/USER_FLOWS.md`](../product/USER_FLOWS.md). This file is the "how", that one is the
"what a user experiences."

## Auth → session → API

`Login.tsx` → `POST /api/auth/login` (or Yandex OAuth round-trip) → `backend/http_auth.py` →
`repository.authenticate()`/`_finish_login_callback` → session row created, cookie set → every
subsequent request carries the cookie + `X-CSRF-Token` header (derived, not stored) →
`_require_session()`/`_require_csrf()` gate every route.

## Request → positions → suppliers → communication

`POST /api/requests` (create) → `POST /api/requests/<id>` search-start action → enqueues
`request_search_jobs` row → client polls a search-step action → `process_search_step`
(`orchestrator.py`) does one SERP position or one enrichment batch per call, persisting a cursor
→ on completion, `request.status = 'completed'`, suppliers now exist in `suppliers`/
`request_suppliers` → composing/sending mail resolves the actual recipient via
`resolve_supplier_for_send` (host match → email match → **create-new-row fallback**, see
`GAP-003`) → `mail_threads`/`mail_messages` created → `request_supplier_states` updated on
reply/bounce.

## Suppliers: discovery → enrichment → contacts → request association

SERP hit → `upsert_search_result` (name defaults to host, never raw SERP title) →
`supplier_enrichment_jobs` enqueued (crawl → registry ИНН guess → web fallback → finance) →
`apply_supplier_enrichment` is the single write-through point: updates `suppliers`,
`global_suppliers` (via `_get_or_create_global_supplier`), `global_supplier_registry`/
`_finances`, and `canonical_companies` (cross-tenant cache) in one call → `_resolve_missing_inn`
checks `canonical_companies` by ИНН **before** a live Checko call, so a second workspace resolving
the same company makes zero Checko calls.

## Messages: mail account → sync → message → correspondence → request/supplier

Background/on-view sync (`maybe_sync_incoming`, throttled) or manual `POST /api/mail/sync` →
IMAP pull (`mail/providers/*.py`) → `import_incoming_messages` → `_find_incoming_thread` (header
match → subject+email match) → matched: appended to `mail_messages`, thread's
`last_message_at` bumped; unmatched: parked in `mail_inbox_messages` (`status='unmatched'`,
never deleted) → human resolves via `attach_inbox_message`/`manually_link_inbox_message` →
`GET /api/correspondence` renders threads, `thread_messages()` marks read as a side effect of
opening.

## AI Assistant: selection → context building → LLM call

User opens "ИИ-помощник" on a thread → frontend offers only sibling threads with
`threadResponseStatus === 'answered'` as extra context (UX filter) → `POST /api/ai/chat` with
`thread_ids` → `chat_service._build_context` **re-validates every id server-side**
(`get_thread_owned`, silently drops anything not belonging to this workspace+request — this is
the real security boundary, not the frontend filter) → per surviving thread, up to 10 most-recent
communication messages, each trimmed to 4500 chars → whole context capped at 40,000 chars → daily
spend check (`ai_chat_usage`) → RouterAI call → response + spend recorded.

## Tasks / reminders

`POST /api/tasks` → `task_reminders` row (channel `in_app`/`email`/`phone`) → **only `in_app`
actually delivers**: `RemindersContext.tsx` polls `GET /api/tasks/reminders/due` every 45s while
a tab is open, renders a toast + calls the browser `Notification` API. `email`/`phone` reminders
are recorded and validated but never dispatched — see `docs/system/CURRENT_STATE.md`.
