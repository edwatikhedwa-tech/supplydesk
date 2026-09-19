"""Canary control for Mail Intelligence (EDW-40): allowlist, budget, kill switch, stop rules, metrics.

Analysis for a workspace runs ONLY when all hold:
  1. MAIL_INTELLIGENCE_ON_SYNC=1 in the environment (master switch; by itself it enables nothing),
  2. the workspace is in ALLOWED_CANARY_WORKSPACES (code) and has an enabled row in mail_intelligence_canary,
  3. the row is not stopped and the window (started_at .. ends_at) is open,
  4. the letter was received at or after started_at (no historical backfill).
The kill switch is `enabled = 0` (or the env flag off): AI processing stops at once, mail receive/send is untouched, nothing is migrated.
Budget: daily and weekly caps in roubles, checked BEFORE every paid call; reaching a cap pauses AI jobs (mail sync continues); a cap is never raised
automatically. Stop rules (evaluate_safety) stop the canary until the owner clears it explicitly.
No message bodies, addresses or credentials are ever written to metrics, events or reports.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ALLOWED_CANARY_WORKSPACES = frozenset({1})
CALL_RESERVE_RUB = 0.05                 # a paid call is refused unless spent + reserve fits under the cap: a cap cannot be exceeded by one call
DEFAULT_DAILY_CAP_RUB = 1.0
DEFAULT_WEEKLY_CAP_RUB = 5.0
CANARY_MAX_DAYS = 14
MIN_DAYS = 7
MIN_MESSAGES = 50
FAILED_JOB_RATE_LIMIT = 0.05
FAILED_JOB_MIN_SAMPLE = 5
BACKLOG_WINDOW_MINUTES = 30
SECRET_ENV_NAMES = ("ROUTERAI_KEY", "MAIL_TOKEN_ENCRYPTION_KEY", "YANDEX_CLIENT_SECRET", "APP_USER_PASSWORD", "XMLRIVER_KEY")


class BudgetPaused(Exception):
    """Raised before a paid call when a cap would be reached. Not a failure: the job is deferred."""


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def env_flag_on() -> bool:
    return os.getenv("MAIL_INTELLIGENCE_ON_SYNC") == "1"


def _day_start(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d") + "T00:00:00+00:00"


class CanaryMixin:
    # ------------------------------------------------------------------ config
    def canary_state(self, workspace_id: int, connection: Any = None) -> dict[str, Any] | None:
        def read(c):
            row = c.execute("SELECT * FROM mail_intelligence_canary WHERE workspace_id=?", (workspace_id,)).fetchone()
            return dict(row) if row else None
        if connection is not None:
            return read(connection)
        with self.connect() as c:
            return read(c)

    def canary_active(self, workspace_id: int, connection: Any = None, *, now: datetime | None = None) -> bool:
        """True only if every gate is open. The environment flag alone is never enough."""
        if not env_flag_on() or workspace_id not in ALLOWED_CANARY_WORKSPACES:
            return False
        st = self.canary_state(workspace_id, connection)
        if not st or not st["enabled"] or st["stopped_at"] or not st["started_at"]:
            return False
        return not (st["ends_at"] and st["ends_at"] <= _iso(now or _now()))

    def canary_accepts_message(self, workspace_id: int, received_iso: str, connection: Any = None) -> bool:
        """Only letters received at or after started_at are ever enqueued."""
        if not self.canary_active(workspace_id, connection):
            return False
        st = self.canary_state(workspace_id, connection)
        return bool(st and received_iso >= st["started_at"])

    def canary_enable(self, workspace_id: int, *, daily_cap_rub: float = DEFAULT_DAILY_CAP_RUB, weekly_cap_rub: float = DEFAULT_WEEKLY_CAP_RUB,
                      started_at: str | None = None, clear_stop: bool = False) -> dict[str, Any]:
        """Owner action. Only allowlisted workspaces. First enable fixes started_at; a re-enable keeps it (no new backfill window) and reconciles the
        letters that arrived while disabled (bounded by started_at, deduplicated by the job key: no loss, no duplicate, no second payment)."""
        if workspace_id not in ALLOWED_CANARY_WORKSPACES:
            raise ValueError("Этот workspace не входит в allowlist canary.")
        now = _now()
        with self.connect() as c:
            st = self.canary_state(workspace_id, c)
            if st and st["stopped_at"] and not clear_stop:
                raise ValueError(f"Canary остановлен ({st['stopped_reason']}). Явно снимите остановку: clear_stop=True.")
            if st:
                c.execute("UPDATE mail_intelligence_canary SET enabled=1, stopped_at=NULL, stopped_reason='', updated_at=? WHERE workspace_id=?", (_iso(now), workspace_id))
            else:
                start = started_at or _iso(now)
                c.execute("INSERT INTO mail_intelligence_canary(workspace_id, enabled, started_at, ends_at, daily_cap_rub, weekly_cap_rub, updated_at) VALUES (?, 1, ?, ?, ?, ?, ?)",
                          (workspace_id, start, _iso(datetime.fromisoformat(start) + timedelta(days=CANARY_MAX_DAYS)), daily_cap_rub, weekly_cap_rub, _iso(now)))
            c.commit()
        st = self.canary_state(workspace_id)
        enqueued = self.enqueue_missing_analysis_jobs(workspace_id, since=st["started_at"]) if env_flag_on() else 0
        return {**st, "reconciled_jobs": enqueued}

    def canary_disable(self, workspace_id: int, reason: str = "owner") -> None:
        with self.connect() as c:
            c.execute("UPDATE mail_intelligence_canary SET enabled=0, updated_at=? WHERE workspace_id=?", (_iso(_now()), workspace_id))
            c.execute("INSERT INTO mail_intelligence_stop_events(workspace_id, kind, reason, detail, created_at) VALUES (?, 'disabled', ?, '', ?)", (workspace_id, reason, _iso(_now())))
            c.commit()

    def canary_stop(self, workspace_id: int, reason: str, detail: str = "") -> None:
        """A stop incident: AI processing halts until the owner clears it. Idempotent."""
        now = _iso(_now())
        with self.connect() as c:
            st = self.canary_state(workspace_id, c)
            if st and not st["stopped_at"]:
                c.execute("UPDATE mail_intelligence_canary SET stopped_at=?, stopped_reason=?, updated_at=? WHERE workspace_id=?", (now, reason, now, workspace_id))
            c.execute("INSERT INTO mail_intelligence_stop_events(workspace_id, kind, reason, detail, created_at) VALUES (?, 'stop', ?, ?, ?)", (workspace_id, reason, detail[:300], now))
            c.commit()

    # ------------------------------------------------------------------ budget
    def canary_spend(self, workspace_id: int, *, now: datetime | None = None) -> dict[str, float]:
        now = now or _now()
        with self.connect() as c:
            day = c.execute("SELECT COALESCE(SUM(cost_rub), 0) AS s FROM mail_ai_reply_cache WHERE workspace_id=? AND created_at>=?", (workspace_id, _day_start(now))).fetchone()["s"]
            week = c.execute("SELECT COALESCE(SUM(cost_rub), 0) AS s FROM mail_ai_reply_cache WHERE workspace_id=? AND created_at>=?", (workspace_id, _iso(now - timedelta(days=7)))).fetchone()["s"]
        return {"day": float(day or 0), "week": float(week or 0)}

    def assert_canary_budget(self, workspace_id: int) -> None:
        """Called before every PAID call (cache replays are free). Refuses when the call could reach a cap."""
        st = self.canary_state(workspace_id)
        if not st:
            raise BudgetPaused("no canary row")
        spend = self.canary_spend(workspace_id)
        if spend["day"] + CALL_RESERVE_RUB > float(st["daily_cap_rub"]) or spend["week"] + CALL_RESERVE_RUB > float(st["weekly_cap_rub"]):
            with self.connect() as c:
                c.execute("INSERT INTO mail_intelligence_stop_events(workspace_id, kind, reason, detail, created_at) VALUES (?, 'pause', 'budget_cap_reached', ?, ?)",
                          (workspace_id, json.dumps({"day": round(spend["day"], 5), "week": round(spend["week"], 5)}), _iso(_now())))
                c.commit()
            raise BudgetPaused("budget cap reached")

    # ------------------------------------------------------------------ safety
    def _secret_values(self) -> list[str]:
        values = [os.getenv(n, "") for n in SECRET_ENV_NAMES]
        with self.connect() as c:
            for sql in ("SELECT credential_encrypted AS v FROM mail_account_profiles", "SELECT access_token_encrypted AS v FROM mail_accounts", "SELECT refresh_token_encrypted AS v FROM mail_accounts"):
                try:
                    values += [str(r["v"])[:20] for r in c.execute(sql).fetchall() if r["v"]]
                except Exception:  # noqa: BLE001 - a missing column is not a leak
                    pass
        return [v for v in values if len(v) >= 12]

    def evaluate_safety(self, workspace_id: int, *, log_paths: list[Path] | None = None, now: datetime | None = None) -> list[dict[str, str]]:
        """Stop-rule findings. Every query is aggregate/structural; nothing returned contains letter content."""
        now = now or _now()
        st = self.canary_state(workspace_id)
        if not st:
            return []
        since = st["started_at"]
        out: list[dict[str, str]] = []
        add = lambda rule, detail: out.append({"rule": rule, "detail": detail})
        with self.connect() as c:
            n = c.execute("""SELECT COUNT(*) AS n FROM (SELECT message_id FROM (
                                 SELECT message_id FROM mail_messages WHERE workspace_id=? AND created_at>=? AND message_id<>''
                                 UNION ALL SELECT message_id FROM mail_inbox_messages WHERE workspace_id=? AND created_at>=? AND message_id<>'' AND status='unmatched') x
                             GROUP BY message_id HAVING COUNT(*)>1) y""", (workspace_id, since, workspace_id, since)).fetchone()["n"]
            if n:
                add("duplicate_message", f"{n} Message-ID with more than one object")
            n = c.execute("SELECT COUNT(*) AS n FROM (SELECT analysis_id, position FROM mail_facts WHERE workspace_id=? AND created_at>=? GROUP BY analysis_id, position HAVING COUNT(*)>1) x", (workspace_id, since)).fetchone()["n"]
            n += c.execute("SELECT COUNT(*) AS n FROM (SELECT f.message_kind, f.message_id FROM mail_facts f WHERE f.workspace_id=? AND f.created_at>=? AND f.state='proposed' GROUP BY f.message_kind, f.message_id HAVING COUNT(DISTINCT f.analysis_id)>1) x", (workspace_id, since)).fetchone()["n"]
            n += c.execute("SELECT COUNT(*) AS n FROM (SELECT message_id, position FROM mail_attachment_facts WHERE workspace_id=? AND created_at>=? GROUP BY message_id, position HAVING COUNT(*)>1) x", (workspace_id, since)).fetchone()["n"]
            if n:
                add("duplicate_fact", f"{n} duplicated fact groups")
            n = c.execute("SELECT COUNT(*) AS n FROM mail_ai_runs WHERE workspace_id=? AND created_at>=? AND provider<>'rules' AND repeat_of_same_content=1 AND COALESCE(cost_rub, 0)>0", (workspace_id, since)).fetchone()["n"]
            n += c.execute("SELECT COUNT(*) AS n FROM (SELECT request_key FROM mail_ai_reply_cache WHERE workspace_id=? GROUP BY request_key HAVING COUNT(*)>1) x", (workspace_id,)).fetchone()["n"]
            if n:
                add("second_paid_call_same_key", f"{n} repeated paid calls for an unchanged key")
            # request-scoped fact invariants: bound to the request of its message, and the price is literally in its quote
            bad_req = 0
            bad_price = 0
            for f in c.execute("""SELECT f.id, f.request_id, f.data_json, f.source_quote, f.message_kind, f.message_id FROM mail_facts f
                                  WHERE f.workspace_id=? AND f.created_at>=? AND f.state='proposed' AND f.request_id IS NOT NULL""", (workspace_id, since)).fetchall():
                if f["message_kind"] == "mail_message":
                    m = c.execute("SELECT request_id FROM mail_messages WHERE id=?", (f["message_id"],)).fetchone()
                    if not m or m["request_id"] != f["request_id"]:
                        bad_req += 1
                else:
                    a = c.execute("SELECT request_id FROM mail_analyses WHERE workspace_id=? AND message_kind='inbox_message' AND message_id=? ORDER BY id DESC LIMIT 1", (workspace_id, f["message_id"])).fetchone()
                    if not a or a["request_id"] != f["request_id"]:
                        bad_req += 1
                if not _price_in_text(json.loads(f["data_json"]).get("price"), f["source_quote"]):
                    bad_price += 1
            for f in c.execute("SELECT f.request_id, f.data_json, f.source_text, f.message_id FROM mail_attachment_facts f WHERE f.workspace_id=? AND f.created_at>=? AND f.request_id IS NOT NULL", (workspace_id, since)).fetchall():
                d = json.loads(f["data_json"])
                if d.get("price") is not None and not _price_in_text(d.get("price"), f["source_text"]):
                    bad_price += 1
                m = c.execute("SELECT request_id FROM mail_messages WHERE id=?", (f["message_id"],)).fetchone()
                if not m or m["request_id"] != f["request_id"]:
                    bad_req += 1
            if bad_price:
                add("false_request_scoped_price_fact", f"{bad_price} facts whose price is not in their own source")
            if bad_req:
                add("fact_bound_to_wrong_request", f"{bad_req} facts whose request differs from their message")
            spend = self.canary_spend(workspace_id, now=now)
            if spend["day"] > float(st["daily_cap_rub"]) + 1e-9 or spend["week"] > float(st["weekly_cap_rub"]) + 1e-9:
                add("budget_cap_exceeded", f"day={round(spend['day'], 4)} week={round(spend['week'], 4)}")
            day_ago = _iso(now - timedelta(hours=24))
            row = c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END), 0) AS f FROM mail_analysis_jobs WHERE workspace_id=? AND finished_at>=? AND status IN ('done', 'failed')", (workspace_id, day_ago)).fetchone()
            if row["n"] >= FAILED_JOB_MIN_SAMPLE and row["f"] / row["n"] > FAILED_JOB_RATE_LIMIT:
                add("failed_jobs_over_5_percent", f"{row['f']}/{row['n']} in 24h")
            if c.execute("SELECT COUNT(*) AS n FROM mail_analysis_jobs WHERE workspace_id=? AND updated_at>=? AND (last_error LIKE '%locked%' OR last_error LIKE '%deadlock%' OR last_error LIKE '%could not obtain lock%')", (workspace_id, day_ago)).fetchone()["n"]:
                add("worker_interferes_with_database", "job errors mention a database lock")
            window = c.execute("SELECT depth, sampled_at FROM mail_intelligence_queue_samples WHERE workspace_id=? AND sampled_at>=? ORDER BY sampled_at", (workspace_id, _iso(now - timedelta(minutes=BACKLOG_WINDOW_MINUTES + 5)))).fetchall()
            if len(window) >= 2 and datetime.fromisoformat(window[-1]["sampled_at"]) - datetime.fromisoformat(window[0]["sampled_at"]) >= timedelta(minutes=BACKLOG_WINDOW_MINUTES):
                depths = [w["depth"] for w in window]
                if depths[-1] > 0 and depths[-1] >= depths[0] and min(depths) >= 1 and not any(d < depths[0] for d in depths):
                    add("backlog_not_shrinking", f"depth {depths[0]} -> {depths[-1]} over {BACKLOG_WINDOW_MINUTES}+ min")
            leaked = self._scan_for_secrets(c, workspace_id, log_paths or [])
            if leaked:
                add("secret_in_logs_or_diagnostics", leaked)
        return out

    def _scan_for_secrets(self, connection: Any, workspace_id: int, log_paths: list[Path]) -> str:
        secrets = self._secret_values()
        if not secrets:
            return ""
        haystacks: list[tuple[str, str]] = []
        for label, sql in (("job errors", "SELECT last_error AS t FROM mail_analysis_jobs WHERE workspace_id=?"), ("model runs", "SELECT COALESCE(error, '') || COALESCE(detail, '') AS t FROM mail_ai_runs WHERE workspace_id=?"),
                           ("attachment calls", "SELECT error AS t FROM mail_attachment_ai_calls WHERE workspace_id=?"), ("stop events", "SELECT detail AS t FROM mail_intelligence_stop_events WHERE workspace_id=?")):
            haystacks += [(label, str(r["t"] or "")) for r in connection.execute(sql, (workspace_id,)).fetchall()]
        for p in log_paths:
            try:
                if p.is_file():
                    haystacks.append((f"file {p.name}", p.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                pass
        for label, text in haystacks:
            if any(s in text for s in secrets):
                return f"secret material found in {label}"
        return ""

    def enforce_canary_safety(self, workspace_id: int, **kw: Any) -> list[dict[str, str]]:
        findings = self.evaluate_safety(workspace_id, **kw)
        if findings and (st := self.canary_state(workspace_id)) and not st["stopped_at"]:
            self.canary_stop(workspace_id, findings[0]["rule"], "; ".join(f"{f['rule']}: {f['detail']}" for f in findings))
        return findings

    def sample_canary_queue(self, workspace_id: int) -> int:
        with self.connect() as c:
            depth = c.execute("SELECT COUNT(*) AS n FROM mail_analysis_jobs WHERE workspace_id=? AND status IN ('queued', 'running')", (workspace_id,)).fetchone()["n"]
            c.execute("INSERT INTO mail_intelligence_queue_samples(workspace_id, depth, sampled_at) VALUES (?, ?, ?)", (workspace_id, depth, _iso(_now())))
            c.commit()
        return int(depth)

    # ------------------------------------------------------------------ metrics
    def canary_metrics(self, workspace_id: int, day: str | None = None) -> dict[str, Any]:
        """Aggregate metrics for one UTC day (default today). Counts, costs and latencies only: no content, no addresses."""
        d = day or _now().strftime("%Y-%m-%d")
        lo, hi = f"{d}T00:00:00+00:00", (datetime.fromisoformat(d + "T00:00:00+00:00") + timedelta(days=1)).isoformat()
        st = self.canary_state(workspace_id) or {}
        since = max(lo, st.get("started_at") or lo)
        with self.connect() as c:
            q = lambda sql, *a: c.execute(sql, (workspace_id, since, hi, *a)).fetchone()[0]
            received = q("SELECT COUNT(*) FROM mail_messages WHERE workspace_id=? AND direction='inbound' AND created_at>=? AND created_at<?") + \
                q("SELECT COUNT(*) FROM mail_inbox_messages WHERE workspace_id=? AND created_at>=? AND created_at<? AND status='unmatched'")
            analyses = c.execute("SELECT id, message_type, status, is_relevant, request_id, match_method FROM mail_analyses WHERE workspace_id=? AND created_at>=? AND created_at<?", (workspace_id, since, hi)).fetchall()
            ids = [a["id"] for a in analyses]
            stage_by_analysis: dict[int, set] = {}
            for r in c.execute("SELECT analysis_id, stage FROM mail_ai_runs WHERE workspace_id=? AND created_at>=? AND created_at<? AND provider<>'rules'", (workspace_id, since, hi)).fetchall():
                stage_by_analysis.setdefault(r["analysis_id"], set()).add(r["stage"])
            durations = sorted(r["duration_ms"] for r in c.execute("SELECT duration_ms FROM mail_analysis_jobs WHERE workspace_id=? AND status='done' AND finished_at>=? AND finished_at<?", (workspace_id, since, hi)).fetchall())
            pct = lambda p: durations[min(len(durations) - 1, int(len(durations) * p))] if durations else 0
            cost = c.execute("SELECT COALESCE(SUM(cost_rub), 0) AS s, COUNT(*) AS n FROM mail_ai_reply_cache WHERE workspace_id=? AND created_at>=? AND created_at<?", (workspace_id, since, hi)).fetchone()
            relevant = [a for a in analyses if a["is_relevant"] and (a["request_id"] is not None or a["message_type"] in ("quote", "pending_quote", "acknowledgement", "question", "decline", "invoice"))]
            att = c.execute("SELECT status, manual_review, reused_from FROM mail_attachment_analyses WHERE workspace_id=? AND created_at>=? AND created_at<?", (workspace_id, since, hi)).fetchall()
            metrics = {
                "day": d, "workspace_id": workspace_id, "received_messages": received, "analyses": len(analyses),
                "analyzed_without_ai": sum(1 for a in analyses if a["id"] not in stage_by_analysis),
                "cheap_ai": sum(1 for a in analyses if "cheap" in stage_by_analysis.get(a["id"], ())), "strong_ai": sum(1 for a in analyses if "strong" in stage_by_analysis.get(a["id"], ())),
                "manual_review": sum(1 for a in analyses if a["status"] == "needs_review") + sum(1 for r in att if r["manual_review"]),
                "jobs_failed": q("SELECT COUNT(*) FROM mail_analysis_jobs WHERE workspace_id=? AND status='failed' AND updated_at>=? AND updated_at<?"),
                "jobs_retried": q("SELECT COUNT(*) FROM mail_analysis_jobs WHERE workspace_id=? AND attempts>1 AND updated_at>=? AND updated_at<?"),
                "duplicate_calls": q("SELECT COUNT(*) FROM mail_ai_runs WHERE workspace_id=? AND created_at>=? AND created_at<? AND provider<>'rules' AND repeat_of_same_content=1"),
                "queue_depth": c.execute("SELECT COUNT(*) FROM mail_analysis_jobs WHERE workspace_id=? AND status IN ('queued', 'running')", (workspace_id,)).fetchone()[0],
                "analysis_p50_ms": pct(0.5), "analysis_p95_ms": pct(0.95),
                "ai_cost_rub": round(float(cost["s"] or 0), 6), "paid_calls": cost["n"],
                "ai_cost_per_message_rub": round(float(cost["s"] or 0) / received, 6) if received else 0.0,
                "procurement_relevant_messages": len(relevant),
                "price_facts": q("SELECT COUNT(*) FROM mail_facts WHERE workspace_id=? AND created_at>=? AND created_at<? AND state='proposed'") + q("SELECT COUNT(*) FROM mail_attachment_facts WHERE workspace_id=? AND created_at>=? AND created_at<?"),
                "rejected_facts": q("SELECT COUNT(*) FROM mail_facts WHERE workspace_id=? AND created_at>=? AND created_at<? AND state='rejected'"),
                "invalid_model_outputs": q("SELECT COUNT(*) FROM mail_ai_runs WHERE workspace_id=? AND created_at>=? AND created_at<? AND status='invalid_output'"),
                "request_matching": {k: sum(1 for a in analyses if (a["match_method"] or "none") == k) for k in sorted({(a["match_method"] or "none") for a in analyses})},
                "attachments": {"processed": len(att), "manual_review": sum(1 for r in att if r["manual_review"]), "reused_same_bytes": sum(1 for r in att if r["reused_from"] is not None), "unreadable": sum(1 for r in att if r["status"] != "ok")},
                "budget_pauses": q("SELECT COUNT(*) FROM mail_intelligence_stop_events WHERE workspace_id=? AND created_at>=? AND created_at<? AND kind='pause'"),
            }
        return metrics

    def canary_snapshot_day(self, workspace_id: int, day: str) -> dict[str, Any]:
        m = self.canary_metrics(workspace_id, day)
        with self.connect() as c:
            c.execute("""INSERT INTO mail_intelligence_metric_snapshots(workspace_id, day, metrics_json, created_at) VALUES (?, ?, ?, ?)
                         ON CONFLICT(workspace_id, day) DO UPDATE SET metrics_json=excluded.metrics_json, created_at=excluded.created_at""", (workspace_id, day, json.dumps(m, ensure_ascii=False), _iso(_now())))
            c.commit()
        return m

    def canary_final_summary(self, workspace_id: int) -> dict[str, Any]:
        st = self.canary_state(workspace_id) or {}
        with self.connect() as c:
            snaps = [json.loads(r["metrics_json"]) for r in c.execute("SELECT metrics_json FROM mail_intelligence_metric_snapshots WHERE workspace_id=? ORDER BY day", (workspace_id,)).fetchall()]
            stops = [dict(r) for r in c.execute("SELECT kind, reason, created_at FROM mail_intelligence_stop_events WHERE workspace_id=? ORDER BY id", (workspace_id,)).fetchall()]
        received = sum(s["received_messages"] for s in snaps)
        relevant = sum(s["procurement_relevant_messages"] for s in snaps)
        days = len(snaps)
        return {"days_observed": days, "received_messages": received, "procurement_relevant_messages": relevant,
                "limited_sample": received < MIN_MESSAGES or days < MIN_DAYS, "manual_review_rate_is_acceptance_criterion": relevant >= 10,
                "total_cost_rub": round(sum(s["ai_cost_rub"] for s in snaps), 5), "paid_calls": sum(s["paid_calls"] for s in snaps), "stop_events": stops, "state": {k: st.get(k) for k in ("started_at", "ends_at", "stopped_reason", "enabled")}}


def _price_in_text(price: Any, text: str | None) -> bool:
    if price is None:
        return True
    text = text or ""
    nums = set()
    for tok in re.findall(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?", text):
        t = tok.replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            nums.add(round(float(t), 2))
        except ValueError:
            pass
    return round(float(price), 2) in nums


class CanaryTickMixin:
    def canary_tick(self, workspace_id: int, worker_id: str, *, limit: int = 20, models: Any = None, vision: Any = None, log_paths: list[Path] | None = None) -> dict[str, Any]:
        """One worker cycle for the canary workspace: window check -> stop rules -> jobs (budget-gated, no OCR/vision) -> queue sample -> stop rules -> daily snapshot.
        Touches nothing outside the analysis tables: receive and send are not part of this process."""
        now = _now()
        st = self.canary_state(workspace_id)
        out: dict[str, Any] = {"workspace_id": workspace_id, "active": False, "findings": [], "jobs": {}}
        if not st or not env_flag_on() or workspace_id not in ALLOWED_CANARY_WORKSPACES:
            return out
        if st["ends_at"] and st["ends_at"] <= _iso(now) and st["enabled"]:
            self.canary_snapshot_day(workspace_id, now.strftime("%Y-%m-%d"))
            self.canary_disable(workspace_id, reason="window_ended")
            out["ended"] = True
            return out
        if not self.canary_active(workspace_id):
            out["stopped_reason"] = st["stopped_reason"]
            return out
        out["active"] = True
        findings = self.enforce_canary_safety(workspace_id, log_paths=log_paths)
        if not findings:
            summary = self.run_analysis_jobs(worker_id, limit=limit, workspace_id=workspace_id, models=models, vision=vision, canary_only=True)
            out["jobs"] = {k: v for k, v in summary.items() if k != "jobs"}
            self.sample_canary_queue(workspace_id)
            findings = self.enforce_canary_safety(workspace_id, log_paths=log_paths)
        out["findings"] = findings
        out["metrics"] = self.canary_snapshot_day(workspace_id, now.strftime("%Y-%m-%d"))
        return out
