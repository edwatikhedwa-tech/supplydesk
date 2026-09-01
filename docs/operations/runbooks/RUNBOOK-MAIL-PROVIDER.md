---
document_id: RUNBOOK-MAIL-PROVIDER-001
status: CURRENT
canonical: false
owner: operations
updated_at: 2026-09-01
source_commit: 6687fa4289d8f65c47a34e8b7124e113cb3201e6
---

# Runbook: mail provider boundary

## Diagnostic interpretation

The diagnostic runner never opens SMTP/IMAP or provider adapters. It can
classify a server as unavailable from safe HTTP probes, but that is not proof
of provider health. Provider credentials, quotas, mailbox contents and real
delivery remain `NOT VERIFIED` unless separately authorized and evidenced.

## Human gate

Real provider authentication, send, retry, credential rotation and mailbox
mutation are `L4_HUMAN_APPROVAL_REQUIRED` or `L5_FORBIDDEN_AUTOMATIC`.
Preflight and preview must remain read-only and must not be used as a hidden
transport attempt.
