PRAGMA foreign_keys = ON;

-- Cross-tenant company directory -- deliberately the ONE table in this file
-- with no workspace_id. Everything else about a supplier (suppliers,
-- global_suppliers, request_suppliers, mail_threads/mail_messages, notes,
-- tasks, prices, ratings) stays workspace-scoped as before; this table only
-- ever holds the general, public facts about a legal entity that any
-- SupplyDesk customer who independently discovers the same ИНН would
-- otherwise have to re-resolve from scratch (registry lookup, Checko call).
-- See docs/domain/SUPPLIER_MODEL.md §6 (DECISION-022) for the reasoning and
-- the explicit boundary on what belongs here vs. what must never leave a
-- workspace.
CREATE TABLE IF NOT EXISTS canonical_companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inn TEXT NOT NULL UNIQUE,
    ogrn TEXT NOT NULL DEFAULT '',
    legal_name TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT '',
    site TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    is_active INTEGER,
    registered_at TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_company_finance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_company_id INTEGER NOT NULL REFERENCES canonical_companies(id) ON DELETE CASCADE,
    report_year INTEGER NOT NULL,
    revenue BIGINT,
    profit BIGINT,
    updated_at TEXT NOT NULL,
    UNIQUE (canonical_company_id, report_year)
);

CREATE TABLE IF NOT EXISTS canonical_company_risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_company_id INTEGER NOT NULL REFERENCES canonical_companies(id) ON DELETE CASCADE,
    risk TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (canonical_company_id, risk)
);

CREATE INDEX IF NOT EXISTS idx_canonical_companies_inn ON canonical_companies(inn);
