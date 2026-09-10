---
document_id: TASK-LOCK-040
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-10
based_on_commit: c65362d3b702f259074b0d9293d70f6065c2400c
---

# Active Task

Task ID: `TASK-MESSAGES-LINKS-STATUS-SEND-AI-20260910`
Agent: `Claude Code`
Mode: `IMPLEMENTATION`
Started: `2026-09-10`
Scope: `Messages screen: clickable HTML email links (port frontend-v2 EmailRenderer), per-request-supplier conversation status (В работе/Отложено/Отклонено), fix real mail send (error handling + reply threading headers) and real attachments in the composer, restructure /api/ai/chat to a server-validated structured context (request_id + thread_ids, no more raw client string), add server-side AI chat persistence (ai_conversations/ai_messages) with a New chat/history UI, and prove all of it with real backend + browser evidence including 3 owner-specified AI stress tests. Full plan: C:\Users\edwat\.claude\plans\playful-wondering-music.md`
Allowed files: `frontend-v2/src/pages/Messages.tsx, frontend-v2/src/components/EmailRenderer.tsx, frontend-v2/src/components/AiChatPanel.tsx, frontend-v2/src/lib/api.ts, frontend-v2/src/lib/types.ts, mail/thread_metadata.py, mail/repository.py, mail/service.py, mail/ai_conversations.py, backend/http_requests.py, supplier_app.py, backend/domain/ai_agent/chat_service.py, migrations/039_thread_conversation_status.sql, migrations/040_ai_conversations.sql, tests/test_thread_conversation_status.py, tests/test_ai_context_scoping.py, docs/ui/MESSAGES_SCREEN_SPEC.md, ai/CURRENT_STATE.md, ai/ACTIVE_TASK.md, ai/DECISIONS.md, ai/DEFERRED_FINDINGS.md`
Status: `PARTIAL — implementation and live verification complete for §1-11; see ai/CURRENT_STATE.md 2026-09-11 entry and ai/DEFERRED_FINDINGS.md FINDING-026..028 for exactly what is NOT_VERIFIED/PARTIAL/FAIL. Not yet committed.`
Last update: `2026-09-11`

**Pending, not done — do not start a new unrelated task assuming this one is closed:**

1. Not committed/pushed/deployed yet — implementation and live verification
   are complete on the local worktree only.
2. `FINDING-026`: real SMTP transmission for send/attachments is
   architecturally unverifiable from `LOCAL_CANONICAL` (`environment ==
   "production"` gate) — needs verification against the actual production
   deployment after review, not a code fix.
3. `FINDING-027`/`FINDING-028`: AI Stress Test 2 (price/term missed for one
   multi-option supplier) and Stress Test 3 (re-asks already-answered
   questions) are real, reproducible model-quality gaps, not code bugs —
   a follow-up task should evaluate structured/tool-based extraction.
4. Attachment UI was added only to the main thread-reply composer
   (`sendReply`), not to the secondary unmatched-inbox reply composer
   (`sendUnmatchedReply`/`replyToInbox`) — backend already supports
   attachments there too; frontend UI not built, disclosed scope boundary.
5. Mail.ru OAuth remains stubbed (pre-existing, out of this task's scope,
   untouched).
6. A few live test artifacts remain in the canonical local DB from this
   session's verification (real `ai_conversations`/`ai_messages` rows,
   one queued-forever test message in request 1059's self-thread with a
   real attachment) — left in place deliberately as honest evidence, not
   cleaned up, since they are harmless (never actually sent, do not affect
   real supplier data).

Superseded/previous entry (kept below for history, not the current task):

---

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
