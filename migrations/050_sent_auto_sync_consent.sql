PRAGMA foreign_keys = ON;

-- An external Sent folder stays manual until its owner gives this narrow,
-- reversible consent.  New and existing accounts start disabled.
ALTER TABLE mail_account_profiles
    ADD COLUMN sent_sync_enabled INTEGER NOT NULL DEFAULT 0;
