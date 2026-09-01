---
document_id: TEST-STRATEGY-001
status: CURRENT
canonical: false
owner: quality
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Test Strategy

## Gates

1. Documentation: `validate_docs.py`, `validate_state.py`, and the
   traceability validator.
2. Diagnostic unit tests: standard-library tests for status classification,
   HTTP expectations, read-only SQLite and machine output.
3. Backend regression: inherited control baseline `373 passed, 1 skipped,
   0 failed, 0 errors`; rerun when the environment is available. Existing
   tests are classified in `TEST_CATALOG.yaml`; they are not rewritten.
4. Frontend: `npm ci`, typecheck, lint, build and public-shell browser test;
   unchanged frontend evidence is inherited and current parity is
   `NOT VERIFIED` in this worktree.
5. Doctor: `-Plan` and `-DryRun`; `-Apply` is not executed in V1.

## Diagnostic outcome vocabulary

- `PASS`: check completed and expected state was observed.
- `PRODUCT_FAILURE`: product or contract behavior is wrong.
- `ENVIRONMENT_GAP`: required local resource/tool is absent.
- `SAFETY_BLOCK`: the requested probe would cross a forbidden boundary.
- `NOT_VERIFIED`: evidence could not be obtained safely.
- `WARNING`: non-blocking quality or inventory finding.

Missing database or `.env` is an `ENVIRONMENT_GAP`, not a generic product
failure. HTTP `401` and `404` are expected outcomes for protected and unknown
probes respectively.

## Coverage metrics

Diagnostic coverage is separate from code coverage and from test verification:

- `TEST_VERIFICATION_LEVEL`: the strongest existing fixture/fake/runtime test
  evidence for the requirement.
- `DIAGNOSTIC_LEVEL`: what the doctor can prove without pretending that a
  static or structural check is behavioral.
- `LIVE_ACCEPTANCE_LEVEL`: whether real external evidence is required; V1.1
  records `NOT_REQUIRED` or `NOT_VERIFIED` explicitly.

Levels are `NONE`, `STATIC`, `STRUCTURAL`, `BEHAVIORAL`, `RUNTIME` and
`LIVE_EXTERNAL`. A static check proves code/config/contract presence only; it
does not prove a mail send, sync, deduplication, pacing, suppression or
delivery outcome.

The traceability validator reports requirement/test/rule/diagnostic counts and
rejects inconsistent doctor/failure-mode mappings without modifying the tree.
