PRAGMA foreign_keys = ON;

-- Initial outreach is unique per request and normalized recipient.  This is
-- deliberately a separate guard from mail_messages: an explicit repeat is
-- allowed by the service without weakening the default invariant.
CREATE TABLE IF NOT EXISTS mail_request_email_guards (
    workspace_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    normalized_email TEXT NOT NULL,
    operation_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, request_id, normalized_email),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (operation_id) REFERENCES mail_send_operations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_request_email_guards_operation
    ON mail_request_email_guards(operation_id);
