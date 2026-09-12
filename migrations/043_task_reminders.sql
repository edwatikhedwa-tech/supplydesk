PRAGMA foreign_keys = ON;

-- Delivery is intentionally outside this MVP step. A reminder is a portable
-- task intention: a later scheduler may dispatch it, but this table knows no
-- provider and performs no network activity. `scheduled_at` stays a local
-- wall-clock value and `timezone` gives that value an unambiguous meaning.
CREATE TABLE IF NOT EXISTS task_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('in_app', 'email')),
    scheduled_at TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled')),
    recipient TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_reminders_task_scheduled
    ON task_reminders(task_id, status, scheduled_at);
