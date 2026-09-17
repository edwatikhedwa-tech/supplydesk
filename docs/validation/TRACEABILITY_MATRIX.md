---
document_id: DOC-VALIDATION-TRACEABILITY-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Traceability Matrix

Requirement → Implementation → Test → Evidence → Result. A row with no test/evidence is marked
`NOT VERIFIED`, never `PASS` — per explicit instruction. This is the audit-produced counterpart
to the pre-existing, coarser `docs/requirements/TRACEABILITY_MATRIX.csv` (capability-level; this
one is requirement-level, matching `docs/spec/requirements.yaml`).

| Requirement | Implementation | Test | Evidence | Result |
|---|---|---|---|---|
| REQ-AUTH-001 | `backend/http_auth.py::_login` | `tests/test_mail_integrity.py` | Unit test passes | PASS |
| REQ-AUTH-002 | `backend/http_auth.py::_require_csrf` | unittest (route-level) | Unit test passes | PASS |
| REQ-REQUEST-001 | `orchestrator.py::process_search_step` + `request_search_jobs` | `tests/test_request_search_cursor_survives_step_release` | Unit test passes | PASS |
| REQ-REQUEST-002 | *(none — v1 only)* | none | `frontend/src/pages/CampaignPage.tsx` has no v2 counterpart | NOT VERIFIED (feature absent) |
| REQ-SUPPLIER-001 | `mail/repository.py::upsert_supplier`/`resolve_supplier_for_send` | none written for this specific failure mode | Live DB query, 2026-09-17: 28/243 rows | **FAIL** — invariant violated, evidence is a live count not a passing test |
| REQ-SUPPLIER-002 | `orchestrator.py::_resolve_missing_inn` | `tests/test_canonical_companies_cache_reuse.py` | Unit test passes (narrow scope) | PASS (partial) |
| REQ-SUPPLIER-003 | *(not on this branch)* | none | Code reviewed on `state/current-20260917-2119` only | NOT VERIFIED |
| REQ-MESSAGE-001 | `mail/repository.py::_find_incoming_thread` | `tests/test_mail_integration.py` | Unit test passes | PASS |
| REQ-MESSAGE-002 | `mail_inbox_messages` path | `tests/test_messages_visibility.py` | Unit test passes | PASS |
| REQ-MESSAGE-003 | (absence of a DELETE route) | source audit | Full-repo grep, one non-routed script found | PASS (by absence) |
| REQ-MESSAGE-004 | `mail/content.py::sanitize_email_html` | none (browser-level) | Sanitizer unit-tested; rendered clickability not proven | NOT VERIFIED |
| REQ-MESSAGE-005 | `mail/providers/yandex.py` CID resolution | none (browser-level) | Parse-time logic read directly; not proven in a rendered browser | NOT VERIFIED |
| REQ-MESSAGE-006 | *(backend only, no frontend consumer)* | none | `MailAttachment[]` type exists, unused for non-draft messages | **FAIL** — capability exists, not reachable by a user |
| REQ-AI-001 | `chat_service._build_context` + `get_thread_owned` | `tests/test_ai_context_scoping.py` | Unit test passes | PASS |
| REQ-AI-002 | `chat_service.send_message` daily-cap check | unittest (referenced, not re-run this pass) | Code path confirmed | PASS (evidence not re-executed this session) |
| REQ-TASK-001 | `mail/tasks.py` | unittest (route-level) | Unit test passes | PASS |
| REQ-TASK-002 | `RemindersContext.tsx` poll + `ReminderToastManager.tsx` | none (browser-level) | Source confirms 45s poll + `Notification()` call | NOT VERIFIED |
| REQ-TASK-003 | *(no send path exists)* | none | `migrations/043_task_reminders.sql` comment explicitly states delivery is out of scope | **FAIL by design** — matches documented MVP scope, not a silent defect |
| REQ-TASK-004 | `mail/task_reminder_mock.py` | none | Module docstring + UI copy both explicitly say "mock" | FAIL by design (labeled) |
| REQ-TASK-005 | *(not implemented)* | none | No Service Worker/Push API/scheduler found anywhere | NOT VERIFIED (feature absent) |
| REQ-UI-001 | *(no shared components)* | none | Manual code audit, `docs/frontend/UI_INVENTORY.md` | **FAIL** — confirmed via direct code reading, not a test |
| REQ-DATA-001 | `mail/db_compat.py::_adapt_postgres_sql` | `tests/test_migration_replay_stability.py`, `tests/test_db_compat_postgres_sql_adapter.py` | Two real production incidents this session, both now fixed and tested | PASS (narrow — only the two known cases are covered, not exhaustively swept) |

## Reading this table

- **PASS** means a real test or direct, reproducible evidence supports the claim.
- **FAIL** means the requirement is confirmed not met, with evidence.
- **NOT VERIFIED** means neither — the code path was read and understood, but no test/live
  evidence exists either way. This is the majority of "browser-behavior" rows, honestly, because
  `frontend-v2` currently has no e2e coverage (`GAP-010`).
