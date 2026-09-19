PRAGMA foreign_keys = ON;

-- Asynchronous mail analysis (EDW-38). Sync only persists and enqueues; a worker reads, calls a model when needed and stores facts.
--
-- mail_analysis_jobs      one job per (workspace, message, job type, analysis version): the unique key deduplicates enqueueing.
--                         A job is claimed with a token and a lease; an expired lease makes it claimable again (crash recovery).
-- mail_ai_reply_cache     every model reply is stored the moment it arrives, before anything else is written. A retry after a crash
--                         replays the stored reply instead of paying for a second call. cost_rub here is the real spend.
-- mail_inbox_attachments  attachments of letters that could not be linked to a request yet. They are kept, not read: extraction waits for
--                         request resolution and moves the files to the linked message.
-- mail_fact_bindings      audit of every binding of a source fact to a request (rebinding after a manual link makes no model call).
CREATE TABLE IF NOT EXISTS mail_analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    message_kind TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    job_type TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 4,
    claim_token TEXT,
    worker_id TEXT NOT NULL DEFAULT '',
    lease_until TEXT,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT NOT NULL DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_analysis_jobs_key
    ON mail_analysis_jobs(workspace_id, message_kind, message_id, job_type, analysis_version);

CREATE INDEX IF NOT EXISTS idx_mail_analysis_jobs_pick
    ON mail_analysis_jobs(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS mail_ai_reply_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    request_key TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    reply_json TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_rub REAL,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    replays INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_ai_reply_cache_key
    ON mail_ai_reply_cache(workspace_id, request_key);

CREATE TABLE IF NOT EXISTS mail_inbox_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_message_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content BLOB NOT NULL,
    FOREIGN KEY (inbox_message_id) REFERENCES mail_inbox_messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_inbox_attachments_message
    ON mail_inbox_attachments(inbox_message_id);

CREATE TABLE IF NOT EXISTS mail_fact_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    fact_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER,
    method TEXT NOT NULL,
    bound_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (fact_id) REFERENCES mail_facts(id) ON DELETE CASCADE
);
