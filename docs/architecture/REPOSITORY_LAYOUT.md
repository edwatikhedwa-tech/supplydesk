---
document_id: REPOSITORY-LAYOUT-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-02
source_commit: 4065242519bb55271d82f65198d27236a33915ba
---

# Repository Layout

This is a concise map of current top-level directories, kept in sync only
after a planned root refactor actually lands. It documents what exists now,
not a target structure. For behavioral component ownership, see
[`COMPONENT_MAP.md`](COMPONENT_MAP.md).

| Path | Contains |
|---|---|
| root composition entrypoints | `supplier_app.py` (local backend entrypoint), plus a shrinking flat package of supplier-discovery/extraction modules still at root (e.g. `serp_parser.py`, `contact_crawler.py`, `email_extractor.py`, `inn_extractor.py`, `collect_inn.py`, `web_lookup.py`, `xmlriver_client.py`, `verify.py`) and the four root tests (`test_extractor.py`, `test_inn.py`, `test_parser.py`, `test_verify.py`) |
| `api/` | `api/index.py` — the Vercel serverless adapter around `supplier_app.py` |
| `backend/` | New product-code area. `backend/integrations/registry/` — provider adapters moved out of the root flat package (`dadata_client.py`, `checko_client.py`); `backend/integrations/llm/` — LLM/provider transport moved out of the root flat package (`llm_fallback.py`, `routerai_client.py`) |
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
- Remaining root modules named in
  `ai/reports/TASK-PYTHON-ROOT-DIAGNOSTIC-20260902-report.md` (including
  `supplier_app.py`, `api/index.py`, `serp_parser.py`) are unmoved and
  require their own bounded, explicitly-scoped task.
