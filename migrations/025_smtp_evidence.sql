PRAGMA foreign_keys = ON;

-- P0 SMTP evidence: keep bounded, credential-free transport facts separate
-- from the stable attempt outcome and the user-facing error message.  The
-- table is provider-neutral and may be populated with NULL when a provider
-- cannot expose a particular field.
CREATE TABLE IF NOT EXISTS mail_send_attempt_evidence (
    attempt_id INTEGER PRIMARY KEY,
    smtp_stage TEXT,
    smtp_code INTEGER,
    smtp_enhanced_status TEXT,
    provider_response_safe TEXT,
    exception_class TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (attempt_id) REFERENCES mail_send_attempts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mail_send_attempt_evidence_stage
    ON mail_send_attempt_evidence(smtp_stage, updated_at);
