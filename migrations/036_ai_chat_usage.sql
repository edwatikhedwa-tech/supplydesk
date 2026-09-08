PRAGMA foreign_keys = ON;

-- Per-user, per-day spend tracking for the AI chat assistant in "Сообщения".
-- Additive-only table (see migration 034/035 comments for why: this repo
-- re-runs every migration on every startup and SQLite has no
-- "ALTER TABLE ADD COLUMN IF NOT EXISTS"). One row per (workspace, user, day);
-- rub_spent accumulates until the day rolls over, giving a hard daily cap
-- enforced server-side in backend/domain/ai_agent/chat_service.py.
CREATE TABLE IF NOT EXISTS ai_chat_usage (
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    usage_date TEXT NOT NULL,
    rub_spent REAL NOT NULL DEFAULT 0,
    calls INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id, usage_date),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
