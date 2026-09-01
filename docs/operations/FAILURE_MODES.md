---
document_id: FAILURE-MODES-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Failure Modes

The machine-readable catalog is [`failure_modes.yaml`](failure_modes.yaml).
Each mode names a symptom, a diagnostic check, a runbook and whether automatic
recovery is allowed. V1 allows no automatic recovery for product, data, mail,
credential or deployment failures.

## Safety levels

- `L0_OBSERVE`: inspect state without changing it.
- `L1_SAFE_RECOVERY`: reversible local recovery with no external side effect.
- `L2_DIAGNOSE`: reproduce and collect evidence in the approved environment.
- `L3_SANDBOX_REPAIR`: patch only a disposable branch/worktree after scope confirmation.
- `L4_HUMAN_APPROVAL_REQUIRED`: a human must approve the exact irreversible scope.
- `L5_FORBIDDEN_AUTOMATIC`: never perform automatically.

Database migrations, production deletion, auth changes, credential rotation,
mass email, real provider sends, permission changes, force-push and deployment
are `L5_FORBIDDEN_AUTOMATIC`. Canonical DB writes and customer deletion are
also human-gated and never part of doctor.

## Outcome interpretation

An absent local database or dependency is an `ENVIRONMENT_GAP`. A broken
manifest, failing test, invalid route contract or malformed schema is a
`PRODUCT_FAILURE`. A requested provider/migration/production mutation is a
`SAFETY_BLOCK`; it is not retried or downgraded to a warning.
