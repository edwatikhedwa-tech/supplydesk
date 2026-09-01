---
document_id: TEST-CASES-001
status: CURRENT
canonical: false
owner: quality
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
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
