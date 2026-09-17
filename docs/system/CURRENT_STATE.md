---
document_id: DOC-SYSTEM-CURRENT-STATE-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Current State — Feature Status Matrix

Statuses: `IMPLEMENTED` (works, has been exercised/tested) · `IMPLEMENTED / NOT VERIFIED` (code
exists, no test or live evidence) · `PARTIAL` · `BROKEN` · `MOCK` · `NOT_IMPLEMENTED` ·
`UNKNOWN`. `IMPLEMENTED` never means "bug-free" — it means the described behavior exists and has
evidence.

This is a **new, audit-produced** document, distinct from `ai/CURRENT_STATE.md` (living
session-state tracker, updated continuously) and `docs/CURRENT_STATE.md` (root-level, marked
`HISTORICAL`, frozen 2026-08-30). Where they conflict, trust this file for 2026-09-17 and `ai/`
for anything after.

## Auth

| Feature | Status | Evidence |
|---|---|---|
| Email+password login | IMPLEMENTED | Single seeded app user (`APP_USER_EMAIL`/`APP_USER_PASSWORD`), PBKDF2-SHA256 240k iterations — `mail/auth.py`, `backend/http_auth.py:32` |
| Yandex OAuth login | IMPLEMENTED | PKCE flow, `backend/http_auth.py:142` |
| Google / Mail.ru OAuth login | NOT_IMPLEMENTED | `frontend-v2/src/pages/Login.tsx:49-53` — buttons explicitly `enabled: false`, labeled "Скоро" in the UI itself, not a hidden stub |
| Session management | IMPLEMENTED | Sliding-expiration server-side token, `HttpOnly`/`SameSite=Lax` cookie |
| CSRF protection | IMPLEMENTED | Derived double-submit token, checked on every mutating route |
| Workspace isolation | IMPLEMENTED | `tests/test_supplier_workspace_isolation.py`; `global_supplier_detail` scoped by `(workspace_id, id)` |
| Multi-tenant signup | NOT_IMPLEMENTED | Single-seeded-user model, not general registration |

## Requests

| Feature | Status | Evidence |
|---|---|---|
| Request/position CRUD | IMPLEMENTED | `backend/http_requests.py`, `tests/test_dashboard.py` |
| Durable, resumable search (SERP → enrich) | IMPLEMENTED | `request_search_jobs` lease/claim queue, `tests/test_request_search_cursor_survives_step_release` |
| Deadline / followup SLA per request | IMPLEMENTED | `request_followup_settings`, `docs/domain/SUPPLIER_MODEL.md` §7.1 (verified accurate this audit) |
| CSV supplier import (preview/apply) | IMPLEMENTED | `backend/domain/supplier_import/`, `/api/supplier-import/{preview,apply}` |
| Logistics quote (Dellin, one request/one supplier) | IMPLEMENTED | `docs/product/CAPABILITY_CATALOG.md` CAP-LOGISTICS-001, live-verified 2026-09-04 against real Dellin API |
| Campaign monitor/control UI (pause/resume/stop, continuation dry-run) | **NOT_IMPLEMENTED in frontend-v2** | Full page exists in `frontend/src/pages/CampaignPage.tsx` (v1) with no v2 route or equivalent — real regression, see `GAP-001` |

## Suppliers

