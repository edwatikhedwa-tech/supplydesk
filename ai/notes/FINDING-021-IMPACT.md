# FINDING-021 Impact Note — `GET /api/mail/threads` performance on large request/supplier sets

## Current state

**Status:** OPEN (not fixed in this task)
**Referenced in:** `ai/DEFERRED_FINDINGS.md` FINDING-021

## Observed behavior

Production data (this session) shows 136 threads across 6 requests. Request 1059 ("Печь-камин — глубокий поиск 20") has **168 suppliers**, the largest in the dataset.

During the AI context selection test with 126 suppliers, FINDING-021 recorded transient 500 errors on `/api/mail/threads?request_id=N&supplier_id=M`.

## Root cause

`/api/mail/threads` in `mail/repository.py::load_thread_messages` runs a multi-join SQL query returning all messages for a `(request_id, supplier_id)` pair. For a large request, loading each thread individually (126+ sequential GET requests from the frontend's AI panel "select all") causes:

1. **N+1 query pattern** — the frontend calls one `/api/mail/threads` per supplier. 126 parallel or near-parallel requests each do a separate SQL round-trip with message-join.
2. **No pagination/slicing** — the entire message history for that thread is loaded every time, even for AI context building that may only need the last N messages (the backend then truncates in `_build_context` using `PER_MESSAGE_CHAR_LIMIT`).
3. **No thread-level batch endpoint** — there is no `GET /api/mail/threads/batch?request_id=N&supplier_ids=[1,2,3]` that could load 126 threads in one round-trip.

## Trigger

Loading Messages with AI panel open + "select all 126 answered suppliers" → 126 parallel `/api/mail/threads` requests → SQLite contention + SQLite busy → 500.

## Recommended follow-up task

After PD-001 is closed:

1. **Add batch endpoint** `GET /api/mail/threads/batch?request_id=N&supplier_ids=1,2,3` that returns all requested threads' messages in a single query (`WHERE request_id = ? AND supplier_id IN (?)`).
2. **Add frontend batching** — instead of 126 parallel calls, chunk supplier IDs into groups of 10–15 and concatenate results.
3. **Optional: add thread-level message limit** — the AI context builder already truncates by char budget; adding a `LIMIT message_count` to the query (e.g. last 20 messages) could reduce per-thread load with negligible context loss.

## Severity

P2 — key user scenario (AI comparison of many suppliers) produces degraded UX (500s). Workaround: select fewer suppliers at a time.