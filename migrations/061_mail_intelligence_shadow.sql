PRAGMA foreign_keys = ON;

-- Shadow mode for the Mail Intelligence canary (EDW-40). While downstream_enabled = 0 the canary only OBSERVES: facts and analyses are stored,
-- but nothing that changes business state runs (no quote_received event, no follow-up closing, no request/supplier/contact change).
--
-- mail_intelligence_canary_flags  per workspace: downstream_enabled is 0 until the owner releases shadow mode after the exit criteria are met.
-- mail_intelligence_audit         one safe audit record per request-scoped price fact and per automatic request match (and per suppressed
--                                 downstream event): ids, extracted value, source span or file location, match method, evidence, review state.
--                                 The letter text is NOT copied here; a reviewer reads it locally through fact_id. Reports pushed to GitHub contain counts only.
CREATE TABLE IF NOT EXISTS mail_intelligence_canary_flags (
    workspace_id INTEGER PRIMARY KEY,
    downstream_enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_intelligence_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    message_kind TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    request_id INTEGER,
    supplier_id INTEGER,
    fact_kind TEXT NOT NULL DEFAULT '',
    fact_id INTEGER NOT NULL DEFAULT 0,
    value_json TEXT NOT NULL DEFAULT '{}',
    span_json TEXT NOT NULL DEFAULT '{}',
    match_method TEXT NOT NULL DEFAULT '',
    confidence TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    review_state TEXT NOT NULL DEFAULT 'pending',
    review_reason TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_intelligence_audit_key
    ON mail_intelligence_audit(workspace_id, kind, message_kind, message_id, fact_kind, fact_id);

CREATE INDEX IF NOT EXISTS idx_mail_intelligence_audit_review
    ON mail_intelligence_audit(workspace_id, kind, review_state);
