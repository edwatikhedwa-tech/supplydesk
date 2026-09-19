"""EDW-40: canary allowlist, no backfill, budget caps, kill switch, stop rules, formats, metrics. No network, no real model."""

from __future__ import annotations

import io
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest import mock

from mail import attachment_intelligence as AI
from mail.canary import ALLOWED_CANARY_WORKSPACES
from mail.providers.yandex import YandexMailProvider
from tests.test_analysis_queue import Base, CountingModels, GOOD_QUOTE
from tests.test_attachment_intelligence import QUOTE, xlsx
from tests.test_attachment_persistence import raw_mail
from tests.test_contact_intelligence import _Fixture

ENV = {"MAIL_INTELLIGENCE_ON_SYNC": "1"}


class EchoModels(CountingModels):
    """Answers like a correct cheap model: the price that is literally in the letter, quoted verbatim."""

    def call(self, stage, system, user, schema):
        import re
        from mail.message_analysis import ModelReply
        with self.lock:
            self.calls += 1
        m = re.search(r"Подшипник 6205-2RS1 — (\d+) руб\.", user)
        if not m:
            return ModelReply({"message_type": "other", "items": []}, "fake/cheap", "fake", 300, 10, 0.001, "catalog_estimate", 40)
        item = dict(GOOD_QUOTE["items"][0], price=int(m.group(1)), source_quote=m.group(0))
        return ModelReply({"message_type": "quote", "items": [item]}, "fake/cheap", "fake", 300, 60, getattr(self, "cost", 0.001), "catalog_estimate", 40)


def iso(dt):
    return dt.astimezone(UTC).isoformat()


class CanaryBase(Base):
    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(os.environ, ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.started = datetime.now(UTC) - timedelta(hours=1)

    def enable(self, **kw):
        return self.repo.canary_enable(self.ws, started_at=iso(self.started), **kw)

    def receive(self, body: str, *, files=(), received: datetime | None = None, subject: str | None = None, sender="sales@podshipnik.example"):
        """A production-style import: enqueue decided by the canary gates (enqueue_analysis=None), letter received at `received`."""
        self.n += 1
        raw = raw_mail(subject or ("Re: " + self.subject), list(files), msg_id=f"<c{self.n}-{id(self)}@x>", sender=sender)
        import email
        from email import policy
        m = email.message_from_bytes(raw, policy=policy.default)
        m.get_body(("plain",)).set_content(body)
        incoming = YandexMailProvider._parse_incoming(m.as_bytes(), email="buyer@example.com", uidvalidity="1", uid=self.n)
        incoming.received_at = received or datetime.now(UTC)
        return self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.acc, messages=[incoming])

    def jobs(self, status=None):
        with self.repo.connect() as c:
            return c.execute("SELECT COUNT(*) AS n FROM mail_analysis_jobs" + (" WHERE status=?" if status else ""), (status,) if status else ()).fetchone()["n"]

    def price_body(self, i: int) -> str:
        return f"Подшипник 6205-2RS1 — {500 + i} руб."


