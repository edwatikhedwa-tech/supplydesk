PRAGMA foreign_keys = ON;

-- Classification is work context, not a public/canonical fact.  The source,
-- confidence and observation time stay next to every value so a manual tag,
-- registry fact and later AI suggestion can never silently replace each other.
CREATE TABLE IF NOT EXISTS workspace_supplier_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    global_supplier_id INTEGER NOT NULL,
    owner_user_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('category', 'product', 'brand', 'specialization')),
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('manual', 'registry', 'ai')),
    confidence TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    source_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (global_supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_supplier_classifications_card
    ON workspace_supplier_classifications(workspace_id, global_supplier_id, kind, value);
