# SupplyDesk Next Stages — 2026-09-01

This file is a planning boundary for the canonical control baseline. It does
not authorize implementation, migration, cleanup or external actions.

## Stage 1 — Baseline handoff

Review the control branch, manifest, classification ledger and audit reports
as one reproducible evidence package. Confirm that the source checkout remains
untouched and that the remote branch is private.

## Stage 2 — Doctor contract

Design the missing doctor gates and machine-readable exit taxonomy. Preserve
`Plan`, `DryRun` and `Apply`; define rollback and keep secrets/data path-only.

## Stage 3 — Reproducible test environment

Define a sanitized test environment and dependency lock policy that can
reproduce backend results without publishing `.env`, databases, mailbox data
or credentials. Resolve the difference between the audit environment and the
data-free control worktree.

## Stage 4 — Unknown review

Have an owner decide the disposition of the three `UNKNOWN_REVIEW` items and
the archive-later packages. No file is deleted or silently promoted by this
baseline.

## Stage 5 — Browser acceptance

Run the real backend plus frontend route matrix in a disposable, safe runtime,
then compare public shell and live-route results with the published audit.
Keep real-email and SMTP/IMAP actions prohibited unless separately authorized.

## Stage 6 — Data and migration safety

Review database backup, migration ordering, integrity and restore procedures.
No migration or canonical database write is part of this stage plan.

## Stage 7 — Release decision

After the previous evidence is complete, make a separate go/no-go decision for
merge or deployment. This baseline does not merge, change the default branch,
force-push or deploy.
