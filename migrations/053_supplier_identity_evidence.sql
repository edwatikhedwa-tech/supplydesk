PRAGMA foreign_keys = ON;

-- Supplier Identity Evidence (EDW-14 / Documentation Pack V1.2.4, GAP-003).
--
-- Why a contact/identifier is believed to belong to a supplier card, and
-- WHERE that belief came from. Three concerns stay separate on purpose:
--   * request-level association  -> request_id <> 0 (this address was used for
--     this supplier in this request);
--   * supplier identity          -> the `suppliers` row itself; only ever
--     reused/merged from evidence with decision='linked' AND strength='strong';
--   * contact evidence           -> the rows below.
-- A weak signal (e.g. mailbox name resembling the site name) is stored as
-- decision='candidate' and NEVER makes two cards one company on its own.
--
-- Additive companion table (this repo replays every migration on every start,
-- see migrations/051_contact_intelligence.sql). Append-only: a correction sets
-- reverted_by_id / supersedes_id instead of deleting history.
-- request_id = 0 means "not tied to one request" (no FK on purpose).
CREATE TABLE IF NOT EXISTS supplier_identity_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL CHECK (kind IN ('email', 'domain', 'inn', 'name', 'phone')),
    value TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'rfq_sent', 'inbound_reply', 'manual_confirmed',
        'official_source', 'import', 'name_token_similarity'
    )),
    source_id TEXT NOT NULL DEFAULT '',
    strength TEXT NOT NULL CHECK (strength IN ('strong', 'medium', 'weak')),
    decision TEXT NOT NULL CHECK (decision IN ('linked', 'candidate', 'conflict', 'rejected')),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_verified_at TEXT NOT NULL,
    supersedes_id INTEGER,
    reverted_by_id INTEGER,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

-- One row per (card, identifier, source): re-recording the same fact is a no-op.
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_identity_evidence_fact
    ON supplier_identity_evidence(workspace_id, supplier_id, kind, value, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_supplier_identity_evidence_lookup
    ON supplier_identity_evidence(workspace_id, kind, value, decision);
