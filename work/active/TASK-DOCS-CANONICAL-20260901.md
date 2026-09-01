# Task: canonical documentation

Task ID: TASK-DOCS-CANONICAL-20260901
Status: COMPLETE LOCALLY — waiting for owner confirmation
Created UTC: 2026-09-01T07:30:00Z

## Current State

The repository has two documentation contours. ai/CURRENT_STATE.md is the
shared state source, while docs/ and Documents/28-8/ contain historical
architecture, audits and old snapshots. Several of those snapshots were
presented as current and contained stale mail and test counts.

## Decisions

- Keep application code, database, migrations, mail settings and deployment
  runtime outside this documentation task.
- Make ai/CURRENT_STATE.md the only current-state source.
- Mark old snapshots as HISTORICAL — NOT CURRENT instead of deleting their
  evidence.
- Add a repository documentation policy and require state/log/report updates in
  the same task as a product or infrastructure change.
- Validate changed Markdown, links, timestamps, secret patterns and state files.

## Current Result

The canonical policy, navigation pointers, historical banners and current-state
snapshot were updated. A report and rollback backups were saved. No product
logic or data changed.

## Next Action

On the next product change, update ai/CURRENT_STATE.md and the affected feature
document in the same commit, then run the documentation acceptance checks.
