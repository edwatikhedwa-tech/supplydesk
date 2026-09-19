"""EDW-13 / GAP-003: связывание личного email с карточкой компании (чистая логика)
и поведение resolve_supplier_for_send на реальном MailRepository."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.domain.supplier_identity.contact_linking import (
    is_free_mail,
    local_part_matches_host,
    match_free_mail_contact,
)
from mail.repository import MailRepository


class ContactLinkingPureTest(unittest.TestCase):
    def test_reordered_tokens_match(self) -> None:
        self.assertTrue(local_part_matches_host("sfera.termo@yandex.ru", "termo-sfera.pro"))

    def test_concatenated_word_matches(self) -> None:
        self.assertTrue(local_part_matches_host("termosfera@gmail.com", "termo-sfera.pro"))

    def test_partial_overlap_does_not_match(self) -> None:
        self.assertFalse(local_part_matches_host("termo.ivanov@yandex.ru", "termo-sfera.pro"))
        self.assertFalse(local_part_matches_host("sales@yandex.ru", "termo-sfera.pro"))

    def test_short_tokens_never_match(self) -> None:
        self.assertFalse(local_part_matches_host("a.b@yandex.ru", "a-b.ru"))

    def test_corporate_email_is_not_free_mail(self) -> None:
        self.assertFalse(is_free_mail("info@termo-sfera.pro"))
        self.assertIsNone(match_free_mail_contact("sfera.termo@termo-sfera.pro", [(1, "termo-sfera.pro")]))

    def test_ambiguous_candidates_return_none(self) -> None:
        pairs = [(1, "termo-sfera.pro"), (2, "termo-sfera.ru")]
        self.assertIsNone(match_free_mail_contact("sfera.termo@yandex.ru", pairs))

    def test_single_candidate_returned(self) -> None:
        pairs = [(1, "termo-sfera.pro"), (2, "other.ru")]
        self.assertEqual(match_free_mail_contact("sfera.termo@yandex.ru", pairs), 1)


class ResolveSupplierForSendIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "identity.sqlite3")
        self.user = self.repo.seed_user("id-a@example.com", "correct-horse")
        self.ws = self.user["workspace_id"]
        self.req = self._request(self.ws, self.user["id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _request(self, ws: int, user_id: int) -> int:
        return self.repo.create_request(
            ws, name="Заявка", description="", positions=[{"name": "Печь", "quantity": "1"}],
            sender_name="Buyer", company_name="ООО Тест", user_id=user_id,
        )

    def _supplier(self, ws: int, req: int, host: str, email: str = "") -> int:
        return self.repo.upsert_supplier(
            workspace_id=ws, external_key=host, name=host, email=email, host=host, request_id=req,
        )

    def _send(self, email: str, req: int | None = None, ws: int | None = None) -> dict:
        return self.repo.resolve_supplier_for_send(
            workspace_id=ws or self.ws, request_id=req or self.req, supplier_id=None,
            email=email, name="", host="", external_key="", user_id=self.user["id"],
        )

    def _count(self, ws: int | None = None) -> int:
        with self.repo.connect() as c:
            return c.execute("SELECT COUNT(*) FROM suppliers WHERE workspace_id=?", (ws or self.ws,)).fetchone()[0]

    def test_personal_email_reuses_host_supplier_and_is_idempotent(self) -> None:
        sid = self._supplier(self.ws, self.req, "termo-sfera.pro")
        first = self._send("sfera.termo@yandex.ru")
        second = self._send("sfera.termo@yandex.ru")
        self.assertEqual((first["supplier_id"], second["supplier_id"]), (sid, sid))
        self.assertTrue(first["existing_supplier"])
        self.assertEqual(self._count(), 1)
        with self.repo.connect() as c:
            rows = c.execute(
                "SELECT COUNT(*) FROM request_suppliers WHERE request_id=? AND supplier_id=?", (self.req, sid),
            ).fetchone()[0]
        self.assertEqual(rows, 1)

    def test_unrelated_personal_email_keeps_old_behavior(self) -> None:
        sid = self._supplier(self.ws, self.req, "termo-sfera.pro")
        result = self._send("ivanov.petr@yandex.ru")
        self.assertNotEqual(result["supplier_id"], sid)
        self.assertEqual(self._count(), 2)

    def test_candidate_with_other_email_is_not_reused(self) -> None:
        sid = self._supplier(self.ws, self.req, "termo-sfera.pro", email="info@termo-sfera.pro")
        result = self._send("sfera.termo@yandex.ru")
        self.assertNotEqual(result["supplier_id"], sid)

    def test_two_matching_candidates_are_not_guessed(self) -> None:
        a = self._supplier(self.ws, self.req, "termo-sfera.pro")
        b = self._supplier(self.ws, self.req, "termo-sfera.ru")
        result = self._send("sfera.termo@yandex.ru")
        self.assertNotIn(result["supplier_id"], {a, b})

    def test_other_request_supplier_is_not_used(self) -> None:
        other_req = self._request(self.ws, self.user["id"])
        sid = self._supplier(self.ws, other_req, "termo-sfera.pro")
        result = self._send("sfera.termo@yandex.ru")
        self.assertNotEqual(result["supplier_id"], sid)

    def test_other_workspace_supplier_is_not_used(self) -> None:
        other = self.repo.seed_user("id-b@example.com", "correct-horse")
        other_req = self._request(other["workspace_id"], other["id"])
        foreign = self._supplier(other["workspace_id"], other_req, "termo-sfera.pro")
        result = self._send("sfera.termo@yandex.ru")
        self.assertNotEqual(result["supplier_id"], foreign)
        self.assertEqual(self._count(other["workspace_id"]), 1)


if __name__ == "__main__":
    unittest.main()
