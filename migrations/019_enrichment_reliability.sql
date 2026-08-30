PRAGMA foreign_keys = ON;

-- Накопительный граф доказательств. Итоговое поле в supplier_profiles отвечает
-- «что приняли», а эта таблица — «почему, откуда и с какой силой». Отдельная
-- таблица сохраняет идемпотентность миграций SQLite/Postgres.
CREATE TABLE IF NOT EXISTS supplier_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    field_value TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    strength TEXT NOT NULL DEFAULT 'weak',
    score INTEGER NOT NULL DEFAULT 0,
    decision TEXT NOT NULL DEFAULT 'observed',
    details_json TEXT NOT NULL DEFAULT '{}',
    first_seen_at TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    UNIQUE (supplier_id, field_name, field_value, source_type, source_url)
);

CREATE INDEX IF NOT EXISTS idx_supplier_evidence_supplier
    ON supplier_evidence(supplier_id, field_name, decision);

-- Незавершённое обогащение живёт отдельно от поиска заявки. Поиск может
-- завершиться, а ровно пропущенная ступень (crawl/registry/web/finance) продолжит
-- попытки после восстановления сети или квоты. Lease делает очередь безопасной
-- при параллельных вкладках и перезапусках serverless-функций.
CREATE TABLE IF NOT EXISTS supplier_enrichment_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    host TEXT NOT NULL,
    stage TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL DEFAULT '',
    claim_token TEXT,
    locked_until TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    UNIQUE (workspace_id, host, stage)
);

CREATE INDEX IF NOT EXISTS idx_supplier_enrichment_jobs_pick
    ON supplier_enrichment_jobs(workspace_id, status, next_attempt_at, locked_until);
