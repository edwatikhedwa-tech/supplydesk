---
document_id: DOC-PRODUCT-SUPPLIERS-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Suppliers — Identity, Enrichment, and the Duplication Gap

The full model (three-tier identity, evidence graph, TTL, tenant isolation) is already
documented in detail and confirmed current in
[`../domain/SUPPLIER_MODEL.md`](../domain/SUPPLIER_MODEL.md) — not duplicated here. This file
adds what that document does not yet cover: the specific, live supplier-duplication defect found
during this audit, verified against the actual local database.

## AS-IS: how a `suppliers` row's identity key is decided

`upsert_supplier` (`mail/repository.py:3363`) keys on `(workspace_id, external_key)` via
`ON CONFLICT DO UPDATE`. `external_key` is normally the host found via search. But
`resolve_supplier_for_send` — the send-time resolver called for every outbound recipient — falls
back, when no host/external_key is known, to:

```python
normalized_key = str(external_key or normalized_host or normalized_email).strip().lower()
```

i.e. it silently uses the **raw email address** as the identity key. This is not a rare edge
case: it fires any time a buyer sends (or a reply arrives from) an address that wasn't the one
search originally found for that company — most commonly a personal Gmail/Yandex/Mail.ru address
used by a real employee instead of the company's own domain.

`resolve_supplier_for_send` does try an email match *first* (`WHERE LOWER(s.email)=?`) before
falling back to host match and then to creating a new row — but that only helps if the
**pre-existing** row's `email` column is already populated with that exact address. A supplier
created via search (`upsert_search_result`) starts with `email=""`. So the very first manual send
to a personal address found on that supplier's own site still creates a duplicate today — this
guard (added in commit `85fb7a2d`) closes the door only after it's already been walked through
once.

## Confirmed scope (live local database, 2026-09-17)

| Metric | Count |
|---|---|
| Total `suppliers` rows | 243 |
| Rows where `external_key == email` (the bug's signature) | 28 (11.5%) |
| Of those, reply address is a personal webmail domain | 12 |

The originally-reported case (request #1059, `sfera.termo@yandex.ru`) is one instance of this
pattern: supplier id 2837 (`external_key=termo-sfera.pro`, has real registry/finance data) and id
3315 (`external_key=email address itself`, holds the actual conversation thread) are two rows for
one real company. Row 3315 was created by an **outbound** send with no host supplied
(`request_suppliers.reason='Добавлен при отправке письма.'`), not by inbound-reply ingestion —
the inbound path (`import_incoming_messages`) never creates a supplier row; it only parks
unmatched mail or threads onto an *existing* supplier.

## Data-preservation constraints for a future fix

Checked for this specific pair: `tasks`, `mail_thread_notes`, `workspace_supplier_contacts`,
`blacklist_entries` all have **zero rows** tied to either id — a merge here would lose nothing.
Row 3315 uniquely holds the live `mail_threads`/`mail_messages`/`request_supplier_states`; row
2837 uniquely holds the search-derived `supplier_profiles`/`request_suppliers` position data. A
correct fix must re-point the mail-side rows onto the enriched card (or vice versa) without
dropping either side — and must handle this generically, since other pairs among the 28 may carry
notes/tasks/overrides this specific pair happens not to have.

## EXPECTED (per the stated invariant)

`docs/domain/SUPPLIER_MODEL.md` §2: "поставщик — каноническая сущность; одна организация не
должна заново создаваться... ни внутри одного workspace." One real-world correspondent should
never occupy two `suppliers` rows in the same workspace merely because it was discovered by host
once and by a personal reply address another time.

## Recorded as

- Invariant violated: `INV-SUP-002` (see [`../spec/PRODUCT_INVARIANTS.md`](../spec/PRODUCT_INVARIANTS.md))
- Gap: `GAP-003`, severity **P0** (see [`../system/KNOWN_GAPS.md`](../system/KNOWN_GAPS.md))

No fix has been applied. This is a documentation/investigation record only, per explicit
instruction for this audit pass.
