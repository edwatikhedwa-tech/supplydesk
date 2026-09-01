---
document_id: COMPONENT-MAP-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Component Map

| ID | Component | Responsibility | Boundary/evidence |
|---|---|---|---|
| COMP-APP | `supplier_app.py` | Application route dispatch, auth and product HTTP surface | GET routes begin near line 239; POST routes near line 470 |
| COMP-AUTH | `supplier_app.py` + `mail/auth.py` | Authentication, sessions, CSRF and ownership gates | Auth routes and integrity tests |
| COMP-REQUEST | `supplier_app.py` + `mail/repository.py` | Request, position and search lifecycle | Request routes and dashboard tests |
| COMP-SUPPLIER | `supplier_app.py` + `mail/repository.py` | Supplier identity, grouping, filters and enrichment | Supplier routes and identity tests |
| COMP-ADAPTER | `api/index.py` | Serverless adapter and environment loading | Imports `supplier_app`; DB fallback is a known runtime limitation |
| COMP-DATABASE | `mail/repository.py` | SQLite persistence and schema initialization | Repository initialization can write/migrate; diagnostics must not instantiate it for canonical DB |
| COMP-SERVICE | `mail/service.py` | Incoming/outgoing orchestration, queue and provider gates | `sync_incoming`, `preflight_bulk`, `queue_*`, `send_claimed_job` |
| COMP-INCOMING | `mail/service.py` + `mail/content.py` | Incoming sync, parsing and unmatched preservation | Mail integration tests |
| COMP-MESSAGE | `mail/repository.py` + `supplier_app.py` | Message visibility and correspondence/outbox views | Messages visibility tests |
| COMP-QUEUE | `mail/queue.py` + `mail/service.py` | Claims, idempotency and recipient guards | Integrity and identity tests |
| COMP-PACING | `mail/pacing.py` | Pacing, reservations, cooldown and budgets | Mail pacing tests |
| COMP-CAMPAIGN | `mail/service.py` + `supplier_app.py` | Campaign stage, pause/stop and safe retry preview | Deliverability tests and campaign routes |
| COMP-RUNTIME | `mail/runtime.py` | Runtime lock, session manifest and provenance | `LiveMailLock`, `RuntimeSession`, path and process checks |
| COMP-PROVIDER | `mail/providers/` | Yandex/Mail.ru provider adapters and base contract | Provider transport boundary; not contacted by diagnostics |
| COMP-DELIVERY | `mail/deliverability.py` | Email validation, suppression, quality, pacing and error classification | Read-only preflight helpers and safety semantics |
| COMP-CONTENT | `mail/content.py` | HTML/plain/CID sanitation and text extraction | Rendering boundary; remote images are not fetched by diagnostics |
| COMP-BOUNCE | `mail/bounce.py` | Bounce classification and suppression | Delivery-history boundary |
| COMP-DISCOVERY | `supplier_discovery_v2/` | Query planning, read-only HTTP, adapters, evidence and qualification | Discovery boundary; no live lookup in diagnostics |
| COMP-MIGRATION | `migrations/` | Versioned schema DDL | Read-only schema inspection only in diagnostics |
| COMP-FRONTEND | `frontend/` | Product client and browser tests | `package.json`, `frontend/src/`, `frontend/tests/` |
| COMP-DOCTOR | `scripts/doctor.ps1` | Windows operator entrypoint | Plan/DryRun/Apply all invoke read-only V1 checks |
| COMP-DIAGNOSTICS | `scripts/diagnostics/` | Standard-library diagnostic contract and runner | No application writes, provider calls or canonical DB writes |
| COMP-REPAIR | `ai/repair-agent/` | Future repair contract only | No implementation or autonomy in V1 |

## Data flow boundary

Browser → `supplier_app.py`/`api/index.py` → `mail/service.py` → repository and
provider adapters. Diagnostic flow stops before provider adapters and uses a
read-only SQLite URI for database inspection.
