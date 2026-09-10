---
document_id: TASK-LOCK-040
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-11
based_on_commit: c65362d3b702f259074b0d9293d70f6065c2400c
---

# Active Task

Task ID: `TASK-MESSAGES-AI-CONTEXT-SUPPLIER-NAME-CANONICAL-20260910`
Agent: `Claude Code`
Mode: `IMPLEMENTATION`
Started: `2026-09-10`
Scope: `Restrict Messages' AI-помощник context to suppliers with status "Есть ответ" (not just "any communication"); root-cause and fix the SEO-title-as-supplier-name bug at both suppliers.name and global_suppliers.name; add a cross-tenant canonical company directory so a company one workspace resolves is reusable by another; record the durable invariants in docs/ui/MESSAGES_SCREEN_SPEC.md and the new docs/domain/SUPPLIER_MODEL.md.`
Allowed files: `frontend-v2/src/pages/Messages.tsx, mail/repository.py, mail/canonical_companies.py, backend/domain/supplier_enrichment/orchestrator.py, supplier_app.py, migrations/038_canonical_companies.sql, tests/test_supplier_name_resolution.py, tests/test_canonical_companies*.py, docs/ui/MESSAGES_SCREEN_SPEC.md, docs/domain/SUPPLIER_MODEL.md, docs/product/messages-workspace.md, CLAUDE.md, AGENTS.md, ai/DECISIONS.md, ai/DEFERRED_FINDINGS.md, ai/CURRENT_STATE.md, ai/ACTIVE_TASK.md`
Status: `PARTIAL — see ai/DEFERRED_FINDINGS.md FINDING-021..023 for exactly what is pending; nothing here is reported DONE without live/automated proof`
Last update: `2026-09-11`

Commits (branch `experiment/frontend-v2-greenfield-20260905`, all deployed to
production and pushed to `origin`): `0d16945`, `f6ed9b8`, `8a8acbc`,
`3728f3e`, `c65362d`. Decisions: `DECISION-021` (AI-context "Есть ответ" +
supplier-name invariants), `DECISION-022` (cross-tenant `canonical_companies`).

**Pending, not done — do not start a new unrelated task assuming this one is closed:**

1. `/maintenance/refresh-bad-global-supplier-names-20260911` has not run on
   production data — `CHECKO_KEY` is not set in the Vercel production
   environment (`checko_unavailable: true` on the one live call attempted
   2026-09-11). Needs the owner to add the key to Vercel env, then the route
   re-run.
2. Checko/DaData's terms of service on storing/caching their API responses
   were never verified (WebSearch/WebFetch were unavailable this session —
   infrastructure failure). The cross-tenant `canonical_companies` write-through
   shipped anyway as an accepted, disclosed risk (internal-product cache, not
   third-party redistribution) — a real ToS check is still owed.
3. Only one enrichment stage (`_resolve_missing_inn`) reads
   `canonical_companies` before spending a live Checko call. The main
   registry-resolution pipeline (`_process_enrich_step` and its `_resume_*`
   methods) does not yet — same cost-saving opportunity, not wired.
4. Cross-tenant dedup is ИНН-only; no cross-workspace domain-level matching.
5. `FINDING-021` (`ai/DEFERRED_FINDINGS.md`): transient 500s on
   `/api/mail/threads` under a large simultaneous "select all" (126 suppliers)
   — unrelated to this task, found while verifying it, not fixed.

Previous completed task report: `ai/reports/TASK-RUNTIME-SELECTION-HARD-GUARD-20260904-report.md`
Completed task report: `ai/reports/TASK-PREPARE-SUPPLYDESK-FOR-EXTERNAL-UI-REDESIGN-20260904-report.md`
Previous completed task report: `ai/reports/TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904-report.md`
Previous completed task report: `ai/reports/TASK-MESSAGES-PRODUCT-ACCEPTANCE-CORRECTION-20260904-report.md`
Completed task report: `ai/reports/TASK-SUPPLYDESK-UI-MODERNIZATION-20260904-report.md`
Completed task report: `ai/reports/TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904-report.md`

Completed task report: `ai/reports/TASK-VERCEL-FRONTEND-V2-LOGIN-20260909-report.md`
Completed task report: `ai/reports/TASK-VERCEL-AI-ACCOUNT-DATA-20260909-report.md`

Superseded/stale entry (kept for history, not the current task): Codex's
`TASK-TEST-DATA-CLEANUP-MAIL-CREDENTIAL-20260909` was left `ACTIVE` in this
file since 2026-09-09 with no further update; its actual production
aftermath (33 suppliers' `request_supplier_states` wrongly deleted for
protected requests 1043/1045/1058/1059/1062) was found and repaired this
session — see commits `905b237`, `09a36b0` and
`ai/reports/` for that investigation. Whether Codex's own task is still
in progress on its side is unknown to this session; do not assume it is
either abandoned or complete without checking with Codex directly.
