PRAGMA foreign_keys = ON;

-- Iteration 3: campaign/content state is separate from the immutable I1
-- operation and target snapshot. It is provider-neutral and has no transport
-- side effects. Re-running migrations is safe because every object is guarded.
CREATE TABLE IF NOT EXISTS mail_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    mail_account_id INTEGER NOT NULL,
    operation_id INTEGER NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    rollout_stage INTEGER NOT NULL DEFAULT 1,
    stage_limit INTEGER NOT NULL DEFAULT 10,
    manual_stage_approval INTEGER NOT NULL DEFAULT 0,
    preflight_status TEXT NOT NULL DEFAULT 'pass',
    preflight_json TEXT NOT NULL DEFAULT '{}',
    provider_warning TEXT,
    pause_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    paused_at TEXT,
    stopped_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (mail_account_id) REFERENCES mail_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (operation_id) REFERENCES mail_send_operations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_campaign_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    operation_target_id INTEGER,
    job_id INTEGER,
    ordinal INTEGER NOT NULL,
    normalized_email TEXT NOT NULL,
    supplier_id INTEGER,
    status TEXT NOT NULL DEFAULT 'waiting',
    personalization_level INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,
    eligible_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (campaign_id, ordinal),
    UNIQUE (campaign_id, operation_target_id),
    UNIQUE (job_id),
    FOREIGN KEY (campaign_id) REFERENCES mail_campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (operation_target_id) REFERENCES mail_send_operation_targets(id) ON DELETE SET NULL,
    FOREIGN KEY (job_id) REFERENCES mail_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_campaigns_workspace_status
    ON mail_campaigns(workspace_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_mail_campaigns_account_status
    ON mail_campaigns(mail_account_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_mail_campaign_targets_campaign_state
    ON mail_campaign_targets(campaign_id, status, ordinal);
CREATE INDEX IF NOT EXISTS idx_mail_campaign_targets_job
    ON mail_campaign_targets(job_id, status);
CREATE INDEX IF NOT EXISTS idx_mail_campaign_targets_email
    ON mail_campaign_targets(normalized_email);
