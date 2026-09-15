---
document_id: TASK-LOCK-040
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-15
based_on_commit: pending-commit-TASK-FOLLOWUP-CONTACT-INTELLIGENCE-20260915
---

# Active Task

Task ID: `TASK-FOLLOWUP-CONTACT-INTELLIGENCE-20260915`
Agent: `Claude Code`
Mode: `IMPLEMENTATION`
Started: `2026-09-15`
Branch: `feature/followup-contact-intelligence-20260915` (base
`experiment/frontend-v2-greenfield-20260905`) — never worked directly on
`ui/external-redesign-shadcn-v2-20260904` or any default/base branch, per
explicit owner instruction.
Scope: `needs_followup derived thread state (configurable per-request SLA,
default 2 business days), «Связаться»/«Напомнить» actions with a historical
contact-result log, a workspace-scoped immediate preferred-contact
override, and a cross-tenant (canonical_companies-based) self-updating
email-contact consensus with hard/soft bounce handling and full
explainability without cross-workspace identity leaks. Full spec: the
owner's 10 acceptance criteria (AC-01..AC-10) in the task prompt.`
Allowed files: `migrations/051_contact_intelligence.sql,
mail/contact_intelligence.py, mail/repository.py, backend/http_requests.py,
frontend-v2/src/lib/types.ts, frontend-v2/src/lib/api.ts,
frontend-v2/src/pages/Messages.tsx,
frontend-v2/src/components/ContactResultModal.tsx(+.test.tsx),
frontend-v2/src/components/SupplierCardContent.tsx,
frontend-v2/package.json, frontend-v2/vitest.config.ts,
frontend-v2/src/setupTests.ts, tests/test_contact_intelligence.py,
docs/domain/SUPPLIER_MODEL.md, docs/ui/MESSAGES_SCREEN_SPEC.md,
ai/CURRENT_STATE.md, ai/ACTIVE_TASK.md, ai/DECISIONS.md,
ai/DEFERRED_FINDINGS.md.`
Status: `PARTIAL — backend fully implemented and tested (14/14 new tests,
full suite 662/662 unchanged); frontend implemented, typechecked, built,
linted and component-tested (4/4); NOT committed, NOT pushed, NOT merged
(explicit owner instruction: no merge/deploy without separate
confirmation). Live authenticated browser verification NOT performed — no
owner credentials available to this session. See
ai/DEFERRED_FINDINGS.md FINDING-037 for the complete, honest list of what
is verified vs. not.`
Last update: `2026-09-15`

---

Task ID: `TASK-MVP-SHOWREADY-20260911`
Agent: `Codex` (продолжение по прямому указанию владельца 2026-09-12)
Mode: `IMPLEMENTATION`
Started: `2026-09-11`
Scope: `Доведение утверждённого MVP-интерфейса до готовности к показу: задачи, календарь, напоминания только через безопасный UI/mock и последующие P0/P1/P2 пункты из docs/product/MVP_BACKLOG.md. Реальные телефония, публикация, deploy и любые новые платные сервисы исключены.`
Allowed files: `Затронутые узкие frontend/backend/test/documentation файлы текущего backlog-пункта; ai/CURRENT_STATE.md, ai/ACTIVE_TASK.md, docs/product/MVP_BACKLOG.md, docs/product/APPROVED_MVP_INTERFACE.md, work/active/TASK-MVP-SHOWREADY-20260911.md.`
Status: `COMPLETE_WITH_LIMITATIONS`
Last update: `2026-09-12`

Current scoped continuation: the prior FAQ-only `SUP-025` outcome did not
meet the owner-provided Support Chat specification. This completed iteration implements
the specified unified technical-support chat with durable conversations,
automatic page/request context, user attachments, and a compact history. It
also makes a task's linked company visible in Calendar using the existing real
`supplier_name` API field. The visual screenshot named by the owner is not
available in the supplied attachment directory, so exact pixel comparison is
tracked as `NOT VERIFIED` until it is attached again; browser verification of
the implementation itself is recorded in `ai/CURRENT_STATE.md`.
The Messages AI assistant now uses the same compact floating visual pattern as
technical support; the former desktop third column/right icon rail has been
replaced with modern header actions for notes, tasks and AI, without changing
the server-side conversation, usage or context contracts.

