PRAGMA foreign_keys = ON;

-- Separate from oauth_states: a login flow starts before any session exists,
-- so the row cannot be bound to a session/user/workspace yet.
CREATE TABLE IF NOT EXISTS oauth_login_states (
    state_hash TEXT PRIMARY KEY,
    code_verifier TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_oauth_login_states_expiry ON oauth_login_states(expires_at);
