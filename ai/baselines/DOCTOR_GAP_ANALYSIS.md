# Project Doctor Gap Analysis — 2026-09-01

## What this records

This is a comparison between the published `PROJECT_DOCTOR_SPEC.md` and the
existing `scripts/doctor.ps1`. It is an analysis only. No doctor expansion or
application implementation is included in the control baseline.

The audit specification describes 27 explicit checklist capabilities. The
current script provides 8 grouped capabilities, approximately 30% coverage.
The denominator is a review count, not a claim that every line in the spec is
an independent feature.

## Implemented and observed

1. Mutually exclusive `-Plan`, `-DryRun` and `-Apply` modes.
2. Project-root and required-file checks.
3. Requirements presence check.
4. `.env` presence and required-key checks without printing values.
5. Python discovery and version check.
6. Required Python import checks.
7. Canonical SQLite path existence check.
8. Port 8000 availability check.

The source checkout `scripts/doctor.ps1 -DryRun` completed successfully with
the local environment available at the time of the audit. The same command in
the data-free control worktree returned two expected errors because `.env` and
`mail-data/supplier.sqlite3` are intentionally not part of the branch.

## Missing or incomplete coverage

The following spec capabilities are not implemented as explicit doctor gates:

- Git branch, HEAD, staged/unstaged/untracked/ignored counts and dirty-state report.
- Node/npm presence and clean-install verification.
- Manifest schema and canonical-path validation.
- Backend HTTP health and required API probes.
- Database integrity, journal mode, backup comparison and write-detection checks.
- Baseline test counts and comparison against known failure IDs.
- Frontend typecheck, lint and production-build checks.
- Playwright public shell, live routes and viewport matrix checks.
- Documentation freshness, links and contradiction checks.
- High-signal secret scan with path-only reporting.
- Worktree isolation and frozen snapshot linkage.
- Machine-readable report output.
- Explicit rollback/restore manifest.
- Review-package and duplicate detection.
- External-service and real-email safety gate.
- Final security allowlist gate.
- Remote branch and push policy checks.
- Exit-code taxonomy separating environment gaps from product failures.

## Safety assessment

No unsafe mutation was observed in `-DryRun`. `-Apply` was not executed. The
existing recovery script is a separate operator tool and remains outside this
baseline's automated execution; no migration, database write, SMTP/IMAP
connection, email send, deletion or remote mutation was performed.

## Recommended next step

Expand the doctor only in a future, separately reviewed task. Keep the current
mode contract and add machine-readable output plus explicit exit categories
before adding broader checks. Do not make missing local secrets or live data a
reason to publish those values.
