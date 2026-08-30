from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.crypto import generate_key
from mail.deliverability import DeliverabilityPreflightError
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import IncomingMessage, TokenSet


UTC = timezone.utc


class MailStatusSemanticsTests(unittest.TestCase):
    """Transport/response regressions for grouped request cards."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "status.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.user_id = int(self.user["id"])
        self.service = MailService(self.repo, lambda _provider: object(), generate_key())
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user_id,
            workspace_id=self.workspace_id,
            token_set=TokenSet("access", "refresh", 3600),
            email="buyer@example.com",
        )
        self.supplier_ids = self._add_group()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _add_group(self) -> list[int]:
        ids = []
        for index in range(4):
            host = f"status-{index}.example.com"
            email = f"status-{index}@example.com"
            supplier_id = self.repo.upsert_search_result(
                self.workspace_id,
                1043,
                host,
                host=host,
                title="Status company",
                snippet="test result",
            )
            self.repo.apply_supplier_enrichment(
                self.workspace_id,
                host,
                email=email,
                inn="7726347929",
                phone="+70000000000",
                region="Москва",
                company_name="Status company",
            )
            ids.append(supplier_id)
        return ids

    def _queue(self, supplier_id: int, email: str, key: str) -> dict:
        return self.service.queue_one(
            user_id=self.user_id,
            workspace_id=self.workspace_id,
            request_id=1043,
            supplier={"id": supplier_id, "email": email, "name": "Status company", "host": "status.example.com"},
            subject="Request",
            body="Body",
            idempotency_key=key,
        )

    def _set_message_status(self, message_id: int, status: str, error: str | None = None) -> None:
        with self.repo.connect() as connection:
            sent_at = "2026-08-30T10:00:00+00:00" if status == "sent" else None
            connection.execute(
                "UPDATE mail_messages SET status=?, sent_at=?, error=? WHERE id=?",
                (status, sent_at, error, message_id),
            )
            connection.execute(
                "UPDATE request_supplier_states SET status=?, last_error=? WHERE request_id=1043 AND last_message_id=?",
                ("sent" if status == "sent" else status, error, message_id),
            )

    def _company(self) -> dict:
        return next(
            item for item in self.repo.list_suppliers(self.workspace_id, 1043)
            if item["email_count"] == 4
        )

    def test_mixed_contacts_have_independent_delivery_and_response_axes(self) -> None:
        accepted = self._queue(self.supplier_ids[0], "status-0@example.com", "mixed-a")
        self._set_message_status(accepted["message_id"], "sent")
        self._queue(self.supplier_ids[1], "status-1@example.com", "mixed-b")
        failed = self._queue(self.supplier_ids[2], "status-2@example.com", "mixed-c")
        self._set_message_status(failed["message_id"], "failed", "provider rejected")

        company = self._company()
        self.assertEqual(company["delivery_counts"], {
            "not_sent": 1,
            "queued": 1,
            "accepted": 1,
            "failed": 1,
            "delivery_unknown": 0,
            "bounced": 0,
            "cancelled": 0,
        })
        self.assertEqual(company["response_status"], "waiting")
        self.assertEqual({contact["delivery_status"] for contact in company["contacts"]}, {"accepted", "queued", "failed", "not_sent"})
        self.assertEqual(self.repo.get_request(self.workspace_id, 1043)["mail_metrics"], {
            "outbound_total": 3,
            "queued": 1,
            "accepted": 1,
            "accepted_effective": 1,
            "failed": 1,
            "delivery_unknown": 0,
            "bounced": 0,
            "cancelled": 0,
            "replies": 0,
        })

    def test_accepted_contact_is_waiting_and_queued_is_not_waiting(self) -> None:
        accepted = self._queue(self.supplier_ids[0], "status-0@example.com", "waiting-a")
        self._set_message_status(accepted["message_id"], "sent")
        self._queue(self.supplier_ids[1], "status-1@example.com", "waiting-b")
        company = self._company()
        self.assertEqual(company["response_status"], "waiting")
        contacts = {contact["email"]: contact for contact in company["contacts"]}
        self.assertEqual(contacts["status-0@example.com"]["response_status"], "waiting")
        self.assertEqual(contacts["status-1@example.com"]["response_status"], "none")

    def test_answered_response_does_not_erase_accepted_transport(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "answered")
        self._set_message_status(queued["message_id"], "sent")
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="reply-1",
                message_id="<reply-1@example.com>",
                in_reply_to="<does-not-match>",
                references=queued.get("message_id_header"),
                from_email="status-0@example.com",
                to_email="buyer@example.com",
                subject="Re: Request",
                body_text="Ответ поставщика",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        company = self._company()
        self.assertEqual(company["response_status"], "answered")
        contact = next(item for item in company["contacts"] if item["email"] == "status-0@example.com")
        self.assertEqual(contact["delivery_status"], "accepted")
        self.assertEqual(contact["response_status"], "answered")

    def test_answered_company_is_skipped_even_when_an_alternate_is_untouched(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "answered-company")
        self._set_message_status(queued["message_id"], "sent")
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="reply-company-1",
                message_id="<reply-company-1@example.com>",
                in_reply_to=None,
                references=queued.get("message_id_header"),
                from_email="status-0@example.com",
                to_email="buyer@example.com",
                subject="Re: Request",
                body_text="Ответ поставщика",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        company = self._company()
        before = self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"]
        with self.assertRaises(DeliverabilityPreflightError):
            self.service.queue_one(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
                supplier={"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]},
                subject="Follow-up", body="Body", idempotency_key="answered-company-follow-up",
            )
        after = self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"]
        self.assertEqual(after, before)

    def test_card_level_answer_blocks_when_reply_sender_is_not_current_email(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "answered-card-fallback")
        self._set_message_status(queued["message_id"], "sent")
        with self.repo.connect() as connection:
            message_id_header = connection.execute(
                "SELECT message_id FROM mail_messages WHERE id=?",
                (queued["message_id"],),
            ).fetchone()[0]
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="reply-card-fallback-1",
                message_id="<reply-card-fallback-1@example.com>",
                in_reply_to=None,
                references=message_id_header,
                from_email="historical-reply@example.com",
                to_email="buyer@example.com",
                subject="Re: Request",
                body_text="Ответ поставщика",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        company = self._company()
        self.assertEqual(company["response_status"], "answered")
        current_contact = next(item for item in company["contacts"] if item["email"] == "status-0@example.com")
        self.assertEqual(current_contact["response_status"], "waiting")
        preflight = self.service.preflight_bulk(
            user_id=self.user_id,
            workspace_id=self.workspace_id,
            request_id=1043,
            suppliers=[{"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]}],
            subject="Follow-up",
            body="Body",
            attachments=[],
        )
        self.assertEqual(preflight["contact_selection"]["answered"], 1)
        self.assertIn("answered", preflight["recipient_results"][0]["reasons"])
        with self.assertRaises(DeliverabilityPreflightError):
            self.service.queue_one(
                user_id=self.user_id,
                workspace_id=self.workspace_id,
                request_id=1043,
                supplier={"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]},
                subject="Follow-up",
                body="Body",
                idempotency_key="answered-card-fallback-send",
            )

    def test_hard_bounce_is_effective_bounce_but_keeps_accepted_history(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "bounce")
        self._set_message_status(queued["message_id"], "sent")
        with self.repo.connect() as connection:
            outbound = connection.execute(
                "SELECT message_id FROM mail_messages WHERE id=?", (queued["message_id"],)
            ).fetchone()
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="bounce-1",
                message_id="<bounce-1@example.com>",
                in_reply_to=None,
                references=None,
                from_email="mailer-daemon@example.com",
                to_email="buyer@example.com",
                subject="Mail delivery failed",
                body_text="Final-Recipient: rfc822; status-0@example.com\n550 5.1.1 No such user",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        company = self._company()
        self.assertEqual(company["delivery_counts"]["bounced"], 1)
        self.assertEqual(company["delivery_counts"]["accepted"], 0)
        self.assertEqual(company["response_status"], "none")
        self.assertEqual(self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["accepted"], 1)
        self.assertEqual(self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["bounced"], 1)
        with self.repo.connect() as connection:
            history = connection.execute(
                "SELECT status, sent_at, message_id FROM mail_messages WHERE id=?", (queued["message_id"],)
            ).fetchone()
        self.assertEqual(history["status"], "sent")
        self.assertIsNotNone(history["sent_at"])
        self.assertEqual(history["message_id"], outbound["message_id"])

    def test_all_sent_contacts_are_not_in_not_sent_semantics(self) -> None:
        for index, supplier_id in enumerate(self.supplier_ids[:2]):
            queued = self._queue(supplier_id, f"status-{index}@example.com", f"all-sent-{index}")
            self._set_message_status(queued["message_id"], "sent")
        company = self._company()
        self.assertEqual(company["unsent_contact_count"], 2)
        self.assertEqual(company["delivery_counts"]["accepted"], 2)
        self.assertEqual(company["response_status"], "waiting")

    def test_no_contact_has_not_sent_count_and_is_not_a_queued_send(self) -> None:
        company = self._company()
        self.assertEqual(company["unsent_contact_count"], 4)
        self.assertEqual(company["delivery_counts"]["not_sent"], 4)
        self.assertEqual(company["delivery_counts"]["queued"], 0)

    def test_partial_send_keeps_unsent_contact_detail_without_not_sent_transport(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "partial")
        self._set_message_status(queued["message_id"], "sent")
        company = self._company()
        self.assertEqual(company["unsent_contact_count"], 3)
        self.assertEqual(company["response_status"], "waiting")

    def test_failed_contact_never_becomes_waiting(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "failed")
        self._set_message_status(queued["message_id"], "failed", "spam-policy")
        company = self._company()
        contact = next(item for item in company["contacts"] if item["email"] == "status-0@example.com")
        self.assertEqual(contact["delivery_status"], "failed")
        self.assertEqual(contact["response_status"], "none")
        self.assertNotEqual(company["response_status"], "waiting")

    def test_delivery_unknown_contact_never_becomes_waiting(self) -> None:
        queued = self._queue(self.supplier_ids[0], "status-0@example.com", "unknown")
        self._set_message_status(queued["message_id"], "delivery_unknown", "provider unavailable")
        company = self._company()
        contact = next(item for item in company["contacts"] if item["email"] == "status-0@example.com")
        self.assertEqual(contact["delivery_status"], "delivery_unknown")
        self.assertEqual(contact["response_status"], "none")

    def test_sent_count_is_historical_smtp_acceptance_not_effective_delivery(self) -> None:
        accepted = self._queue(self.supplier_ids[0], "status-0@example.com", "metrics-accepted")
        self._set_message_status(accepted["message_id"], "sent")
        queued = self._queue(self.supplier_ids[1], "status-1@example.com", "metrics-queued")
        bounced = self._queue(self.supplier_ids[2], "status-2@example.com", "metrics-bounced")
        self._set_message_status(bounced["message_id"], "sent")
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="metrics-bounce-1",
                message_id="<metrics-bounce-1@example.com>",
                in_reply_to=None,
                references=None,
                from_email="mailer-daemon@example.com",
                to_email="buyer@example.com",
                subject="Mail delivery failed",
                body_text="Final-Recipient: rfc822; status-2@example.com\\n550 5.1.1 No such user",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS sent_count FROM mail_messages WHERE request_id=1043 AND direction='outbound' AND status='sent'",
            ).fetchone()
        self.assertEqual(int(row["sent_count"]), 2)
        metrics = self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]
        self.assertEqual(metrics["outbound_total"], 3)
        self.assertEqual(metrics["queued"], 1)
        self.assertEqual(metrics["accepted"], 2)
        self.assertEqual(metrics["accepted_effective"], 1)
        self.assertEqual(metrics["bounced"], 1)

    def test_grouped_company_send_creates_one_outbound_message(self) -> None:
        company = self._company()
        self._queue(company["id"], company["email"], "one-card")
        with self.repo.connect() as connection:
            rows = connection.execute(
                "SELECT supplier_id, to_email FROM mail_messages WHERE request_id=1043 AND direction='outbound'"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(int(rows[0]["supplier_id"]), int(company["id"]))
        self.assertEqual(rows[0]["to_email"], company["email"])

    def test_company_send_uses_one_never_used_alternate_after_mixed_history(self) -> None:
        sent = self._queue(self.supplier_ids[0], "status-0@example.com", "four-sent")
        self._set_message_status(sent["message_id"], "sent")
        queued = self._queue(self.supplier_ids[1], "status-1@example.com", "four-queued")
        failed = self._queue(self.supplier_ids[2], "status-2@example.com", "four-failed")
        self._set_message_status(failed["message_id"], "failed", "provider rejected")
        company = self._company()
        result = self.service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            supplier={"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]},
            subject="Request", body="Body", idempotency_key="four-card",
        )
        with self.repo.connect() as connection:
            rows = connection.execute(
                "SELECT supplier_id, to_email FROM mail_messages WHERE request_id=1043 AND direction='outbound' ORDER BY id"
            ).fetchall()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]["to_email"], "status-3@example.com")
        self.assertEqual(int(rows[-1]["supplier_id"]), self.supplier_ids[3])
        self.assertIn("message_id", result)
        self.assertEqual(queued["message_id"], rows[1][0])

    def test_all_used_company_is_not_retried_without_explicit_override(self) -> None:
        for index, supplier_id in enumerate(self.supplier_ids):
            queued = self._queue(supplier_id, f"status-{index}@example.com", f"used-{index}")
            self._set_message_status(queued["message_id"], "failed" if index == 2 else "sent", "failed" if index == 2 else None)
        company = self._company()
        before = self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"]
        with self.assertRaises(DeliverabilityPreflightError):
            self.service.queue_one(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
                supplier={"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]},
                subject="Retry", body="Body", idempotency_key="all-used-blocked",
            )
        after = self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"]
        self.assertEqual(before, after)
        repeated = self.service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            supplier={"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]},
            subject="Retry", body="Body", idempotency_key="all-used-explicit", allow_repeat=True,
        )
        self.assertIn("message_id", repeated)
        self.assertEqual(self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"], before + 1)

    def test_queued_accepted_unknown_bounced_and_failed_are_not_auto_retried(self) -> None:
        fifth = self.repo.upsert_search_result(
            self.workspace_id, 1043, "status-4.example.com",
            host="status-4.example.com", title="Status company", snippet="test result",
        )
        self.repo.apply_supplier_enrichment(
            self.workspace_id, "status-4.example.com", email="status-4@example.com",
            inn="7726347929", phone="+70000000000", region="Москва", company_name="Status company",
        )
        sent = self._queue(self.supplier_ids[0], "status-0@example.com", "five-sent")
        self._set_message_status(sent["message_id"], "sent")
        self._queue(self.supplier_ids[1], "status-1@example.com", "five-queued")
        failed = self._queue(self.supplier_ids[2], "status-2@example.com", "five-failed")
        self._set_message_status(failed["message_id"], "failed", "provider rejected")
        unknown = self._queue(self.supplier_ids[3], "status-3@example.com", "five-unknown")
        self._set_message_status(unknown["message_id"], "delivery_unknown", "provider unavailable")
        bounced = self._queue(fifth, "status-4@example.com", "five-bounced")
        self._set_message_status(bounced["message_id"], "sent")
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="five-bounce",
                message_id="<five-bounce@example.com>",
                in_reply_to=None,
                references=None,
                from_email="mailer-daemon@example.com",
                to_email="buyer@example.com",
                subject="Mail delivery failed",
                body_text="Final-Recipient: rfc822; status-4@example.com\n550 5.1.1 No such user",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        company = next(item for item in self.repo.list_suppliers(self.workspace_id, 1043) if item["email_count"] == 5)
        before = self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"]
        result = self.service.preflight_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            suppliers=[{"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]}],
            subject="Retry", body="Body", attachments=[],
        )
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["eligible"], 0)
        self.assertEqual(self.repo.get_request(self.workspace_id, 1043)["mail_metrics"]["outbound_total"], before)


if __name__ == "__main__":
    unittest.main()
