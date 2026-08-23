CREATE TABLE IF NOT EXISTS mail_inbox_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    mail_account_id INTEGER NOT NULL,
    provider_message_id TEXT NOT NULL,
    message_id TEXT,
    in_reply_to TEXT,
    references_header TEXT,
    from_email TEXT NOT NULL,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT NOT NULL,
    received_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unmatched',
    created_at TEXT NOT NULL,
    UNIQUE (mail_account_id, provider_message_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_inbox_workspace_received ON mail_inbox_messages(workspace_id, received_at);
