PRAGMA foreign_keys = ON;

-- Presentation metadata belongs to the operator, not to the mail transport
-- state. The request/supplier pair is the durable thread identity in this
-- product (mail_threads has the same unique constraint per workspace).
CREATE TABLE IF NOT EXISTS mail_thread_user_metadata (
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    is_important INTEGER NOT NULL DEFAULT 0 CHECK (is_important IN (0, 1)),
    priority INTEGER CHECK (priority IN (1, 2, 3) OR priority IS NULL),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id, request_id, supplier_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_thread_user_metadata_thread
    ON mail_thread_user_metadata(workspace_id, user_id, request_id, supplier_id);
