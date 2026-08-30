PRAGMA foreign_keys = ON;

-- A manual request association is deliberately separate from mail_threads and
-- mail_messages. The latter require a supplier and represent the actual mail
-- history; an unmatched sender can be linked to a request without inventing a
-- supplier or duplicating the original message in that history.
CREATE TABLE IF NOT EXISTS mail_inbox_request_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    inbox_message_id INTEGER NOT NULL UNIQUE,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER,
    source TEXT NOT NULL DEFAULT 'manual',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (inbox_message_id) REFERENCES mail_inbox_messages(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_inbox_request_links_request
    ON mail_inbox_request_links(workspace_id, request_id, active);
