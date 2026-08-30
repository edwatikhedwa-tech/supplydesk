PRAGMA foreign_keys = ON;

-- Iteration 1 outgoing-mail integrity. Companion tables are intentional:
-- this repository re-runs every migration on every startup and SQLite does
-- not provide a portable, repeatable ALTER TABLE ADD COLUMN IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS mail_send_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    mail_account_id INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL,
    fingerprint_schema_version INTEGER NOT NULL,
    expected_recipient_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'assembling',
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, idempotency_key),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_send_operation_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id INTEGER NOT NULL,
    normalized_email TEXT NOT NULL,
    supplier_id INTEGER NOT NULL,
    message_id_header TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT NOT NULL,
    resend_of_message_id INTEGER,
    message_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (operation_id, normalized_email),
    FOREIGN KEY (operation_id) REFERENCES mail_send_operations(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES mail_messages(id) ON DELETE SET NULL
);

-- A missing row is the explicit marker for a pre-iteration job. New jobs get
-- one row during creation/claim; it stores claim proof, the lease, and the
-- durable gate before SMTP DATA.
CREATE TABLE IF NOT EXISTS mail_job_integrity (
    job_id INTEGER PRIMARY KEY REFERENCES mail_jobs(id) ON DELETE CASCADE,
    operation_id INTEGER REFERENCES mail_send_operations(id) ON DELETE SET NULL,
    state_schema_version INTEGER NOT NULL,
    claim_owner TEXT,
    claim_token TEXT,
    lease_expires_at TEXT,
    irreversible_at TEXT,
    copy_status TEXT NOT NULL DEFAULT 'pending',
    copy_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mail_message_integrity (
    message_id INTEGER PRIMARY KEY REFERENCES mail_messages(id) ON DELETE CASCADE,
    state_schema_version INTEGER NOT NULL,
    resend_of_message_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mail_reply_integrity (
    reply_id INTEGER PRIMARY KEY REFERENCES mail_inbox_replies(id) ON DELETE CASCADE,
    state_schema_version INTEGER NOT NULL,
    irreversible_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- No foreign keys deliberately: this is the immutable snapshot that survives
-- request, supplier, and user cleanup. Current workspace ownership is checked
-- before insertion; IDs are historical values, never live references.
CREATE TABLE IF NOT EXISTS mail_delivery_resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    request_id INTEGER,
    supplier_id INTEGER,
    message_id INTEGER NOT NULL,
    recipient_email TEXT NOT NULL,
    message_id_header TEXT,
    delivery_state TEXT NOT NULL DEFAULT 'delivery_unknown',
    resolved_by INTEGER,
    resolved_at TEXT NOT NULL,
    comment TEXT,
    UNIQUE (message_id)
);

CREATE TABLE IF NOT EXISTS mail_runtime_controls (
    id INTEGER PRIMARY KEY,
    outgoing_enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

INSERT INTO mail_runtime_controls(id, outgoing_enabled, updated_at)
VALUES (1, 0, '')
ON CONFLICT(id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_mail_messages_outgoing_message_id
    ON mail_messages(mail_account_id, direction, message_id);
CREATE INDEX IF NOT EXISTS idx_mail_send_operations_status
    ON mail_send_operations(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_mail_send_operation_targets_message
    ON mail_send_operation_targets(message_id);
CREATE INDEX IF NOT EXISTS idx_mail_job_integrity_lease
    ON mail_job_integrity(lease_expires_at, irreversible_at);
CREATE INDEX IF NOT EXISTS idx_mail_delivery_resolutions_workspace
    ON mail_delivery_resolutions(workspace_id, resolved_at);
