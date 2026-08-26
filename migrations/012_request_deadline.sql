PRAGMA foreign_keys = ON;

-- Procurement deadline for a заявка. Separate table, not a column added to
-- `requests` (which already exists in deployed databases) — SQLite has no
-- "ALTER TABLE ADD COLUMN IF NOT EXISTS" and this repo re-runs every
-- migration on every startup (see MailRepository.ensure_schema), so schema
-- changes must stay purely additive (new table) to remain safe to re-run.
CREATE TABLE IF NOT EXISTS request_details (
    request_id INTEGER PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
    deadline TEXT NOT NULL DEFAULT ''
);
