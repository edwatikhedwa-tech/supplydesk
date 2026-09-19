"""EDW-35: inbound attachments are captured by the mail parser, stored once, analysed once per (bytes, version),
facts keep their locator, a repeat costs nothing. No network."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from mail.providers.yandex import YandexMailProvider
from mail.repository import MailRepository
from tests.test_attachment_intelligence import QUOTE, xlsx
from tests.test_contact_intelligence import _Fixture


def raw_mail(subject: str, files: list[tuple[str, bytes]], *, msg_id: str, sender: str = "sales@podshipnik.example", to: str = "buyer@example.com") -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = sender, to, subject, msg_id
    m.set_content("Добрый день! КП во вложении.")
    for name, data in files:
        m.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return m.as_bytes()


class Models:
    def __init__(self) -> None:
        self.calls = 0


class AttachmentPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "att.sqlite3")
        self.fx = _Fixture(self.repo, "att-a@example.com")
        self.ws = self.fx.workspace_id
        self.req = self.fx.create_request(name="Подшипники")
        with self.repo.connect() as c:
            c.execute("INSERT INTO request_positions(request_id, position_key, name, quantity, created_at) VALUES (?, 'pos-1', 'Подшипник SKF 6205-2RS1', '40', '2026-09-19')", (self.req,))
            c.execute("INSERT INTO request_positions(request_id, position_key, name, quantity, created_at) VALUES (?, 'pos-2', 'Подшипник 6306-2Z HRB', '30', '2026-09-19')", (self.req,))
        self.supplier, self.thread, self.global_supplier = self.fx.add_supplier_thread(self.req, inn="7707083893", email="sales@podshipnik.example", host="podshipnik.example")
        with self.repo.connect() as c:
            self.subject = c.execute("SELECT subject FROM mail_threads WHERE id=?", (self.thread,)).fetchone()["subject"]
        self.n = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def receive(self, files, *, msg_id=None):
        self.n += 1
        raw = raw_mail("Re: " + self.subject, files, msg_id=msg_id or f"<m{self.n}@x>")
        incoming = YandexMailProvider._parse_incoming(raw, email="buyer@example.com", uidvalidity="1", uid=self.n)
        with self.repo.connect() as c:
            acc = int(c.execute("SELECT mail_account_id FROM mail_threads WHERE id=?", (self.thread,)).fetchone()["mail_account_id"])
        return self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=acc, messages=[incoming]), incoming

    def test_parser_keeps_real_attachments_with_bytes(self) -> None:
        data = xlsx(QUOTE)
        _, incoming = self.receive([("kp.xlsx", data)])
        self.assertEqual([(a["filename"], a["size_bytes"], a["content"] == data) for a in incoming.attachments], [("kp.xlsx", len(data), True)])

    def test_import_stores_attachments_once_and_a_repeat_sync_does_not_duplicate(self) -> None:
        data = xlsx(QUOTE)
        first, incoming = self.receive([("kp.xlsx", data)], msg_id="<same@x>")
        self.assertEqual((first["imported"], len(first["imported_message_ids"])), (1, 1))
        with self.repo.connect() as c:
            acc = int(c.execute("SELECT mail_account_id FROM mail_threads WHERE id=?", (self.thread,)).fetchone()["mail_account_id"])
        again = self.repo.import_incoming_messages(workspace_id=self.ws, user_id=self.fx.user_id, account_id=acc, messages=[incoming])
        self.assertEqual((again["imported"], again["skipped"]), (0, 1))
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_attachments").fetchone()["n"], 1)

    def test_analysis_facts_have_locator_and_a_second_run_does_nothing(self) -> None:
        first, _ = self.receive([("kp.xlsx", xlsx(QUOTE))])
        mid = first["imported_message_ids"][0]
        one = self.repo.analyze_message_attachments(self.ws, mid)
        self.assertEqual((one["analysed"], one["facts"], one["ai_calls"]), (1, 2, 0))
        with self.repo.connect() as c:
            rows = c.execute("SELECT loc_json, match_json FROM mail_attachment_facts WHERE message_id=? ORDER BY position", (mid,)).fetchall()
        self.assertTrue(all('"sheet"' in r["loc_json"] for r in rows))
        self.assertIn('"exact"', rows[0]["match_json"])
        two = self.repo.analyze_message_attachments(self.ws, mid)
        self.assertEqual((two["analysed"], two["already_done"], two["facts"]), (0, 1, 2))
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_attachment_facts").fetchone()["n"], 2)

    def test_same_bytes_under_another_name_or_message_are_not_analysed_again(self) -> None:
        data = xlsx(QUOTE)
        a, _ = self.receive([("kp.xlsx", data)])
        b, _ = self.receive([("other-name.xlsx", data)])
        self.repo.analyze_message_attachments(self.ws, a["imported_message_ids"][0])
        second = self.repo.analyze_message_attachments(self.ws, b["imported_message_ids"][0])
        self.assertEqual((second["analysed"], second["reused_same_bytes"], second["facts"]), (0, 1, 2))
        with self.repo.connect() as c:
            row = c.execute("SELECT reused_from, ai_calls, cost_rub, ocr_pages FROM mail_attachment_analyses ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual((row["reused_from"] is not None, row["ai_calls"], row["cost_rub"], row["ocr_pages"]), (True, 0, 0, 0))

    def test_same_filename_with_changed_content_is_a_new_analysis(self) -> None:
        a, _ = self.receive([("kp.xlsx", xlsx(QUOTE))])
        changed = [list(r) for r in QUOTE]
        changed[3][5], changed[3][6] = 1900, 76000
        b, _ = self.receive([("kp.xlsx", xlsx(changed))])
        self.repo.analyze_message_attachments(self.ws, a["imported_message_ids"][0])
        second = self.repo.analyze_message_attachments(self.ws, b["imported_message_ids"][0])
        self.assertEqual((second["analysed"], second["reused_same_bytes"]), (1, 0))

    def test_a_broken_attachment_goes_to_manual_review_without_facts(self) -> None:
        a, _ = self.receive([("kp.xlsx", xlsx(QUOTE)[:150])])
        s = self.repo.analyze_message_attachments(self.ws, a["imported_message_ids"][0])
        self.assertEqual((s["facts"], s["items"][0]["status"]), (0, "unreadable"))


if __name__ == "__main__":
    unittest.main()


class E2EFindingsRegressionTest(unittest.TestCase):
    """Found by the real-mailbox end-to-end run (EDW-31)."""

    def test_our_own_request_subject_is_not_a_quote_signal(self) -> None:
        from mail.message_analysis import needs_extraction, normalize_text
        self.assertFalse(needs_extraction(normalize_text("Re: Запрос цены: Подшипники [SD-1064]", "Добрый день! Спасибо за запрос, принято в работу.")))
        self.assertFalse(needs_extraction(normalize_text("Re: Запрос цены: Подшипники [SD-1064]", "КП во вложении.")))
        self.assertTrue(needs_extraction(normalize_text("Re: Запрос", "Цену пришлём завтра, срок 5 дней.")))
        self.assertTrue(needs_extraction(normalize_text("Re: Запрос", "Подшипник 6205 — 1 850 руб.")))

    def test_the_inbound_copy_of_our_own_outbound_letter_is_not_a_second_object(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = MailRepository(Path(temp.name) / "dbl.sqlite3")
        fx = _Fixture(repo, "dbl-a@example.com")
        req = fx.create_request()
        supplier, thread, _g = fx.add_supplier_thread(req, inn="7707083893", email="b@example.com", host="example.com")
        fx.send_outbound(request_id=req, supplier_id=supplier, to_email="b@example.com", sent_at=datetime.now(UTC))
        with repo.connect() as c:
            c.execute("UPDATE mail_messages SET message_id='<own-rfq@yandex.ru>' WHERE direction='outbound'")
            row = c.execute("SELECT message_id, mail_account_id FROM mail_messages WHERE direction='outbound' ORDER BY id DESC LIMIT 1").fetchone()
            other = c.execute("INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at) VALUES (?, ?, 'mailru', 'b@example.com', 'connected', 'x', 'x')",
                              (fx.user_id, fx.workspace_id)).lastrowid
        raw = raw_mail("Запрос", [], msg_id=row["message_id"], sender="a@example.com", to="b@example.com")
        incoming = YandexMailProvider._parse_incoming(raw, email="b@example.com", uidvalidity="1", uid=1)
        res = repo.import_incoming_messages(workspace_id=fx.workspace_id, user_id=fx.user_id, account_id=int(other), messages=[incoming])
        self.assertEqual((res["imported"], res["unmatched"], res["skipped"]), (0, 0, 1))
        with repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_inbox_messages").fetchone()["n"], 0)


class BodyWithAttachmentsTest(AttachmentPersistenceTest):
    def test_a_letter_with_attachments_and_no_price_in_its_text_makes_no_model_call(self) -> None:
        a, _ = self.receive([("kp.xlsx", xlsx(QUOTE))])
        calls = []

        class Boom:
            def model_for(self, stage): return "m"
            def call(self, *args, **kwargs):
                calls.append(1)
                raise AssertionError("the model must not be called")
        res = self.repo.analyze_message(self.ws, a["imported_message_ids"][0], models=Boom())
        self.assertEqual((calls, res["status"]), ([], "final"))
