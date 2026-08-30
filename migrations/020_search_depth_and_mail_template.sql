PRAGMA foreign_keys = ON;

-- Flexible per-request depth. The previous table intentionally accepted only
-- 1/3/5; keep it for backward compatibility and copy its data once into the
-- new table instead of rebuilding a live SQLite/Postgres table destructively.
CREATE TABLE IF NOT EXISTS request_search_config (
    request_id INTEGER PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
    search_depth INTEGER NOT NULL DEFAULT 1,
    CHECK (search_depth BETWEEN 1 AND 100)
);

INSERT INTO request_search_config(request_id, search_depth)
SELECT request_id, search_depth FROM request_search_options WHERE search_depth BETWEEN 1 AND 100
ON CONFLICT(request_id) DO NOTHING;

-- One editable procurement letter template per workspace. Attachments are
-- stored separately so replacement is atomic and message attachments can keep
-- their existing immutable copies after a template is edited.
CREATE TABLE IF NOT EXISTS workspace_mail_templates (
    workspace_id INTEGER PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_mail_template_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspace_mail_templates(workspace_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content BLOB NOT NULL,
    UNIQUE (workspace_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_workspace_mail_template_attachments
    ON workspace_mail_template_attachments(workspace_id, id);
