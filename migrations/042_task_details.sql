PRAGMA foreign_keys = ON;

-- Tasks existed before their time, priority and assignee details.  This is a
-- companion table rather than ALTER TABLE because every migration is rerun on
-- startup and SQLite has no idempotent ADD COLUMN. `due_at` is intentionally a
-- local wall-clock ISO value (YYYY-MM-DDTHH:MM); `timezone` records the IANA
-- zone that gives the value meaning. A future reminder scheduler converts the
-- pair to an instant, so neither UI nor storage guesses the user's zone.
CREATE TABLE IF NOT EXISTS task_details (
    task_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    due_at TEXT,
    timezone TEXT,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    assignee_user_id INTEGER,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_task_details_assignee_due
    ON task_details(assignee_user_id, due_at);
