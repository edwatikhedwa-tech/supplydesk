---
document_id: TEST-CASES-001
status: CURRENT
canonical: false
owner: quality
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Diagnostic Test Cases

| ID | Setup | Expected |
|---|---|---|
| TC-DIAG-001 | Probe an expected `200` endpoint | `PASS`, not generic non-200 logic |
| TC-DIAG-002 | Probe protected endpoint without credentials | `PASS` on `401` |
| TC-DIAG-003 | Probe unknown endpoint | `PASS` on `404` |
| TC-DIAG-004 | Inspect disposable SQLite file through read-only URI | Integrity/schema metadata is read; checker performs no write |
| TC-DIAG-005 | Omit database or `.env` | `ENVIRONMENT_GAP` |
| TC-DIAG-006 | Run doctor `-Plan` | Plan is printed; repository and runtime are unchanged |
| TC-DIAG-007 | Run doctor `-DryRun` | JSON evidence is emitted outside the repository; exit code reflects status |
| TC-DIAG-008 | Add a forbidden secret-like path name | Name is reported; secret values are never printed |
| TC-DIAG-009 | Run traceability validator with unknown link | Validation fails without editing files |
| TC-DIAG-010 | Attempt provider or migration probe | `SAFETY_BLOCK` or no probe is attempted |
| TC-DIAG-011 | Inspect a corrupt disposable SQLite file | `PRODUCT_FAILURE/FM-DATA-001`; no write occurs |
| TC-DIAG-012 | Simulate unavailable backend or missing database | `ENVIRONMENT_GAP`; no recovery is attempted |
| TC-DIAG-013 | Simulate invalid frontend manifest | `PRODUCT_FAILURE/INSTALL_FAIL` |
| TC-DIAG-014 | Compare local untracked and staged `.env` paths | local is allowed; staged is `SAFETY_BLOCK` |
| TC-DIAG-015 | Scan a staged secret-like literal | location/type are reported with value `REDACTED` only |
| TC-DIAG-016 | Run `doctor -Apply` | `SAFETY_BLOCK`; no recovery action is implemented |

Existing product tests remain authoritative for detailed behavior and are
listed in `TEST_CATALOG.yaml`; this file does not replace them.

---

## Product test cases (added 2026-09-17 full audit)

The table above (`TC-DIAG-*`) covers the "Doctor" diagnostic tool only. The groups below cover
actual product behavior, per area, following the audit's requested `TC-AUTH/REQ/MSG/SUP/MAIL/AI/
UI/DATA` grouping. `Automation candidate` names the layer that should eventually verify it;
`Status` is honest about what's actually been run.

| ID | Requirement | Preconditions | Steps | Expected | Current | Automation candidate | Status |
|---|---|---|---|---|---|---|---|
| TC-AUTH-001 | REQ-AUTH-001 | Seeded user exists | POST /api/auth/login with correct credentials | 200, session cookie set | Matches | unittest (exists) | PASS |
| TC-AUTH-002 | REQ-AUTH-002 | Logged in | POST a mutating route without X-CSRF-Token | 403 | Matches | unittest (exists) | PASS |
| TC-REQ-001 | REQ-REQUEST-001 | None | Create request, start search, reload mid-search | Search resumes from cursor, does not restart or duplicate work | Matches | unittest (exists) | PASS |
| TC-REQ-002 | REQ-REQUEST-002 | Bulk send in progress | Try to pause/stop it from the live UI | A control to pause/stop exists | **No such control exists in frontend-v2** | Playwright | NOT VERIFIED (feature absent — GAP-001) |
| TC-SUP-001 | REQ-SUPPLIER-001 | Two requests find the same real company by different sender addresses | Check `suppliers` table | One row for that company in this workspace | **Two rows created** | unittest (new) | FAIL (GAP-003) |
| TC-SUP-002 | REQ-SUPPLIER-002 | Company already resolved by workspace A | Workspace B's search finds the same ИНН | Zero new Checko calls from workspace B | Matches for `_resolve_missing_inn` path only | unittest (exists) | PASS (partial scope) |
| TC-MSG-001 | REQ-MESSAGE-001 | Supplier has replied before, In-Reply-To header matches | New reply arrives | Threaded onto the existing thread | Matches | unittest (exists) | PASS |
| TC-MSG-002 | REQ-MESSAGE-002 | Reply from an unrecognized address | Reply arrives | Message appears in "Письма без заявки", not lost | Matches | unittest (exists) | PASS |
| TC-MSG-003 | REQ-MESSAGE-004 | A received HTML email with a link | Open the thread in the browser | Link is clickable, opens in a new tab | Sanitizer forces target=_blank; not proven in a real browser | Playwright (new) | NOT VERIFIED |
| TC-MSG-004 | REQ-MESSAGE-006 | A received message has an attachment | Open the thread | Attachment is visible and downloadable | **Not rendered anywhere in the UI** | Playwright (new) | FAIL (GAP-004) |
| TC-MAIL-001 | BR-MAIL-002 | Two suppliers resolve to the same final email after contact-priority resolution | Attempt bulk send | Blocked as duplicate | Matches (fixed 2026-09-16) | unittest (exists) | PASS |
| TC-AI-001 | REQ-AI-001 | Request has a supplier matched but never emailed | Open AI assistant, ask about the request | That supplier's (nonexistent) messages are not in context | Matches — no thread exists for it at all | unittest (exists) | PASS |
| TC-AI-002 | REQ-AI-002 | Workspace has hit its daily AI spend cap | Ask the assistant another question | Refused with a clear limit message, no LLM call made | Matches | unittest (exists) | PASS |
| TC-UI-001 | REQ-UI-001 | None | Compare `<input>` markup across 3 different pages | Same shared component, same classes | Each page has its own copy with drift | Vitest/visual snapshot (new) | FAIL (GAP-005) |
| TC-UI-002 | — | None | Load Login.tsx | Same design tokens as rest of app | Uses literal colors, different palette | Visual regression (new) | FAIL (GAP-008) |
| TC-DATA-001 | REQ-DATA-001 | Postgres backend, a query using `COLLATE NOCASE` or a Python bool bound to an int column | Execute the query | No error | Fixed this session for the two known cases; pattern not exhaustively re-swept | unittest (exists for the two fixed cases) | PASS (narrow scope) |
| TC-TASK-001 | REQ-TASK-002 | Task due, tab open | Wait for the 45s poll | Toast + Notification API fire | Matches by source reading | Playwright (new) | NOT VERIFIED |
| TC-TASK-002 | REQ-TASK-003 | Task due, reminder channel = email | Wait for due time | An email is sent | **No email is ever sent** | Playwright/manual (new) | FAIL (by design — MOCK) |
