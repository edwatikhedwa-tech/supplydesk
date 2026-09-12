PRAGMA foreign_keys = ON;

-- A support conversation is intentionally independent from mail threads and
-- supplier correspondence: it represents a user request to SupplyDesk.
CREATE TABLE IF NOT EXISTS support_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    linked_request_id INTEGER,
    category TEXT NOT NULL DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'in_progress', 'waiting_user', 'resolved')),
    current_url TEXT NOT NULL DEFAULT '',
    current_section TEXT NOT NULL DEFAULT '',
    browser TEXT NOT NULL DEFAULT '',
    app_version TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (linked_request_id) REFERENCES requests(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_support_conversations_user_updated
    ON support_conversations(workspace_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('user', 'support')),
    text TEXT NOT NULL DEFAULT '',
    attachment_filename TEXT NOT NULL DEFAULT '',
    attachment_mime_type TEXT NOT NULL DEFAULT '',
    attachment_content BLOB,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES support_conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_support_messages_conversation_created
    ON support_messages(conversation_id, created_at ASC, id ASC);
