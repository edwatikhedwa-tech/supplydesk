PRAGMA foreign_keys = ON;

-- Personal contact data is never part of canonical_companies or the public
-- supplier card.  It belongs to one workspace and may additionally be private
-- to the member who entered it.
CREATE TABLE IF NOT EXISTS workspace_supplier_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    global_supplier_id INTEGER NOT NULL,
    owner_user_id INTEGER NOT NULL,
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'workspace')),
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (global_supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_supplier_contacts_visibility
    ON workspace_supplier_contacts(workspace_id, global_supplier_id, visibility, owner_user_id);
