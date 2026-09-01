# Tool results

All results below are from the external audit workspace or read-only GitHub
queries. No absent tool result was simulated.

| Tool | Availability | Used | Version | Purpose / result | Limitations |
|---|---|---|---|---|---|
| Git | AVAILABLE | USED | 2.55.0.windows.3 | branch/HEAD/status/remotes/history and file lists | source queried read-only |
| GitHub MCP | NOT AVAILABLE | NOT USED | — | no callable GitHub MCP exposed | GitHub CLI used instead |
| GitHub CLI | AVAILABLE | USED | 2.96.0 | private repository, branches, workflow and API security-state queries | code scanning/dependabot API returned unavailable/403 |
| ripgrep | AVAILABLE | USED | 15.2.0 | references, docs, entrypoints and secret-pattern search | absence of a match is not deletion proof |
| Knip | AVAILABLE | USED | 6.34.0 | JS/TS files, exports and dependency candidates | partial: Vite config failed on `rollup/parseAst`; no removal flag |
| Knip MCP | NOT AVAILABLE | NOT USED | — | no callable tool exposed | no result simulated |
| Ruff | AVAILABLE | USED | 0.16.5 | Python check-only analysis | 194 findings; no autofix |
| Vulture | AVAILABLE | USED | 2.16 | Python dead-code candidates at confidence 60+ | 59 candidates are leads only |
| pytest | AVAILABLE | USED | 9.1.1 | backend functional baseline | 321 PASS, 52 FAIL, 1 SKIP, 0 ERROR |
| pytest-cov | AVAILABLE | USED | 7.1.0 | measured coverage | 74.23%; same baseline failures; app entrypoint not imported |
| Playwright | AVAILABLE | USED | 1.62.1 | real local route/browser checks and screenshots | live-email historical fixture not verified; no authenticated mutation flows |
| Semgrep | NOT AVAILABLE | NOT USED | — | executable not present | optional; not a snapshot blocker |
| CodeQL | NOT AVAILABLE | NOT USED | — | executable not present; GitHub code scanning disabled | heavy local setup intentionally skipped |
| Context7 MCP/plugin | NOT AVAILABLE | NOT USED | — | no callable Context7 capability exposed in this session | local source and official tool versions used instead |

## Supporting toolchain

- Python 3.11.7;
- Node.js v26.4.0;
- npm 11.17.0;
- frontend: React 18, Vite 5, TypeScript 5, Storybook 8.6, ESLint 9;
- `pip check`: PASS;
- `npm ls --depth=0`: noisy copied vendor tree, 134 extraneous and 5 invalid
  top-level packages, 0 missing.

The repository-local `ai/tools/validate_state.py` was also run read-only in the
audit copy: **FAIL** because one historical report contains six absolute links
to the original `<LOCAL_PATH>/Temp/` path. This is documented as a portability
finding; source state was not edited.

## Safety

No `--allow-remove-files`, unsafe autofix, migration, database write, SMTP
action, Git push, merge, force-push or source cleanup was performed.
