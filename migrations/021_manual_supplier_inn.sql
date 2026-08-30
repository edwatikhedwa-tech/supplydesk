PRAGMA foreign_keys = ON;

-- Источник ИНН хранится отдельно от самого значения: пользовательский ввод
-- не должен теряться при следующем автоматическом обогащении сайта.
CREATE TABLE IF NOT EXISTS supplier_inn_sources (
    supplier_id INTEGER PRIMARY KEY REFERENCES suppliers(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL DEFAULT 'auto',
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_supplier_inn_sources_type
    ON supplier_inn_sources(source_type, updated_at);
