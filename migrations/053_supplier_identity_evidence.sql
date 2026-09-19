PRAGMA foreign_keys = ON;

-- Supplier Identity Evidence (EDW-14 / Documentation Pack V1.2.4 + V1.3, GAP-003).
--
-- THE single store of PRIMARY facts about a contact (email) of a supplier card
-- and where each fact came from. Everything else is derived from it:
--   * identity reuse for a new send  -> assertion='ownership' AND strength='strong'
--                                       AND state='confirmed';
--   * cross-tenant contact quality   -> canonical_company_contact_* (mail/contact_intelligence.py)
--                                       is a PROJECTION of these rows, rebuilt by one
--                                       reconcile function (see migration 054).
--
-- What a row asserts (`assertion`):
--   association  -> request-level only ("we sent an RFQ to this address for this
--                   supplier card in this request"). NEVER proves that the address
--                   belongs to the legal entity, so it is never used to reuse an identity.
--   ownership    -> "this address belongs to this supplier".
--   deliverability -> bounce facts (negative signal about the address, not identity).
--
-- Lifecycle (`state`): candidate -> confirmed | rejected ; confirmed -> revoked.
-- `ambiguous` is not stored: it is derived when one address has confirmed strong
-- ownership evidence for more than one supplier card.
--
-- Additive companion table (this repo replays every migration on every start,
-- see migrations/051_contact_intelligence.sql). Append-only: a correction changes
-- `state` (never deletes), so history stays. request_id = 0 means "not tied to one
-- request" (no FK on purpose). occurred_at = when the underlying event happened
-- (message time), created_at = when we recorded it.
CREATE TABLE IF NOT EXISTS supplier_identity_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL CHECK (kind IN ('email', 'domain', 'inn', 'name', 'phone')),
    value TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'rfq_sent', 'inbound_reply', 'manual_confirmed', 'official_source',
        'workspace_contact_result', 'hard_bounce', 'soft_bounce',
        'import', 'name_token_similarity'
    )),
    source_id TEXT NOT NULL DEFAULT '',
    assertion TEXT NOT NULL CHECK (assertion IN ('association', 'ownership', 'deliverability')),
    strength TEXT NOT NULL CHECK (strength IN ('strong', 'medium', 'weak')),
    state TEXT NOT NULL CHECK (state IN ('candidate', 'confirmed', 'rejected', 'revoked')),
    reason TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_verified_at TEXT NOT NULL,
    decided_by_user_id INTEGER,
    decided_at TEXT,
    revoke_reason TEXT NOT NULL DEFAULT '',
    supersedes_id INTEGER,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

-- One row per (card, identifier, source): re-recording the same fact never
-- creates a second row and never resurrects a revoked/rejected one.
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_identity_evidence_fact
    ON supplier_identity_evidence(workspace_id, supplier_id, kind, value, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_supplier_identity_evidence_lookup
    ON supplier_identity_evidence(workspace_id, kind, value, state);
