# Canonical Duplicate Audit — Cleanup Batch 2

Status: `PASS_WITH_LIMITATIONS`

Audit date: `2026-09-01`

Scope: current canonical Git tree at Batch 2 commit `d2ceef3`. The inventory
used `git ls-files` and SHA-256 for every tracked regular file. Generated,
cache, runtime-data, dependency and quarantine trees are not tracked in this
scope; no quarantine content was added to Git.

## Result

- Tracked files inspected: `387`
- Files hashed: `387`
- Exact duplicate groups: `2`
- Files in duplicate groups: `4`
- Duplicate files deleted: `0`

An equal hash is evidence of equal bytes, not evidence that one path can be
removed. Each group was checked against path ownership, references, runtime or
documentation role, package topology and Git history.

## Group 1 — KEEP

Hash: `7eb70257593da06f682a3ddda54a9d260d4fc514f645237f5ca74b08f8da61a6`

- `ai/inbox/.gitkeep` — preserves the empty task-input directory.
- `ai/reports/.gitkeep` — preserves the empty report directory.

The files are equal by content but have different directory semantics. The
state validator explicitly treats both paths as owned control-plane roots.
Removing either would make that directory disappear from a fresh checkout.

## Group 2 — KEEP

Hash: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

- `supplier_discovery_v2/tests/__init__.py` — package marker for the discovery
  test tree.
- `tests/__init__.py` — package marker for the main test tree.

The files are equal by content but belong to two independently discovered
Python test package roots. Test commands, import paths and the repository test
runner distinguish those roots. Git history confirms both paths are retained
control/test structure, not accidental file copies.

## Decision

No group met all deletion gates: same bytes, same purpose, no independent path
semantics, no active references and green regression. Both groups remain
`KEEP`; no canonical source, test package marker or control directory was
deleted.
