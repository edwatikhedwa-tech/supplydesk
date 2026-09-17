---
document_id: DOC-TECH-INTEGRATIONS-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# External Integrations

| Integration | Client | Env var(s) | Purpose | Notes |
|---|---|---|---|---|
| Checko (company registry + finance) | `backend/integrations/registry/checko_client.py` | `CHECKO_KEY` | ИНН → registry status, ОГРН, finance history, risks | **Not configured in production** as of this audit's start (fixed mid-session for the migration-backfill work, but general enrichment on prod still depends on this being set). Paid API — pricing/limits not verified this session. |
| DaData | `backend/integrations/registry/dadata_client.py` | (see client) | Registry lookups, likely a fallback/alternate to Checko | Not deep-audited this pass |
| RouterAI (LLM) | `backend/integrations/llm/routerai_client.py` | `ROUTERAI_CHAT_KEY`, `ROUTERAI_CHAT_MODEL` (default `meta-llama/llama-3.3-70b-instruct`) | Powers the AI assistant chat | OpenAI-SDK-compatible; live per-model pricing fetched from RouterAI's own `/models` catalog at call time |
| XMLRiver (SERP) | `backend/integrations/search/xmlriver_client.py` | `XMLRIVER_USER`, `XMLRIVER_KEY` | Supplier discovery search | Missing credentials produce a request-level `error` status (`test_search_step_persists_configuration_error_instead_of_losing_job`), not a crash |
| Dellin (Деловые Линии) | `backend/integrations/logistics/dellin_client.py` | (see client) | Manual shipping-cost calculator | Live-verified against the real API 2026-09-04 |
| Yandex Mail (OAuth + IMAP/SMTP) | `mail/providers/yandex.py` | Yandex OAuth app credentials | Login, mail account connect, incoming/outgoing mail | Also usable as a login provider (`/api/auth/yandex/start`), separate from the mail-account connect flow |
| Mail.ru | `mail/providers/` (app-password based) | — | Mail account connect (incoming/outgoing) | App-password auth mode, not OAuth |
| Vercel Postgres / Supabase | `mail/repository.py` via `psycopg` | `DATABASE_URL` (Secret), `POSTGRES_URL*` (Config, same DB) | Production database | `DATABASE_URL` cannot be pulled back via `vercel env pull` (Secret-type); `POSTGRES_URL_NON_POOLING` (Config-type) points at the same DB and is pullable — used this session to run the local→prod enrichment backfill |

## Cost/compliance notes surfaced this audit

- Checko/DaData terms-of-service compliance for the cross-tenant `canonical_companies` cache
  (storing/re-serving their data across different workspaces) was explicitly **not verified**
  before that feature shipped (`docs/domain/SUPPLIER_MODEL.md` §4) — the owner accepted this as a
  risk for an internal, non-resold cache, not as a confirmed compliance fact.
- No pricing/limits for Checko or DaData were confirmed by this audit (out of scope; flag for a
  dedicated cost-awareness pass before relying on volume from either).
