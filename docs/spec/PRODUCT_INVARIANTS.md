---
document_id: DOC-SPEC-PRODUCT-INVARIANTS-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Product Invariants

Durable rules SupplyDesk must uphold. Each has a stable ID, a status (`HELD` = verified true in
current code, `VIOLATED` = confirmed broken, `PARTIAL` = held in most but not all paths), and
evidence. Extracted from actual code/tests plus the pre-existing `docs/requirements/
BUSINESS_RULES.md` (`BR-*` ids kept as-is where still accurate, cross-referenced rather than
duplicated).

## Messages

| ID | Rule | Status | Evidence |
|---|---|---|---|
| INV-MSG-001 | A message/thread is never physically deleted by any user-facing action — only status/visibility changes. | HELD | Only DELETE in the repo touching these tables is in an offline maintenance script with no HTTP route |
| INV-MSG-002 | An unmatched inbound message is preserved, never silently dropped, until a human resolves it. | HELD | `mail_inbox_messages`, no path removes a row except explicit `ignore` (status change, not deletion) |
| INV-MSG-003 | `conversation_status` (personal workflow label) never affects sending or blacklist status. | HELD | `thread_metadata.py::set_thread_status`, confirmed by both `docs/ui/MESSAGES_SCREEN_SPEC.md` §13 and this audit |
| BR-MSG-001 | Incoming messages are deduplicated and remain visible with no request match. | HELD | `tests/test_mail_integration.py`, `tests/test_messages_visibility.py` |

## Suppliers

| ID | Rule | Status | Evidence |
|---|---|---|---|
| INV-SUP-001 | One real ИНН groups as one `global_suppliers` identity within a workspace; different ИНН stays separate. | HELD | `global_suppliers UNIQUE(workspace_id, inn)`, `tests/test_supplier_identity.py` |
| **INV-SUP-002** | **One real-world supplier must not uncontrollably create new independent `suppliers` rows on repeated discovery/contact.** | **VIOLATED (confirmed live, not historical)** | `resolve_supplier_for_send`'s key-degrades-to-raw-email fallback creates a duplicate when no host is known at write time — 28/243 rows (11.5%) in the audited local DB carry this signature. See `GAP-003`, [`../product/SUPPLIERS.md`](../product/SUPPLIERS.md) |
| INV-SUP-003 | A cross-tenant company resolution (`canonical_companies`) is reused instead of re-querying Checko for a company another workspace already resolved. | HELD (partially — only in `_resolve_missing_inn`, not the main enrich pipeline) | `tests/test_canonical_companies_cache_reuse.py`; `docs/domain/SUPPLIER_MODEL.md` §4 honestly documents the partial scope |
| INV-SUP-004 | Workspace-private data (contacts, notes, tasks, prices) never leaks into the cross-tenant `canonical_companies` layer. | HELD | `tests/test_canonical_companies.py::test_write_through_carries_no_tenant_specific_data`, `tests/test_supplier_workspace_isolation.py` |
| INV-SUP-005 | A manually-entered ИНН is never silently overwritten by a later automatic candidate. | HELD | `tests/test_manual_inn_is_visible_and_wins_over_later_auto_candidate` |

## AI Assistant

| ID | Rule | Status | Evidence |
|---|---|---|---|
| INV-AI-001 | A supplier must not enter AI context solely because it is linked to a request — only because real communication exists. | HELD | Fixed 2026-09-10 (`0d16945`); server-enforced via `get_thread_owned`, not just a frontend filter. See [`../product/AI_ASSISTANT.md`](../product/AI_ASSISTANT.md) |
| INV-AI-002 | AI usage cannot exceed the configured daily spend cap. | HELD | Checked before every LLM call, `ai_chat_usage` |

## Mail sending safety

| ID | Rule | Status | Evidence |
|---|---|---|---|
| BR-MAIL-001 | Deliverability preflight/preview never calls a real provider. | HELD | `tests/test_mail_deliverability.py` |
| BR-MAIL-002 | One company identity does not receive multiple grouped outbound messages in one operation. | HELD | `tests/test_supplier_identity.py` |
| BR-MAIL-003 | A used recipient is never silently reused; an alternate must be `NEVER_USED` before selection. | HELD | `tests/test_mail_status_semantics.py` |
| BR-MAIL-004 | Repeating an idempotent operation does not create another message/job. | HELD | `tests/test_mail_integrity.py` |
| BR-MAIL-006 | Hard bounce suppresses future use; soft bounce keeps a recoverable history, never deletes. | HELD | `mail/bounce.py`, `tests/test_mail_status_semantics.py` |
| INV-MAIL-004 | Two suppliers whose resolved recipient converges on the same final email are blocked as duplicates, counted post-resolution not pre-resolution. | HELD | Fixed 2026-09-16, `docs/domain/SUPPLIER_MODEL.md` §7.4, `tests/test_contact_resolution_send_path.py` |

## Data/runtime safety

| ID | Rule | Status | Evidence |
|---|---|---|---|
| BR-DATA-001 | Destructive request deletion is blocked while delivery resolution is unresolved. | HELD | 409 response, `tests/test_mail_status_semantics.py` |
| BR-RUNTIME-001 | Only the canonical runtime may hold the canonical lock; other runtimes write only their own manifest. | HELD | `mail/runtime.py`, `tests/test_canonical_runtime.py` |
| BR-CONTENT-001 | HTML is sanitized; remote-image fetching is never a prerequisite for rendering. | HELD | `mail/content.py` |
| BR-AUTH-001 | A request must never expose another workspace's records. | HELD | `tests/test_mail_integrity.py` |

## Maintenance/operational safety (newly extracted this audit)

| ID | Rule | Status | Evidence |
|---|---|---|---|
| INV-OPS-001 | A maintenance route that spends a metered third-party API budget must be POST (not GET), CSRF-protected, and bounded by an explicit per-call budget. | **VIOLATED by `force_enrich_all_suppliers`** (as written on the snapshot branch — not merged into the active branch) | GET, no CSRF check, no rate limit, no budget cap, unbounded Checko spend (`2×N` calls worst case). See `GAP-002` |
