---
document_id: TASK-LOCK-041
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-19
based_on_commit: d2221d8
---

# Active Task

Task ID: `EDW-7` (Linear) — Iteration 2: Mail Intelligence Core
Agent: `Claude Code`
Mode: `IMPLEMENTATION`
Branch: `experiment/frontend-v2-greenfield-20260905`
Scope: minimal vertical slice `incoming message -> exact rules -> unified analysis -> fact store + provenance ->
idempotency -> cheap->strong cascade -> manual review -> downstream event without a second AI call`.
Out of scope: the 24 historical duplicate pairs (EDW-22), live-sync wiring, LLM matching, price history, logistics.
Allowed files: `migrations/057_mail_analysis_core.sql, mail/message_analysis.py, mail/repository.py (mixin wiring only),
tests/test_mail_analysis_core.py, scripts/pg_gate.py, docs/domain/MAIL_ANALYSIS.md, ai/*`.
Previous task `TASK-CALENDAR-REMINDERS-20260916` is finished; its record is in git history.
