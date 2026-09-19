PRAGMA foreign_keys = ON;

-- Contact intelligence becomes a PROJECTION of supplier_identity_evidence
-- (EDW-14). canonical_company_contact_signals stays append-only (migration 051
-- promises "never UPDATEd or DELETEd"), so when the evidence behind a signal is
-- revoked, merged away or rolled back, the signal is not deleted: it is marked
-- here, and every read of signals ignores marked rows. Un-revoking (e.g. an
-- unmerge restores the evidence) simply removes the mark; this table is derived
-- state owned by the single reconcile function, not history.
CREATE TABLE IF NOT EXISTS canonical_company_contact_signal_revocations (
    signal_id INTEGER PRIMARY KEY REFERENCES canonical_company_contact_signals(id) ON DELETE CASCADE,
    reason TEXT NOT NULL DEFAULT '',
    revoked_at TEXT NOT NULL
);
