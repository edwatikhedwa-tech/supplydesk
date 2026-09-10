PRAGMA foreign_keys = ON;

-- User-facing conversation status for a supplier within one заявка (В
-- работе / Отложено / Отклонено). Deliberately NOT a column on
-- mail_thread_user_metadata (which already exists in deployed databases) --
-- SQLite has no "ALTER TABLE ADD COLUMN IF NOT EXISTS" and this repo
-- re-runs every migration on every startup (see
-- MailRepository.ensure_schema), so schema changes must stay purely
-- additive (new table), same convention as migrations/012 and /035.
--
-- Deliberately separate from blacklist_entries: this status is per
-- (workspace, user, request, supplier) -- it never suppresses sending and
-- never affects any other заявка the same supplier is part of. NULL/absent
-- row means "no status" (the default, third-priority bucket in the UI).
CREATE TABLE IF NOT EXISTS mail_thread_status (
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'deferred', 'rejected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id, request_id, supplier_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_thread_status_lookup
    ON mail_thread_status(workspace_id, user_id, request_id, supplier_id);
