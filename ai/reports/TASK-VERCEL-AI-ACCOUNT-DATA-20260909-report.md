---
document_id: TASK-VERCEL-AI-ACCOUNT-DATA-20260909-REPORT
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-09
source_commit: a8916e08ab38023606a6808d40fb339f8449be97
---

# Production AI and account data repair

HISTORICAL — NOT CURRENT. Current authority: [CURRENT_STATE.md](../CURRENT_STATE.md).

## Goal, scope and completion

Restore the production AI assistant, keep the Yandex sign-in entry point, and
make requests, correspondence and the complete workspace supplier directory
visible in the owner's account. Scope was limited to the reproduced AI usage
write, a read-only supplier-directory API/UI path, focused tests, production
deployment and operational records. No cleanup, merge, migration, credential or
mail-send change was authorized or performed.

DONE: deployment `dpl_D4bfbGDmQPZy2XBzVoy7Shsv3mNV` is READY at
https://supplydesk-2769.vercel.app/. Authenticated acceptance showed 17 requests,
505 supplier rows, real correspondence and a successful AI answer. An anonymous
session showed the Yandex login action.

## Confirmed cause and changes

RouterAI returned a successful provider response, after which PostgreSQL
rejected the daily-usage upsert because `rub_spent` was unqualified and existed
in both the target and excluded rows. `mail/ai_chat_usage.py` now qualifies the
target-table counters. New repository/API code returns every supplier identity
belonging to the active workspace, while preserving the existing verified-INN
global cards and tenant boundary. The supplier UI identifies rows without INN,
links them back to their source request when possible, and uses responsive cards
below the desktop breakpoint.

The earlier 466 figure was the count of unique identities visible across 17
request-detail views (592 request/supplier links), not the complete workspace.
The directory contains 505 identities and all currently lack a verified INN.
The extra 39 may include blacklisted, excluded, orphaned, manual or test/contact
rows; the exact partition and historic search provider are not verified because
their source field is blank. Similar names can remain separate when neither INN
nor another safe legal identifier proves they are the same company.

## Verification evidence

- Workspace guard and `git diff --check`: PASS.
- Focused AI and supplier-directory suite: 4 PASS; the optional disposable
  PostgreSQL case skipped because no local PostgreSQL URL was available.
- Supplier identity suite: 27/27 PASS.
- Full Python suite: 512 tests PASS, 2 PostgreSQL-URL-dependent skips.
- Frontend production build: PASS. Lint: zero errors; warnings remain.
- Production HTTP: `/` 200, `/api/auth/me` 200, unknown API 404.
- Production logs after final deployment: no error-level entries found.
- Authenticated browser: 17 requests, 505 suppliers, correspondence loaded,
  live AI prompt answered without the former server error.
- Independent anonymous browser: Yandex login action visible.
- Supplier screenshots inspected at 1440x900, 1024x768 and 390x844; document
  width matched viewport and browser console errors were empty.

Visual evidence:
`frontend-v2/artifacts/supplier-directory-20260909/desktop-1440x900.png`,
`tablet-1024x768.png`, and `mobile-390x844.png`.

## Limits, cost and rollback

Docker is not required for SupplyDesk or Vercel. It was attempted only as a
disposable local PostgreSQL test environment and did not become ready; no Docker
configuration was changed. The production PostgreSQL flow provides the live
integration evidence, but that optional local test remains unverified. No new
service, paid plan or trial was enabled. The AI acceptance prompt was
non-sensitive and its small usage rounded to `0.00 ₽` in the interface; exact
provider billing was not independently verified.

The production deployment includes pre-existing unstaged runtime compatibility
patches in `api/index.py` and `mail/db_compat.py`; they remain owner work and were
not included in the task commit. To roll back code, revert commit `a8916e0`. To
roll back production, promote the preceding READY deployment, understanding
that doing so restores the former AI and supplier-directory defects. No Git
push was performed.

## Next step

No action is required for normal use. If the owner wants duplicates or the extra
39 identities reviewed, perform a separate read-only provenance audit first and
require an explicit allowlist before any merge or deletion.
