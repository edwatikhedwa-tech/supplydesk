PRAGMA foreign_keys = ON;

-- A provider-switch continuation is an explicit operator operation.  The
-- selected target snapshot is immutable; result_json only records the
-- atomic preparation result needed for idempotent replays.
CREATE TABLE IF NOT EXISTS mail_continuation_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    provider_type TEXT NOT NULL CHECK (provider_type IN ('yandex', 'mailru')),
    mail_account_id INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL,
    selection_fingerprint TEXT NOT NULL,
    source_state_json TEXT NOT NULL,
    selected_targets_json TEXT NOT NULL,
    effective_targets_json TEXT NOT NULL,
    skipped_targets_json TEXT NOT NULL,
    limit_count INTEGER NOT NULL CHECK (limit_count > 0),
    operation_id INTEGER,
    result_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'empty')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, idempotency_key),
    UNIQUE (operation_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES mail_campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (operation_id) REFERENCES mail_send_operations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_continuation_plans_campaign
    ON mail_continuation_plans(campaign_id, created_at);
