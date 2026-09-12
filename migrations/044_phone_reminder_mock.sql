PRAGMA foreign_keys = OFF;

-- SQLite cannot extend a CHECK constraint in place.  Preserve every existing
-- provider-neutral reminder while widening the portable channel vocabulary to
-- include the temporary phone mock.  No provider fields are introduced.
CREATE TABLE task_reminders_next (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('in_app', 'email', 'phone')),
    scheduled_at TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled', 'mock_triggered')),
    recipient TEXT,
    mock_state TEXT CHECK (mock_state IN ('mock', 'not_connected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

INSERT INTO task_reminders_next(id, task_id, channel, scheduled_at, timezone, status, recipient, mock_state, created_at, updated_at)
SELECT id, task_id, channel, scheduled_at, timezone, status, recipient, NULL, created_at, updated_at
FROM task_reminders;

DROP TABLE task_reminders;
ALTER TABLE task_reminders_next RENAME TO task_reminders;
CREATE INDEX idx_task_reminders_task_scheduled
    ON task_reminders(task_id, status, scheduled_at);

PRAGMA foreign_keys = ON;
