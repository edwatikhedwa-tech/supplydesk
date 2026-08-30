PRAGMA foreign_keys = ON;

-- P0 safe cross-provider retry plans.  A plan is an operator-approved,
-- provider-switching ledger entry; it is never an instruction to call SMTP.
-- The original job/message/attempt IDs are historical references on purpose:
-- the source rows must remain immutable even if the retry is later accepted,
-- rejected, or becomes delivery-unknown.
CREATE TABLE IF NOT EXISTS mail_cross_provider_retries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    original_job_id INTEGER NOT NULL,
    original_message_id INTEGER NOT NULL,
    original_attempt_id INTEGER NOT NULL,
    target_provider TEXT NOT NULL CHECK (target_provider IN ('mailru', 'yandex')),
    target_mail_account_id INTEGER NOT NULL,
    normalized_recipient TEXT NOT NULL,
    retry_reason TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    selection_fingerprint TEXT NOT NULL,
    source_state_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    operation_id INTEGER,
    result_json TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, idempotency_key),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (target_mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (operation_id) REFERENCES mail_send_operations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_cross_provider_retries_source
    ON mail_cross_provider_retries(workspace_id, original_job_id, original_message_id, status);
CREATE INDEX IF NOT EXISTS idx_mail_cross_provider_retries_supplier
    ON mail_cross_provider_retries(request_id, supplier_id, normalized_recipient, status);