Completed MVP scope and disclosed limits: `SUP-015`, `SUP-017`, `SUP-018`, `SUP-019` and `SUP-020`
are complete locally. `SUP-021` (supplier contact persons) is PARTIAL: API,
isolation and desktop UI exist, but no live owner-data write was performed.
`SUP-022` is PARTIAL: CSV-first preview/mapping UI and authenticated API parse
UTF-8 CSV in memory, flag invalid INN and workspace duplicate candidates.
Confirmed Apply creates only new cards with valid INN, skips duplicates strictly
by INN and never updates or merges existing cards; audit records keep import
source, line and author. The preview/confirmation round-trip was checked using
an artificial CSV (one create candidate, one INN duplicate and one missing-INN
row) at 1280/768/390 px; final Apply was intentionally not invoked, so no
owner-data card was created. XLSX remains unverified.
`SUP-023` is PARTIAL: migration 046 stores workspace-only category/product/
brand/specialization facts with a durable source and confidence; the card
supports manual labels without claiming registry/AI provenance. Focused source,
ownership and validation tests pass; registry/AI producers and a live owner-data
write are intentionally not implemented. This was followed by `SUP-024`
public-vs-workspace supplier-data isolation.
`SUP-024` is PARTIAL: a two-workspace regression now proves cards cannot be
read or used as a mutation target across the workspace boundary, including
matching-ИНН suppliers. A separate live second-user browser session was not
opened. This was followed by `SUP-025` Support Assistant, limited to
truthful product help and an explicit human-escalation path.
`SUP-025` is PARTIAL: the support mini-chat is the sole primary support path;
`/help` is now secondary «Справка», removed from the sidebar and reachable from
that window. It contains verified local product guidance and a truthful
unknown-question path that only copies a user-authored request for manual
escalation. It makes no support ticket, network call or AI claim. This was
followed by `SUP-026`, an evidence-based decision on whether advanced shared-note
versioning is justified for the MVP.
`SUP-026` is DONE as an evidence-based non-expansion: the MVP retains one
current private and one current workspace note per context. A correctness fix
records the last workspace-note editor; no revision history is justified until
separate conflict/recovery/audit acceptance criteria exist. This was followed
by `SUP-027`, an evidence audit for explainable supplier scoring.
`SUP-027` is DONE as an evidence-based non-expansion: raw registry risks,
finance, response metrics and per-deal ratings remain separate. There is no
approved weighting, freshness rule, rater/reason, missing-data rule or owner
for a composite score. The only remaining backlog item, `SUP-028`, is
explicitly DEFERRED real telephony and is outside this task's authorized scope.
The historical mail/Checko record below is retained as evidence only; it is not
an active-task conflict.

---

Historical record from the preceding mail/Checko task (not active scope):

Mail acceptance substage: `PASS` on `2026-09-11`. The canonical SQLite
identity and `.env` now point to
`C:\Users\edwat\SupplyDesk\mail-data\supplier.sqlite3` in production mode.
Both connected accounts passed SMTP+IMAP authentication; Yandex accepted the
test to `edwatikh@gmail.com` with SMTP `250 2.0.0`, Mail.ru accepted the test
to `edwatik@gmail.com` with SMTP `250`, and both Message-IDs were found in
Sent. The send window used no queue worker and created no request/supplier/
campaign/job record. Outgoing was disabled afterward. One canonical owner
runtime remains ready on port 8000 (PID 24660), owns the live-mail lock, and
has durable/effective outgoing disabled. The owner independently confirmed
receipt in both target Gmail mailboxes.

Thread-rendering substage: `PASS` on `2026-09-11` at the available desktop
viewport. The first outbound message is collapsed as «Исходный запрос» while
the supplier's new answer remains visible. Live canonical data exposed a
previously unsupported localized Gmail quote header (`date/time, <email>:`
without `написал`); the matcher was widened narrowly, 10 focused unit tests
pass, and the real reply now shows «Показать процитированную переписку».
Expanding it restored the full original commercial text. No stored message was
modified. Tablet/mobile screenshots remain `NOT VERIFIED` because the local
Windows policy blocked the viewport-capable browser executable.

Previous task (`TASK-MESSAGES-LINKS-STATUS-SEND-AI-20260910`) is complete and committed at `b2c620b2b1c336aab60d45347a032d82bd75275d` on this same branch -- the "not yet committed" note in that task's own record was written before the commit landed; superseded by this entry.

---
Scope: `Messages screen: clickable HTML email links (port frontend-v2 EmailRenderer), per-request-supplier conversation status (В работе/Отложено/Отклонено), fix real mail send (error handling + reply threading headers) and real attachments in the composer, restructure /api/ai/chat to a server-validated structured context (request_id + thread_ids, no more raw client string), add server-side AI chat persistence (ai_conversations/ai_messages) with a New chat/history UI, and prove all of it with real backend + browser evidence including 3 owner-specified AI stress tests. Full plan: C:\Users\edwat\.claude\plans\playful-wondering-music.md`
Allowed files: `frontend-v2/src/pages/Messages.tsx, frontend-v2/src/components/EmailRenderer.tsx, frontend-v2/src/components/AiChatPanel.tsx, frontend-v2/src/lib/api.ts, frontend-v2/src/lib/types.ts, mail/thread_metadata.py, mail/repository.py, mail/service.py, mail/ai_conversations.py, backend/http_requests.py, supplier_app.py, backend/domain/ai_agent/chat_service.py, migrations/039_thread_conversation_status.sql, migrations/040_ai_conversations.sql, tests/test_thread_conversation_status.py, tests/test_ai_context_scoping.py, docs/ui/MESSAGES_SCREEN_SPEC.md, ai/CURRENT_STATE.md, ai/ACTIVE_TASK.md, ai/DECISIONS.md, ai/DEFERRED_FINDINGS.md`
Status: `PARTIAL — implementation and live verification complete for §1-11; see ai/CURRENT_STATE.md 2026-09-11 entry and ai/DEFERRED_FINDINGS.md FINDING-026..028 for exactly what is NOT_VERIFIED/PARTIAL/FAIL. Not yet committed.`
Last update: `2026-09-11`

**Pending, not done — do not start a new unrelated task assuming this one is closed:**

1. Not committed/pushed/deployed yet — implementation and live verification
   are complete on the local worktree only.
2. `FINDING-026` is resolved for provider transport: the explicitly authorized
   production-mode canonical runtime test on 2026-09-11 received post-DATA
   SMTP 250 from both Yandex and Mail.ru and found both Message-IDs in Sent.
   The bounded test intentionally bypassed supplier/request/campaign queue
   records, so it does not add a new claim about those already-tested UI paths.
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
