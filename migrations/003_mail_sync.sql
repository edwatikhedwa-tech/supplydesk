CREATE TABLE IF NOT EXISTS mail_sync_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_account_id INTEGER NOT NULL UNIQUE,
    folder TEXT NOT NULL DEFAULT 'INBOX',
    uidvalidity TEXT,
    last_uid INTEGER NOT NULL DEFAULT 0,
    last_sync_at TEXT,
    last_imported_count INTEGER NOT NULL DEFAULT 0,
    last_unmatched_count INTEGER NOT NULL DEFAULT 0,
    last_error_at TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_sync_states_account ON mail_sync_states(mail_account_id);
