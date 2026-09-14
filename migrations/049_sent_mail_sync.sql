PRAGMA foreign_keys = ON;

-- Inbox keeps its legacy cursor for compatibility. Sent is intentionally a
-- separate stream: its UID sequence and UIDVALIDITY are independent.
CREATE TABLE IF NOT EXISTS mail_folder_sync_states (
    mail_account_id INTEGER NOT NULL,
    folder TEXT NOT NULL,
    uidvalidity TEXT,
    last_uid INTEGER NOT NULL DEFAULT 0,
    last_sync_at TEXT,
    last_imported_count INTEGER NOT NULL DEFAULT 0,
    last_linked_count INTEGER NOT NULL DEFAULT 0,
    last_error_at TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (mail_account_id, folder),
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

-- Only messages deliberately marked with [SD-…] arrive here. This avoids
-- importing unrelated personal Sent mail while preserving a durable record of
-- the external message and why it was linked.
CREATE TABLE IF NOT EXISTS mail_sent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    mail_account_id INTEGER NOT NULL,
    provider_message_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    in_reply_to TEXT,
    references_header TEXT,
    from_email TEXT NOT NULL,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    request_id INTEGER,
    match_status TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (mail_account_id, provider_message_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_sent_messages_request
    ON mail_sent_messages(workspace_id, request_id, sent_at DESC);
