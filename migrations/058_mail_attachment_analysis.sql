PRAGMA foreign_keys = ON;

-- Attachment Intelligence (EDW-35): one analysis per attachment and analysis version, a ledger of every model
-- call, and facts with provenance. Additive companion tables; the incoming attachment bytes stay in mail_attachments.
--
-- mail_attachment_analyses   result of reading ONE attachment. The unique key (workspace, attachment, version) is the
--                            idempotency key. reused_from points at the analysis whose result was reused when the same
--                            bytes (sha256) were already analysed under the same version: zero parsing, zero model calls.
-- mail_attachment_facts      extracted lines with a locator (page and box, sheet and row, table and row, paragraph) and the
--                            match to a request position. A fact never changes the request or the supplier by itself.
-- mail_attachment_ai_calls   ledger: model, tokens, provider-reported cost, latency of every vision or text call.
CREATE TABLE IF NOT EXISTS mail_attachment_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    attachment_id INTEGER NOT NULL,
    filename TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    status TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    parser TEXT NOT NULL DEFAULT '',
    needs_ocr INTEGER NOT NULL DEFAULT 0,
    is_quote INTEGER NOT NULL DEFAULT 0,
    manual_review INTEGER NOT NULL DEFAULT 0,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    terms_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    reused_from INTEGER,
    ocr_pages INTEGER NOT NULL DEFAULT 0,
    ai_calls INTEGER NOT NULL DEFAULT 0,
    cost_rub REAL NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_attachment_analyses_key
    ON mail_attachment_analyses(workspace_id, attachment_id, analysis_version);

CREATE INDEX IF NOT EXISTS idx_mail_attachment_analyses_sha
    ON mail_attachment_analyses(workspace_id, sha256, analysis_version);

CREATE INDEX IF NOT EXISTS idx_mail_attachment_analyses_message
    ON mail_attachment_analyses(workspace_id, message_id);

CREATE TABLE IF NOT EXISTS mail_attachment_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    attachment_analysis_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    request_id INTEGER,
    supplier_id INTEGER,
    position INTEGER NOT NULL DEFAULT 0,
    data_json TEXT NOT NULL,
    loc_json TEXT NOT NULL,
    source_text TEXT NOT NULL DEFAULT '',
    match_json TEXT NOT NULL DEFAULT '{}',
    review TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (attachment_analysis_id) REFERENCES mail_attachment_analyses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_attachment_facts_message
    ON mail_attachment_facts(workspace_id, message_id);

CREATE TABLE IF NOT EXISTS mail_attachment_ai_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    attachment_analysis_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_rub REAL,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (attachment_analysis_id) REFERENCES mail_attachment_analyses(id) ON DELETE CASCADE
);
