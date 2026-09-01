---
document_id: REQUIREMENTS-CATALOG-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Requirements Catalog

Active requirements are extracted from implementation and existing tests.
`DRAFT` items describe a safe future boundary and are not accepted product
contracts. `SAFETY` is a control requirement; `OPERATIONAL` covers evidence
and recovery practice.

| ID | Type | Status | Critical | Summary |
|---|---|---|---|---|
| REQ-AUTH-001 | FUNCTIONAL | ACTIVE | yes | Requests and mail data are scoped to the authenticated workspace. |
| REQ-AUTH-002 | SAFETY | ACTIVE | yes | CSRF, ownership and rate-limit gates must block unsafe access. |
| REQ-REQUEST-001 | FUNCTIONAL | ACTIVE | no | Operators can create and inspect requests and positions. |
| REQ-REQUEST-002 | FUNCTIONAL | ACTIVE | no | Search/enrichment progress and retry state are durable. |
| REQ-SUPPLIER-001 | FUNCTIONAL | ACTIVE | no | Supplier identity, grouping, filters and blacklist semantics are stable. |
| REQ-SUPPLIER-002 | FUNCTIONAL | ACTIVE | no | Manual identifiers and enrichment evidence are persisted without duplicates. |
| REQ-DISCOVERY-001 | FUNCTIONAL | ACTIVE | no | Discovery uses planned queries and evidence-backed candidate qualification. |
| REQ-MESSAGE-001 | FUNCTIONAL | ACTIVE | no | Queue-only, sent/failed and incoming visibility are distinct. |
| REQ-MAIL-001 | FUNCTIONAL | ACTIVE | yes | Incoming sync parses, deduplicates and preserves unmatched mail. |
| REQ-MAIL-002 | SAFETY | ACTIVE | yes | Deliverability preflight is read-only and does not contact SMTP. |
| REQ-MAIL-003 | SAFETY | ACTIVE | yes | Duplicate recipients and non-idempotent retries are blocked. |
| REQ-MAIL-004 | FUNCTIONAL | ACTIVE | no | HTML/plain/CID content is sanitized and rendered safely. |
| REQ-MAIL-005 | SAFETY | ACTIVE | yes | Accepted or uncertain delivery is not automatically retried. |
| REQ-MAIL-006 | SAFETY | ACTIVE | yes | Pacing, budgets, reservations and kill switch gate outgoing work. |
| REQ-MAIL-007 | FUNCTIONAL | ACTIVE | no | Bounce classification drives suppression while retaining history. |
| REQ-MAIL-008 | FUNCTIONAL | ACTIVE | no | Campaign stages and pause/stop state are durable. |
| REQ-DATA-001 | SAFETY | ACTIVE | yes | Canonical database diagnostics are read-only; integrity is explicit. |
| REQ-RUNTIME-001 | SAFETY | ACTIVE | yes | Canonical runtime lock and provenance prevent unsafe parallel operation. |
| REQ-FRONTEND-001 | FUNCTIONAL | ACTIVE | no | Frontend shell and key views meet type, lint, build and browser gates. |
| REQ-DIAG-001 | OPERATIONAL | ACTIVE | yes | Doctor reports typed outcomes for repository and runtime checks. |
| REQ-DIAG-002 | OPERATIONAL | ACTIVE | yes | Doctor emits machine-readable evidence and stable exit codes. |
| REQ-DIAG-003 | OPERATIONAL | DRAFT | yes | Future repair agent works only in a sandbox after human confirmation. |

## Acceptance rule

Only `ACTIVE` rows are accepted contracts. A traceability row for
`REQ-DIAG-003` is intentionally marked `DRAFT` and cannot satisfy an active
requirement gate.
