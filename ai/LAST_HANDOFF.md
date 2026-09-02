---
document_id: HANDOFF-006
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-02
based_on_commit: d7fa86d2456bd7f59a7a6d055acfc6d20a96bbd5
---

# Last Handoff

This handoff records the completed bounded root refactor of two standalone
CLI surfaces. No other root Python module, business logic, or product
behavior changed.

## Цель

Перенести реализацию `collect_contacts.py` и `benchmark_models.py` в
`scripts/` и `benchmarks/` соответственно, сохранив CLI-совместимость через
тонкие root wrapper'ы, по решению
`ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md`.

## Что изменено

- Added `scripts/collect_contacts.py` and `benchmarks/benchmark_models.py`
  as the single canonical implementations (identical logic; only the `.env`
  root-lookup calculation and a couple of doc/help strings changed).
- Reduced root `collect_contacts.py` and `benchmark_models.py` to thin
  compatibility wrappers that import and call the moved `main()`.
- Added `tests/diagnostics/test_operator_cli_root_compat.py` (4 tests)
  guarding `.env`-root resolution and wrapper delegation.
- Updated `ai/CURRENT_STATE.md`, `ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`,
  this handoff, and added
  `ai/reports/TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902-report.md`.

## Что проверено

- Workspace Guard passed before task-lock and before mutation.
- Fresh reference check found no Python imports of either module outside
  their own files, the diagnostic report, and state files.
- `python collect_contacts.py --help` and `python -m scripts.collect_contacts
  --help` produce byte-identical output and exit `0`; same for
  `benchmark_models.py` / `python -m benchmarks.benchmark_models --help`.
- Exit code without arguments matches (`1`) between old and new
  `collect_contacts` invocation, with no network/provider action.
- `scripts.collect_contacts.REPO_ROOT` and `benchmarks.benchmark_models.REPO_ROOT`
  both resolve to the repository root — proven structurally without reading
  `.env` contents.
- `python -m unittest tests.diagnostics.test_operator_cli_root_compat -v`:
  `4/4` passed. Full `tests/diagnostics` discovery: `49/49` passed.
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py`: all `PASS`. `git diff --check`: `PASS`.
- Staged diff scanned for secret-like literals: only environment-variable
  names and code identifiers, no values.

## Что не прошло

`tests/diagnostics/test_change_classifier.py` produced `9 errors`
(`FileNotFoundError` for `pwsh`). Reproduced identically on the unmodified
working tree via `git stash`, so this is a pre-existing environment gap
(PowerShell Core not on `PATH`), not caused by this task.

## Что не проверено

NOT VERIFIED: undocumented external Python-import compatibility for either
moved module (explicitly out of scope); direct `python
scripts/collect_contacts.py` / `python benchmarks/benchmark_models.py`
invocation without `-m` or the wrapper (not a required entrypoint, and would
need its own `sys.path` decision); live `--web`/`--llm`/`--verify`/
`--prepare`/`--run` provider paths (forbidden by this task's "no live
provider execution" rule).

## Текущее состояние runtime

No runtime was started for this task. No provider call, real mail, or
canonical database write occurred.

## Следующий рациональный шаг

Any further root moves (`supplier_app.py`, `api/index.py`, `serp_parser.py`,
or the remaining 12+ runtime modules named in the root diagnostic) need their
own bounded task with explicit import/subprocess/deployment contracts.

## Не повторять

Do not use the legacy OneDrive checkout for development, do not output or
save secret values, do not run real mail or live provider calls, do not
modify protected local data, do not move `supplier_app.py`/`api/index.py`/
`serp_parser.py` or any of the other listed runtime modules without a
separate task, and do not add a second acknowledgement to an intermediate
message.
