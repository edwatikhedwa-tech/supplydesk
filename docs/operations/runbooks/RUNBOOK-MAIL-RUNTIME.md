---
document_id: RUNBOOK-MAIL-RUNTIME-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: mail runtime

## Observe

Use `scripts/doctor.ps1 -DryRun` and inspect only typed evidence. The default
`DOC-011` check is `mail_runtime_contract_static`: it checks source markers and
does not prove live runtime health, mailbox synchronization, provider
connectivity or delivery. Runtime lock/provenance behavior is covered by
`tests/test_canonical_runtime.py`. Queue, pacing, deduplication, suppression
and delivery uncertainty are covered by the mail test catalog.

## Safety levels

Runtime inspection is `L0_OBSERVE`/`L2_DIAGNOSE`; live runtime health remains
`NOT_VERIFIED` unless an explicitly recorded runtime or external acceptance
run supplies evidence. Do not instantiate a repository against canonical
data, claim a job, sync a mailbox, enable outgoing, or contact a provider as
part of diagnosis.

## Recovery

An uncertain provider acceptance stays unresolved until evidence is reconciled;
it is not automatically retried. Any continuation is a separate human-
approved operation with an exact recipient and job scope.