class GatingTest(CanaryBase):
    def test_the_environment_flag_alone_enqueues_nothing(self) -> None:
        r = self.receive(self.price_body(1))
        self.assertEqual((r["imported"], r["analysis_jobs_enqueued"], self.jobs()), (1, 0, 0))

    def test_only_the_allowlisted_workspace_can_be_enabled(self) -> None:
        self.assertEqual(ALLOWED_CANARY_WORKSPACES, frozenset({1}))
        other = _Fixture(self.repo, "other-ws@example.com")
        self.assertNotEqual(other.workspace_id, 1)
        with self.assertRaises(ValueError):
            self.repo.canary_enable(other.workspace_id)
        self.assertFalse(self.repo.canary_active(other.workspace_id))
        with self.repo.connect() as c:                                      # even a forged row does not open the gate
            c.execute("INSERT INTO mail_intelligence_canary(workspace_id, enabled, started_at, ends_at, updated_at) VALUES (?, 1, ?, ?, 'x')", (other.workspace_id, iso(self.started), iso(self.started + timedelta(days=14))))
        self.assertFalse(self.repo.canary_active(other.workspace_id))

    def test_a_row_without_the_environment_flag_does_nothing(self) -> None:
        self.enable()
        with mock.patch.dict(os.environ, {"MAIL_INTELLIGENCE_ON_SYNC": "0"}):
            self.assertFalse(self.repo.canary_active(self.ws))
            self.assertEqual(self.receive(self.price_body(2))["analysis_jobs_enqueued"], 0)

    def test_only_letters_received_after_canary_started_at_are_enqueued(self) -> None:
        self.enable()
        old = self.receive(self.price_body(3), received=self.started - timedelta(minutes=5))
        new = self.receive(self.price_body(4), received=self.started + timedelta(minutes=5))
        self.assertEqual((old["analysis_jobs_enqueued"], new["analysis_jobs_enqueued"]), (0, 1))

    def test_enabling_never_backfills_history(self) -> None:
        for i in range(3):
            self.receive(self.price_body(10 + i), received=self.started - timedelta(days=3))          # imported before the window, flag not active: no jobs
        r = self.enable()
        self.assertEqual((r["reconciled_jobs"], self.jobs()), (0, 0))

    def test_the_worker_only_serves_canary_workspaces(self) -> None:
        self.receive(self.price_body(5), received=self.started + timedelta(minutes=1)) if self.enable() else None
        other = _Fixture(self.repo, "other-ws2@example.com")
        with self.repo.connect() as c:
            c.execute("INSERT INTO mail_analysis_jobs(workspace_id, message_kind, message_id, job_type, analysis_version, status, next_attempt_at, created_at, updated_at) VALUES (?, 'mail_message', 1, 'body', 'v', 'queued', '2000-01-01', 'x', 'x')", (other.workspace_id,))
        job = self.repo.claim_analysis_job("w", canary_only=True)
        self.assertEqual(job["workspace_id"], self.ws)
        self.assertIsNone(self.repo.claim_analysis_job("w", canary_only=True))


class ReconcileInTickTest(CanaryBase):
    def test_a_letter_imported_by_a_process_without_the_flag_is_picked_up_by_the_worker_but_history_is_not(self) -> None:
        self.enable()
        with mock.patch.dict(os.environ, {"MAIL_INTELLIGENCE_ON_SYNC": "0"}):        # the app process runs without the flag
            self.receive(self.price_body(1), received=self.started + timedelta(minutes=1))
            self.receive(self.price_body(2), received=self.started - timedelta(days=2))
        self.assertEqual(self.jobs(), 0)
        out = self.repo.canary_tick(self.ws, "w1", models=EchoModels())
        self.assertEqual((out["reconciled_jobs"], self.jobs("done")), (1, 1))         # only the letter after started_at


class BudgetTest(CanaryBase):
    class Pricey(EchoModels):
        cost = 0.04

    def test_daily_cap_pauses_ai_jobs_but_mail_keeps_flowing_and_the_cap_is_never_raised(self) -> None:
        self.enable(daily_cap_rub=0.1, weekly_cap_rub=5.0)
        for i in range(5):
            self.receive(self.price_body(20 + i), received=self.started + timedelta(minutes=i + 1))
        m = self.Pricey()
        out = self.repo.canary_tick(self.ws, "w1", models=m)
        self.assertEqual(m.calls, 2)                                          # 0.04 + 0.04, third would need 0.04 + 0.05 reserve beyond 0.1
        self.assertEqual(out["jobs"]["deferred"], 3)
        spend = self.repo.canary_spend(self.ws)
        self.assertLessEqual(spend["day"], 0.1)
        self.assertEqual(self.jobs("done"), 2)
        self.assertEqual(self.jobs("queued"), 3)                              # nothing failed, nothing lost: waiting for the window
        more = self.receive(self.price_body(30), received=datetime.now(UTC))   # ordinary receive is unaffected
        self.assertEqual(more["imported"], 1)
        self.repo.canary_tick(self.ws, "w1", models=m)
        self.assertEqual(m.calls, 2)                                          # still paused: no automatic increase
        self.assertEqual(float(self.repo.canary_state(self.ws)["daily_cap_rub"]), 0.1)
        self.assertFalse(self.repo.evaluate_safety(self.ws))                  # pausing is not an incident

    def test_weekly_cap_is_enforced_independently(self) -> None:
        self.enable(daily_cap_rub=100.0, weekly_cap_rub=0.1)
        for i in range(4):
            self.receive(self.price_body(40 + i), received=self.started + timedelta(minutes=i + 1))
        m = self.Pricey()
        self.repo.canary_tick(self.ws, "w1", models=m)
        self.assertEqual(m.calls, 2)

    def test_defaults_are_the_agreed_caps(self) -> None:
        st = self.enable()
        self.assertEqual((float(st["daily_cap_rub"]), float(st["weekly_cap_rub"])), (1.0, 5.0))

    def test_overspend_is_a_stop_incident(self) -> None:
        self.enable(daily_cap_rub=0.1)
        with self.repo.connect() as c:
            c.execute("INSERT INTO mail_ai_reply_cache(workspace_id, request_key, stage, model, reply_json, cost_rub, created_at) VALUES (?, 'k', 'cheap', 'm', '{}', 0.5, ?)", (self.ws, iso(datetime.now(UTC))))
        self.assertIn("budget_cap_exceeded", [f["rule"] for f in self.repo.enforce_canary_safety(self.ws)])
        self.assertIsNotNone(self.repo.canary_state(self.ws)["stopped_at"])


