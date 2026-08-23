PRAGMA foreign_keys = ON;

-- A reply thread for inbox mail that has no linked request/supplier (an
-- unsolicited sender, not someone matched to a заявка). Kept separate from
-- mail_threads/mail_messages, whose request_id/supplier_id are NOT NULL by
-- design: SQLite has no ALTER COLUMN, and this repo re-runs every migration
-- on every startup (see MailRepository.ensure_schema), so schema changes here
-- must stay purely additive to remain safe to re-run.
CREATE TABLE IF NOT EXISTS mail_inbox_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    mail_account_id INTEGER NOT NULL,
    peer_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    last_message_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (workspace_id, mail_account_id, peer_email),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_inbox_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_thread_id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    mail_account_id INTEGER NOT NULL,
    provider_message_id TEXT,
    message_id TEXT,
    in_reply_to TEXT,
    references_header TEXT,
    from_email TEXT NOT NULL,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sending',
    error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    FOREIGN KEY (inbox_thread_id) REFERENCES mail_inbox_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_inbox_replies_thread ON mail_inbox_replies(inbox_thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_mail_inbox_threads_lookup ON mail_inbox_threads(workspace_id, mail_account_id, peer_email);
