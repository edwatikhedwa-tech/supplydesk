# .gitignore recommendations

## Observed rules

The root `.gitignore` protects `.env*`, `results/`, `*.csv`, `*.json`,
`artifacts/`, `cache/`, Python caches/virtualenvs, `mail-data/`, SQLite files,
`tmp/` and runtime JSON/lock files. `frontend/.gitignore` protects
`node_modules`, `dist`, local env files, Playwright artifacts and test results.

## Findings

1. **P2 — rule contradiction:** the root file first contains `!.env.example`,
   but later contains another `.env*`. `git check-ignore` proves that
   `.env.example` is currently ignored. Decide whether the example is a safe
   tracked template; if yes, put the negation after the final broad rule and
   verify with `git check-ignore`.
2. **P2 — broad generated patterns:** global `*.json` and `*.csv` can hide
   useful fixtures or manifests. Existing exceptions are narrow; document and
   test every intentional tracked exception.
3. **P2 — local data protection:** `mail-data/`, `*.sqlite3`, `*.db` and
   `runtime/*.json` are correctly protected for local state, but their presence
   must remain visible in a local-only inventory so operators do not confuse
   ignored with disposable.
4. **P3 — naming drift:** both `.vercel` and `.env*` rules occur more than once;
   duplicate rules increase maintenance ambiguity.

## Suggested future verification

Do not edit `.gitignore` in this task. In a separate narrowly scoped change,
use `git check-ignore -v` for `.env.example`, a safe fixture JSON, a CSV export,
`mail-data/supplier.sqlite3`, `runtime/canonical_manifest.json`, frontend
`dist`, and Playwright results. Run `git status --ignored --untracked-files=all`
and verify no source, migration, test or required configuration is hidden by
accident.

No cleanup or rule change was performed.
