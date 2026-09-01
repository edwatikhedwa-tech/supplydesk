<!-- Publication note: the source report set contains a count discrepancy for local env-like files (5 vs 6). Exact contents and final count were not read; treat the count as NOT VERIFIED. -->

# SupplyDesk source state capture

Captured: 2026-09-01, Europe/Volgograd. This is a read-only state capture, not
the requested functional audit baseline.

## Repository

- absolute root: `<LOCAL_PROJECT_ROOT>`;
- remote: `https://github.com/edwatikhedwa-tech/supplydesk.git`;
- GitHub visibility: `PRIVATE`;
- branch: `codex/TASK-STATE-CONTROL-20260830`;
- HEAD: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`;
- upstream: `origin/codex/TASK-STATE-CONTROL-20260830`;
- ahead of upstream: 30 commits;
- tracked files: 266;
- modified tracked files: 2 (`ai/DECISIONS.md`, `ai/DEFERRED_FINDINGS.md`);
- staged modifications: 0;
- untracked paths: 709;
- ignored paths: 55 319;
- source files: 56 544;
- source size: 956 748 919 bytes.

## Runtime and toolchain

- OS: Windows NT 10.0.26200.0;
- PowerShell: 7.6.4;
- Git: 2.55.0.windows.3;
- ripgrep: 15.2.0;
- Python: 3.11.7;
- Node.js: v26.4.0;
- npm: 11.17.0;
- GitHub CLI: 2.96.0;
- system virtualenv directories `.venv` and `venv`: not present;
- `frontend/node_modules`: present;
- frontend: React 18 + Vite 5 + TypeScript 5, Playwright 1.62.1,
  Storybook 8.6, ESLint 9, Lighthouse 13;
- backend entrypoint: `supplier_app.py`; it reads `PORT`, default 8000;
- serverless/backend surface: `api/index.py` exists;
- database: SQLite `mail-data\\supplier.sqlite3`, 8 310 784 bytes;
- local database integrity: `ok`, read-only check;
- project process observed: Python PID 16704, listening on `127.0.0.1:8000`;
- runtime command: exact command line not recorded to avoid exposing secrets;
- `.github/workflows`: not present;
- local `.env*`: 5 files; values were not read into reports.

## Existing test surfaces

- backend test tree: `tests/`, 45 files including fixtures and Playwright specs;
- additional source tests: `supplier_source_tests/`, 8 files;
- frontend test tree: `frontend/tests/`, 15 files;
- Playwright config: `frontend/playwright.config.ts`, viewport matrix includes
  1920, 1640, 1440, 1280, 1024, 768, 390 and 360 widths;
- available frontend scripts: `dev`, `build`, `lint`, `typecheck`, `test`,
  `test:visual`, `test:storybook-visual`, `storybook`, `build-storybook`,
  `lhci`;
- `tests/run-tests.ps1`: not found at the requested path;
- `scripts/doctor.ps1`: present as an untracked source file, not executed.

## Source smoke observation

With the existing source server still running and without credentials:

| URL | Status | Meaning |
|---|---:|---|
| `/` | 200 | HTML shell responded |
| `/api/auth/me` | 200 | auth probe endpoint responded |
| `/api/requests` | 401 | protected endpoint rejected unauthenticated request |
| `/api/mail/status` | 401 | protected endpoint rejected unauthenticated request |
| `/api/does-not-exist` | 404 | unknown API route handled |

These checks did not send email, use SMTP, modify the database, or authenticate.
They are not the audit-copy functional baseline because the physical snapshot
verification failed first.
