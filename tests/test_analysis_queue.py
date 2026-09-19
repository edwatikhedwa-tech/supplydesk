"""EDW-38: acknowledgement / pending_quote without a model, routing before extraction, source vs request-scoped facts,
asynchronous analysis (sync only enqueues), retry, crash recovery, two workers, tenant isolation, cross-mailbox sent sync."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from mail import analysis_queue as Q
from mail.message_analysis import ANALYSIS_VERSION, ModelReply, classify_acknowledgement, normalize_text
from mail.providers.yandex import YandexMailProvider
from mail.repository import MailRepository
from tests.test_attachment_intelligence import QUOTE, xlsx
from tests.test_attachment_persistence import raw_mail
from tests.test_contact_intelligence import _Fixture

GOOD_QUOTE = {"message_type": "quote", "items": [{"name": "Подшипник SKF 6205-2RS1", "brand": None, "sku": "6205-2RS1", "quantity": None, "unit": None, "price": 500,
                                                  "currency": "RUB", "vat_included": None, "lead_time_days": None, "source_quote": "Подшипник 6205-2RS1 — 500 руб."}]}


class CountingModels:
    """Scripted cheap model; counts PAID calls (calls that reached the provider)."""

    def __init__(self, data=None) -> None:
        self.data, self.calls, self.lock = data if data is not None else GOOD_QUOTE, 0, threading.Lock()

    def model_for(self, stage):
        return "fake/cheap" if stage == "cheap" else None

    def call(self, stage, system, user, schema):
        with self.lock:
            self.calls += 1
        return ModelReply(self.data, "fake/cheap", "fake", 300, 60, 0.001, "catalog_estimate", 40)


class Boom:
    def model_for(self, stage):
        return "fake/cheap"

    def call(self, *a, **k):
        raise AssertionError("no model call allowed here")


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "q.sqlite3")
        self.fx = _Fixture(self.repo, "q-a@example.com")
        self.ws = self.fx.workspace_id
        self.req = self.fx.create_request(name="Подшипники")
        self.supplier, self.thread, _g = self.fx.add_supplier_thread(self.req, inn="7707083893", email="sales@podshipnik.example", host="podshipnik.example")
        with self.repo.connect() as c:
            self.subject = c.execute("SELECT subject FROM mail_threads WHERE id=?", (self.thread,)).fetchone()["subject"]
            self.acc = int(c.execute("SELECT mail_account_id FROM mail_threads WHERE id=?", (self.thread,)).fetchone()["mail_account_id"])
            if not c.execute("SELECT 1 FROM request_suppliers WHERE request_id=? AND supplier_id=?", (self.req, self.supplier)).fetchone():
                c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) VALUES (?, ?, '[]', 'test', 'manual', 'x')", (self.req, self.supplier))
        self.n = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def mail(self, subject=None, body="Добрый день!", files=(), sender="sales@podshipnik.example", enqueue=True, headers=True):
        self.n += 1
        raw = raw_mail(subject or ("Re: " + self.subject), list(files), msg_id=f"<q{self.n}-{id(self)}@x>", sender=sender)
        if body != "Добрый день!":
            import email
            from email import policy
            m = email.message_from_bytes(raw, policy=policy.default)
            m.get_body(("plain",)).set_content(body)
            raw = m.as_bytes()
        incoming = YandexMailProvider._parse_incoming(raw, email="buyer@example.com", uidvalidity="1", uid=self.n)
        return self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.acc, messages=[incoming], enqueue_analysis=enqueue)


class AcknowledgementTest(unittest.TestCase):
    def test_pending_quote_and_acknowledgement_are_deterministic(self) -> None:
        subject = "Re: Запрос цены [SD-1064]"
        for body in ("Готовим предложение, вернёмся с ценой.", "Направим КП позже.", "Цену пришлём завтра, уточняем у производителя.", "Вернёмся с ценой в ближайшее время."):
            self.assertEqual(classify_acknowledgement(normalize_text(subject, body)), "pending_quote", body)
        for body in ("Спасибо за запрос, принято в работу.", "Ваш запрос получен."):
            self.assertEqual(classify_acknowledgement(normalize_text(subject, body)), "acknowledgement", body)

    def test_anything_with_a_number_or_a_real_price_is_not_an_acknowledgement(self) -> None:
        for body in ("Готовим предложение: подшипник 6205 — 1 850 руб.", "Направим КП на 40 шт. позже.", "Цена 500 руб., подтвердим позже.", "Подшипник 6205-2RS1, вернёмся с ценой"):
            self.assertIsNone(classify_acknowledgement(normalize_text("Re", body)), body)

    def test_a_marker_or_a_date_alone_does_not_block_the_rule(self) -> None:
        self.assertEqual(classify_acknowledgement(normalize_text("Re", "По заявке [SD-1064] от 12.09.2026: направим КП позже.")), "pending_quote")


class RoutingBeforeExtractionTest(Base):
    def test_pending_quote_reply_costs_nothing_and_is_not_a_quote(self) -> None:
        r = self.mail(body="Готовим предложение, вернёмся с ценой.")
        res = self.repo.analyze_message(self.ws, r["imported_message_ids"][0], models=Boom())
        self.assertEqual((res["message_type"], res["ai_calls"], res["facts"]), ("pending_quote", 0, []))

    def test_unmatched_forward_without_a_price_makes_no_model_call_until_the_request_is_resolved(self) -> None:
        r = self.mail(subject="Fwd: КП от завода", body="Пересылаю предложение поставщика.", sender="someone@else.example")
        self.assertEqual((r["imported"], r["unmatched"]), (0, 1))
        res = self.repo.analyze_message(self.ws, r["unmatched_inbox_ids"][0], kind="inbox_message", models=Boom())
        self.assertEqual((res["ai_calls"], res["result"].get("rule"), res["status"]), (0, "awaiting_request_resolution", "needs_review"))

    def test_price_on_an_unmatched_letter_becomes_an_unscoped_source_fact_and_is_rebound_without_a_model(self) -> None:
        r = self.mail(subject="Предложение", body="Подшипник 6205-2RS1 — 500 руб.", sender="someone@else.example")
        inbox = r["unmatched_inbox_ids"][0]
        models = CountingModels()
        res = self.repo.analyze_message(self.ws, inbox, kind="inbox_message", models=models)
        self.assertEqual((models.calls, len(res["facts"])), (1, 1))
        with self.repo.connect() as c:
            fact = c.execute("SELECT id, request_id, supplier_id, source_quote, source_start FROM mail_facts WHERE message_id=?", (inbox,)).fetchone()
        self.assertEqual((fact["request_id"], fact["supplier_id"]), (None, None))                      # source fact: no request, no item
        self.assertTrue(fact["source_quote"])
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analysis_events").fetchone()["n"], 0)   # nothing downstream before a request exists
        self.repo.attach_inbox_message(self.ws, self.fx.user_id, inbox, self.req, self.supplier)
        with self.repo.connect() as c:
            fact = c.execute("SELECT request_id, supplier_id FROM mail_facts WHERE id=?", (fact["id"],)).fetchone()
            bindings = c.execute("SELECT method FROM mail_fact_bindings").fetchall()
            analysis = c.execute("SELECT status, match_method, request_id FROM mail_analyses WHERE message_id=? AND message_kind='inbox_message'", (inbox,)).fetchone()
        self.assertEqual((fact["request_id"], fact["supplier_id"]), (self.req, self.supplier))
        self.assertEqual(([b["method"] for b in bindings], analysis["status"], analysis["match_method"]), (["attach_inbox_message"], "final", "manual"))
        self.assertEqual(models.calls, 1)                                                                 # rebinding made no model call

    def test_attachments_of_an_unmatched_letter_are_kept_unread_and_move_with_the_link(self) -> None:
        import os
        os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
        self.addCleanup(os.environ.pop, "MAIL_INTELLIGENCE_ON_SYNC", None)
        self.repo.canary_enable(self.ws, started_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat())     # the environment flag alone is not enough any more
        r = self.mail(subject="Fwd: КП", body="Пересылаю.", files=[("kp.xlsx", xlsx(QUOTE))], sender="someone@else.example")
        inbox = r["unmatched_inbox_ids"][0]
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_inbox_attachments").fetchone()["n"], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_attachment_analyses").fetchone()["n"], 0)      # not read before resolution
        moved = self.repo.attach_inbox_message(self.ws, self.fx.user_id, inbox, self.req, self.supplier)
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_attachments WHERE message_id=?", (moved["message_id"],)).fetchone()["n"], 1)
            job = c.execute("SELECT job_type, status FROM mail_analysis_jobs WHERE message_id=? AND message_kind='mail_message'", (moved["message_id"],)).fetchone()
        self.assertEqual((job["job_type"], job["status"]), ("attachments", "queued"))


class AsyncAnalysisTest(Base):
    def test_sync_import_only_enqueues_and_analyses_nothing(self) -> None:
        r = self.mail(body="Подшипник 6205-2RS1 — 500 руб.", files=[("kp.xlsx", xlsx(QUOTE))])
        self.assertEqual((r["imported"], r["analysis_jobs_enqueued"]), (1, 2))
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analyses").fetchone()["n"], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_attachment_analyses").fetchone()["n"], 0)
            self.assertEqual(sorted(x["job_type"] for x in c.execute("SELECT job_type FROM mail_analysis_jobs").fetchall()), ["attachments", "body"])

    def test_the_worker_analyses_and_a_repeated_import_does_not_enqueue_or_pay_again(self) -> None:
        r = self.mail(body="Подшипник 6205-2RS1 — 500 руб.")
        m = CountingModels()
        s = self.repo.run_analysis_jobs("w1", models=m)
        self.assertEqual((s["done"], m.calls), (1, 1))
        with self.repo.connect() as c:
            c.execute("INSERT INTO mail_analysis_jobs(workspace_id, message_kind, message_id, job_type, analysis_version, status, next_attempt_at, created_at, updated_at) "
                      "VALUES (?, 'mail_message', ?, 'body', 'other', 'queued', '2000-01-01', 'x', 'x')", (self.ws, r["imported_message_ids"][0]))
        self.repo.run_analysis_jobs("w1", models=m)
        self.assertEqual(m.calls, 1)                                        # same message, same content hash: idempotent
        with self.repo.connect() as c:
            self.assertEqual(self.repo.enqueue_analysis_for_message(c, self.ws, "mail_message", r["imported_message_ids"][0]), 0)

    def test_crash_between_saving_the_letter_and_enqueueing_is_repaired_by_reconciliation(self) -> None:
        r = self.mail(body="Подшипник 6205-2RS1 — 500 руб.", enqueue=False)
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analysis_jobs").fetchone()["n"], 0)
        self.assertEqual(self.repo.enqueue_missing_analysis_jobs(self.ws, since="2000-01-01"), 1)
        self.assertEqual(self.repo.enqueue_missing_analysis_jobs(self.ws, since="2000-01-01"), 0)          # and only once
        m = CountingModels()
        self.assertEqual(self.repo.run_analysis_jobs("w1", models=m)["done"], 1)

    def test_retry_with_backoff_then_failed(self) -> None:
        self.mail(body="Подшипник 6205-2RS1 — 500 руб.")

        class Failing(CountingModels):
            def call(self, *a, **k):
                raise RuntimeError("provider down")
        for attempt in range(1, 5):
            with self.repo.connect() as c:
                c.execute("UPDATE mail_analysis_jobs SET next_attempt_at='2000-01-01' WHERE status='queued'")
            s = self.repo.run_analysis_jobs("w1", models=Failing())
            self.assertEqual(s["processed"], 1, attempt)
        with self.repo.connect() as c:
            job = c.execute("SELECT status, attempts, last_error FROM mail_analysis_jobs").fetchone()
        self.assertEqual((job["status"], job["attempts"]), ("failed", 4))

    def test_crash_after_the_model_answered_but_before_the_result_was_committed_does_not_pay_twice(self) -> None:
        import mail.message_analysis as MA
        self.mail(body="Подшипник 6205-2RS1 — 500 руб.")
        m = CountingModels()
        real = MA.validate_extraction
        armed = {"on": True}

        def dying(*a, **k):
            if armed["on"]:
                armed["on"] = False
                raise RuntimeError("process died after the model answered")
            return real(*a, **k)
        MA.validate_extraction = dying
        self.addCleanup(setattr, MA, "validate_extraction", real)
        first = self.repo.run_analysis_jobs("w1", models=m)
        self.assertEqual((first["retried"], m.calls), (1, 1))
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT status FROM mail_analyses").fetchone()["status"], "in_progress")     # what a crash leaves behind
            c.execute("UPDATE mail_analysis_jobs SET next_attempt_at='2000-01-01' WHERE status='queued'")
        second = self.repo.run_analysis_jobs("w2", models=m)
        self.assertEqual((second["done"], second["replays"], m.calls), (1, 1, 1))                                # replayed, not paid again
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT status FROM mail_analyses").fetchone()["status"], "final")
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_facts").fetchone()["n"], 1)

    def test_two_workers_never_analyse_one_message_twice(self) -> None:
        for _ in range(8):
            self.mail(body="Подшипник 6205-2RS1 — 500 руб.")          # eight different letters (message ids differ), identical text
        m = CountingModels()
        results: list = []

        def work(name):
            results.append(self.repo.run_analysis_jobs(name, models=m))
        threads = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sum(r["done"] for r in results), 8)
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analysis_jobs WHERE status='done'").fetchone()["n"], 8)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analyses").fetchone()["n"], 8)
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_facts").fetchone()["n"], 8)
        self.assertLessEqual(m.calls, 8)                                    # never more than one paid call per message

    def test_an_expired_lease_is_reclaimed_and_a_live_lease_is_not(self) -> None:
        self.mail(body="Подшипник 6205-2RS1 — 500 руб.")
        job = self.repo.claim_analysis_job("dead-worker", lease_seconds=300)
        self.assertIsNotNone(job)
        self.assertIsNone(self.repo.claim_analysis_job("w2"))                # lease alive
        with self.repo.connect() as c:
            c.execute("UPDATE mail_analysis_jobs SET lease_until='2000-01-01' WHERE id=?", (job["id"],))
        again = self.repo.claim_analysis_job("w2")
        self.assertEqual((again["id"], again["attempts"]), (job["id"], 2))
        self.assertEqual(self.repo.finish_analysis_job(job), "lost_claim")   # the dead worker can no longer complete it


class ReconciliationBoundTest(Base):
    def test_history_before_since_is_never_queued(self) -> None:
        self.mail(body="Подшипник 6205-2RS1 — 500 руб.", enqueue=False)
        self.assertEqual(self.repo.enqueue_missing_analysis_jobs(self.ws, since="2999-01-01"), 0)     # the flag was switched on "later": history stays untouched
        self.assertEqual(self.repo.enqueue_missing_analysis_jobs(self.ws, since="2000-01-01", limit=1), 1)


class TenantIsolationTest(unittest.TestCase):
    def test_jobs_replies_and_attachment_analyses_are_per_workspace(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = MailRepository(Path(temp.name) / "t.sqlite3")
        a, b = _Fixture(repo, "iso-a@example.com"), _Fixture(repo, "iso-b@example.com")
        self.assertNotEqual(a.workspace_id, b.workspace_id)
        reqs = {}
        for fx in (a, b):
            req = fx.create_request(name="Заявка")
            sup, thread, _g = fx.add_supplier_thread(req, inn="7707083893" if fx is a else "7701000011", email="s@x.example", host="x.example")
            with repo.connect() as c:
                t = c.execute("SELECT subject, mail_account_id FROM mail_threads WHERE id=?", (thread,)).fetchone()
            reqs[fx.workspace_id] = (req, t["subject"], int(t["mail_account_id"]), fx.user_id)
        data = xlsx(QUOTE)
        for i, fx in enumerate((a, b)):
            req, subject, acc, user = reqs[fx.workspace_id]
            inc = YandexMailProvider._parse_incoming(raw_mail("Re: " + subject, [("kp.xlsx", data)], msg_id=f"<iso{i}@x>", sender="s@x.example"), email="b@example.com", uidvalidity="1", uid=i + 1)
            repo.import_incoming_messages(workspace_id=fx.workspace_id, user_id=user, account_id=acc, messages=[inc], enqueue_analysis=True)
        only_a = repo.claim_analysis_job("wa", workspace_id=a.workspace_id)
        self.assertEqual(only_a["workspace_id"], a.workspace_id)
        repo.finish_analysis_job(only_a)
        for ws in (a.workspace_id, b.workspace_id):
            with repo.connect() as c:
                ids = [r["id"] for r in c.execute("SELECT id FROM mail_messages WHERE workspace_id=? AND direction='inbound'", (ws,)).fetchall()]
            repo.analyze_message_attachments(ws, ids[0])
        with repo.connect() as c:
            rows = c.execute("SELECT workspace_id, reused_from FROM mail_attachment_analyses ORDER BY id").fetchall()
        self.assertEqual([(r["workspace_id"], r["reused_from"]) for r in rows], [(a.workspace_id, None), (b.workspace_id, None)])   # same bytes, two tenants: no cross-tenant reuse
        with repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_attachment_facts WHERE workspace_id=?", (b.workspace_id,)).fetchone()["n"], 2)
        models = CountingModels()
        for fx in (a, b):
            cm = Q.CachingModels(models, repo, fx.workspace_id)
            cm.call("cheap", "s", "identical request", {})
        self.assertEqual(models.calls, 2)                                    # the reply cache is not shared between workspaces


class CrossMailboxSentSyncTest(Base):
    """Two mailboxes of one workspace: A -> B and B -> A, including the Sent folders."""

    def setUp(self) -> None:
        super().setUp()
        with self.repo.connect() as c:
            self.other = int(c.execute("INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at) VALUES (?, ?, 'mailru', 'boxb@example.com', 'connected', 'x', 'x')",
                                       (self.fx.user_id, self.ws)).lastrowid)
            c.execute("UPDATE mail_accounts SET email='boxa@example.com' WHERE id=?", (self.acc,))
            self.ref = c.execute("SELECT email_reference FROM request_email_references WHERE request_id=?", (self.req,)).fetchone()

    def sent_msg(self, mid, sender, to, subject):
        return SimpleNamespace(provider_message_id=f"imap:Sent:1:{mid}", message_id=f"<{mid}@x>", in_reply_to=None, references=None, from_email=sender, to_email=to,
                               subject=subject, body_text="t", body_html="", received_at=datetime.now(UTC), folder="Sent", direction="outbound", recipient_emails=(to,), attachments=())

    def objects(self, message_id):
        with self.repo.connect() as c:
            return sum(c.execute(f"SELECT COUNT(*) AS n FROM {t} WHERE message_id=?", (message_id,)).fetchone()["n"] for t in ("mail_messages", "mail_inbox_messages", "mail_sent_messages"))

    def test_b_to_a_sent_copy_is_not_a_second_object_in_either_order(self) -> None:
        ref = self.ref["email_reference"] if self.ref else "SD-1"
        subject = f"Re: Запрос [{ref}]"
        sent = self.sent_msg("ba1", "boxb@example.com", "boxa@example.com", subject)
        for order in ("inbound_first", "sent_first"):
            mid = f"<{order}@x>"
            sent = self.sent_msg(order, "boxb@example.com", "boxa@example.com", subject)
            inbound = YandexMailProvider._parse_incoming(raw_mail("Re: " + self.subject, [], msg_id=mid, sender="boxb@example.com", to="boxa@example.com"), email="boxa@example.com", uidvalidity="1", uid=90 + len(order))
            if order == "inbound_first":
                self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.acc, messages=[inbound], enqueue_analysis=False)
                self.repo.import_sent_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.other, messages=[sent])
            else:
                self.repo.import_sent_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.other, messages=[sent])
                self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.acc, messages=[inbound], enqueue_analysis=False)
            self.assertEqual(self.objects(mid), 1 if order == "sent_first" else 1, order)
            with self.repo.connect() as c:
                self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM suppliers WHERE lower(email)='boxa@example.com'").fetchone()["n"], 0, "no phantom supplier from a Sent copy")

    def test_a_to_b_outbound_is_one_object_after_syncing_both_mailboxes_and_both_sent_folders(self) -> None:
        with self.repo.connect() as c:
            c.execute("INSERT INTO mail_messages(thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id, message_id, direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, '<rfq1@x>', 'outbound', 'boxa@example.com', 'boxb@example.com', 'Запрос', 't', '', 'sent', 'x', 'x')",
                      (self.thread, self.ws, self.fx.user_id, self.req, self.supplier, self.acc))
        copy_in_b = YandexMailProvider._parse_incoming(raw_mail("Запрос", [], msg_id="<rfq1@x>", sender="boxa@example.com", to="boxb@example.com"), email="boxb@example.com", uidvalidity="1", uid=5)
        res = self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.other, messages=[copy_in_b], enqueue_analysis=True)
        self.assertEqual((res["imported"], res["unmatched"], res["skipped"], res["analysis_jobs_enqueued"]), (0, 0, 1, 0))
        self.repo.import_sent_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=self.acc, messages=[self.sent_msg("rfq1", "boxa@example.com", "boxb@example.com", "Запрос")])
        self.assertEqual(self.objects("<rfq1@x>"), 1)


if __name__ == "__main__":
    unittest.main()
