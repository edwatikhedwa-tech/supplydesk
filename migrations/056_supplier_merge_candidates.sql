PRAGMA foreign_keys = ON;

-- Review queue for suspected duplicate supplier cards (EDW-21). A row is only a QUESTION for the
-- workspace owner (are these two cards the same company); registering or listing candidates changes no
-- supplier data. The decision is one of: merge (via the reversible merge_suppliers), reject (sticky:
-- the pair is never proposed again), later (stays in the queue). Additive companion table.
CREATE TABLE IF NOT EXISTS supplier_merge_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    survivor_supplier_id INTEGER NOT NULL,
    merged_supplier_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'later', 'rejected', 'merged')),
    reason TEXT NOT NULL DEFAULT '',
    detected_at TEXT NOT NULL,
    decided_by_user_id INTEGER,
    decided_at TEXT,
    merge_id INTEGER,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (survivor_supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (merged_supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_merge_candidates_pair
    ON supplier_merge_candidates(workspace_id, survivor_supplier_id, merged_supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_merge_candidates_status
    ON supplier_merge_candidates(workspace_id, status);
