PRAGMA foreign_keys = ON;

-- Which inbound thread messages the buyer has actually opened. Without this,
-- the "Новые ответы" dashboard KPI could only count every inbound message
-- ever received and never go back down (see PROJECT_DOCUMENTATION.md §18,
-- 23 Aug audit finding). Separate table, not a column on mail_messages —
-- SQLite has no "ALTER TABLE ADD COLUMN IF NOT EXISTS" and this repo re-runs
-- every migration on every startup (see MailRepository.ensure_schema), so
-- schema changes must stay purely additive (new table) to remain safe to
-- re-run.
CREATE TABLE IF NOT EXISTS mail_message_reads (
    message_id INTEGER PRIMARY KEY REFERENCES mail_messages(id) ON DELETE CASCADE,
    read_at TEXT NOT NULL DEFAULT ''
);
