---
document_id: AUDIT-SECURITY-FINDINGS-20260901
status: HISTORICAL
canonical: false
owner: audit
updated_at: 2026-09-01
source_commit: b5a454f9b39f3cbf01d640d5b67e4231ca25733a
---

# Security and secret-safety findings

## Method

High-signal patterns for private keys, common cloud/API tokens and authorization
headers were searched with `rg` over project-owned code and documentation,
excluding vendor, database and generated trees. Git history was searched for the
same patterns. Secret values were never printed or copied into this report.

## Results

- **P0 proven secrets:** none found by the high-signal scan;
- tracked `.env*` files: none (`git ls-files .env*` returned no files);
- local env-like files: 6, all ignored; only path, size and hashes were handled:
  `.env`, `.env.example`, `.env.local`, `.env.p0-backup-20260830`,
  `.env.production.local`, `.vercel/.env.preview.local`;
- actual values inside those files: **NOT VERIFIED by design**;
- Git history high-signal scan: no match;
- source database and local mail data remain sensitive local state and were not
  included as row contents in reports;
- no real email or external SMTP action was performed.

## Risks

1. **P1 operational risk:** ignored local env files may contain credentials;
   filesystem access must remain restricted and they must never be committed.
2. **P2 visibility risk:** broad ignore rules can hide local databases, exports
   and runtime state from ordinary Git review. This is why the audit records
   ignored FILES separately.
3. **P2 documentation risk:** reports must continue to use paths/statuses only;
   do not paste tokens, email bodies, cookies or database rows into evidence.

No secret rotation was initiated because no concrete exposed secret was proven,
and changing credentials would be an external operational action outside this
read-only audit.
