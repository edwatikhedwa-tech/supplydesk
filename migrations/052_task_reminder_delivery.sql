PRAGMA foreign_keys = OFF;

-- Real delivery-state tracking for task reminders (in-app toast + Notification
-- Center), replacing the previous "scheduled row that nothing ever reads"
-- state. SQLite cannot extend a CHECK constraint in place, so the table is
-- rebuilt exactly as migrations 043/044 already did, preserving every row.
--
-- New states: 'triggered' (reminder is due and has been surfaced at least
-- once), 'snoozed' is intentionally NOT a distinct persisted state -- a
-- snooze simply reschedules the reminder back to 'scheduled' with a new
-- scheduled_at, per the product rule that closing/snoozing a reminder must
-- never be confused with completing the underlying task. 'dismissed' means
-- the user closed the toast with x; the task is untouched and the reminder
-- keeps showing in the Notification Center.
--
-- read_at powers the Notification Center's unread badge, independent of the
-- toast lifecycle: a reminder can be 'triggered' and already read (user
-- opened the bell) while its toast is still open, or dismissed and still
-- unread (user never opened the center).
CREATE TABLE task_reminders_next (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('in_app', 'email', 'phone')),
    scheduled_at TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'triggered', 'dismissed', 'cancelled', 'mock_triggered')),
    recipient TEXT,
    mock_state TEXT CHECK (mock_state IN ('mock', 'not_connected')),
    read_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

INSERT INTO task_reminders_next(id, task_id, channel, scheduled_at, timezone, status, recipient, mock_state, read_at, created_at, updated_at)
SELECT id, task_id, channel, scheduled_at, timezone, status, recipient, mock_state, NULL, created_at, updated_at
FROM task_reminders;

DROP TABLE task_reminders;
ALTER TABLE task_reminders_next RENAME TO task_reminders;
CREATE INDEX idx_task_reminders_task_scheduled
    ON task_reminders(task_id, status, scheduled_at);

-- Per-user notification preferences (§13 of the reminder spec): sound and
-- browser-notification opt-in. The browser's own permission grant is never
-- stored here (it lives in the browser itself) -- this is only the user's
-- in-app preference for whether SupplyDesk should attempt to use it.
CREATE TABLE IF NOT EXISTS user_notification_settings (
    user_id INTEGER PRIMARY KEY,
    sound_enabled INTEGER NOT NULL DEFAULT 1 CHECK (sound_enabled IN (0, 1)),
    browser_notifications_enabled INTEGER NOT NULL DEFAULT 0 CHECK (browser_notifications_enabled IN (0, 1)),
    default_reminder_offset_minutes INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

PRAGMA foreign_keys = ON;
