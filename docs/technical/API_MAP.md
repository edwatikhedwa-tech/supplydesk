---
document_id: DOC-TECH-API-MAP-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# API Map

Complete route inventory for `supplier_app.py` @ `dc66b0b` (branch
`experiment/frontend-v2-greenfield-20260905`). Supersedes `docs/api/README.md`/
`docs/api/messages.md` for route completeness (those remain accurate for the narrower scope they
cover — correspondence/messages metadata — but were never exhaustive).

## Cross-cutting auth/safety rules

Every route requires a valid session (`_require_session()`, 401 otherwise) **except**:
`/api/auth/login`, `/api/auth/me`, `/api/auth/yandex/start`, `/oauth/yandex/callback`,
static assets, and the SPA shell fallback.

Every mutating route (POST/PUT/DELETE) additionally requires:
- `_require_csrf()` — 403 on missing/wrong `X-CSRF-Token` header (derived
  `sha256(session_cookie + ":csrf")`, not a stored random value)
- `allow_api_request()` — 429 after 30 requests/60s per session token

Owner-only routes (`is_workspace_owner` check, all under `/maintenance/*`): 403 with a Russian
error message if the caller isn't the workspace owner.

## GET routes

| Path | Auth | Purpose |
|---|---|---|
| `/maintenance/test-data-cleanup-20260909` | session + owner | HTML confirmation page for test-data cleanup |
| `/assets/*`, `/fonts/*` | none | Static frontend bundle / fonts |
| `/api/auth/me` | none | Current session/user info |
| `/api/auth/yandex/start` | none | Begin Yandex OAuth login |
| `/api/support/*` | session | Support-chat sub-router |
| `/api/dashboard/summary` | session | Dashboard KPIs |
| `/api/tasks` | session | List tasks |
| `/api/tasks/reminders/due` | session | Due reminders (polled) |
| `/api/tasks/reminders/feed` | session | Notification feed |
| `/api/notification-settings` | session | Notification prefs |
| `/api/workspace/members` | session | List workspace members |
| `/api/requests`, `/api/requests/*` | session | Request list + sub-router (positions, search, followup, thread notes, ratings) |
| `/api/suppliers` | session | List suppliers, filterable |
| `/api/blacklist` | session | List blacklist |
| `/api/global-suppliers`, `/api/global-suppliers/*` | session | Global-supplier directory + detail sub-router |
| `/api/supplier-directory` | session | Supplier directory |
| `/api/correspondence` | session | List mail threads (triggers throttled incoming sync) |
| `/api/logistics/freight-types`, `/api/logistics/terminals` | session | Logistics lookup |
| `/api/mail/template` | session | Get saved mail template |
| `/api/mail/status` | session | Mail service status |
| `/api/mail/runtime/outgoing` | session | Outgoing-mail feature-flag state |
| `/api/mail/accounts` | session | List connected mail accounts |
| `/api/mail/inbox`, `/inbox/requests`, `/inbox/preview`, `/inbox/unmatched` | session | Unmatched incoming mail (full / preview / manual-link candidates) |
| `/api/mail/request-status` | session | Per-request supplier mail statuses |
| `/api/mail/queue`, `/queue/messages` | session | Queue stats / outbox |
| `/api/mail/campaigns/<id>` | session | Campaign summary (**no v2 UI consumes this today**, see GAP-001) |
| `/api/mail/threads` | session | Thread messages |
| `/api/mail/search` | session | Full-text mail search |
| `/api/ai/chat/usage` | session | AI daily spend/limit |
| `/api/ai/conversations`, `/api/ai/conversations/<id>` | session | AI conversation list/detail |
| `/api/mail/inbox/<id>/suggestions` | session | Suggested request matches for an unmatched message |
| `/api/mail/inbox/conversation` | session | Full inbox conversation thread |
| `/api/mail/yandex/start` | session | Begin OAuth to connect a mailbox |
| `/oauth/yandex/callback` | none (state-token validated) | OAuth callback — both login and mail-connect |
| anything else under `/api/*`, `/oauth/*` | — | 404 |
| source-looking paths (`.py`, `.env`, ...) | — | 404 (explicit anti-scanner guard) |
| any other path | none | SPA shell |

## POST routes

Owner-only maintenance routes (all POST, all CSRF+rate-limited): `/maintenance/
restore-global-suppliers-20260909`, `/restore-deleted-suppliers-20260910`, `/
backfill-placeholder-supplier-names-20260911`, `/refresh-bad-global-supplier-names-20260911`.
**`/maintenance/force-enrich-all-suppliers` is not present on this branch** — see `GAP-002` in
[`../system/KNOWN_GAPS.md`](../system/KNOWN_GAPS.md).

`/api/auth/login` (pre-auth, no CSRF by definition) and `/api/auth/logout` (session+CSRF, no
rate limit) are the two auth exceptions. Everything else below is session+CSRF+rate-limited:

