PRAGMA foreign_keys = ON;

-- Canary control for Mail Intelligence (EDW-40). The environment flag alone never switches analysis on: a workspace needs an enabled row here.
--
-- mail_intelligence_canary     one row per allowed workspace: kill switch (enabled), start of the window (only letters received after started_at are analysed),
--                              hard end, budget caps in roubles, and the stop record (a stop is never lifted automatically).
-- mail_intelligence_stop_events  every stop or pause with its reason; nothing here ever raises a budget.
-- mail_intelligence_queue_samples  queue depth over time (backlog monitoring).
-- mail_intelligence_metric_snapshots  one aggregated row per workspace and day (counts and costs only, no message content).
CREATE TABLE IF NOT EXISTS mail_intelligence_canary (
    workspace_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    ends_at TEXT,
    daily_cap_rub REAL NOT NULL DEFAULT 1.0,
    weekly_cap_rub REAL NOT NULL DEFAULT 5.0,
    stopped_at TEXT,
    stopped_reason TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_intelligence_stop_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_intelligence_stop_events_ws
    ON mail_intelligence_stop_events(workspace_id, created_at);

CREATE TABLE IF NOT EXISTS mail_intelligence_queue_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    sampled_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mail_intelligence_queue_samples_ws
    ON mail_intelligence_queue_samples(workspace_id, sampled_at);

CREATE TABLE IF NOT EXISTS mail_intelligence_metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_intelligence_metric_snapshots
    ON mail_intelligence_metric_snapshots(workspace_id, day);
