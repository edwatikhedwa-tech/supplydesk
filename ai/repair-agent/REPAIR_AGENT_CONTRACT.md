---
document_id: REPAIR-AGENT-CONTRACT-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Repair Agent Contract

This is a specification only. V1 includes no repair-agent implementation,
autonomy, scheduler or production access.

## Required flow

`Detect → Diagnose → Confirm scope → Create sandbox branch → Reproduce →
Patch → focused tests → regression → doctor → evidence → await approval`.

## Non-negotiable boundaries

The agent must never directly access production, send real mail, delete a
customer, apply a migration, rotate credentials, force-push, merge, disable a
test, or change an expected output merely to make a gate green. A repair must
be limited to an explicitly confirmed allowlist, preserve a rollback path, and
produce evidence before any human approval request.

## Approval contract

`L0_OBSERVE` and `L2_DIAGNOSE` are read-only. `L1_SAFE_RECOVERY` is allowed
only when reversible and local. `L3_SANDBOX_REPAIR` requires a separate
branch/worktree. `L4_HUMAN_APPROVAL_REQUIRED` and `L5_FORBIDDEN_AUTOMATIC`
cannot be executed by an autonomous agent.
