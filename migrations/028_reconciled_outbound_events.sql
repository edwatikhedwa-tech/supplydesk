PRAGMA foreign_keys = ON;

-- Provider-neutral evidence for a historical outbound acceptance which is not
-- copied into the live job/message/attempt ledger.  evidence_sha256 is the
-- idempotency key for a verified evidence record.
CREATE TABLE IF NOT EXISTS mail_reconciled_outbound_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    normalized_recipient TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('accepted')),
    rfc_message_id TEXT NOT NULL,
    accepted_at TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    evidence_reference TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    operator_reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_reconciled_outbound_target
    ON mail_reconciled_outbound_events(request_id, supplier_id, normalized_recipient);
