PRAGMA foreign_keys = ON;

-- Free-text operator notes per request/supplier thread. Separate table, not
-- a column on mail_thread_user_metadata (migration 034, already deployed) —
-- SQLite has no "ALTER TABLE ADD COLUMN IF NOT EXISTS" and this repo re-runs
-- every migration on every startup (see MailRepository.ensure_schema), so
-- schema changes must stay purely additive (new table) to remain safe to
-- re-run. Same composite identity as mail_thread_user_metadata.
CREATE TABLE IF NOT EXISTS mail_thread_notes (
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id, request_id, supplier_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);
