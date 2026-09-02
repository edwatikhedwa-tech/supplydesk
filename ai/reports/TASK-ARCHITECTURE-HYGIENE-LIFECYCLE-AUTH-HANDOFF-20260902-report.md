# TASK-ARCHITECTURE-HYGIENE-LIFECYCLE-AUTH-HANDOFF-20260902

## Result

`PASS_WITH_LIMITATIONS` — policy-only architecture/lifecycle and browser-auth
handoff controls were added. Product behavior, current browser tests, CI
routing, Knip configuration, Python code and repository root structure were
not changed.

Branch: `audit/frontend-knip-20260902`

Source checkout before this task: `84083130e3a75eb5a6d4fa83957db6760724379b`.

## Goal and scope

The goal was to prevent new root sprawl, permanent versioned copies, stale
component ambiguity, undocumented lifecycle states and unsafe assumptions that
an agent may use an owner's browser session. The change is deliberately
limited to the shared agent contract, frontend browser runbook, architecture
registry and required control-plane traceability.

## Changes

- Added the architecture placement, root growth, versioned-garbage, component
  lifecycle, deprecation, disabled-feature, temporary-file, architecture
  change-check and repository-layout rules to `ai/AI_CONTRACT.md`.
- Added the canonical component registry/template at
  `docs/architecture/COMPONENT_LIFECYCLE.md`.
- Recorded the existing deferred manual real-email Playwright configuration;
  no deletion or restoration was authorized.
- Added local-only human-in-the-loop headed Chromium authentication handoff,
  non-interactive CI requirements and the public `/login` timeout diagnosis to
  `docs/operations/runbooks/RUNBOOK-FRONTEND.md`.
- Linked the lifecycle registry and conditional repository-layout document from
  `docs/architecture/README.md`.
- Updated the current state and durable decision register for this control
  change; no VibeCoding V1.3 rewrite was made.

## Contradiction audit

- The shared `ai/AI_CONTRACT.md` is already the common contract referenced by
  Codex, Claude and project adapters; no parallel contract was introduced.
- Existing `supplier_discovery_v2/` is a confirmed canonical product area in
  the component map. The new rule rejects new migration copies but does not
  rename an existing component solely because of a historical suffix.
- The frontend public-shell scenario opens `/login` without authentication.
  A `networkidle` timeout is therefore a request/background-network or browser
  diagnostic question first, not a request for owner login.

## Architecture change check

- `DUPLICATE_IMPLEMENTATION: NO` — no product implementation was added.
- `NEW_ROOT_SOURCE_FILES: NONE` — no root source file was created.
- `TEMP_FILES_LEFT: NONE` — no temporary project file was created.
- `DEPRECATED_COMPONENTS_RECORDED: NOT_NEEDED` — no component was retained as
  `DEPRECATED`; the one non-active record is explicitly `DEFERRED`.
- `SUPERSEDED_COMPONENTS_REMOVED: NOT_NEEDED` — this task introduced no
  replacement implementation.
- `REPOSITORY_LAYOUT: NOT_NEEDED` — no root refactor or new major directory
  was planned.

## Verification

- Workspace Guard: `PASS` — canonical workspace confirmed before mutation.
- `python ai/tools/validate_docs.py`: `PASS`, `GATE-001..009`.
- `python ai/tools/validate_state.py`: `PASS`.
- `python ai/tools/validate_vibecoding.py`: `PASS`, 36 registry tools parsed.
- `python -m unittest tests/diagnostics/test_vibecoding_governance.py`:
  `16/16 PASS`.
- `git diff --check`: `PASS`.
- Changed-file allowlist and product-scope check: `PRODUCT_CODE_CHANGED=NO`.
- Exact current test/config evidence: `frontend/tests/frontend-audit.spec.ts`
  was unchanged; `frontend/tests/real-email-diagnostic.spec.ts` is absent;
  `frontend/playwright.real-email.config.ts` is retained and not executed.

## Not run / limitations

- Backend, frontend build, Playwright, screenshots and runtime smoke were
  `NOT_NEEDED` for this policy-only task; no user-visible product behavior
  changed.
- The local interactive auth handoff was not exercised; no personal browser,
  credentials, cookies or authentication state were accessed.
- FULL CI is `NOT_NEEDED` by the requested delivery scope. The declared
  `DELIVERY_MODE: PUBLISH` still requires the ordinary push, remote SHA and
  FAST CI proof at closeout.

## Security and rollback

No secret values, cookies, tokens, environment contents, runtime data, mail
data, database files or personal browser state were read, saved or staged.
Rollback is a normal Git revert of this task commit; no destructive cleanup or
history rewrite is required.

## Delivery

Commit, remote SHA and FAST CI are recorded after publication. After FAST PASS,
the task stops without opening a follow-up pass.
