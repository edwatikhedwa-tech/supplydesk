-- Durable, resumable request search jobs.
--
-- Vercel can recycle a serverless function immediately after it returns a
-- response. A Python daemon thread therefore cannot be the source of truth
-- for a search. The job row keeps the cursor in the database so a later
-- authenticated request can continue the same search safely.
CREATE TABLE IF NOT EXISTS request_search_jobs (
    request_id        INTEGER PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
    workspace_id      INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    stage             TEXT NOT NULL DEFAULT 'serp',
    position_index    INTEGER NOT NULL DEFAULT 0,
    enrich_hosts_json TEXT NOT NULL DEFAULT '[]',
    enrich_index      INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'queued',
    claim_token       TEXT,
    locked_until      TEXT,
    attempts          INTEGER NOT NULL DEFAULT 0,
    last_error        TEXT,
    created_at        TEXT NOT NULL DEFAULT '',
    updated_at        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_request_search_jobs_pick
    ON request_search_jobs(status, locked_until, updated_at);
