"""Identity confidence and contact quality are two different questions and must never collapse into
one score (EDW-14 follow-up).

  identity confidence: "does this address belong to THIS supplier?"   (evidence assertion/strength/state)
  contact quality:     "is this address a working, useful contact?"   (signals the evidence produces)
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.supplier_identity_evidence import _POLICY, _SIGNAL_MAP, sufficient_for_identity_reuse
from tests.test_contact_evidence_single_source import EMAIL, _Base


class PolicyTablesAreSeparateTest(unittest.TestCase):
    def test_manual_confirmation_is_strong_for_identity_but_only_weak_for_quality(self) -> None:
        assert _POLICY["manual_confirmed"][:2] == ("ownership", "strong")
        self.assertTrue(sufficient_for_identity_reuse(*_POLICY["manual_confirmed"]))
        self.assertEqual(_SIGNAL_MAP["manual_confirmed"], ("workspace_confirmed", "weak"))

    def test_inbound_reply_is_strong_for_both(self) -> None:
        self.assertTrue(sufficient_for_identity_reuse(*_POLICY["inbound_reply"]))
        self.assertEqual(_SIGNAL_MAP["inbound_reply"], ("inbound_reply", "strong"))

    def test_rfq_sent_is_neither_and_a_bounce_says_nothing_about_identity(self) -> None:
        self.assertFalse(sufficient_for_identity_reuse(*_POLICY["rfq_sent"]))
        self.assertNotIn("rfq_sent", _SIGNAL_MAP)
        for bounce in ("hard_bounce", "soft_bounce"):
            self.assertFalse(sufficient_for_identity_reuse(*_POLICY[bounce]))
            self.assertIn(bounce, _SIGNAL_MAP)

    def test_similarity_is_neither(self) -> None:
        self.assertFalse(sufficient_for_identity_reuse(*_POLICY["name_token_similarity"]))
        self.assertNotIn("name_token_similarity", _SIGNAL_MAP)


class EndToEndTest(_Base):
    def test_manual_confirmation_settles_identity_without_making_the_contact_look_proven(self) -> None:
        w, u = self.ws[0].workspace_id, self.ws[0].user_id
        self.repo.confirm_supplier_contact(w, u, self.sup[0], EMAIL)
        state = self.repo.contact_state(w, EMAIL)
        self.assertEqual((state["state"], state["identity_confidence"]), ("confirmed", "strong"))
        self.assertEqual(self.repo.contact_quality(w, EMAIL), {"positive_strong": 0, "positive_weak": 1, "negative": 0})
        contact = next(c for c in self.contacts(0)["global_contacts"] if c["email"] == EMAIL)
        self.assertFalse(contact["has_strong_signal"])          # quality has no strong proof
        self.assertEqual(contact["status"], "candidate")        # so it is not promoted by a confirmation alone

    def test_a_real_reply_is_strong_for_both(self) -> None:
        w = self.ws[0].workspace_id
        self.reply(0)
        self.contacts(0)  # raw-inserted message: the pull-based sync derives the evidence
        self.assertEqual(self.repo.contact_state(w, EMAIL)["identity_confidence"], "strong")
        self.assertEqual(self.repo.contact_quality(w, EMAIL)["positive_strong"], 1)
        self.assertTrue(next(c for c in self.contacts(0)["global_contacts"] if c["email"] == EMAIL)["has_strong_signal"])

    def test_rfq_only_gives_neither(self) -> None:
        w = self.ws[0].workspace_id
        self.ws[0].send_outbound(request_id=self.req[0], supplier_id=self.sup[0], to_email="quiet@yandex.ru",
                                 sent_at=datetime.now(timezone.utc))
        self.repo.backfill_email_evidence_from_messages(w)
        self.assertEqual(self.repo.contact_state(w, "quiet@yandex.ru")["identity_confidence"], "none")
        self.assertEqual(self.repo.contact_quality(w, "quiet@yandex.ru"), {"positive_strong": 0, "positive_weak": 0, "negative": 0})

    def test_a_bounce_is_negative_quality_and_no_identity(self) -> None:
        w = self.ws[0].workspace_id
        self.ws[0].receive_inbound(
            request_id=self.req[0], supplier_id=self.sup[0], from_email="mailer-daemon@yandex.ru",
            subject="Undelivered Mail Returned to Sender",
            body_text="550 5.1.1 User unknown\nFinal-Recipient: rfc822; dead.box@yandex.ru\nStatus: 5.1.1")
        self.repo.backfill_email_evidence_from_messages(w)
        self.assertEqual(self.repo.contact_state(w, "dead.box@yandex.ru")["identity_confidence"], "none")
        self.assertEqual(self.repo.contact_quality(w, "dead.box@yandex.ru")["negative"], 1)


class MigrationsArePostgresSafeTest(unittest.TestCase):
    def test_new_migrations_contain_no_question_mark_or_percent_anywhere(self) -> None:
        # PostgresConnection rewrites '?' to a placeholder even inside SQL comments, and psycopg treats '%'
        # as one: a stray character in a comment breaks the whole migration on PostgreSQL only (found in EDW-20).
        for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
            if int(path.name[:3]) >= 53:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("?", text, path.name)
                self.assertNotIn("%", text, path.name)


if __name__ == "__main__":
    unittest.main()
