PRAGMA foreign_keys = ON;

-- Read state for messages that have not been matched to a request yet.
-- It is separate from mail_message_reads because mail_inbox_messages and
-- mail_messages are different immutable message models.
CREATE TABLE IF NOT EXISTS mail_inbox_message_reads (
    message_id INTEGER PRIMARY KEY REFERENCES mail_inbox_messages(id) ON DELETE CASCADE,
    read_at TEXT NOT NULL DEFAULT ''
);
