---
document_id: TASK-BROWSER-FULL-STABILITY-MAGICRINGS-20260902
status: CURRENT
canonical: false
owner: Codex
updated_at: 2026-09-02
based_on_commit: e7e1873160f26faaa9a6385c1b8b14c6c96a540c
---

# Browser Full Stability — MagicRings Reduced Motion

## Status

`LOCAL_PASS_REMOTE_PENDING`

`DELIVERY_MODE: PUBLISH`

## Goal and scope

Remove the public-shell readiness dependency on `networkidle`, make the
`MagicRings` WebGL animation respect `prefers-reduced-motion`, run the
public-shell acceptance in reduced-motion mode, and verify normal animation and
WebGL fallback behavior.

Auth handoff, OAuth, backend/API, database, mail data, secrets, Knip, worker
count, unrelated frontend tests and login visual design are out of scope.

`DOC_IMPACT=YES`: the current browser test contract and product motion behavior
changed and are recorded here and in the canonical current-state documents.

## Implementation

- `frontend/src/components/MagicRings.tsx`: extracted the uniform update/render
  path, stopped continuous RAF scheduling in reduced mode, rendered a stable
  WebGL frame, resumed normal animation after a media-query change, and removed
  the media-query listener during cleanup.
- `frontend/tests/frontend-audit.spec.ts`: scoped Playwright
  `reducedMotion: 'reduce'` to the public-shell test, replaced
  `waitUntil: 'networkidle'` with `waitUntil: 'domcontentloaded'`, and waited for
  the visible `Вход в рабочее пространство` heading.
- `frontend/playwright.config.ts`: unchanged; `workers: 4` remains active.

## Local evidence

- Workspace Guard: `PASS`.
- `npm run typecheck`: `PASS`.
- `npm run lint`: `PASS` with five pre-existing warnings and zero errors.
- `npm run build`: `PASS`.
- Public shell single viewport: `1/1 PASS` with one worker.
- Public shell all configured viewports: `8/8 PASS` with four workers.
- Reduced-motion focused browser check: canvas present, `rafDelta=0`.
- Normal-motion focused browser check: canvas present, RAF continued scheduling.
- Runtime media-query switch: reduced `0`, normal `8`, reduced again `+1`
  queued final frame.
- WebGL unsupported fallback: fallback present, no canvas, no RAF.
- HTTP smoke: `/login` `200`, `/api/auth/me` `200`, unknown API `404`.
- Runtime logs contained no error/unhandled/exception/failed entries; runtime
  was stopped and port `18000` was free.
- Screenshots were captured for `1920x1080`, `1640x900`, `1440x900`, `1280x800`,
  `1024x768`, `768x1024`, `390x844` and `360x800`, then reviewed as candidate
  evidence. `NO APPROVED BASELINE` — no baseline was updated.

## Findings and rationale

The prior heterogeneous Browser Full timeouts were consistent with continuous
Three.js rendering competing with screenshot/Axe work on the hosted runner.
The prior traces did not prove a permanently pending HTTP request. The
remediation is therefore a high-confidence hypothesis test, not mathematical
proof of causality.

The UI locator is the actual public-shell heading rather than an arbitrary
delay. Reduced motion is a legitimate accessibility behavior, so no test-only
product flag or hidden environment switch was introduced.

## Remote gates

- Commit: `PENDING`.
- Push: `PENDING`.
- Remote SHA match: `PENDING`.
- FAST CI: `PENDING`.
- Browser Full: `PENDING`.
- `MAGICRINGS_STARVATION_CAUSALITY`: `NOT_VERIFIED` until remote Browser Full.

## Rollback

Revert the task commit on this branch. No database, mail, environment,
quarantine or legacy-workspace rollback is required.

## Not verified

Hosted-runner post-fix Browser Full, remote SHA and FAST CI are pending. Exact
CPU/GPU profiling is intentionally not collected. Real provider/OAuth flows,
real mail, canonical database and interactive auth handoff were not exercised.
