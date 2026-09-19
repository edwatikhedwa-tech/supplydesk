PRAGMA foreign_keys = ON;

-- Mail Intelligence Core (Iteration 2, EDW-7): one analysis per (message, content, version), a ledger of
-- every model call, a fact store with provenance, and downstream events. Additive companion tables.
--
-- mail_analyses      the unified result of analysing ONE incoming message. The unique key is the
--                    idempotency key: the same unchanged message under the same analysis version is
--                    never analysed twice (0 extra model calls).
-- mail_ai_runs       ledger: one row per decision stage, including the rule-only stages (provider is
--                    rules, cost 0), so the share of mail handled without AI is measurable.
-- mail_facts         extracted facts with provenance: the verbatim source quote and its offsets in the
--                    normalised message text. State is proposed, superseded or rejected; a fact never
--                    changes the request or the supplier by itself.
-- mail_analysis_events  downstream events, one per (analysis, type), consumed without any model call.
CREATE TABLE IF NOT EXISTS mail_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    message_kind TEXT NOT NULL CHECK (message_kind IN ('mail_message', 'inbox_message')),
    message_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'final', 'needs_review', 'pending_retry')),
    stage TEXT NOT NULL DEFAULT 'rules' CHECK (stage IN ('rules', 'cheap', 'strong')),
    message_type TEXT NOT NULL DEFAULT '',
    is_relevant INTEGER NOT NULL DEFAULT 1,
    match_method TEXT NOT NULL DEFAULT '',
    request_id INTEGER,
    supplier_id INTEGER,
    candidates_json TEXT NOT NULL DEFAULT '[]',
    result_json TEXT NOT NULL DEFAULT '{}',
    review_reason TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    reuse_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_analyses_idempotency
    ON mail_analyses(workspace_id, message_kind, message_id, content_hash, analysis_version);

CREATE INDEX IF NOT EXISTS idx_mail_analyses_message
    ON mail_analyses(workspace_id, message_kind, message_id);

CREATE TABLE IF NOT EXISTS mail_ai_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    analysis_id INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('classify', 'extract', 'extract_escalation', 'reprocess')),
    stage TEXT NOT NULL CHECK (stage IN ('rules', 'cheap', 'strong')),
    provider TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    endpoint TEXT NOT NULL DEFAULT '',
    cost_rub REAL,
    cost_source TEXT NOT NULL DEFAULT 'none' CHECK (cost_source IN ('none', 'catalog_estimate', 'provider_reported')),
    latency_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('ok', 'invalid_output', 'error', 'skipped_budget', 'not_needed')),
    error TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    repeat_of_same_content INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES mail_analyses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_ai_runs_day
    ON mail_ai_runs(workspace_id, created_at);

CREATE TABLE IF NOT EXISTS mail_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    analysis_id INTEGER NOT NULL,
    message_kind TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    request_id INTEGER,
    supplier_id INTEGER,
    kind TEXT NOT NULL CHECK (kind IN ('quote_item')),
    position INTEGER NOT NULL DEFAULT 0,
    data_json TEXT NOT NULL,
    source_quote TEXT NOT NULL,
    source_start INTEGER NOT NULL,
    source_end INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'superseded', 'rejected')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES mail_analyses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_facts_lookup
    ON mail_facts(workspace_id, request_id, supplier_id, state);

CREATE TABLE IF NOT EXISTS mail_analysis_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    analysis_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('quote_received')),
    payload_json TEXT NOT NULL DEFAULT '{}',
    handled_at TEXT,
    handler_result TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES mail_analyses(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_analysis_events_once
    ON mail_analysis_events(analysis_id, event_type);
