"""Asynchronous mail analysis (EDW-38).

sync:    fetch -> persist -> deduplicate -> enqueue (same transaction as the import) -> return. No model, no OCR, no parsing.
worker:  claim (token + lease) -> rules -> model only if needed -> validate -> persist facts -> complete.

Guarantees, each covered by tests/test_analysis_queue.py:
  * enqueueing the same message twice = one job (unique key);
  * a message saved without a job (crash between import and enqueue) is found by enqueue_missing_analysis_jobs;
  * two workers never hold one job (conditional claim with a token; an expired lease is reclaimed);
  * a crash after the model answered but before the result was committed does not pay twice: the reply is stored in
    mail_ai_reply_cache the moment it arrives and replayed on retry;
  * retry with backoff, then `failed` (the message stays for manual review).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .attachment_intelligence import ANALYSIS_VERSION as ATTACHMENT_VERSION
from .canary import BudgetPaused
from .message_analysis import ANALYSIS_VERSION as BODY_VERSION, ModelReply

LEASE_SECONDS = 300
BACKOFF_SECONDS = (30, 120, 600, 1800)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _after(seconds: float) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


def intelligence_enabled() -> bool:
    return os.getenv("MAIL_INTELLIGENCE_ON_SYNC") == "1"


def _request_key(stage: str, model: str, system: str, user: Any, schema: Any) -> str:
    payload = json.dumps([stage, model, system, user, schema], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingModels:
    """Wraps a models adapter: the reply is persisted immediately (own commit) and replayed for an identical request."""

    def __init__(self, inner: Any, repository: Any, workspace_id: int, guard: Any = None) -> None:
        self.inner, self.repository, self.workspace_id, self.guard = inner, repository, workspace_id, guard
        self.paid_calls = 0
        self.replays = 0

    def model_for(self, stage: str) -> str | None:
        return self.inner.model_for(stage) if hasattr(self.inner, "model_for") else "model"

    def call(self, stage: str, system: str, user: Any, schema: dict[str, Any]) -> ModelReply:
        key = _request_key(stage, self.model_for(stage) or "", system, user, schema)
        with self.repository.connect() as c:
            row = c.execute("SELECT id, reply_json FROM mail_ai_reply_cache WHERE workspace_id=? AND request_key=?", (self.workspace_id, key)).fetchone()
            if row:
                c.execute("UPDATE mail_ai_reply_cache SET replays=replays+1 WHERE id=?", (row["id"],))
                c.commit()
                self.replays += 1
                d = json.loads(row["reply_json"])
                return ModelReply(d.get("data"), d.get("model", ""), d.get("provider", "routerai"), int(d.get("input_tokens") or 0), int(d.get("output_tokens") or 0),
                                  0.0, "none", 0, d.get("error", ""))
        if self.guard is not None:
            self.guard()              # budget check BEFORE a paid call (raises BudgetPaused); replays above are free
        reply = self.inner.call(stage, system, user, schema)
        self.paid_calls += 1
        blob = {"data": reply.data, "model": reply.model, "provider": reply.provider, "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens, "error": reply.error}
        with self.repository.connect() as c:
            c.execute(
                """INSERT INTO mail_ai_reply_cache(workspace_id, request_key, stage, model, reply_json, input_tokens, output_tokens, cost_rub, latency_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(workspace_id, request_key) DO NOTHING""",
                (self.workspace_id, key, stage, reply.model, json.dumps(blob, ensure_ascii=False), reply.input_tokens, reply.output_tokens, reply.cost_rub, reply.latency_ms, _now()))
            c.commit()
        return reply


class AnalysisQueueMixin:
    # ---------------------------------------------------------------- enqueue
    def _enqueue_job(self, connection: Any, workspace_id: int, kind: str, message_id: int, job_type: str, version: str) -> int:
        now = _now()
        return connection.execute(
            """INSERT INTO mail_analysis_jobs(workspace_id, message_kind, message_id, job_type, analysis_version, status, next_attempt_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
               ON CONFLICT(workspace_id, message_kind, message_id, job_type, analysis_version) DO NOTHING""",
            (workspace_id, kind, message_id, job_type, version, now, now, now)).rowcount

    def enqueue_analysis_for_message(self, connection: Any, workspace_id: int, kind: str, message_id: int, *, has_attachments: bool = False) -> int:
        """Called inside the import transaction: the message and its jobs are committed together."""
        n = self._enqueue_job(connection, workspace_id, kind, message_id, "body", BODY_VERSION)
        if kind == "mail_message" and has_attachments:
            n += self._enqueue_job(connection, workspace_id, kind, message_id, "attachments", ATTACHMENT_VERSION)
        return n

    def enqueue_missing_analysis_jobs(self, workspace_id: int, *, since: str, limit: int = 500) -> int:
        """Reconciliation for a crash between 'message saved' and 'job saved'. `since` is REQUIRED: only messages created at or after it are
        considered, so switching the flag on can never queue (and pay for) the whole mailbox history by accident."""
        n = 0
        with self.connect() as c:
            for r in c.execute("""SELECT m.id, (SELECT COUNT(*) FROM mail_attachments a WHERE a.message_id=m.id) AS att FROM mail_messages m
                                  WHERE m.workspace_id=? AND m.direction='inbound'
                                    AND m.created_at>=?
                                    AND NOT EXISTS (SELECT 1 FROM mail_analyses x WHERE x.workspace_id=m.workspace_id AND x.message_kind='mail_message' AND x.message_id=m.id)
                                  ORDER BY m.id LIMIT ?""",
                               (workspace_id, since, limit)).fetchall():
                n += self.enqueue_analysis_for_message(c, workspace_id, "mail_message", int(r["id"]), has_attachments=bool(r["att"]))
            for r in c.execute("""SELECT i.id FROM mail_inbox_messages i WHERE i.workspace_id=? AND i.status='unmatched'
                                    AND i.created_at>=?
                                    AND NOT EXISTS (SELECT 1 FROM mail_analyses x WHERE x.workspace_id=i.workspace_id AND x.message_kind='inbox_message' AND x.message_id=i.id)
                                  ORDER BY i.id LIMIT ?""",
                               (workspace_id, since, limit)).fetchall():
                n += self.enqueue_analysis_for_message(c, workspace_id, "inbox_message", int(r["id"]))
            c.commit()
        return n

    # ---------------------------------------------------------------- claim / finish
    def claim_analysis_job(self, worker_id: str, *, workspace_id: int | None = None, lease_seconds: int = LEASE_SECONDS, canary_only: bool = False) -> dict[str, Any] | None:
        now, token = _now(), uuid4().hex
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE") if not self.database_url else None
            where = "(status='queued' AND next_attempt_at<=?) OR (status='running' AND lease_until IS NOT NULL AND lease_until<?)"
            args: list[Any] = [now, now]
            canary_sql = (" AND workspace_id IN (SELECT workspace_id FROM mail_intelligence_canary WHERE enabled=1 AND stopped_at IS NULL)" if canary_only else "")
            sql = f"SELECT id FROM mail_analysis_jobs WHERE ({where})" + canary_sql + (" AND workspace_id=?" if workspace_id else "") + " ORDER BY id LIMIT 1"
            cand = c.execute(sql, args + ([workspace_id] if workspace_id else [])).fetchone()
            if not cand:
                c.commit()
                return None
            claimed = c.execute(
                f"""UPDATE mail_analysis_jobs SET status='running', claim_token=?, worker_id=?, lease_until=?, attempts=attempts+1, started_at=?, updated_at=?
                    WHERE id=? AND ({where})""",
                (token, worker_id, _after(lease_seconds), now, now, cand["id"], now, now)).rowcount
            if not claimed:
                c.commit()
                return None
            row = c.execute("SELECT * FROM mail_analysis_jobs WHERE id=? AND claim_token=?", (cand["id"], token)).fetchone()
            c.commit()
        return dict(row) if row else None

    def finish_analysis_job(self, job: dict[str, Any], *, error: str = "", duration_ms: int = 0) -> str:
        """done | queued (retry, backoff) | failed. Only the holder of the claim token can finish a job."""
        now = _now()
        with self.connect() as c:
            if not error:
                ok = c.execute("UPDATE mail_analysis_jobs SET status='done', finished_at=?, updated_at=?, duration_ms=?, last_error='', lease_until=NULL WHERE id=? AND claim_token=?",
                               (now, now, duration_ms, job["id"], job["claim_token"])).rowcount
                c.commit()
                return "done" if ok else "lost_claim"
            attempts = int(job["attempts"])
            if attempts >= int(job["max_attempts"]):
                status, nxt = "failed", now
            else:
                status, nxt = "queued", _after(BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)])
            ok = c.execute("UPDATE mail_analysis_jobs SET status=?, next_attempt_at=?, last_error=?, updated_at=?, duration_ms=?, lease_until=NULL WHERE id=? AND claim_token=?",
                           (status, nxt, error[:300], now, duration_ms, job["id"], job["claim_token"])).rowcount
            c.commit()
            return status if ok else "lost_claim"

    # ---------------------------------------------------------------- worker
    def _analysis_models_for_worker(self, workspace_id: int) -> tuple[Any, Any]:
        text = self._default_analysis_models()
        vision = None
        vm = os.getenv("MAIL_ATTACHMENT_VISION_MODEL", "").strip()
        if text is not None and vm:
            from .message_analysis import RouterAiAnalysisModels
            vision = RouterAiAnalysisModels(text.client, cheap_model=vm, strong_model=None)
        return (CachingModels(text, self, workspace_id) if text is not None else None,
                CachingModels(vision, self, workspace_id) if vision is not None else None)

    def run_analysis_jobs(self, worker_id: str, *, limit: int = 100, workspace_id: int | None = None, models: Any = None, vision: Any = None,
                          lease_seconds: int = LEASE_SECONDS, canary_only: bool = False) -> dict[str, Any]:
        summary = {"worker": worker_id, "processed": 0, "done": 0, "retried": 0, "failed": 0, "deferred": 0, "lost_claim": 0, "model_calls": 0, "replays": 0, "seconds": 0.0, "jobs": []}
        started = time.monotonic()
        for _ in range(limit):
            job = self.claim_analysis_job(worker_id, workspace_id=workspace_id, lease_seconds=lease_seconds, canary_only=canary_only)
            if not job:
                break
            ws = int(job["workspace_id"])
            t0 = time.monotonic()
            error = ""
            m, v = (models, vision) if models is not None or vision is not None else self._analysis_models_for_worker(ws)
            guard = (lambda w=ws: self.assert_canary_budget(w)) if canary_only else None
            if models is not None:
                m = CachingModels(models, self, ws, guard)
            elif isinstance(m, CachingModels):
                m.guard = guard
            if vision is not None:
                v = CachingModels(vision, self, ws, guard)
            elif isinstance(v, CachingModels):
                v.guard = guard
            if int(job["attempts"]) > 1:      # a previous attempt died: it left its analysis in_progress; this claim owns the job, so recover it now
                with self.connect() as rc:
                    rc.execute("UPDATE mail_analyses SET status='pending_retry' WHERE workspace_id=? AND message_kind=? AND message_id=? AND status='in_progress'",
                               (ws, job["message_kind"], job["message_id"]))
                    rc.commit()
            try:
                if job["job_type"] == "body":
                    res = self.analyze_message(ws, int(job["message_id"]), kind=job["message_kind"], models=m)
                    if res.get("status") == "pending_retry":
                        error = "provider_error_pending_retry"
                elif job["job_type"] == "attachments":
                    self.analyze_message_attachments(ws, int(job["message_id"]), models=None, vision=v, ocr_enabled=not canary_only)
                else:
                    error = f"unknown job type {job['job_type']}"
            except BudgetPaused:
                # not a failure: put the job back untouched (no attempt used), release the half-done analysis, wait for the window to reopen
                with self.connect() as rc:
                    rc.execute("UPDATE mail_analyses SET status='pending_retry' WHERE workspace_id=? AND message_kind=? AND message_id=? AND status='in_progress'", (ws, job["message_kind"], job["message_id"]))
                    rc.execute("UPDATE mail_analysis_jobs SET status='queued', attempts=attempts-1, next_attempt_at=?, lease_until=NULL, updated_at=? WHERE id=? AND claim_token=?",
                               (_after(1800), _now(), job["id"], job["claim_token"]))
                    rc.commit()
                summary["deferred"] += 1
                summary["jobs"].append({"job": job["id"], "type": job["job_type"], "kind": job["message_kind"], "message": job["message_id"], "outcome": "deferred_budget", "ms": 0, "error": ""})
                continue
            except Exception as exc:  # noqa: BLE001 - a failed job is recorded and retried, never raised into the worker loop
                error = f"{type(exc).__name__}: {exc}"[:300]
            duration = int((time.monotonic() - t0) * 1000)
            outcome = self.finish_analysis_job(job, error=error, duration_ms=duration)
            summary["processed"] += 1
            summary[{"done": "done", "queued": "retried", "failed": "failed", "lost_claim": "lost_claim"}[outcome]] += 1
            for wrapper in (m, v):
                if isinstance(wrapper, CachingModels):
                    summary["model_calls"] += wrapper.paid_calls
                    summary["replays"] += wrapper.replays
            summary["jobs"].append({"job": job["id"], "type": job["job_type"], "kind": job["message_kind"], "message": job["message_id"], "outcome": outcome, "ms": duration, "error": error})
        summary["seconds"] = round(time.monotonic() - started, 2)
        return summary
