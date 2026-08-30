PRAGMA foreign_keys = ON;

-- Mail provider-specific settings and secrets live separately from the
-- legacy OAuth columns in mail_accounts.  The credential reference is a
-- non-secret identifier; the encrypted value is never returned by API code.
CREATE TABLE IF NOT EXISTS mail_account_profiles (
    account_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    auth_mode TEXT NOT NULL CHECK (auth_mode IN ('oauth', 'app_password')),
    credential_reference TEXT NOT NULL UNIQUE,
    credential_encrypted TEXT,
    outgoing_enabled INTEGER NOT NULL DEFAULT 0,
    incoming_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_account_profiles_auth_mode
    ON mail_account_profiles(auth_mode, updated_at);
