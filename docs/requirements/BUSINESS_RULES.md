---
document_id: BUSINESS-RULES-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Business Rules

Rules below are the smallest durable decisions supported by code and tests.
The linked test names are evidence; a missing live runtime is not silently
converted into a pass.

| ID | Rule | Evidence |
|---|---|---|
| BR-AUTH-001 | A request must not expose another workspace's records. | `tests/test_mail_integrity.py` ownership/auth tests |
| BR-MAIL-001 | Deliverability preflight and preview do not call a provider. | `tests/test_mail_deliverability.py` preflight tests |
| BR-MAIL-002 | One company identity is not sent multiple grouped outbound messages in one operation. | `tests/test_supplier_identity.py` grouped outbound tests |
| BR-MAIL-003 | A used recipient is not silently reused; an alternate must be `NEVER_USED` before selection. | `tests/test_mail_status_semantics.py` alternate recipient tests |
| BR-MAIL-004 | Repeating an idempotent operation does not create another message or job. | `tests/test_mail_integrity.py` idempotency tests |
| BR-MAIL-005 | `accepted` and `delivery_unknown` are not automatic retry permissions. | `tests/test_mail_status_semantics.py` retry tests |
| BR-MAIL-006 | Hard bounce suppresses future use; soft bounce retains a recoverable state and history. | `tests/test_mail_status_semantics.py`, `mail/bounce.py` |
| BR-MAIL-007 | Pacing, reservation, budget and kill-switch gates are checked at send time. | `tests/test_mail_pacing.py`, `tests/test_mail_deliverability.py` |
| BR-MAIL-008 | Campaign pause/stop and stage transitions are durable and respected by queue work. | `tests/test_mail_deliverability.py` |
| BR-MAIL-009 | Provider failures are classified; a timeout after provider acceptance is uncertain, not a safe retry. | `mail/deliverability.py`, `tests/test_mail_status_semantics.py` |
| BR-MSG-001 | Incoming messages are deduplicated and remain visible when no request match exists. | `tests/test_mail_integration.py`, `tests/test_messages_visibility.py` |
| BR-SUPPLIER-001 | Same INN groups as one identity; different INN values remain separate. | `tests/test_supplier_identity.py` |
| BR-DATA-001 | Destructive request deletion is blocked while delivery resolution is unresolved. | `tests/test_mail_status_semantics.py` |
| BR-RUNTIME-001 | Only the canonical runtime may own the canonical lock; other runtimes write only their own manifest. | `tests/test_canonical_runtime.py`, `mail/runtime.py` |
| BR-CONTENT-001 | HTML is sanitized and remote image fetching is not a prerequisite for rendering. | `mail/content.py`, `tests/test_mail_deliverability.py` |

## Safety interpretation

These rules do not authorize production sends, migration application,
credential changes, customer deletion, deployment, force-push or merge.