class KillSwitchTest(CanaryBase):
    def test_enable_process_disable_receive_enable_again_without_loss_duplicates_or_double_payment(self) -> None:
        self.enable()
        self.receive(self.price_body(50), received=self.started + timedelta(minutes=1))
        m = EchoModels()
        self.repo.canary_tick(self.ws, "w1", models=m)
        self.assertEqual((m.calls, self.jobs("done")), (1, 1))
        self.repo.canary_disable(self.ws)
        self.assertFalse(self.repo.canary_active(self.ws))
        r = self.receive(self.price_body(51), received=datetime.now(UTC))     # mail is received normally while AI is off
        self.assertEqual((r["imported"], r["analysis_jobs_enqueued"]), (1, 0))
        self.assertEqual(self.repo.canary_tick(self.ws, "w1", models=m)["active"], False)
        self.assertEqual(m.calls, 1)                                          # nothing processed while disabled
        back = self.enable()
        self.assertEqual(back["reconciled_jobs"], 1)                         # only the letter that arrived meanwhile; the first one is NOT re-queued
        self.assertEqual(iso(self.started), back["started_at"])              # the window did not move: no new backfill
        self.repo.canary_tick(self.ws, "w1", models=m)
        self.repo.canary_tick(self.ws, "w1", models=m)
        self.assertEqual(m.calls, 2)                                          # one call per message, none repeated
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_messages WHERE direction='inbound'").fetchone()["n"], 2)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_facts").fetchone()["n"], 2)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM (SELECT request_key FROM mail_ai_reply_cache GROUP BY request_key HAVING COUNT(*)>1) x").fetchone()["n"], 0)
        self.assertFalse(self.repo.evaluate_safety(self.ws))

    def test_disabling_stops_claims_at_once_and_never_touches_mail_tables(self) -> None:
        self.enable()
        self.receive(self.price_body(60), received=self.started + timedelta(minutes=1))
        with self.repo.connect() as c:
            before = c.execute("SELECT COUNT(*) AS n FROM mail_messages").fetchone()["n"]
        self.repo.canary_disable(self.ws)
        self.assertIsNone(self.repo.claim_analysis_job("w", canary_only=True))
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_messages").fetchone()["n"], before)

    def test_a_stopped_canary_needs_an_explicit_owner_action_to_restart(self) -> None:
        self.enable()
        self.repo.canary_stop(self.ws, "false_request_scoped_price_fact", "test")
        with self.assertRaises(ValueError):
            self.repo.canary_enable(self.ws)
        self.assertFalse(self.repo.canary_active(self.ws))
        self.assertTrue(self.repo.canary_enable(self.ws, clear_stop=True)["enabled"])


