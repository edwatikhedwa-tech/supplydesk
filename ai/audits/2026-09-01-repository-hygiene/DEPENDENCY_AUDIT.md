# Dependency audit

## Scope and safety

Проверялись только audit workspace и его копии зависимостей. Исходный
`package-lock.json`, `requirements.txt` и исходная папка `node_modules` не
изменялись. Удаление пакетов не выполнялось.

## Python

Declared runtime requirements were read from `requirements.txt`; the audit
environment installed them in `.audit-venv-system` with system site packages so
the application could import its native `nh3` dependency on Windows.

- Python: 3.11.7;
- `pip check`: **PASS**, no broken requirements;
- observed packages include `requests 2.32.5`, `beautifulsoup4 4.14.3`,
  `lxml 6.1.2`, `cryptography 46.0.7`, `psycopg 3.3.4`, `nh3 0.3.6`,
  `quotequail 0.5.0`, `openai 2.20.0`, `dnspython 2.8.0`, `pypdf 6.16.2`;
- analysis tools are recorded separately in `TOOL_RESULTS.md`.

## JavaScript/TypeScript

The frontend is React 18 + Vite 5 + TypeScript 5, with Playwright, Storybook,
ESLint and Lighthouse tooling declared in `frontend/package.json`.

- `npm run typecheck`: **PASS**;
- `npm run lint`: **PASS with 8 warnings, 0 errors**;
- `npm run build`: **PASS** (Vite transformed 2,205 modules);
- `npm ls --depth=0`: **FAIL/NOISY** in the copied vendor tree: 134
  top-level packages are marked `extraneous`, 5 are `invalid`, 0 are missing.
  This is evidence that the copied `node_modules` is not a clean lockfile
  installation; it is not evidence that every listed package is removable.
- Knip 6.34.0 produced a raw report but exited non-zero while loading
  `vite.config.ts`: `Cannot find module 'rollup/parseAst'`. It also reported
  candidate unused files/exports/dependencies. These remain candidates only.

## Findings

1. Recreate a clean dependency tree in a disposable audit copy using the
   committed lockfile before making package decisions.
2. Investigate the Vite/Rollup mismatch that blocks complete Knip analysis.
3. Do not remove the 134 `extraneous` packages from the copied tree: the tree
   is generated/local state and has no authority over `package.json`.
4. Review Knip findings only after explicit entry points, Storybook conventions,
   dynamic imports and route registration are configured.

Evidence files: `npm-ls-latest.json`, `npm-ls.json`, `knip.json`,
`knip.stderr.log`, `pip-list.json`, `pip-check.log`.

## Classification

`node_modules`, Python tool environments and build output are
`DEPENDENCY_VENDOR`/`CACHE`/`GENERATED`, not project-owned source. No dependency
received `DELETE_CANDIDATE` status in this audit.
