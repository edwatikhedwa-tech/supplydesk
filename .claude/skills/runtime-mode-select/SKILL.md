---
name: runtime-mode-select
description: Classifies RUNTIME_MODE (LOCAL_CANONICAL / SAFE_TEST / CI / OTHER) and picks the correct start command and port before starting the SupplyDesk backend. Use before running supplier_app.py, scripts/start_local_canonical.ps1, or any test-runtime script, and before choosing port 8000 vs 18000.
---

# Runtime mode selection

SupplyDesk has two backend runtime modes that must never be substituted for
each other (see CLAUDE.md and `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`):

| Mode | Port | Credentials | Use for |
|---|---|---|---|
| `LOCAL_CANONICAL` | 8000 | real provider credentials | the owner's normal work session |
| `SAFE_TEST` | 18000 | none, by design | automated/CI-style test runs only |

**Never use `SAFE_TEST` for the owner's normal work session, even if it was
already running earlier in the session.** Proven-working is not the same as
correct-for-this-purpose.

## Steps

1. Classify the purpose of this run against `PROJECT_MANIFEST.yaml`'s
   `runtime_modes` block.
2. Read `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md` for the
   current canonical start procedure — do not assume it is unchanged from
   memory.
3. Run the workspace guard if it has not already run this session:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
   ```
4. Start via the dedicated launcher for the classified mode, `-Plan` first
   to confirm readiness without side effects, then `-Apply`:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_canonical.ps1 -Plan
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_canonical.ps1 -Apply
   ```
   (`scripts/start_local_canonical.ps1` refuses to start a second process if
   port 8000 is already occupied — treat that as evidence a canonical
   instance is already running, not as an error to route around.)
5. For `SAFE_TEST`, use the corresponding `scripts/start_test_runtime.ps1` /
   `scripts/stop_test_runtime.ps1` pair instead — never point owner-facing
   work at port 18000.

## Verification

`scripts/runtime_guard.py` is the single runtime-selection authority: all
required purposes map deterministically to one of the two modes, and a
mismatch prints a `FAIL` with the reason rather than starting silently in the
wrong mode. Trust its verdict over any prior assumption about which mode is
"the one we've been using."
