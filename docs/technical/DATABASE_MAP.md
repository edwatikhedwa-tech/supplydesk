---
document_id: DOC-TECH-DATABASE-MAP-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Database Map

Final schema state after all 53 migration files (`migrations/001_mail_integration.sql` through
`migrations/052_task_reminder_delivery.sql`), reconstructed by reading every migration — not
migration history, the resulting table set. Supersedes `docs/data/README.md`, which is a
directory-purpose stub with no table content at all (not stale exactly — it simply never had
this content).

**Known migration-numbering issue:** two files both claim `026` (`026_mail_account_profiles.sql`
and `026_request_email_send_guards.sql`). Both apply (alphabetical glob order), both are
idempotent, neither is broken — flagged as `GAP-012`.

## Runtime: SQLite (dev) vs Postgres (production)

Confirmed: production sets `DATABASE_URL` → `mail/repository.py` connects via `psycopg`
(Postgres); local dev has no `DATABASE_URL` → SQLite file at `mail-data/supplier.sqlite3`.
`mail/db_compat.py` translates the SQLite-dialect SQL the repository is written in (row factory,
`BEGIN IMMEDIATE`→`BEGIN`, `last_insert_rowid()`→`LASTVAL()`, `COLLATE NOCASE`→`LOWER()`,
`INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`). This layer has already caused two real production
incidents this session (a SQLite-only migration guard, and the `COLLATE NOCASE` crash) — both
fixed, both were latent since the day they were written because Postgres had never actually been
exercised with a real `CHECKO_KEY` before. `vercel.json` excludes `*.db`/`*.sqlite3` from the
deployed bundle, consistent with Postgres being the only viable production store.

## Auth / workspace

| Table | Introduced | Purpose |
|---|---|---|
| `users`, `workspaces`, `workspace_members`, `sessions` | 001 | Core identity |
| `oauth_states` | 001 | OAuth CSRF-state tracking |
| `oauth_login_states` | 005 | Login-specific OAuth state |

## Requests / dashboard

| Table | Introduced | Purpose |
|---|---|---|
| `requests` | 001 | The заявка itself |
| `request_meta` | 002 | Status/progress/error |
| `request_positions` | 002 | Line items |
| `request_details` | 012 | Deadline |
| `request_search_jobs` | 017 | Durable lease/claim search queue |
| `request_search_options` | 018 | **Legacy, superseded but still read** (LEFT JOIN alongside its successor) |
| `request_search_config` | 020 | Current search-depth config |
| `request_email_references` | 048 | Public `SD-xxxx` email reference marker |
| `request_followup_settings` | 051 | Per-request SLA override |

## Suppliers — workspace-scoped identity

| Table | Introduced | Purpose |
|---|---|---|
| `suppliers` | 001 | Host/crawl identity, key `(workspace_id, external_key)` |
| `supplier_profiles` | 002 | ИНН/enrichment profile |
| `request_suppliers` | 002 | Request↔supplier match (positions, source, reason) |
| `blacklist_entries` | 002 | Per-workspace blacklist |
| `supplier_evidence` | 019 | Field-level evidence graph (currently only used for ИНН candidates) |
| `supplier_enrichment_jobs` | 019 | Durable per-stage retry queue |
| `supplier_inn_sources` | 021 | ИНН provenance |

## Suppliers — global card (ИНН-deduped, still workspace-scoped)

| Table | Introduced | Purpose |
|---|---|---|
| `global_suppliers` | 007 | ИНН-unique company card, `UNIQUE(workspace_id, inn)` |
| `global_supplier_links` | 007 | 1:1 `suppliers.id` → `global_suppliers.id` |
| `global_supplier_issues`, `request_supplier_ratings` | 007 | User feedback |
| `global_supplier_registry` | 008 | Registry facts (ОГРН, status, active, registered_at) |
| `global_supplier_finances` | 009 | Latest-year finance |
| `global_supplier_finance_history` | 014 | Historical finance |
| `global_supplier_risks` | 015 | Registry risk flags |
| `global_supplier_blacklist` | 010 | Global-card blacklist state |

## Suppliers — cross-tenant canonical (no `workspace_id`)

| Table | Introduced | Purpose |
|---|---|---|
| `canonical_companies` | 038 | ИНН-unique public facts, shared across all workspaces (DECISION-022) |
| `canonical_company_finance_history`, `canonical_company_risks` | 038 | Shared history/risk |
| `canonical_company_contacts` | 051 | Company email directory with assignment/status |
| `canonical_company_contact_signals` | 051 | Append-only trust signals (`workspace_confirmed`, `inbound_reply`, `official_source`, bounces) |
| `canonical_company_contact_promotions` | 051 | Append-only audit of preferred-status changes |

## Suppliers — workspace-private contact/classification layer

