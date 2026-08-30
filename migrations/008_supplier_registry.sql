PRAGMA foreign_keys = ON;

-- Registry facts from Checko (age/status/OGRN) for the ИНН-keyed CRM card
-- (frontend/src/components/suppliers/SupplierPanel.tsx). Kept as a separate
-- table, not columns on global_suppliers, because SQLite has no
-- "ALTER TABLE ADD COLUMN IF NOT EXISTS" and this repo re-runs every
-- migration on every startup (see MailRepository.ensure_schema) — schema
-- changes here must stay purely additive (new table) to remain safe to
-- re-run. See Documents/28-8/PROJECT_DOCUMENTATION.md §2 (migrations) and
-- Documents/28-8/suppliers-screen.md.
--
-- Deliberately does NOT include revenue/profit: checko_client.py only calls
-- Checko's company-registry endpoint, never a financial-statements endpoint —
-- there is no source for those two fields anywhere in this codebase today.
CREATE TABLE IF NOT EXISTS global_supplier_registry (
    global_supplier_id INTEGER PRIMARY KEY REFERENCES global_suppliers(id) ON DELETE CASCADE,
    ogrn TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    is_active INTEGER,
    registered_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
