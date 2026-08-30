PRAGMA foreign_keys = ON;

-- P0 runtime lineage.  The UUID is useful only together with the canonical
-- path and the durable session provenance; it is not a standalone authority.
CREATE TABLE IF NOT EXISTS mail_database_identity (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    database_uuid TEXT NOT NULL UNIQUE,
    canonical_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mail_runtime_sessions (
    runtime_id TEXT PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('production', 'development', 'test')),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    pid INTEGER NOT NULL,
    cwd TEXT NOT NULL,
    db_path TEXT NOT NULL,
    db_identity TEXT,
    git_revision TEXT,
    outgoing_allowed INTEGER NOT NULL DEFAULT 0,
    canonical_check_passed INTEGER NOT NULL DEFAULT 0,
    live_mail_lock_acquired INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_runtime_sessions_started
    ON mail_runtime_sessions(started_at DESC);

-- Each irreversible attempt is linked to the runtime that owned the guard.
-- Keeping this as a companion table avoids changing the stable attempt ledger.
CREATE TABLE IF NOT EXISTS mail_send_attempt_runtime (
    attempt_id INTEGER PRIMARY KEY,
    runtime_id TEXT NOT NULL,
    db_identity TEXT NOT NULL,
    canonical_check_passed INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (attempt_id) REFERENCES mail_send_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (runtime_id) REFERENCES mail_runtime_sessions(runtime_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_mail_send_attempt_runtime_runtime
    ON mail_send_attempt_runtime(runtime_id, recorded_at);
