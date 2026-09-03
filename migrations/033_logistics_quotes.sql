PRAGMA foreign_keys = ON;

-- Manual per-request, per-supplier shipping cost estimates from an external
-- carrier calculator (currently only Dellin/Деловые Линии — see
-- backend/integrations/logistics/dellin_client.py). No workspace_id column:
-- request_id already ties every row to exactly one workspace through
-- requests(workspace_id), the same pattern request_supplier_states already
-- uses for a per-request/per-supplier table.
CREATE TABLE IF NOT EXISTS logistics_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER,
    carrier TEXT NOT NULL DEFAULT 'dellin',
    route_from TEXT NOT NULL,
    route_to TEXT NOT NULL,
    cargo_places INTEGER NOT NULL,
    cargo_weight_kg REAL NOT NULL,
    cargo_volume_m3 REAL NOT NULL,
    cargo_max_dims_cm TEXT NOT NULL,
    price REAL,
    currency TEXT NOT NULL DEFAULT 'RUB',
    vat_included INTEGER,
    term_days INTEGER,
    cost_breakdown_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    raw_response_json TEXT,
    calculated_at TEXT NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_logistics_quotes_request_supplier
    ON logistics_quotes(request_id, supplier_id);
