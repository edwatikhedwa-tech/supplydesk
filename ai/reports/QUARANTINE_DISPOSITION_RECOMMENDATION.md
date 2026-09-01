# Quarantine Disposition Recommendation — 2026-09-01

Status: `RETAINED — recommendation only; no deletion performed`

The external quarantine remains outside the repository and outside Git. The
following recommendations are future disposition categories, not permission
to purge. Permanent deletion requires a separate owner-approved task.

## Current retained inventory

| Category | Files | Bytes | Recommendation | Suggested retention |
|---|---:|---:|---|---|
| `01_REVIEW_PACKAGES` | 210 | 8,236,960 | `SAFE_TO_PURGE_LATER` after final acceptance and owner confirms no recovery need | Until final acceptance is retained remotely and owner approves purge. |
| `02_BACKUP_COPIES` | 11 | 980,704 | `RETAIN_AS_HISTORY` until source/data recovery review; then `SAFE_TO_PURGE_LATER` if an equivalent snapshot exists | Retain through the next recovery review. |
| `03_OLD_EXPORTS` | 13 | 38,160,562 | `PRIVACY_REVIEW_REQUIRED` before purge because exports may contain business or personal data | Retain until content category and privacy owner are confirmed. |
| `04_HISTORICAL_LOCAL_ONLY` | 1,247 | 85,291,334 | `RETAIN_AS_HISTORY`; items containing real mail identities also require privacy review | Retain as historical evidence or replace only with an equivalent approved snapshot. |
| `05_UNKNOWN_REVIEW` | 3 | 43,845 | `UNKNOWN` — do not purge until the owner reviews the three former legacy unknowns | Retain until explicit disposition. |
| `MANIFEST` | 2 | 38,181 | `RETAIN_AS_HISTORY` for chain-of-custody metadata | Retain with the quarantine record. |
| **Total** | **1,486** | **132,751,586** | **No purge in this task** | **Retained** |

## Safety boundary

- No quarantine file was inspected beyond path/metadata needed for the
  classification already recorded by Batch 1 and Batch 2 evidence.
- No secrets, database contents or real-mail contents are reproduced here.
- The quarantine is not a source of truth and must not be added to Git.
- A future purge should first produce a dry-run manifest, confirm recovery
  equivalence and privacy disposition, then obtain explicit owner approval.

## Rollback

No rollback is needed because this task did not modify the quarantine. Before
any future purge, the exact manifest and approved retention decision must be
stored outside the repository; this recommendation itself authorizes nothing.
