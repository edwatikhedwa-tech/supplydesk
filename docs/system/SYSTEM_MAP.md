---
document_id: DOC-SYSTEM-MAP-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# System Map

Full-repository audit produced 2026-09-17 on branch `experiment/frontend-v2-greenfield-20260905`
@ `dc66b0b`. This is the entry point for the new `docs/system|product|frontend|technical|spec|
testing|validation|decisions` documentation tree created by that audit. It **supersedes**
`docs/architecture/COMPONENT_MAP.md` (dated 2026-09-04, predates `frontend-v2` entirely — kept
for history, not for current facts) as the map of what actually runs today.

Older docs are not discarded: where they were verified accurate during this audit they are
cited directly instead of being re-written. See [`KNOWN_GAPS.md`](KNOWN_GAPS.md) for the exact
list of what was confirmed stale.

## What SupplyDesk is

A single-tenant-per-workspace B2B procurement tool: a buyer creates a "заявка" (request) with
one or more line-item positions, the system searches the web for candidate suppliers, enriches
them (company registry + finance data via Checko), emails them, and tracks replies as
correspondence tied back to the request. A per-workspace AI assistant can answer questions using
that request's actual email history. Tasks/reminders and a small logistics-quote calculator
round out the MVP.

## Repository layout (top level)

| Path | Role |
|---|---|
| `supplier_app.py` | Main HTTP handler — all route dispatch (GET/POST/PUT/DELETE), auth/CSRF/rate-limit enforcement, background-thread startup |
| `api/index.py` | Thin Vercel serverless adapter wrapping `supplier_app.py` |
| `mail/` | Persistence + business-logic layer: `MailRepository` (mixin-composed God-object, ~9000+ lines) plus focused modules (`service.py`, `content.py`, `bounce.py`, `pacing.py`, `queue.py`, `runtime.py`, `db_compat.py`, `tasks.py`, `task_reminder_delivery.py`, `contact_intelligence.py`, `canonical_companies.py`, `ai_chat_usage.py`, `ai_conversations.py`, `auth.py`, `auth_accounts.py`, `providers/`) |
| `backend/` | Newer, better-separated domain services: `http_*.py` (route mixins), `domain/{supplier_enrichment,supplier_identity,supplier_import,logistics,ai_agent}/`, `integrations/{llm,logistics,registry,search}/` |
| `migrations/` | 53 versioned `.sql` files, replayed on every process start (`MailRepository.ensure_schema()`) — see [`../technical/DATABASE_MAP.md`](../technical/DATABASE_MAP.md) |
| `frontend-v2/` | **The live, deployed frontend** (React 19 + Vite + Tailwind v4 + react-router-dom v7, hash routing) |
| `frontend/` | **Dead code, not deployed.** Frozen since ~2026-09-04; richer QA tooling (Playwright/Storybook/axe/Applitools) never ported to v2. See [`../frontend/FRONTEND_ARCHITECTURE.md`](../frontend/FRONTEND_ARCHITECTURE.md) |
| `supplier_discovery_v2/` | Query planning / read-only HTTP discovery adapters |
| `scripts/` | PowerShell operator tooling: workspace guard, canonical-runtime launcher, diagnostics |
| `tests/` | ~90 Python `unittest` files (backend regression) + a "source-inspection" pattern (`test_*_ui.py` asserts on `.tsx` source text, does not render anything) |
| `ai/` | Living session/task-state tracker (`CURRENT_STATE.md`, `ACTIVE_TASK.md`, `DEFERRED_FINDINGS.md`, governance rules) — the canonical "what's true right now" source, distinct from this static `docs/` tree |
| `docs/` | Structural/architecture/requirements documentation (this tree) — a pre-existing, disciplined system (status/owner/updated_at/source_commit front-matter) that predates and partially overlaps this audit's new files |

## Which frontend is real (verified, not assumed)

`vercel.json` builds `frontend-v2` only (`buildCommand: cd frontend-v2 && npm run build`,
`outputDirectory: frontend-v2/dist`, and explicitly excludes `frontend/**` from the serverless
bundle). `frontend/` has had zero commits in ~2 weeks while `frontend-v2/` has near-daily
activity. Full detail: [`../frontend/FRONTEND_ARCHITECTURE.md`](../frontend/FRONTEND_ARCHITECTURE.md).

## Production vs local runtime

- **Production (Vercel):** Postgres via `DATABASE_URL` (`mail/repository.py` branches on this;
  `mail/db_compat.py` translates the SQLite-dialect SQL the repository is written in).
- **Local dev:** SQLite only, file at `mail-data/supplier.sqlite3`, no `DATABASE_URL` set.
- Both run the *same* migrations and the *same* `MailRepository` code — the compat layer is the
  only place dialect differences are handled, and it has already had two real production
  incidents (SQLite-only migration guard, `COLLATE NOCASE`) fixed this session precisely because
  Postgres had never been exercised with real data before `CHECKO_KEY` was configured there.