`/api/enrichment/step` (Vercel heartbeat for the enrichment job queue), `/api/mail/runtime/
outgoing`, `/api/mail/test`, `/api/mail/accounts/mailru/connect`, `/api/mail/accounts/<id>/
{sent-sync,test}`, `/api/mail/sync`, `/api/mail/sent/{preview,sync}`, `/api/mail/topic/
{preview,import}`, `/api/mail/diagnose*` (5 diagnostic variants), `/api/mail/resync`, `/api/mail/
disconnect`, `/api/mail/template`, `/api/mail/deliverability/{preflight,preview}`, `/api/mail/
send`, `/api/mail/send-bulk`, `/api/mail/cross-provider-retry/{preview,apply}`, `/api/mail/
campaigns/<id>/{continuation-dry-run,continuation-apply,pause,resume,stop}`, `/api/mail/
messages/<id>/{verify,resend,resolve}`, `/api/mail/inbox/{manual-link,manual-unlink,ignore,
attach,reply}`, `/api/correspondence/metadata`, `/api/ai/chat`, `/api/support/*` (POST),
`/api/tasks` (create), `/api/supplier-import/{preview,apply}`, `/api/tasks/<id>/done`, `/api/
tasks/reminders/{read-all,<id>/dismiss,<id>/snooze,<id>/read}`, `/api/notification-settings`
(save), `/api/requests` (create), `/api/blacklist` (add), `/api/mail/suppression`, `/api/
irrelevant`, `/api/blacklist/<id>/restore`, `/api/global-suppliers/*` (action sub-router),
`/api/requests/*` (action sub-router — search start/step, ИНН update, ratings, followup
settings, thread notes, contact-result).

## PUT / DELETE

| Path | Method | Purpose |
|---|---|---|
| `/api/tasks/<id>` | PUT | Update a task |
| `/api/mail/accounts/<id>` | DELETE | Disconnect a mail account |
| `/api/tasks/<id>` | DELETE | Delete a task |
| `/api/requests/<id>` | DELETE | Delete a request (409 if delivery resolution required — `BR-DATA-001`) |

## Error handling pattern

`do_POST` wraps its whole dispatch cascade in one `try/except`, typed in this precedence:
`DeliverabilityPreflightError`→409 (carries `preflight` detail) · `PermissionError`→403 ·
`(ValueError, TypeError, ProviderError, EncryptionConfigError)`→400, or 503 specifically for a
`ProviderError` marked transient · bare `Exception`→`log.exception(...)` then 500 with a generic
Russian message (this catch-all was added after a real debugging incident where `/api/ai/chat`
failed silently and untraced). `do_PUT`/`do_DELETE` use the same status-code conventions with
per-route `try/except` instead of one wrapping cascade. All JSON error bodies are
`{"error": "<Russian message>"}`.

## Background jobs (not routes, but part of the API surface's runtime behavior)

| Job | Trigger | Purpose |
|---|---|---|
| `request_search_jobs` | On-demand (`POST /api/requests/<id>` search-step action), polled while the request card is open | SERP search → per-position host enrichment, one step per call |
| `supplier_enrichment_jobs` | Local: background thread every 15s. Vercel: `POST /api/enrichment/step` heartbeat (thread disabled when `VERCEL` env var is set) | Retry queue for crawl/registry/web/finance enrichment stages, per-stage backoff up to 6h |
| Mail sync | Background thread every 300s (local) + per-view throttle 45s (`maybe_sync_incoming`, triggered by opening Messages/Inbox) | IMAP pull for all active accounts |

## Domain services (`backend/`)

| Module | Responsibility |
|---|---|
| `http_auth.py` | Login, OAuth start/callback, session/CSRF helpers |
| `http_global_suppliers.py` | Global supplier card detail, notes, contacts, classifications |
| `http_requests.py` | Request/position/search lifecycle, logistics quotes, followup, thread notes |
| `http_static.py` | Static asset serving, fixture loading |
| `http_support.py` | In-app support chat |
| `domain/ai_agent/chat_service.py` | AI chat orchestration + daily spend budget |
| `domain/logistics/quote_service.py` | Freight/terminal search + quote calc (Dellin) |
| `domain/supplier_enrichment/` | Full SERP→crawl→registry→web→finance pipeline, both job-queue drivers |
| `domain/supplier_identity/` | Email/ИНН extraction, ИНН checksum + registry resolution, domain-ownership verification |
| `domain/supplier_import/` | Bulk CSV import preview/apply |
| `integrations/llm/` | Budget-capped LLM extraction fallback + RouterAI client |
| `integrations/logistics/` | Dellin freight API client |
| `integrations/registry/` | Checko + DaData clients |
| `integrations/search/` | XMLRiver SERP client, fallback web lookup |
| `integrations/secret_redaction.py` | Log/error secret redaction |
