# Publish manifest — TASK-REMOTE-SETUP-SIMPLIFIED

Status: `VERIFIED — explicit staged tree passed security checks`

Generated: `2026-08-30T17:55:25Z`
Project root: `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS`
Branch: `codex/TASK-STATE-CONTROL-20260830`
Source HEAD before this task's publish commit: `34b064bddeec5b2598f7f9f251d5ec374deadbab`
Publication commit: `85fb7a2d9ac2f3697f33c7b5f930f44adabf799e`
Repository: `https://github.com/edwatikhedwa-tech/supplydesk` (`private`)
Push: `PASS` — `codex/TASK-STATE-CONTROL-20260830` → `origin`.

## Inclusion rule

The publish set is the exact set staged by an explicit `git add --` path list.
This manifest records the specification; `git diff --cached --name-status` is
the final authority before commit. No `git add .` or `git add -A` is allowed.

## Included directories

- `api/` — backend entrypoint only
- `mail/` — mail-domain source modules
- `frontend/src/` — frontend source and the required static icon
- `tests/` — offline Python tests
- `frontend/tests/` — selected offline Playwright specs only
- `migrations/` — SQL source files; not executed
- `fixtures/` — demo/enrichment fixtures only
- `fonts/` — required application fonts
- `supplier_discovery_v2/` — source, tests and documentation only; no local data/output
- `docs/` — current project documentation files only
- `ai/` — state, contracts, adapters, templates, validator and reports

## Included root files

`AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.vercelignore`, `requirements.txt`,
`skills-lock.json`, `stop_domains.txt`, `vercel.json`, confirmed root backend
modules (`benchmark_models.py`, `checko_client.py`, `collect_contacts.py`,
`collect_inn.py`, `contact_crawler.py`, `dadata_client.py`,
`email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `llm_fallback.py`,
`routerai_client.py`, `serp_parser.py`, `supplier_app.py`, `verify.py`,
`web_lookup.py`, `xmlriver_client.py`) and the four confirmed root tests
(`test_extractor.py`, `test_inn.py`, `test_parser.py`, `test_verify.py`).

Frontend root manifests/configuration included explicitly:
`frontend/.gitignore`, `frontend/eslint.config.js`, `frontend/index.html`,
`frontend/lighthouserc.cjs`, `frontend/package-lock.json`,
`frontend/package.json`, `frontend/playwright.config.ts`,
`frontend/playwright.storybook.config.ts`, `frontend/postcss.config.js`,
`frontend/tailwind.config.js`, `frontend/tsconfig.app.json`,
`frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`.

## Explicit exclusions

- All `.env*`, including `.env`, `.env.local`, `.env.p0-backup-20260830`,
  `.env.production.local`, `.env.example` and `.vercel/.env.preview.local`.
- `Temp/`, `runtime/`, `tmp/`, `mail-data/`, local databases, cache, build
  output, `node_modules/`, generated reports and logs.
- Screenshots/snapshots and archives (`*.png`/`*.jpg` test snapshots,
  `*.zip`, `*.rar`, `*.7z`, `*.tar`, `*.gz`). The source icon in
  `frontend/src/assets/checko-icon.png` is an explicit required static asset.
- Backups, review exports, `P0_REVIEW*`, `REVIEW_*`,
  `mailru-mvp-backup-20260829/`, `Documents/`, `.agents/` and OneDrive-local
  material.
- `scripts/`, `supplier_source_tests/`, `benchmarks/`, `run_probe.py`,
  `keywords.txt`, and one-off root Markdown/status artifacts: not required for
  this shared snapshot or not sufficiently verified.
- `supplier_discovery_v2/data/`, `supplier_discovery_v2/out/`,
  `supplier_discovery_v2/protected_manifest.json`, Python caches and all
  frontend live/real-email configs, fixtures and diagnostics.
- Deleted tracked paths are not staged and are not restored or removed by this
  task. Current deleted paths are recorded separately in the final report.

## Size and count

Publish set file count: `218`
Publish set size: `3,053,727` bytes (`2.912 MiB`, index blob size)
Staged diff entries relative to source HEAD: `184` (`91 A`, `71 M`, `22 D`)

## Safety note

Local excluded env files remain in place and are not moved. A high-confidence
credential-like match was found only in excluded `.env.production.local`; its
value is intentionally not recorded. The staged-tree scan found no
high-confidence credential pattern. History scanning found no high-confidence
secret pattern in the commits that will be pushed. The final report records
patterns and limitations without exposing values.
