# Final Canonical Inventory — 2026-09-01

Status: `CONFIRMED — final hygiene acceptance scope`

This is a lightweight inventory of the canonical checkout. It intentionally
does not enumerate dependency trees, caches, screenshots, mail data or the
external quarantine. Paths in this report are repository-relative.

## Metrics

| Metric | Result |
|---|---:|
| Tracked canonical files | 390 |
| Tracked root objects | 45 (30 files, 15 directories) |
| Unknown canonical files | 0 |
| Unknown canonical directories | 0 |
| Unknown root objects | 0 |
| Review-required canonical files | 1 (`frontend/src/components/suppliers/RiskFactors.tsx`) |
| Review-required non-file item | 1 direct `lighthouse` dev dependency |
| Exact duplicate groups | 2 groups / 4 files, all kept |
| Historical review packages inside canonical | 0 |
| Backup copies inside canonical | 0 |
| ZIP review packages inside canonical | 0 |
| Generated artifacts tracked | 0 |
| Secret/env files tracked | 0 |
| Database files tracked | 0 |

## Root files

| Classification | Objects | Why at root |
|---|---|---|
| `PROJECT_CONFIG` | `.gitignore`, `.vercelignore`, `PROJECT_MANIFEST.yaml`, `requirements-test.txt`, `requirements.txt`, `skills-lock.json`, `stop_domains.txt`, `vercel.json` | Repository policy, dependency/bootstrap metadata, deployment configuration and provider stop-list are consumed from the repository root. |
| `PROJECT_DOCUMENTATION_ENTRYPOINT` | `AGENTS.md`, `CLAUDE.md` | Agent/project operating instructions are discovered at the repository root. |
| `ACTIVE_MODULE` / `CLI_TOOL` | `benchmark_models.py`, `checko_client.py`, `collect_contacts.py`, `collect_inn.py`, `contact_crawler.py`, `dadata_client.py`, `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `llm_fallback.py`, `routerai_client.py`, `serp_parser.py`, `supplier_app.py`, `verify.py`, `web_lookup.py`, `xmlriver_client.py` | Root-level imports, backend imports, documented CLI invocations or operator scripts require these import paths; no relocation is safe in this task. |
| `TEST` | `test_extractor.py`, `test_inn.py`, `test_parser.py`, `test_verify.py` | Root-level tests import the root modules directly and remain part of the existing test layout. |

Evidence for the Python classifications: direct imports in `supplier_app.py`,
`mail/repository.py`, `tests/test_enrichment_pipeline.py`,
`scripts/verify_enrichment_live.py` and the four root tests; documented CLI
invocations in `collect_contacts.py`, `collect_inn.py`, `benchmark_models.py`
and `Documents/28-8/README.md`; and Git history for each tracked root module.

## Root directories

| Classification | Directories | Why at root |
|---|---|---|
| `PROJECT_DOCUMENTATION_ENTRYPOINT` | `ai/`, `docs/` | Operational control/state and product documentation ownership boundaries. |
| `RUNTIME_MODULE` | `api/`, `frontend/`, `mail/`, `migrations/`, `fonts/` | Backend/serverless entrypoint, frontend application, mail domain, schema source and required UI assets. |
| `TEST` | `tests/`, `supplier_source_tests/`, `fixtures/` | Automated tests, source-verification tests and controlled fixtures. |
| `CLI_TOOL` | `scripts/`, `benchmarks/` | Operator scripts and reproducible benchmark inputs/tools. |
| `ACTIVE_MODULE` / `LEGACY_LAYOUT_BUT_REQUIRED` | `supplier_discovery_v2/`, `work/`, `Documents/` | Existing importable discovery package, retained active work layout and historical/operator documentation referenced by the current repository. |

No root object is `UNKNOWN`. Root Python reorganization is explicitly deferred
to a separate `ROOT-MODULE-REORGANIZATION` task because changing import paths
could alter runtime or test behavior.

## Duplicate groups retained

- `ai/inbox/.gitkeep` and `ai/reports/.gitkeep`: identical placeholders for two
  intentionally different owned directories.
- `supplier_discovery_v2/tests/__init__.py` and `tests/__init__.py`: identical
  package markers for two different test package roots.

## Frontend review candidates

- `frontend/src/components/suppliers/RiskFactors.tsx`: `REVIEW_LATER`; no
  current import was found, but it is canonical UI source and was not deleted.
- `frontend/lighthouserc.cjs`: `KEEP_CONFIRMED`; consumed by the `lhci` script.
- `frontend/playwright.live-email.config.ts`: `KEEP_CONFIRMED`; manual
  live-mail acceptance configuration; real mail remains forbidden here.
- `frontend/playwright.real-email.config.ts`: `KEEP_CONFIRMED`; manual
  diagnostic configuration; real provider access remains unverified.
- Direct `lighthouse` dev dependency: `DEPRECATION_CANDIDATE`; any removal
  requires a separate dependency-cleanup task and clean-install acceptance.

## Generated and protected local categories

Observed or policy-covered generated/local categories are ignored and are not
tracked: Python caches, `.ruff_cache`, `.venv-test`, `runtime/test-data`,
runtime JSON/log markers, `frontend/node_modules`, `frontend/dist`, frontend
test results and artifacts. Protected `.env*`, `mail-data`, credentials and
real-mail evidence are not part of this canonical tracked inventory.

## Evidence boundary

The counts above were obtained from `git ls-files`, `git ls-tree`, direct
filesystem inspection and the `.gitignore` matrix on
`control/final-hygiene-acceptance-20260901`. No secret or mail-data contents
were read. The inventory does not claim live-provider or production parity.
