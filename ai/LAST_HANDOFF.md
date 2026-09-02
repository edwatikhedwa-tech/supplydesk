---
document_id: HANDOFF-008
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-02
based_on_commit: e8ba5b637b163d38d8d4313f4865f1c4a571e2d3
---

# Last Handoff

This handoff records completion of the previously deferred `checko_client.py`
registry move, done together with a matching migration of the immutability
protected-path list so the guard was never weakened.

## Цель

Завершить перенос `checko_client.py` в
`backend/integrations/registry/checko_client.py`, одновременно перенеся
защиту `supplier_discovery_v2/immutability_check.py` на новый путь, и
закрыть `FINDING-017`.

## Что изменено

- Moved `checko_client.py` to `backend/integrations/registry/checko_client.py`
  (byte-identical, Git-recognized rename).
- Updated `supplier_app.py`, `scripts/verify_enrichment_live.py`,
  `tests/test_enrichment_pipeline.py` import lines to the canonical path.
- Updated `supplier_discovery_v2/immutability_check.py:protected_paths()` to
  protect the new location instead of the old root path — the only change in
  that file; nothing else in it was touched.
- Added 2 tests to `supplier_discovery_v2/tests/test_immutability.py`.
- Updated `docs/architecture/REPOSITORY_LAYOUT.md` and `CLAUDE.md` to stop
  claiming Checko is still at root.
- Marked `FINDING-017` `RESOLVED` in `ai/DEFERRED_FINDINGS.md` (in place,
  same file/format as `FINDING-006`'s `SUPERSEDED` — not deleted, not moved
  into the frozen `HISTORICAL` chronicle, which was out of this task's scope).
- Added `ai/reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md`.

## Что проверено

- Workspace Guard passed before task-lock and before mutation.
- Fresh reference scan (independent of the prior task's list) confirmed the
  same 3 code importers and the immutability path dependency; found and
  verified `tests/test_dashboard.py`'s `patch.object(supplier_app,
  "CheckoClient", ...)` needed no change (module-attribute patch, not a
  dotted-path string).
- `backend.integrations.registry.checko_client`, `supplier_app` import
  cleanly; `from api.index import handler, _APP` succeeds under
  `SUPPLYDESK_ENV=test` (full offline chain); `python
  scripts/verify_enrichment_live.py --help` exits `0`.
- Fresh baseline generated against the real, moved tree verifies clean
  (`verify() == []`); `protected_paths()` contains the new path and not the
  old root path.
- A disposable synthetic copy of the new Checko path (built only under
  `tempfile.TemporaryDirectory()`, never the real project file), mutated
  after baselining, is correctly reported as changed.
- `supplier_discovery_v2.tests.test_immutability`: `3/3` passed.
  `tests.test_enrichment_pipeline`: `8/8` passed. `tests.test_dashboard`:
  `13/13` passed. Full `supplier_discovery_v2/tests`: `14/14` passed.
- Full `tests/diagnostics` discovery: `52/61` passed; the remaining `9`
  errors are the same pre-existing `pwsh`-missing gap already proven
  unrelated in an earlier task — not re-investigated here.
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py`: all `PASS`. `git diff --check`: `PASS`.
- Staged diff scanned for secret-like literals: only `CHECKO_KEY`/`self.key`
  identifiers, no values. `0` external provider calls of any kind.

## Что не прошло

Nothing this task touched failed.

## Что не проверено

NOT VERIFIED: real Vercel build/deploy (not re-audited; the `vercel.json`
structural check from the prior task was reused unchanged since `vercel.json`
was not touched). NOT VERIFIED: undocumented external Python-import
compatibility for `checko_client`.

## Текущее состояние runtime

No runtime was started for this task. No provider call, real mail, or
canonical database write occurred.

## Следующий рациональный шаг

Both registry provider adapters (`dadata_client.py`, `checko_client.py`) now
live under `backend/integrations/registry/`. Remaining root modules named in
`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md` — `supplier_app.py`,
`api/index.py`, `serp_parser.py`, and the rest of the flat root package —
each need their own bounded, explicitly-scoped task before any further move.

## Не повторять

Do not use the legacy OneDrive checkout for development, do not output or
save secret values, do not run real mail or live provider calls, do not
modify protected local data, do not move a protected file referenced by
`supplier_discovery_v2/immutability_check.py` without migrating its
protected-path entry in the same change, do not touch
`supplier_discovery_v2/` product logic (`pipeline.py`, `contacts.py`,
`matching.py`, `query_planner.py`, `connectors/`, `direct_site.py`,
`xmlriver_subprocess.py`, `storage.py`, `run.py`) outside an explicitly
authorized exception, and do not add a second acknowledgement to an
intermediate message.
