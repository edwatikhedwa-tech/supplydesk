PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS request_meta (
    request_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'draft',
    search_progress INTEGER NOT NULL DEFAULT 0,
    search_total INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS request_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    position_key TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (request_id, position_key),
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS supplier_profiles (
    supplier_id INTEGER PRIMARY KEY,
    inn TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    covers_json TEXT NOT NULL DEFAULT '[]',
    site_unavailable INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS request_suppliers (
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    position_keys_json TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    is_irrelevant INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (request_id, supplier_id),
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS blacklist_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    supplier_id INTEGER,
    external_key TEXT NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'company',
    reason TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    restored_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_request_meta_status ON request_meta(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_request_positions_request ON request_positions(request_id);
CREATE INDEX IF NOT EXISTS idx_request_suppliers_request ON request_suppliers(request_id, is_irrelevant);
CREATE INDEX IF NOT EXISTS idx_blacklist_active ON blacklist_entries(workspace_id, restored_at);
CREATE INDEX IF NOT EXISTS idx_audit_workspace ON audit_events(workspace_id, created_at);
