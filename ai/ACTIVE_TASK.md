---
document_id: TASK-LOCK-041
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-19
based_on_commit: d2221d8
---

# Active Task

Task ID: `EDW-38` (Linear) — limited-enablement readiness of Mail Intelligence (async analysis, routing before extraction, source vs request-scoped facts)
Agent: `Claude Code`
Mode: `CLOSING` (implementation finished, pushed; next stage = canary plan for ONE workspace, flag stays OFF)
Branch: `experiment/frontend-v2-greenfield-20260905`
Scope: `migrations/058, 059`, `mail/attachment_intelligence.py, attachment_analysis.py, analysis_queue.py, diagnostics.py`, mail parser/import/sync wiring,
`tests/test_analysis_queue.py, test_attachment_*.py, test_diagnostic_hygiene.py`, `benchmarks/attachment_intelligence`, `benchmarks/e2e_mail`, `docs/benchmarks/*`.
Out of scope: enabling `MAIL_INTELLIGENCE_ON_SYNC` anywhere; real supplier benchmark; S17 recall (own follow-up task); EDW-22.
Previous task `EDW-7` slice 1 is finished; its record is in git history.