## Background execution model

No cron. Two durable, lease-based job queues (`request_search_jobs`, `supplier_enrichment_jobs`)
designed to survive a serverless function freezing mid-request:
- Locally: a background daemon thread polls due jobs every 15s (`orchestrator.py`).
- On Vercel (`VERCEL` env var set): the daemon is disabled; the frontend instead calls
  `POST /api/enrichment/step` as a heartbeat, advancing exactly one step per invocation.

A separate mail-sync thread pulls IMAP every 300s locally, plus a per-view-throttled sync
(`maybe_sync_incoming`, 45s) triggered by opening Messages.

## Three-tier supplier identity model (verified against `docs/domain/SUPPLIER_MODEL.md`)

1. `suppliers` — per-workspace, keyed by `(workspace_id, external_key=host)`. Holds the
   crawl/mail identity.
2. `global_suppliers` — per-workspace, ИНН-deduped "company card."
3. `canonical_companies` — cross-tenant (no `workspace_id`), ИНН-keyed, public facts only.

This model is real and mostly enforced — but has one confirmed, live gap (not historical): see
[`INV-SUP-002` in `../spec/PRODUCT_INVARIANTS.md`](../spec/PRODUCT_INVARIANTS.md) and
[`GAP-003` in `KNOWN_GAPS.md`](KNOWN_GAPS.md).

## AI assistant (verified real, not mock)

Calls a live LLM via RouterAI (`ROUTERAI_CHAT_KEY` env var, default model
`meta-llama/llama-3.3-70b-instruct`). Context assembly is server-validated (`get_thread_owned`
re-checks every client-supplied thread id against workspace+request) and explicitly limited to
suppliers with real communication — the historical "all suppliers of a request leak into AI
context" bug was found and fixed 2026-09-10 (commit `0d16945`) and is confirmed still fixed. Full
detail: [`../product/AI_ASSISTANT.md`](../product/AI_ASSISTANT.md).

## Tasks/Calendar (verified: CRUD real, delivery mostly not)

Task CRUD and completion are real, DB-backed, wired to routes. The `/calendar` full-page route
was deleted 2026-09-17 as dead code (its nav entry was already removed) — the Dashboard's
`DashboardCalendar` widget is the only calendar UI now, and it renders real task data. Reminder
*delivery* is honest about its limits: in-app (foreground toast + Notification API while a tab is
open, 45s poll) is the only channel that actually fires anything; email reminders are recorded
but never sent (no send path exists); phone reminders are explicitly labeled a local mock in the
UI copy itself. Full detail: [`../product/PRODUCT_MODEL.md`](../product/PRODUCT_MODEL.md).

## Auth

Two login methods: email+password (single seeded app user via `APP_USER_EMAIL`/
`APP_USER_PASSWORD` — not general signup) and Yandex OAuth (PKCE). Sessions are opaque
server-side tokens in an `HttpOnly`/`SameSite=Lax` cookie. CSRF is a derived
(`sha256(session+":csrf")`) double-submit token, not a stored random value. Authorization is
workspace-implicit (trusts `session["workspace_id"]`) plus a single owner-only role gate for
maintenance routes. Full detail: [`../technical/API_MAP.md`](../technical/API_MAP.md).

## Cross-reference index

| Topic | Document |
|---|---|
| Feature-by-feature status (IMPLEMENTED/PARTIAL/BROKEN/MOCK/NOT_IMPLEMENTED) | [`CURRENT_STATE.md`](CURRENT_STATE.md) |
| Everything found wrong, not fixed | [`KNOWN_GAPS.md`](KNOWN_GAPS.md) |
| Product invariants (durable rules, each with an ID) | [`../spec/PRODUCT_INVARIANTS.md`](../spec/PRODUCT_INVARIANTS.md) |
| Full API route inventory | [`../technical/API_MAP.md`](../technical/API_MAP.md) |
| Full database schema | [`../technical/DATABASE_MAP.md`](../technical/DATABASE_MAP.md) |
| Frontend v1 vs v2, UI component inventory | [`../frontend/`](../frontend/FRONTEND_ARCHITECTURE.md) |
| Messages/mail business rules | [`../product/MESSAGES.md`](../product/MESSAGES.md) |
| Supplier identity model + the duplicate-identity gap | [`../product/SUPPLIERS.md`](../product/SUPPLIERS.md) |
| AI assistant context rules | [`../product/AI_ASSISTANT.md`](../product/AI_ASSISTANT.md) |
| requirements.yaml, test cases, traceability | [`../spec/`](../spec/requirements.yaml), [`../testing/`](../testing/TEST_CASES.md), [`../validation/TRACEABILITY_MATRIX.md`](../validation/TRACEABILITY_MATRIX.md) |
