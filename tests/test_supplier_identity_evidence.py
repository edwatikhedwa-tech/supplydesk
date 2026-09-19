"""EDW-13 / EDW-14 / GAP-003: identity evidence (request association vs supplier
identity vs contact evidence). Similarity is a weak signal; only confirmed
evidence may reuse a supplier identity."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.domain.supplier_identity.contact_linking import (
    is_free_mail,
    local_part_resembles_host,
    weak_candidate_supplier_ids,
)
from mail.crypto import generate_key
from mail.queue import MailQueue
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import IncomingMessage, TokenSet
from tests.test_mail_integration import FakeProvider

PERSONAL = "sfera.termo@yandex.ru"


class WeakSignalPureTest(unittest.TestCase):
    def test_resemblance_is_detected_but_only_as_a_weak_signal(self) -> None:
        self.assertTrue(local_part_resembles_host(PERSONAL, "termo-sfera.pro"))
        self.assertTrue(local_part_resembles_host("termosfera@gmail.com", "termo-sfera.pro"))
        self.assertEqual(weak_candidate_supplier_ids(PERSONAL, [(1, "termo-sfera.pro")]), [1])

    def test_no_signal_for_partial_short_or_corporate(self) -> None:
        self.assertFalse(local_part_resembles_host("termo.ivanov@yandex.ru", "termo-sfera.pro"))
        self.assertFalse(local_part_resembles_host("a.b@yandex.ru", "a-b.ru"))
        self.assertFalse(is_free_mail("info@termo-sfera.pro"))
        self.assertEqual(weak_candidate_supplier_ids("sfera.termo@termo-sfera.pro", [(1, "termo-sfera.pro")]), [])


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "evidence.sqlite3")
        self.repo.set_outgoing_enabled(True)
        self.user = self.repo.seed_user("ev-a@example.com", "correct-horse")
        self.ws = self.user["workspace_id"]
        self.provider = FakeProvider()
        self.service = MailService(self.repo, lambda _: self.provider, generate_key())
        self.account = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.ws,
            token_set=TokenSet("a", "r", 3600), email="user@example.com",
        )
        self.req = self._request(self.ws, self.user["id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _request(self, ws: int, user_id: int) -> int:
        return self.repo.create_request(
            ws, name="Заявка", description="", positions=[{"name": "Печь", "quantity": "1"}],
            sender_name="Buyer", company_name="ООО Тест", user_id=user_id,
        )

    def _host_supplier(self, host: str = "termo-sfera.pro", ws: int | None = None, req: int | None = None) -> int:
        return self.repo.upsert_supplier(
            workspace_id=ws or self.ws, external_key=host, name=host, email="", host=host,
            request_id=req or self.req,
        )

    def _queue_rfq(self) -> None:
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.ws, request_id=self.req,
            supplier={"name": "ООО Термосфера", "email": "info@termo-sfera.pro", "host": "termo-sfera.pro"},
            subject="Запрос", body="Текст",
        )

    def _send_rfq_and_get_reply_from(self, from_email: str) -> int:
        """Real flow: RFQ to the corporate address, then a header-matched reply from `from_email`."""
        self._queue_rfq()
        MailQueue(self.repo, self.service)._process(self.repo.claim_job())
        with self.repo.connect() as c:
            sent = c.execute(
                "SELECT supplier_id, message_id FROM mail_messages WHERE direction='outbound' AND request_id=?",
                (self.req,),
            ).fetchone()
        self.repo.import_incoming_messages(
            workspace_id=self.ws, user_id=self.user["id"], account_id=self.account, messages=[IncomingMessage(
                provider_message_id="imap:INBOX:1:1", message_id="<reply-1@yandex.ru>",
                in_reply_to=sent["message_id"], references=sent["message_id"],
                from_email=from_email, to_email="user@example.com", subject="Re: Запрос",
                body_text="Ответ", body_html="<p>Ответ</p>", received_at=datetime.now(timezone.utc),
            )],
        )
        return int(sent["supplier_id"])

    def _send_to(self, email: str, *, ws: int | None = None, req: int | None = None) -> dict:
        return self.repo.resolve_supplier_for_send(
            workspace_id=ws or self.ws, request_id=req or self.req, supplier_id=None, email=email,
            name="", host="", external_key="", user_id=self.user["id"],
        )

    def _count(self, ws: int | None = None) -> int:
        with self.repo.connect() as c:
            return c.execute("SELECT COUNT(*) FROM suppliers WHERE workspace_id=?", (ws or self.ws,)).fetchone()[0]


class ConfirmedEvidenceReusesIdentityTest(_Base):
    def test_rfq_sent_is_recorded_as_request_level_association_only(self) -> None:
        self._queue_rfq()
        rows = self.repo.list_supplier_identity_evidence(self.ws, email="info@termo-sfera.pro")
        self.assertEqual(
            [(r["source_type"], r["assertion"], r["strength"], r["request_id"]) for r in rows],
            [("rfq_sent", "association", "medium", self.req)],
        )

    def test_real_reply_from_personal_address_becomes_strong_evidence_and_reuses_identity(self) -> None:
        sid = self._send_rfq_and_get_reply_from(PERSONAL)
        evidence = self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid, email=PERSONAL)
        self.assertEqual(
            [(e["source_type"], e["strength"], e["state"]) for e in evidence],
            [("inbound_reply", "strong", "confirmed")],
        )
        before = self._count()
        result = self._send_to(PERSONAL)
        self.assertEqual(result["supplier_id"], sid)
        self.assertTrue(result["existing_supplier"])
        self.assertEqual(self._count(), before)
        self.assertEqual(self._send_to(PERSONAL)["supplier_id"], sid)  # repeat: idempotent
        self.assertEqual(self._count(), before)

    def test_user_confirmation_reuses_identity(self) -> None:
        sid = self._host_supplier()
        self.repo.confirm_supplier_contact(self.ws, self.user["id"], sid, PERSONAL, request_id=self.req)
        self.assertEqual(self._send_to(PERSONAL)["supplier_id"], sid)
        self.assertEqual(self._count(), 1)

    def test_backfill_from_existing_messages_is_idempotent(self) -> None:
        sid = self._send_rfq_and_get_reply_from(PERSONAL)
        with self.repo.connect() as c:
            c.execute("DELETE FROM supplier_identity_evidence")
        first = self.repo.backfill_email_evidence_from_messages(self.ws)
        n = len(self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid))
        self.repo.backfill_email_evidence_from_messages(self.ws)
        self.assertGreaterEqual(first["evidence_recorded"], 2)
        self.assertEqual(len(self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid)), n)


class NoEvidenceNeverLinksTest(_Base):
    def test_resemblance_alone_does_not_reuse_identity_but_is_recorded_as_candidate(self) -> None:
        sid = self._host_supplier()
        result = self._send_to(PERSONAL)
        self.assertNotEqual(result["supplier_id"], sid)  # no evidence -> no automatic union
        candidates = self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid, email=PERSONAL)
        self.assertEqual(
            [(c["source_type"], c["strength"], c["state"]) for c in candidates],
            [("name_token_similarity", "weak", "candidate")],
        )

    def test_candidate_evidence_is_never_used_to_link(self) -> None:
        sid = self._host_supplier()
        self._send_to(PERSONAL)  # records weak candidate on sid
        other_req = self._request(self.ws, self.user["id"])
        self._host_supplier(req=other_req)
        again = self._send_to(PERSONAL, req=other_req)
        self.assertNotEqual(again["supplier_id"], sid)

    def test_bounce_or_technical_sender_is_not_evidence(self) -> None:
        sid = self._send_rfq_and_get_reply_from("mailer-daemon@yandex.ru")
        self.assertEqual(
            self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid, email="mailer-daemon@yandex.ru"), [],
        )

    def test_unrelated_personal_email_creates_own_card_as_before(self) -> None:
        sid = self._host_supplier()
        result = self._send_to("ivanov.petr@yandex.ru")
        self.assertNotEqual(result["supplier_id"], sid)
        self.assertEqual(self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid, email="ivanov.petr@yandex.ru"), [])


class IsolationAndAmbiguityTest(_Base):
    def test_other_workspace_evidence_is_never_used(self) -> None:
        other = self.repo.seed_user("ev-b@example.com", "correct-horse")
        other_req = self._request(other["workspace_id"], other["id"])
        foreign = self._host_supplier(ws=other["workspace_id"], req=other_req)
        self.repo.confirm_supplier_contact(other["workspace_id"], other["id"], foreign, PERSONAL, request_id=other_req)
        result = self._send_to(PERSONAL)
        self.assertNotEqual(result["supplier_id"], foreign)
        self.assertEqual(self._count(other["workspace_id"]), 1)

    def test_cannot_confirm_a_foreign_workspace_supplier(self) -> None:
        other = self.repo.seed_user("ev-c@example.com", "correct-horse")
        foreign = self._host_supplier(ws=other["workspace_id"], req=self._request(other["workspace_id"], other["id"]))
        with self.assertRaises(ValueError):
            self.repo.confirm_supplier_contact(self.ws, self.user["id"], foreign, PERSONAL)

    def test_two_confirmed_candidates_are_refused_not_guessed(self) -> None:
        a = self._host_supplier("termo-sfera.pro")
        b = self._host_supplier("other-company.ru")
        self.repo.confirm_supplier_contact(self.ws, self.user["id"], a, PERSONAL)
        self.repo.confirm_supplier_contact(self.ws, self.user["id"], b, PERSONAL)
        before = self._count()
        with self.assertRaises(ValueError):
            self._send_to(PERSONAL)
        self.assertEqual(self._count(), before)  # nothing merged, nothing created

    def test_revoked_evidence_is_ignored(self) -> None:
        sid = self._host_supplier()
        self.repo.confirm_supplier_contact(self.ws, self.user["id"], sid, PERSONAL)
        self.repo.revoke_supplier_contact(self.ws, self.user["id"], sid, PERSONAL, reason="ошибка")
        self.assertNotEqual(self._send_to(PERSONAL)["supplier_id"], sid)


if __name__ == "__main__":
    unittest.main()