| Table | Introduced | Purpose |
|---|---|---|
| `workspace_supplier_contacts` | 045 | Manual contact persons, private/workspace visibility |
| `workspace_supplier_classifications` | 046 | Manual/registry/AI category labels, provenance kept distinct |
| `workspace_supplier_contact_events` | 051 | "Связаться" call-result history |
| `workspace_supplier_contact_overrides` | 051 | Workspace-preferred email override, append-only (superseded, not deleted) |

## Mail transport

`mail_accounts`(001) · `mail_threads`(001, unique `(workspace_id, request_id, supplier_id)`) ·
`mail_messages`(001) · `mail_attachments`(001) · `mail_jobs`(001) ·
`request_supplier_states`(001, per-request/supplier **delivery status**, distinct from
`request_suppliers`'s match metadata) · `mail_sync_states`(003) · `mail_inbox_messages`(004,
unmatched inbound, no request/supplier FK) · `mail_inbox_threads`/`mail_inbox_replies`(006) ·
`mail_message_reads`/`mail_inbox_message_reads`(011/032) · `mail_inbox_request_links`(031,
manual-link resolution) · `mail_account_profiles`(026, `+sent_sync_enabled` added by 050) ·
`mail_folder_sync_states`(049) · `mail_sent_messages`(049).

## Mail outgoing integrity / pacing / campaigns

`mail_send_operations`/`_targets`(022) · `mail_job_integrity`/`mail_message_integrity`/
`mail_reply_integrity`(022) · `mail_delivery_resolutions`(022) · `mail_runtime_controls`(022) ·
`mail_request_email_guards`(026) · `mail_account_outbound_state`/`mail_send_reservations`/
`mail_send_attempts`(023) · `mail_send_attempt_evidence`(025) · `mail_campaigns`/
`mail_campaign_targets`(024, **backing the campaign monitor page that has no v2 UI — GAP-001**) ·
`mail_database_identity`/`mail_runtime_sessions`/`mail_send_attempt_runtime`(027) ·
`mail_reconciled_outbound_events`(028) · `mail_continuation_plans`(029) ·
`mail_cross_provider_retries`(030).

## Mail UI metadata

`mail_thread_user_metadata`(034) · `mail_thread_notes`(035, per-user) ·
`mail_thread_workspace_notes`(041, shared) · `mail_thread_status`(039, the `conversation_status`
label) · `workspace_mail_templates`/`_attachments`(020).

## Tasks

`tasks`(037) · `task_details`(042) · `task_reminders`(043, rebuilt by 044/052) ·
`user_notification_settings`(052). **`tasks.supplier_id` FK points to `global_suppliers(id)`,
not `suppliers(id)`** — an easy misread worth calling out explicitly.

## AI / Logistics / Misc

`ai_chat_usage`(036) · `ai_conversations`/`ai_messages`(040) · `logistics_quotes`(033) ·
`audit_events`(002) · `search_result_sources`(013) · `support_conversations`/
`support_messages`(047).

## Postgres-only DDL

`016_finance_bigint.sql` widens finance columns to BIGINT — skipped on SQLite via an explicit
`-- postgres-only` marker `ensure_schema()` checks for.

## Key relationships to remember

- `suppliers` →(1:1 via `global_supplier_links`)→ `global_suppliers`. A `suppliers` row belongs
  to at most one global card.
- `global_suppliers` ↔ `canonical_companies`: **no FK** — joined implicitly by matching `inn`
  value only.
- `request_suppliers` (match metadata: positions, source, reason) vs `request_supplier_states`
  (delivery status, `last_message_id`) — two different concerns on the same composite key,
  deliberately split since migration 001 vs 002.
- `mail_inbox_messages` has no request/supplier FK by definition (that's what "unmatched" means)
  — linked later via `mail_inbox_request_links`.
- `workspace_supplier_contacts`/`_classifications`/`_contact_overrides` key off
  `global_supplier_id` (workspace-private); `canonical_company_contacts` keys off
  `canonical_company_id` (cross-tenant) — parallel, not FK-linked. See
  `docs/domain/SUPPLIER_MODEL.md` §6-7 for the full boundary rationale.

## Orphan check

Spot-checked less-obvious tables (`audit_events`, `request_supplier_ratings`,
`mail_thread_workspace_notes`, `global_supplier_issues`, `search_result_sources`,
`mail_reconciled_outbound_events`, `workspace_supplier_contact_overrides`,
`canonical_company_contact_promotions/signals`, `support_conversations/messages`,
`logistics_quotes`, `mail_database_identity`, `mail_runtime_sessions`) — **no confirmed orphans**,
all have live call sites. The only "superseded but not removed" table is
`request_search_options` (018), whose data was copied forward into `request_search_config` (020)
in the same migration; `mail/repository.py` still reads both.
