---
document_id: DOCS-README-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-17
source_commit: dc66b0b
---

# SupplyDesk documentation

This is the product-documentation entrypoint. SupplyDesk is a private
repository containing a Python backend, a serverless API entrypoint, a
frontend, and SQLite-backed mail/supplier workflows as recorded in the project
manifest. Current runtime facts belong to [`ai/CURRENT_STATE.md`](../ai/CURRENT_STATE.md),
not this index.

## Documentation map

- [`product/`](product/README.md) — product documentation boundary and entrypoint.
- [`requirements/`](requirements/README.md) — business and functional requirements.
- [`architecture/`](architecture/README.md) — architecture documentation. **See the staleness
  note below before trusting its `COMP-FRONTEND` row.**
- [`data/`](data/README.md) — data model and persistence documentation (directory-purpose stub
  only; see [`technical/DATABASE_MAP.md`](technical/DATABASE_MAP.md) for actual schema content).
- [`api/`](api/README.md) — API contracts and endpoint documentation (narrow scope; see
  [`technical/API_MAP.md`](technical/API_MAP.md) for the complete route inventory).
- [`testing/`](testing/README.md) — test strategy and acceptance evidence.
- [`operations/`](operations/README.md) — runbooks and operational procedures.
- [`domain/`](domain/SUPPLIER_MODEL.md) — supplier identity/enrichment domain model (current,
  read this before any supplier-related task).
- [`ui/`](ui/MESSAGES_SCREEN_SPEC.md) — Messages screen UI spec (current).
- [`DOCUMENTATION_POLICY.md`](DOCUMENTATION_POLICY.md) — lifecycle, ownership, and definition of done.

### New tree from the 2026-09-17 full system/product audit

Produced to give the next agent a verified, AS-IS model of the system with no guessing. Start at
[`system/SYSTEM_MAP.md`](system/SYSTEM_MAP.md).

- [`system/`](system/SYSTEM_MAP.md) — system map, feature-status matrix
  ([`CURRENT_STATE.md`](system/CURRENT_STATE.md)), and everything found wrong
  ([`KNOWN_GAPS.md`](system/KNOWN_GAPS.md)).
- [`product/PRODUCT_MODEL.md`](product/PRODUCT_MODEL.md),
  [`USER_FLOWS.md`](product/USER_FLOWS.md), [`MESSAGES.md`](product/MESSAGES.md),
  [`SUPPLIERS.md`](product/SUPPLIERS.md), [`AI_ASSISTANT.md`](product/AI_ASSISTANT.md) — product
  behavior, verified against code, not assumed from the UI.
- [`frontend/FRONTEND_ARCHITECTURE.md`](frontend/FRONTEND_ARCHITECTURE.md),
  [`UI_INVENTORY.md`](frontend/UI_INVENTORY.md),
  [`FRONTEND_V1_V2_COMPARISON.md`](frontend/FRONTEND_V1_V2_COMPARISON.md) — which frontend is
  actually live, and the evidence-based root cause of the visual inconsistency complaint.
- [`technical/API_MAP.md`](technical/API_MAP.md), [`DATABASE_MAP.md`](technical/DATABASE_MAP.md),
  [`DATA_FLOW.md`](technical/DATA_FLOW.md), [`INTEGRATIONS.md`](technical/INTEGRATIONS.md).
- [`spec/PRODUCT_INVARIANTS.md`](spec/PRODUCT_INVARIANTS.md),
  [`spec/requirements.yaml`](spec/requirements.yaml) — durable rules and per-requirement status,
  distinct from the coarser pre-existing `requirements/requirements.yaml`.
- [`testing/TEST_CASES.md`](testing/TEST_CASES.md) (product test cases appended alongside the
  existing diagnostic ones), [`testing/TEST_STRATEGY.md`](testing/TEST_STRATEGY.md) (extended
  with a frontend-v2 QA gap section).
- [`validation/TRACEABILITY_MATRIX.md`](validation/TRACEABILITY_MATRIX.md) — requirement →
  implementation → test → evidence → result, `NOT VERIFIED` is never silently upgraded to PASS.
- [`decisions/`](decisions/README.md) — empty by design; this audit made no decisions, only
  findings.

**Staleness note:** `docs/architecture/COMPONENT_MAP.md` and `docs/product/CAPABILITY_CATALOG.md`
(both marked `status: CURRENT`, dated 2026-09-01/04) predate `frontend-v2` and describe the
retired `frontend/` as *the* frontend. Not deleted (historical value), but do not trust them for
"what's live" — see `docs/system/KNOWN_GAPS.md` (`GAP-011`).

## Current control context

Read [`../AGENTS.md`](../AGENTS.md), [`../PROJECT_MANIFEST.yaml`](../PROJECT_MANIFEST.yaml),
and [`../ai/CURRENT_STATE.md`](../ai/CURRENT_STATE.md) before using these
documents for implementation decisions.

