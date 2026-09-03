---
document_id: TASK-LOCK-033
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-03
based_on_commit: 6b782b2
---

# Active Task

Task ID: `NONE`
Agent: `Claude`
Mode: `IDLE`
Started: `2026-09-03`
Scope: `No active task; TASK-BOUNDED-SUPPLIER-APP-ROUTE-HELPERS-EXTRACT-20260903 (batches A+B) is closed: request-route and global-supplier-route helpers moved to backend/http_requests.py/backend/http_global_suppliers.py, composed via inheritance; do_GET/do_POST/do_DELETE untouched; DISPATCH_TABLE evaluated as NOT_NEEDED (do_GET/do_POST's remaining size is inline mail-route bodies, not if/elif overhead a table would fix); 497 tests / 0 failures. Batch C (mail HTTP route helpers) explicitly NOT started -- mail routes have no existing sub-router method to lift, unlike requests/global-suppliers, so extracting them means creating new method boundaries inside do_GET/do_POST rather than a pure move; needs an explicit owner decision before proceeding. mail/repository.py mixin split remains the other open item.`
Allowed files: `none — no active task`
Status: `IDLE — TASK-BOUNDED-SUPPLIER-APP-ROUTE-HELPERS-EXTRACT-20260903 completed; batch C awaiting owner decision`
Last update: `2026-09-03`
