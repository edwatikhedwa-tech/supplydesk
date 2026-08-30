-- Per-request search configuration.
--
-- Kept as a separate table because this project re-runs migrations on every
-- start and must support both SQLite and PostgreSQL without a non-idempotent
-- ALTER TABLE on the existing request_meta table.
CREATE TABLE IF NOT EXISTS request_search_options (
    request_id INTEGER PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
    search_depth INTEGER NOT NULL DEFAULT 1,
    CHECK (search_depth IN (1, 3, 5))
);
