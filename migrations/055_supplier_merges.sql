PRAGMA foreign_keys = ON;

-- Reversible supplier merge (EDW-16 / Documentation Pack V1.2.5).
-- A merge NEVER physically loses data: every row that is re-pointed or set aside is
-- recorded in supplier_merge_moves (old value / full row snapshot), so an unmerge can
-- restore the exact previous state. The merged card stays as a hidden shell so its
-- external_key/email keep resolving to the survivor (see mail/supplier_merge.py).
-- Additive companion tables (every migration is replayed on every start).
CREATE TABLE IF NOT EXISTS supplier_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    survivor_supplier_id INTEGER NOT NULL,
    merged_supplier_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'reverted')),
    reason TEXT NOT NULL DEFAULT '',
    inn_verdict TEXT NOT NULL DEFAULT '',
    merged_by_user_id INTEGER,
    merged_at TEXT NOT NULL,
    reverted_by_user_id INTEGER,
    reverted_at TEXT,
    conflicts_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (survivor_supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (merged_supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_supplier_merges_lookup
    ON supplier_merges(workspace_id, merged_supplier_id, status);

-- op = 'update' (one column re-pointed: old_value -> new_value, row located by key_json)
--    | 'delete' (row set aside because the survivor already had the same fact: row_json is
--                its full snapshot, re-inserted on unmerge)
--    | 'insert' (row created by the merge itself, e.g. contact evidence for the merged card's
--                address: deleted again on unmerge).
CREATE TABLE IF NOT EXISTS supplier_merge_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merge_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    table_name TEXT NOT NULL,
    op TEXT NOT NULL CHECK (op IN ('update', 'delete', 'insert')),
    key_json TEXT NOT NULL DEFAULT '{}',
    column_name TEXT NOT NULL DEFAULT '',
    old_value TEXT,
    new_value TEXT,
    row_json TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (merge_id) REFERENCES supplier_merges(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_supplier_merge_moves_merge ON supplier_merge_moves(merge_id, seq);
