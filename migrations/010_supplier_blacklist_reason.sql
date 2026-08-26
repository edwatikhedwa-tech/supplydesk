PRAGMA foreign_keys = ON;

-- Why a company is on the CRM blacklist (relationship_status='blacklisted')
-- and when. Separate table, not columns on global_suppliers (migration 007,
-- already deployed) — SQLite has no "ALTER TABLE ADD COLUMN IF NOT EXISTS"
-- and this repo re-runs every migration on every startup (see
-- MailRepository.ensure_schema), so schema changes must stay purely
-- additive (new table) to remain safe to re-run.
CREATE TABLE IF NOT EXISTS global_supplier_blacklist (
    global_supplier_id INTEGER PRIMARY KEY REFERENCES global_suppliers(id) ON DELETE CASCADE,
    reason TEXT NOT NULL DEFAULT '',
    blacklisted_at TEXT NOT NULL DEFAULT ''
);
