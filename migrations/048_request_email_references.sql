PRAGMA foreign_keys = ON;

-- This is a companion table rather than a column on requests: every migration
-- is replayed on startup, and SQLite cannot repeat ALTER TABLE ADD COLUMN
-- portably.  The repository exposes it as the immutable request field
-- `email_reference`.
CREATE TABLE IF NOT EXISTS request_email_references (
    request_id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    email_reference TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (workspace_id, email_reference),
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_request_email_references_workspace_reference
    ON request_email_references(workspace_id, email_reference);

-- Existing requests receive the same stable public reference that newly
-- created requests receive.  This is idempotent and does not overwrite one.
INSERT INTO request_email_references(request_id, workspace_id, email_reference, created_at)
SELECT id, workspace_id, 'SD-' || id, created_at
FROM requests
WHERE 1
ON CONFLICT(request_id) DO NOTHING;
