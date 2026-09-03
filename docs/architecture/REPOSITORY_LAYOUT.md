---
document_id: REPOSITORY-LAYOUT-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-03
source_commit: 6af2af1822820e996f1126b8a1b26d19be0000f0
---

# Repository Layout

This is a concise map of current top-level directories, kept in sync only
after a planned root refactor actually lands. It documents what exists now,
not a target structure. For behavioral component ownership, see
[`COMPONENT_MAP.md`](COMPONENT_MAP.md).

| Path | Contains |
|---|---|
| root composition entrypoints | `supplier_app.py` (local backend entrypoint), plus a shrinking flat package of supplier-discovery/extraction modules still at root (e.g. `serp_parser.py`, `collect_inn.py`) and the four root tests (`test_extractor.py`, `test_inn.py`, `test_parser.py`, `test_verify.py`) |
| `api/` | `api/index.py` — the Vercel serverless adapter around `supplier_app.py` |
| `backend/` | New product-code area. `backend/integrations/registry/` — provider adapters moved out of the root flat package (`dadata_client.py`, `checko_client.py`); `backend/integrations/llm/` — LLM/provider transport moved out of the root flat package (`llm_fallback.py`, `routerai_client.py`); `backend/integrations/search/` — SERP/web-lookup integrations moved out of the root flat package (`web_lookup.py`, `xmlriver_client.py`); `backend/domain/supplier_identity/` — supplier-identity product logic moved out of the root flat package (`email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `verify.py`); `backend/domain/supplier_enrichment/` — supplier-enrichment crawling logic moved out of the root flat package (`contact_crawler.py`) |
| `mail/` | Real Yandex IMAP/SMTP integration and SQLite-backed mail repository |
| `migrations/` | Versioned SQL schema DDL |
| `frontend/` | React/Vite SPA (TypeScript, Tailwind) |
| `scripts/` | Operator/control tooling, plus one moved CLI implementation (`scripts/collect_contacts.py`) with a root compatibility wrapper |
| `benchmarks/` | Offline fixtures (`enrichment_cases.json`) and one moved CLI implementation (`benchmarks/benchmark_models.py`) with a root compatibility wrapper |
| `tests/` | Backend unittest suites, including `tests/diagnostics/` |
| `supplier_discovery_v2/` | Isolated discovery pilot; does not import or modify production parser code (see its own `README.md`) |

## Moves in progress

- `TASK-BOUNDED-ROOT-REFACTOR-CLI-20260902`: `collect_contacts.py` and
  `benchmark_models.py` implementations moved to `scripts/` and
  `benchmarks/`; root files are thin compatibility wrappers.
- `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902` +
  `TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902`:
  `dadata_client.py` and `checko_client.py` both moved to
  `backend/integrations/registry/`, no root wrapper (no confirmed external
  Python-import consumer for either). `supplier_discovery_v2/immutability_check.py`'s
  protected-path list was migrated to Checko's new location in the same
  change that moved it, so the existing immutability guard was never
  weakened.
- `TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902`: `llm_fallback.py` and
  `routerai_client.py` moved to `backend/integrations/llm/`, no root
  wrapper. `supplier_app.py`, `collect_inn.py`,
  `scripts/collect_contacts.py` and `benchmarks/benchmark_models.py` updated
  to the canonical import path.
- `TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902`:
  `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py` and `verify.py`
  moved to `backend/domain/supplier_identity/`, no root wrapper. 14 known
  consumers updated (`supplier_app.py`, `contact_crawler.py`, `collect_inn.py`,
  `web_lookup.py`, `scripts/collect_contacts.py`, `scripts/verify_enrichment_live.py`,
  `benchmarks/benchmark_models.py`, `backend/integrations/llm/llm_fallback.py`,
  `backend/integrations/registry/dadata_client.py`, `mail/repository.py`, root
  tests, and `tests/test_enrichment_pipeline.py`), including two not named in
  the original diagnostic (`web_lookup.py`, `mail/repository.py`) found by a
  fresh full-tree scan rather than assumed from the prior evidence.
  `supplier_discovery_v2/immutability_check.py`'s protected-path list was
  migrated for the three already-protected files
  (`email_extractor.py`/`inn_extractor.py`/`verify.py`) in the same change;
  `inn_resolver.py` was deliberately left unprotected — it was never
  protected before, and moving beside the other three is not evidence for
  adding it.
- `TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903`: `web_lookup.py`
  and `xmlriver_client.py` moved to `backend/integrations/search/`, no root
  wrapper. Both are 0-diff pure moves (`git diff -M --stat`). 6 confirmed
  consumers updated to the canonical import path (`supplier_app.py`,
  `collect_inn.py`, `scripts/collect_contacts.py`, `test_extractor.py`,
  `serp_parser.py`, `test_parser.py`); `serp_parser.py` itself stays
  `DEFER`red (unmoved) per the diagnostic — only its one internal import line
  was touched. `supplier_discovery_v2/xmlriver_subprocess.py` is unaffected:
  it invokes the untouched `serp_parser.py` by absolute path via
  `subprocess.run(..., cwd=...)`, so `serp_parser.py`'s own updated import
  resolves normally at that call site.
  `supplier_discovery_v2/immutability_check.py`'s protected-path list was
  migrated for both files in the same change, so the existing immutability
  guard was never weakened.
- `TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903`:
  `contact_crawler.py` moved to `backend/domain/supplier_enrichment/`, no root
  wrapper. It is a 0-diff pure move (`git diff -M --stat`); its only internal
  import was already the canonical `backend.domain.supplier_identity.email_extractor`
  path from an earlier pass. 6 confirmed consumers updated to the canonical
  import path (`supplier_app.py`, `collect_inn.py`,
  `benchmarks/benchmark_models.py`, `scripts/verify_enrichment_live.py`,
  `scripts/collect_contacts.py`, `tests/test_enrichment_pipeline.py`,
  `tests/diagnostics/test_collect_inn_llm_path.py`).
  `supplier_discovery_v2/immutability_check.py`'s protected-path list was
  migrated in the same change, so the existing immutability guard was never
  weakened.
- Remaining root modules named in
  `ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md` (including
  `supplier_app.py`, `api/index.py`, `serp_parser.py`, `collect_inn.py`) are
  unmoved and require their own bounded, explicitly-scoped task. `serp_parser.py`
  is `DEFER`red pending an explicit subprocess/deployment contract decision
  because `supplier_discovery_v2/xmlriver_subprocess.py` hardcodes its root
  path; `collect_inn.py` mixes a reusable enrichment pipeline with a CLI and
  needs an explicit split (not a pure move) before it can move.
