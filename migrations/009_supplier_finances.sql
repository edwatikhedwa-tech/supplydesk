PRAGMA foreign_keys = ON;

-- Revenue/net profit for the last available reporting year, from Checko's
-- /v2/finances (Rosstat/GIR BO data). Separate table, not columns added to
-- global_supplier_registry (migration 008) — that table already exists in
-- deployed databases and SQLite has no "ALTER TABLE ADD COLUMN IF NOT
-- EXISTS"; this repo re-runs every migration on every startup (see
-- MailRepository.ensure_schema), so schema changes must stay purely
-- additive (new table) to remain safe to re-run. See
-- docs/suppliers-screen.md §5.1 and PROJECT_DOCUMENTATION.md §2.
CREATE TABLE IF NOT EXISTS global_supplier_finances (
    global_supplier_id INTEGER PRIMARY KEY REFERENCES global_suppliers(id) ON DELETE CASCADE,
    report_year INTEGER,
    revenue INTEGER,
    profit INTEGER,
    updated_at TEXT NOT NULL DEFAULT ''
);
