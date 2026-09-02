---
document_id: DOCS-ARCHITECTURE-README-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-02
source_commit: 84083130e3a75eb5a6d4fa83957db6760724379b
---

# Architecture documentation

## Purpose

Architecture decisions, system boundaries, integrations, and deployment
topology supported by repository or runtime evidence.

## Canonical ownership

This directory owns product architecture documentation. Operational state and
task decisions remain in `ai/**`.

## Expected artifacts

Architecture decision records, system context, component boundaries, and
deployment notes with source references. The component lifecycle registry is
the canonical record for retained, deprecated, disabled, superseded,
experimental and deferred components: [`COMPONENT_LIFECYCLE.md`](COMPONENT_LIFECYCLE.md).

Repository placement rules are shared in [`ai/AI_CONTRACT.md`](../../ai/AI_CONTRACT.md).
`docs/architecture/REPOSITORY_LAYOUT.md` is added only when a planned root
refactor introduces a new major directory.

## Status

`CURRENT` as an entrypoint; detailed architecture is not inferred where the
repository does not provide evidence.

