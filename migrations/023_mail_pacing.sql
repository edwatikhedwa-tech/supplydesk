PRAGMA foreign_keys = ON;

-- Iteration 2: one persisted limiter state per mail account.  No historical
-- mail job is changed or requeued by this migration; rows are created lazily
-- when a worker first needs to reserve a send slot.
CREATE TABLE IF NOT EXISTS mail_account_outbound_state (
    mail_account_id INTEGER PRIMARY KEY,
    next_send_not_before TEXT,
    cooldown_until TEXT,
    cooldown_reason TEXT,
    cooldown_level INTEGER NOT NULL DEFAULT 0,
    breaker_state TEXT NOT NULL DEFAULT 'closed',
    breaker_reason TEXT,
    breaker_until TEXT,
    failure_window_started_at TEXT,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_failure_at TEXT,
    last_error TEXT,
    last_operation_id INTEGER,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_send_reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_account_id INTEGER NOT NULL,
    owner_type TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    reservation_token TEXT NOT NULL UNIQUE,
    reserved_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    scheduled_not_before TEXT,
    status TEXT NOT NULL DEFAULT 'reserved',
    started_at TEXT,
    released_at TEXT,
    consumed_at TEXT,
    release_reason TEXT,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_send_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    message_id INTEGER,
    reply_id INTEGER,
    mail_account_id INTEGER NOT NULL,
    reservation_token TEXT,
    attempt_number INTEGER NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    outcome TEXT NOT NULL,
    provider_classification TEXT,
    irreversible_reached INTEGER NOT NULL DEFAULT 0,
    cooldown_triggered INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT,
    sanitized_error TEXT,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_account_outbound_cooldown
    ON mail_account_outbound_state(cooldown_until, breaker_state, breaker_until);
CREATE INDEX IF NOT EXISTS idx_mail_send_reservations_account_status
    ON mail_send_reservations(mail_account_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_mail_send_reservations_owner
    ON mail_send_reservations(owner_type, owner_id, status);
CREATE INDEX IF NOT EXISTS idx_mail_send_attempts_account_started
    ON mail_send_attempts(mail_account_id, started_at);
CREATE INDEX IF NOT EXISTS idx_mail_send_attempts_job
    ON mail_send_attempts(job_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_mail_send_attempts_message
    ON mail_send_attempts(message_id, attempt_number);
