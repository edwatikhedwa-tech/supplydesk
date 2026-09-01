---
document_id: CAPABILITY-CATALOG-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Product Capability Catalog

This is an evidence map, not a product wish list. `CONFIRMED` means the
repository contains an implementation and a named test or route. `PARTIAL`
means code exists but runtime or end-to-end evidence is incomplete. `NOT
VERIFIED` is deliberately not counted as a delivered capability.

| ID | Capability | Status | Evidence | Diagnostic evidence |
|---|---|---|---|---|
| CAP-AUTH-001 | Session, login/logout and workspace-scoped access | CONFIRMED | `supplier_app.py` auth routes; `mail/auth.py`; `tests/test_mail_integrity.py` | DOC-004, DOC-005 |
| CAP-REQUEST-001 | Request and position lifecycle | CONFIRMED | `supplier_app.py` request routes; `mail/repository.py`; `tests/test_dashboard.py` | DOC-004, DOC-007 |
| CAP-SUPPLIER-001 | Supplier listing, filters, identity grouping and blacklist | CONFIRMED | `supplier_app.py` supplier routes; `tests/test_supplier_identity.py` | DOC-004, DOC-007 |
| CAP-DISCOVERY-001 | Offline/query-planned supplier discovery and enrichment | CONFIRMED | `supplier_discovery_v2/`; `tests/test_query_planner.py`; `tests/test_enrichment_pipeline.py` | DOC-004, DOC-007 |
| CAP-MESSAGE-001 | Correspondence, outbox and message visibility | CONFIRMED | `supplier_app.py` mail routes; `tests/test_messages_visibility.py` | DOC-004, DOC-005 |
| CAP-INCOMING-001 | Incoming sync, parsing, deduplication and unmatched messages | CONFIRMED | `mail/service.py`; `mail/content.py`; `tests/test_mail_integration.py` | DOC-004, DOC-005 |
| CAP-OUTGOING-001 | Outgoing queue with provider gate and send semantics | CONFIRMED | `mail/service.py`; `mail/queue.py`; `tests/test_outgoing_safety.py` | DOC-004, DOC-005 |
| CAP-RENDERING-001 | HTML/plain/CID content sanitation and rendering | CONFIRMED | `mail/content.py`; `frontend/tests/email-renderer-responsive.spec.ts` | DOC-004, DOC-006 |
| CAP-LINKING-001 | Message-to-request and supplier linking | CONFIRMED | `mail/repository.py`; `supplier_app.py`; `tests/test_supplier_identity.py` | DOC-004, DOC-005 |
| CAP-THREADING-001 | Stable mail threads and reply headers | CONFIRMED | `mail/repository.py`; `tests/test_mail_integration.py` | DOC-004, DOC-005 |
| CAP-DEDUP-001 | Recipient and idempotency protection | CONFIRMED | `mail/deliverability.py`; `tests/test_supplier_identity.py`; `tests/test_mail_integrity.py` | DOC-004, DOC-005 |
| CAP-PACING-001 | Pacing, reservations, cooldown and campaign budgets | CONFIRMED | `mail/pacing.py`; `tests/test_mail_pacing.py` | DOC-004, DOC-005 |
| CAP-DELIVERY-001 | Delivery status and uncertainty semantics | CONFIRMED | `mail/deliverability.py`; `tests/test_mail_status_semantics.py` | DOC-004, DOC-005 |
| CAP-SUPPRESSION-001 | Bounce and suppression handling | CONFIRMED | `mail/bounce.py`; `tests/test_mail_status_semantics.py` | DOC-004, DOC-005 |
| CAP-CAMPAIGN-001 | Campaign stages, pause/stop and safe retry preview | CONFIRMED | `supplier_app.py` campaign routes; `tests/test_mail_deliverability.py` | DOC-004, DOC-005 |
| CAP-DATABASE-001 | SQLite persistence, migrations and integrity checks | PARTIAL | `mail/repository.py`; `migrations/001..032`; runtime DB absent in this worktree | DOC-003 |
| CAP-FRONTEND-001 | Frontend shell, product views and responsive acceptance | CONFIRMED | `frontend/src/`; `frontend/tests/`; inherited 8-pass shell evidence | DOC-006 |
| CAP-RUNTIME-001 | Canonical runtime lock, provenance and session manifests | CONFIRMED | `mail/runtime.py`; `tests/test_canonical_runtime.py` | DOC-001, DOC-004 |
| CAP-DIAGNOSTIC-001 | Read-only environment, contract and safety diagnostics | PARTIAL | `scripts/doctor.ps1` before this task; V1 artifacts created here | DOC-001..DOC-010 |

## Evidence boundaries

The catalog does not claim current provider health, current database rows,
live mailbox delivery, or source-checkout parity. Those remain `NOT VERIFIED`
until safe, authorized evidence is available.
