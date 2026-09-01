---
document_id: RUNBOOK-TEST-FAILURE-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: test or diagnostic failure

1. Record the exact command, branch, HEAD, status, exit code and diagnostic
   output path. Never copy secret values into the record.
2. Classify the result as `PRODUCT_FAILURE`, `ENVIRONMENT_GAP`,
   `SAFETY_BLOCK`, `NOT_VERIFIED` or `WARNING`.
3. Reproduce only in the approved isolated worktree. Use a disposable/local
   database for write-oriented tests; the canonical database stays read-only.
4. Preserve the existing expectation. Do not disable tests or change expected
   output just to make the gate green.
5. For a code repair, follow the repair contract's
   `Detect → Diagnose → Confirm scope → Create sandbox branch → Reproduce →
   Patch → focused tests → regression → doctor → evidence → await approval`
   flow. If the same failure cannot be safely reproduced, record
   `NOT VERIFIED` and stop.
