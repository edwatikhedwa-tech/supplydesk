---
document_id: TEST-STRATEGY-001
status: CURRENT
canonical: false
owner: quality
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Test Strategy

## Gates

1. Documentation: `validate_docs.py`, `validate_state.py`, and the
   traceability validator.
2. Diagnostic unit tests: standard-library tests for status classification,
   HTTP expectations, read-only SQLite and machine output.
3. Backend regression: historical control baseline `373 passed, 1 skipped`;
   the reproducible official runner now executes the current combined suite
   and records its actual totals. Existing tests are classified in
   `TEST_CATALOG.yaml`; they are not rewritten.
4. Frontend: `npm ci`, typecheck, lint, build and public-shell browser test;
   clean dependency setup is required before claiming current parity.
5. Doctor: `-Plan` and profile-aware `-DryRun`; `-Apply` remains blocked.

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
Offline eligibility is not the same as behavioral proof: live provider
acceptance and repair actions remain outside the canonical offline gate.

## Gate 4 clarification (2026-09-17 audit)

Gate 4 above ("Frontend: npm ci, typecheck, lint, build and public-shell browser test") was
written before `frontend-v2` existed and, as implemented in `.github/workflows/ci.yml` today,
runs **two different depths** under one name:
- `frontend` job (v1, `frontend/` — not deployed): npm ci → typecheck → lint → build →
  `browser_smoke`/`browser_full` (real Playwright against a live test backend).
- `frontend_v2` job (v2, `frontend-v2/` — **the actually deployed UI**): npm ci → lint → build
  only. **No runtime/browser check runs against the live frontend at all.**

This means the deployed application currently has weaker CI coverage than the retired one. See
[`../frontend/UI_INVENTORY.md`](../frontend/UI_INVENTORY.md) for what that lets slip through
(no browser proof that links are clickable, that a reminder toast actually appears, etc. — see
the `NOT VERIFIED` rows in `TEST_CASES.md`'s product test-case table).

## Minimal QA infrastructure proposal — what to ADD, not what to install from scratch

Full existing-tooling inventory: see `docs/system/KNOWN_GAPS.md` (`GAP-010`). Summary of what
already exists and must **not** be reinstalled:

| Tool | Already present, where |
|---|---|
| TypeScript, Vite, oxlint, Vitest + Testing Library | `frontend-v2` |
| ESLint, Playwright, `@axe-core/playwright`, Applitools Eyes, Storybook (+a11y addon), Lighthouse CI, `knip` | `frontend/` (v1) only — real, working configs, just pointed at the wrong (retired) app |
| unittest backend suite (~90 files), `tests/run-tests.ps1` | repo root |
| CI (`.github/workflows/ci.yml`) | exists, already gates backend + v1 frontend |

**Proposal (not started, per explicit instruction for this audit pass):** the fastest path to
real coverage for the live app is **re-pointing** the already-working v1 Playwright/axe config at
`frontend-v2` (same `@playwright/test`/`@axe-core/playwright` versions, new base URL and a handful
of updated selectors) rather than standing up a second, parallel toolchain from zero. Storybook
and Applitools are lower priority — they require the most setup work per unit of risk reduced,
given the primitives inventory in `docs/frontend/UI_INVENTORY.md` shows the underlying visual
inconsistency is concentrated in 5 known component categories, not general layout drift.
Recommended order: (1) Playwright smoke test hitting the same routes CI's old `browser_smoke`
covered, (2) axe-core pass on the same routes, (3) visual regression only after the Input/
Checkbox/Card/Table/Tabs primitives are unified (testing against a known-inconsistent baseline
would just snapshot the inconsistency).
