# Dead-code and static-analysis audit

## Rule

Static analyzers identify leads, not deletion approvals. A
`HIGH_CONFIDENCE_DELETE_CANDIDATE` requires at least three independent proofs;
none was approved or deleted here. Routes, decorators, callbacks, background
jobs, plugin registration and dynamic attributes require special review.

## Ruff

Command was check-only and limited to project-owned Python surfaces (`api`,
`mail`, `scripts`, `tests`, `supplier_source_tests` and root Python entrypoints).
Result: **194 violations across 49 files**. Main codes: `I001` 43, `BLE001` 20,
`F401` 18, `UP041` 16, `UP035` 11, `RUF100` 11, `F841` 11, `SIM117` 9,
`UP037` 6, `S110` 5, `SIM102` 5; the remainder are listed in `ruff.json`.
No autofix was run.

These are maintainability findings, not proof of unused modules. In particular,
unused-import warnings can be safe to fix only in an isolated code task with
tests; no such fix belongs to this snapshot audit.

## Vulture

Vulture 2.16 found **59 candidates** at minimum confidence 60. Examples include
`api/index.py:handler`, provider helpers in `mail/providers/yandex.py`, methods
and attributes in `mail/repository.py`, service helpers, and some
`supplier_app.py` handlers/enrichment methods. Confidence 90–100 candidates
included `formataddr`, `decode_content` and `initial_response_ok`.

Framework routes and callbacks appear among the candidates; therefore none is a
safe deletion candidate without runtime reference and browser/API evidence.
Raw output: `vulture.log`.

## Knip

Knip 6.34.0 reported an unused `RiskFactors.tsx` file, possible unused
devDependencies (`@storybook/test`, `lighthouse`), unlisted Storybook imports,
and unused exports in `src/lib/utils.ts`, `useRequestState.ts`, campaign and
registry modules. The report is partial because Vite config loading failed on
`rollup/parseAst`. Raw output: `knip.json`.

## Coverage

`pytest-cov` measured `mail`, `supplier_app.py` and `api` while the existing
backend suite ran: 6,259 statements, 4,646 covered, **74.23%**. The suite had
the same 52 baseline failures, so coverage is not a clean green run.
`supplier_app.py` was not imported during the measured tests. No measured file
had 0% coverage, but 0% coverage would not prove unused code anyway.

## Conclusion

There are actionable cleanup leads, but no high-confidence deletion proof. The
correct next step is targeted review with clean dependencies, explicit entry
points, runtime route checks and a baseline comparison—not file removal.
