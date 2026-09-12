PRAGMA foreign_keys = ON;

-- A single workspace note is intentionally separate from the per-user legacy
-- note table (035). Existing personal notes therefore remain private without
-- a lossy migration or a change to their composite identity.
CREATE TABLE IF NOT EXISTS mail_thread_workspace_notes (
    workspace_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    author_user_id INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, request_id, supplier_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE RESTRICT
);