class StopRulesTest(CanaryBase):
    def setUp(self) -> None:
        super().setUp()
        self.enable()
        self.receive(self.price_body(70), received=self.started + timedelta(minutes=1))
        self.repo.canary_tick(self.ws, "w1", models=EchoModels())
        self.assertFalse(self.repo.evaluate_safety(self.ws))                 # a clean run has no findings
        self.now = iso(datetime.now(UTC))

    def rules(self):
        return [f["rule"] for f in self.repo.evaluate_safety(self.ws)]

    def test_false_request_scoped_price_fact(self) -> None:
        with self.repo.connect() as c:
            c.execute("UPDATE mail_facts SET source_quote='цена по запросу'")
        self.assertIn("false_request_scoped_price_fact", self.rules())

    def test_fact_bound_to_the_wrong_request(self) -> None:
        with self.repo.connect() as c:
            c.execute("UPDATE mail_facts SET request_id=request_id+1")
        self.assertIn("fact_bound_to_wrong_request", self.rules())

    def test_duplicate_message(self) -> None:
        with self.repo.connect() as c:
            row = c.execute("SELECT * FROM mail_messages WHERE direction='inbound' ORDER BY id DESC LIMIT 1").fetchone()
            cols = [k for k in row.keys() if k != "id"]
            c.execute(f"INSERT INTO mail_messages({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [row[k] for k in cols])
        self.assertIn("duplicate_message", self.rules())

    def test_duplicate_fact(self) -> None:
        with self.repo.connect() as c:
            row = c.execute("SELECT * FROM mail_facts ORDER BY id DESC LIMIT 1").fetchone()
            cols = [k for k in row.keys() if k != "id"]
            c.execute(f"INSERT INTO mail_facts({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [row[k] for k in cols])
        self.assertIn("duplicate_fact", self.rules())

    def test_second_paid_call_for_the_same_key(self) -> None:
        with self.repo.connect() as c:
            c.execute("UPDATE mail_ai_runs SET repeat_of_same_content=1, cost_rub=0.01 WHERE provider<>'rules'")
        self.assertIn("second_paid_call_same_key", self.rules())

    def test_secret_material_in_diagnostics(self) -> None:
        with mock.patch.dict(os.environ, {"ROUTERAI_KEY": "sk-test-ABCDEFGHIJKLMNOP"}):
            with self.repo.connect() as c:
                c.execute("UPDATE mail_analysis_jobs SET last_error='boom sk-test-ABCDEFGHIJKLMNOP'")
            findings = self.repo.evaluate_safety(self.ws)
        self.assertIn("secret_in_logs_or_diagnostics", [f["rule"] for f in findings])
        self.assertNotIn("sk-test-ABCDEFGHIJKLMNOP", json.dumps(findings))    # the finding itself never repeats the secret

    def test_failed_jobs_over_five_percent_in_24_hours(self) -> None:
        with self.repo.connect() as c:
            for i in range(9):
                c.execute("INSERT INTO mail_analysis_jobs(workspace_id, message_kind, message_id, job_type, analysis_version, status, next_attempt_at, finished_at, created_at, updated_at) VALUES (?, 'mail_message', ?, 'body', 'f', ?, 'x', ?, 'x', ?)",
                          (self.ws, 500 + i, "failed" if i < 2 else "done", self.now, self.now))
        self.assertIn("failed_jobs_over_5_percent", self.rules())

    def test_backlog_that_does_not_shrink_for_30_minutes(self) -> None:
        with self.repo.connect() as c:
            c.execute("DELETE FROM mail_intelligence_queue_samples")
            for minutes, depth in ((34, 5), (25, 5), (15, 6), (5, 6), (1, 6)):
                c.execute("INSERT INTO mail_intelligence_queue_samples(workspace_id, depth, sampled_at) VALUES (?, ?, ?)", (self.ws, depth, iso(datetime.now(UTC) - timedelta(minutes=minutes))))
        self.assertIn("backlog_not_shrinking", self.rules())

    def test_a_shrinking_backlog_is_fine(self) -> None:
        with self.repo.connect() as c:
            c.execute("DELETE FROM mail_intelligence_queue_samples")
            for minutes, depth in ((34, 9), (25, 7), (15, 5), (5, 3), (1, 2)):
                c.execute("INSERT INTO mail_intelligence_queue_samples(workspace_id, depth, sampled_at) VALUES (?, ?, ?)", (self.ws, depth, iso(datetime.now(UTC) - timedelta(minutes=minutes))))
        self.assertNotIn("backlog_not_shrinking", self.rules())

    def test_worker_lock_contention_with_the_database(self) -> None:
        with self.repo.connect() as c:
            c.execute("UPDATE mail_analysis_jobs SET last_error='OperationalError: database is locked'")
        self.assertIn("worker_interferes_with_database", self.rules())

    def test_any_finding_stops_the_canary_and_the_worker_then_does_nothing(self) -> None:
        with self.repo.connect() as c:
            c.execute("UPDATE mail_facts SET source_quote='цена по запросу'")
        out = self.repo.canary_tick(self.ws, "w1", models=EchoModels())
        self.assertEqual(out["findings"][0]["rule"], "false_request_scoped_price_fact")
        self.assertEqual(self.repo.canary_state(self.ws)["stopped_reason"], "false_request_scoped_price_fact")
        self.receive(self.price_body(71), received=datetime.now(UTC))
        m = EchoModels()
        self.assertFalse(self.repo.canary_tick(self.ws, "w1", models=m)["active"])
        self.assertEqual(m.calls, 0)


class FormatsAndMetricsTest(CanaryBase):
    def png(self) -> bytes:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (400, 300), "white").save(buf, "PNG")
        return buf.getvalue()

    def test_text_formats_are_read_and_scans_go_to_manual_review_without_ocr_or_vision(self) -> None:
        self.enable()
        self.receive("КП во вложении.", files=[("kp.xlsx", xlsx(QUOTE)), ("scan.png", self.png())], received=self.started + timedelta(minutes=1))
        with mock.patch.object(AI, "ocr_image", side_effect=AssertionError("OCR must not run in the canary")):
            self.repo.canary_tick(self.ws, "w1", models=EchoModels())
        with self.repo.connect() as c:
            rows = {r["filename"]: dict(r) for r in c.execute("SELECT filename, status, manual_review, parser, reasons_json FROM mail_attachment_analyses").fetchall()}
            facts = c.execute("SELECT COUNT(*) AS n FROM mail_attachment_facts").fetchone()["n"]
        self.assertEqual((rows["kp.xlsx"]["manual_review"], rows["scan.png"]["manual_review"]), (0, 1))
        self.assertIn("scan_or_image_manual_review", rows["scan.png"]["reasons_json"])
        self.assertEqual(facts, 2)                                            # the xlsx lines only

    def test_metrics_contain_every_agreed_counter_and_no_content(self) -> None:
        self.enable()
        self.receive(self.price_body(80), received=self.started + timedelta(minutes=1))
        self.receive("Готовим предложение, вернёмся с ценой.", received=self.started + timedelta(minutes=2))
        self.repo.canary_tick(self.ws, "w1", models=EchoModels())
        m = self.repo.canary_metrics(self.ws)
        for key in ("received_messages", "analyzed_without_ai", "cheap_ai", "strong_ai", "manual_review", "jobs_failed", "jobs_retried", "duplicate_calls", "queue_depth", "analysis_p50_ms",
                    "analysis_p95_ms", "ai_cost_rub", "ai_cost_per_message_rub", "procurement_relevant_messages", "price_facts", "rejected_facts", "request_matching", "attachments"):
            self.assertIn(key, m)
        self.assertEqual((m["received_messages"], m["cheap_ai"], m["analyzed_without_ai"], m["price_facts"], m["queue_depth"]), (2, 1, 1, 1, 0))
        text = json.dumps(m, ensure_ascii=False)
        self.assertNotIn("Подшипник", text)
        self.assertNotIn("@", text)

    def test_final_summary_marks_a_limited_sample_and_the_review_rate_criterion(self) -> None:
        self.enable()
        self.receive(self.price_body(90), received=self.started + timedelta(minutes=1))
        self.repo.canary_tick(self.ws, "w1", models=EchoModels())
        s = self.repo.canary_final_summary(self.ws)
        self.assertTrue(s["limited_sample"])
        self.assertFalse(s["manual_review_rate_is_acceptance_criterion"])     # fewer than 10 procurement-relevant letters


if __name__ == "__main__":
    unittest.main()