| Feature | Status | Evidence |
|---|---|---|
| Three-tier identity (suppliers/global_suppliers/canonical_companies) | IMPLEMENTED | `docs/domain/SUPPLIER_MODEL.md` (verified current) |
| ИНН-based dedup within workspace | IMPLEMENTED | `global_suppliers UNIQUE(workspace_id, inn)` |
| Cross-tenant company cache | IMPLEMENTED | `canonical_companies`, `tests/test_canonical_companies_cache_reuse.py` |
| Host-based supplier identity, one row per domain | **PARTIAL — confirmed live gap** | Silently degrades to the raw email address as key when no host is known at write time (`resolve_supplier_for_send` fallback, `mail/repository.py:3551`) — 28/243 supplier rows in the local DB currently carry this exact signature (11.5%). See `GAP-003`, `INV-SUP-002` |
| Checko enrichment (registry + finance) | IMPLEMENTED | `backend/integrations/registry/checko_client.py`; requires `CHECKO_KEY` (not set in production as of this audit) |
| `force_enrich_all_suppliers` maintenance route | **NOT ON THIS BRANCH** | Exists only on `state/current-20260917-2119` (this session's git snapshot), not merged into `experiment/frontend-v2-greenfield-20260905`. See `GAP-002` |
| Manual ИНН entry + protection from auto-overwrite | IMPLEMENTED | `tests/test_manual_inn_is_visible_and_wins_over_later_auto_candidate` |

## Messages / Mail

| Feature | Status | Evidence |
|---|---|---|
| Inbound thread matching (headers, then subject+email) | IMPLEMENTED | `mail/repository.py:2638-2660` |
| Unmatched-mail inbox (never silently dropped) | IMPLEMENTED | `mail_inbox_messages`, verified: no user-facing DELETE exists anywhere for messages/threads |
| Attachments — outbound (compose) | IMPLEMENTED | Size limits enforced, stored as BLOB |
| Attachments — inbound, rendered in thread view | **PARTIAL** | Parsed and stored (`mail_attachments`), but `frontend-v2/src/pages/Messages.tsx` never renders/downloads them for already-sent or received messages — real unrendered capability, not documented as a limitation anywhere before this audit. `GAP-004` |
| HTML sanitization (nh3/Ammonia allowlist) | IMPLEMENTED | `mail/content.py::sanitize_email_html`, matches `docs/ui/MESSAGES_SCREEN_SPEC.md` §9 |
| Links clickable in rendered email | **IMPLEMENTED / NOT VERIFIED** | Sanitizer forces `target="_blank"` + safe `rel`, but no Playwright/browser test asserts the rendered result is actually clickable — assumption, not proof |
| CID inline images | IMPLEMENTED | Resolved to `data:` URLs at parse time; any residual `cid:` src stripped at render time as defense in depth |
| Unread/read tracking | IMPLEMENTED | Read is a side effect of opening a thread (`mail_message_reads` row insert); no "mark unread" path exists |
| `needs_followup` derived flag | IMPLEMENTED | Confirmed matches `docs/domain/SUPPLIER_MODEL.md` §7.1 exactly |
| Physical message/thread deletion | NOT_IMPLEMENTED (by design) | Only one DELETE statement exists in the whole repo (`scripts/supplier_identity_audit.py`, an offline script, no HTTP route) — matches the stated invariant that status changes, not deletion, represent user actions |
| Contact-priority resolution (workspace override → cross-tenant consensus → fallback) | IMPLEMENTED | `mail/contact_intelligence.py::resolve_contact_priority`, 14 tests in `tests/test_contact_resolution_send_path.py` |

## AI Assistant

| Feature | Status | Evidence |
|---|---|---|
| Real LLM call (not mock) | IMPLEMENTED | RouterAI, `backend/integrations/llm/routerai_client.py` |
| Context scoped to suppliers with real communication only | IMPLEMENTED | Fixed 2026-09-10 (`0d16945`), server-re-validated (`get_thread_owned`), confirmed still correct this audit |
| Daily spend cap | IMPLEMENTED | `ai_chat_usage` table, default 10₽/day, checked before calling the model |
| Per-minute/burst rate limiting | NOT_IMPLEMENTED | Only the daily cumulative cap exists |
| Context size/token accounting | **PARTIAL** | Character-based truncation only (40,000-char budget, blunt suffix cut); no real token counting |

## Tasks / Calendar

| Feature | Status | Evidence |
|---|---|---|
| Task CRUD + completion | IMPLEMENTED | Full route set, real tables |
| Task reminders — in-app (toast, tab open) | IMPLEMENTED | 45s poll, `RemindersContext.tsx` |
| Task reminders — browser push (tab closed) | NOT_IMPLEMENTED | No Service Worker/Push API/server scheduler |
| Task reminders — email | **MOCK** (recorded, never sent) | No send path exists anywhere for `channel='email'` reminders despite the form accepting/validating it |
| Task reminders — phone | MOCK (explicitly labeled in UI) | "Телефонный канал работает только как local mock: звонка не будет." |
| Calendar display | IMPLEMENTED | `DashboardCalendar.tsx`, real task data, not fixture |
| Full-page `/calendar` | REMOVED 2026-09-17 | Was dead/unreachable code after nav entry removal; deleted this session |

## Frontend

| Feature | Status | Evidence |
|---|---|---|
| frontend-v2 is the deployed UI | IMPLEMENTED (confirmed) | `vercel.json` builds only `frontend-v2` |
| frontend (v1) still deployed anywhere | NOT_IMPLEMENTED | Zero commits in ~2 weeks, explicitly excluded from the Vercel bundle |
| Shared UI primitives: Button, Modal, Toast, Loading/Empty/Error states | IMPLEMENTED, consistently reused | See `../frontend/UI_INVENTORY.md` |
| Shared UI primitives: Input, Checkbox, Card, Table, Tabs | **NOT_IMPLEMENTED as shared components** — each page reinvents its own | Root cause of the "Frankenstein" visual effect, see `../frontend/UI_INVENTORY.md` |
| Frontend-v2 browser/e2e/visual test coverage | NOT_IMPLEMENTED | v1 has Playwright+axe+Storybook+Applitools; none of it ported to v2. CI's `frontend_v2` job only runs lint+build, no runtime checks |

## QA infrastructure

| Tool | frontend-v2 | frontend (v1) |
|---|---|---|
| TypeScript | ✅ | ✅ |
| Linter | oxlint (not ESLint) | ESLint |
| Unit tests | Vitest + Testing Library (4 files only) | — |
| E2E/browser | ❌ none | ✅ Playwright |
| Accessibility | ❌ none | ✅ axe-core |
| Visual regression | ❌ none | ✅ Applitools Eyes |
| Component catalog | ❌ none | ✅ Storybook |
| Backend tests | unittest, ~90 files, `tests/run-tests.ps1` | (shared) |
| CI | `.github/workflows/ci.yml` — `frontend_v2` job is lint+build only | `frontend`/`browser_smoke`/`browser_full` jobs run real Playwright |
