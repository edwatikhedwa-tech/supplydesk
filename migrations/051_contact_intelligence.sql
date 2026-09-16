PRAGMA foreign_keys = ON;

-- needs_followup / self-updating contacts (SUP-030). Companion tables only --
-- see migrations/012_request_deadline.sql for why: this repo replays every
-- migration file on every process start (MailRepository.ensure_schema) and
-- SQLite has no portable "ALTER TABLE ADD COLUMN IF NOT EXISTS", so schema
-- growth must stay additive. needs_followup itself is never stored -- it is
-- computed at read time (mail/contact_intelligence.py::annotate_needs_followup)
-- from this table plus mail_messages/request_supplier_states, the same way
-- threadResponseStatus is derived client-side (frontend-v2/src/lib/derive.ts).

-- Per-request configurable SLA before a "Ждём ответа" thread is flagged
-- needs_followup. Missing row = default (2 business days).
CREATE TABLE IF NOT EXISTS request_followup_settings (
    request_id INTEGER PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
    sla_business_days INTEGER NOT NULL DEFAULT 2,
    updated_at TEXT NOT NULL
);

-- One workspace's own log of "Связаться" contact-result actions on a
-- needs_followup conversation. Purely an additional history record -- never
-- touches transport/delivery state (request_supplier_states) or the
-- per-user workflow status (mail_thread_status, migrations/039).
CREATE TABLE IF NOT EXISTS workspace_supplier_contact_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    global_supplier_id INTEGER,
    user_id INTEGER NOT NULL,
    result TEXT NOT NULL CHECK (result IN (
        'not_reached', 'contact_confirmed', 'new_email_provided',
        'call_back_later', 'supplier_declines'
    )),
    comment TEXT NOT NULL DEFAULT '',
    new_email TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (global_supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_supplier_contact_events_thread
    ON workspace_supplier_contact_events(workspace_id, request_id, supplier_id, created_at);

-- Workspace-scoped preferred-contact OVERRIDE. Takes effect immediately and
-- only within this workspace (AC-02/AC-03) -- independent of the cross-tenant
-- consensus below. Append-only: a new preference supersedes the previous row
-- (superseded_at set), never UPDATEd away, so this workspace's own contact
-- history is never lost (AC-07 at the workspace level).
CREATE TABLE IF NOT EXISTS workspace_supplier_contact_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    global_supplier_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'rfq' CHECK (purpose IN
        ('rfq', 'sales', 'tender', 'general', 'personal', 'unknown')),
    source_event_id INTEGER,
    set_by_user_id INTEGER NOT NULL,
    basis TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    superseded_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (global_supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (source_event_id) REFERENCES workspace_supplier_contact_events(id) ON DELETE SET NULL,
    FOREIGN KEY (set_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_supplier_contact_overrides_current
    ON workspace_supplier_contact_overrides(workspace_id, global_supplier_id, purpose, superseded_at);

-- ---------------------------------------------------------------------
-- Cross-tenant layer, extending canonical_companies (DECISION-022,
-- migrations/038_canonical_companies.sql; see docs/domain/SUPPLIER_MODEL.md
-- §6 for the boundary this must respect and DECISION-024 for why this
-- feature's consensus has to live here rather than on the per-workspace
-- global_suppliers.id -- a different workspace has a different row/id for
-- the same real company, so "3 independent workspaces" cannot be counted
-- there. Keyed by canonical_company_id (ИНН). workspace_id is retained on
-- signals ONLY to deduplicate independent confirmations -- it is never
-- surfaced to another workspace (see mail/contact_intelligence.py).
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS canonical_company_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_company_id INTEGER NOT NULL REFERENCES canonical_companies(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'unknown' CHECK (purpose IN
        ('rfq', 'sales', 'tender', 'general', 'personal', 'unknown')),
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN
        ('preferred', 'secondary', 'deprecated', 'candidate')),
    last_verified_at TEXT,
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (canonical_company_id, email)
);

CREATE INDEX IF NOT EXISTS idx_canonical_company_contacts_company
    ON canonical_company_contacts(canonical_company_id, status);

-- Append-only -- never UPDATEd or DELETEd. This IS the historical evidence
-- trail behind every promotion/demotion decision ("все изменения контактов
-- историчны"). source is a natural idempotency key (e.g. "message:123",
-- "contact_event:45") so re-syncing the same real-world event never
-- double-counts it as two independent confirmations.
CREATE TABLE IF NOT EXISTS canonical_company_contact_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_company_id INTEGER NOT NULL REFERENCES canonical_companies(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN (
        'workspace_confirmed', 'inbound_reply', 'official_source',
        'hard_bounce', 'soft_bounce'
    )),
    strength TEXT NOT NULL CHECK (strength IN ('strong', 'weak')),
    workspace_id INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    basis TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    UNIQUE (canonical_company_id, email, signal_type, source)
);

CREATE INDEX IF NOT EXISTS idx_canonical_company_contact_signals_lookup
    ON canonical_company_contact_signals(canonical_company_id, email, signal_type, created_at);

-- Explainable audit trail of each computed promotion/demotion, so the
-- supplier card can say *why* a contact is preferred (AC-09) without ever
-- exposing which workspaces contributed -- only the count and whether a
-- strong signal was present.
CREATE TABLE IF NOT EXISTS canonical_company_contact_promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_company_id INTEGER NOT NULL REFERENCES canonical_companies(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    confirming_workspace_count INTEGER NOT NULL,
    had_strong_signal INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_canonical_company_contact_promotions_company
    ON canonical_company_contact_promotions(canonical_company_id, email, decided_at);
