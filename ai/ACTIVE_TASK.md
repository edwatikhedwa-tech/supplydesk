---
document_id: TASK-LOCK-034
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-03
based_on_commit: babc99a
---

# Active Task

Task ID: `NONE`
Agent: `Claude`
Mode: `IDLE`
Started: `2026-09-03`
Scope: `No active task; TASK-BOUNDED-MAIL-REPOSITORY-AUTH-ACCOUNTS-EXTRACT-20260903 is closed: ~25 auth/session/OAuth-state/mail-account CRUD methods moved to mail/auth_accounts.py as AuthAccountsMixin (zero cross-cluster coupling, confirmed by fresh audit); mail/time_utils.py created to resolve a circular import (iso_now/iso_after/utc_now/DEFAULT_SESSION_LIFETIME_SECONDS), re-exported from mail/repository.py for existing consumers; 497 tests / 0 failures. Remaining mail/repository.py clusters by increasing risk: mail templates (trivial), dashboard/reporting (has real fan-out to 3 clusters), campaign creation+lifecycle (one domain split by file distance), then the risky queue/campaign/inbox-reply cluster sharing send-attempt/job-transition helpers (audit recommends its own _SendAttemptInfraMixin). supplier_app.py batch C (mail HTTP route helpers) still awaits a separate owner decision.`
Allowed files: `none — no active task`
Status: `IDLE — TASK-BOUNDED-MAIL-REPOSITORY-AUTH-ACCOUNTS-EXTRACT-20260903 completed`
Last update: `2026-09-03`
