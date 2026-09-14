from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.crypto import generate_key
from mail.providers.yandex import YandexMailProvider
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import IncomingMessage, TokenSet


class FakeTopicProvider:
    def __init__(self, preview: list[IncomingMessage], fetched: list[IncomingMessage]) -> None:
        self.preview = preview
        self.fetched = fetched
        self.preview_calls = 0
        self.fetch_calls = 0
        self.subjects: list[str] = []

    def preview_topic(self, _email: str, _token: str, *, subject: str, max_messages: int) -> list[IncomingMessage]:
        self.preview_calls += 1
        self.subjects.append(subject)
        assert max_messages == 200
        return self.preview

    def fetch_topic(self, _email: str, _token: str, *, subject: str, max_messages: int) -> list[IncomingMessage]:
        self.fetch_calls += 1
        self.subjects.append(subject)
        assert max_messages == 200
        return self.fetched


class MailTopicImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "topic.sqlite3")
        self.user = self.repo.seed_user("topic-owner@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.user_id = int(self.user["id"])
        created = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
        self.topic = "[SD-1061] Проверка запроса"
        self.preview_message = IncomingMessage(
            provider_message_id="imap:INBOX:1:20", message_id="<topic-20@example.com>",
            in_reply_to=None, references=None, from_email="supplier@example.com", to_email="buyer@example.com",
            subject="Re: [SD-1061] Проверка запроса", body_text="", body_html="", received_at=created,
            folder="INBOX", direction="inbound",
        )
        self.sent_message = IncomingMessage(
            provider_message_id="imap:Sent:1:21", message_id="<topic-21@example.com>",
            in_reply_to=None, references=None, from_email="buyer@example.com", to_email="supplier@example.com",
            subject=self.topic, body_text="Прошу проверить", body_html="<p>Прошу проверить</p>", received_at=created,
            folder="Sent", direction="outbound",
        )
        self.incoming_message = IncomingMessage(
            provider_message_id="imap:INBOX:1:20", message_id="<topic-20@example.com>",
            in_reply_to=None, references=None, from_email="supplier@example.com", to_email="buyer@example.com",
            subject="Re: [SD-1061] Проверка запроса", body_text="Да, получили", body_html="<p>Да, получили</p>", received_at=created,
            folder="INBOX", direction="inbound",
        )
        self.provider = FakeTopicProvider([self.preview_message], [self.sent_message, self.incoming_message])
        self.service = MailService(self.repo, lambda _provider: self.provider, generate_key())
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user_id, workspace_id=self.workspace_id,
            token_set=TokenSet("access-secret", "refresh-secret", 3600), email="buyer@example.com",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_preview_reads_headers_only_and_writes_nothing(self) -> None:
        preview = self.service.preview_mail_topic(self.user_id, self.workspace_id, subject=self.topic)
        self.assertEqual((preview["count"], preview["email_reference"], preview["existing_request_id"]), (1, "SD-1061", None))
        self.assertEqual(preview["items"][0]["folder"], "Входящие")
        self.assertEqual(self.provider.preview_calls, 1)
        self.assertEqual(self.provider.fetch_calls, 0)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages").fetchone()[0], 0)

    def test_confirmed_import_creates_draft_with_original_marker_and_all_messages(self) -> None:
        with self.assertRaisesRegex(ValueError, "подтвердите импорт"):
            self.service.import_mail_topic(self.user_id, self.workspace_id, subject=self.topic)
        result = self.service.import_mail_topic(self.user_id, self.workspace_id, subject=self.topic, confirmed=True)
        self.assertEqual((result["imported"], result["linked_suppliers"], result["created_suppliers"]), (2, 1, 1))
        request = self.repo.get_request(self.workspace_id, result["request_id"])
        self.assertEqual(request["email_reference"], "SD-1061")
        self.assertEqual(self.provider.fetch_calls, 1)
        with self.repo.connect() as connection:
            history = connection.execute("SELECT direction, subject FROM mail_messages WHERE request_id=? ORDER BY created_at", (result["request_id"],)).fetchall()
        self.assertEqual([row["direction"] for row in history], ["outbound", "inbound"])

    def test_existing_marker_is_never_reused_for_a_second_draft(self) -> None:
        existing_id = self.repo.create_request(
            self.workspace_id, user_id=self.user_id, name="Существующая", description="",
            positions=[{"name": "Позиция"}], sender_name="", company_name="", email_reference="SD-1061",
        )
        preview = self.service.preview_mail_topic(self.user_id, self.workspace_id, subject=self.topic)
        self.assertEqual(preview["existing_request_id"], existing_id)
        with self.assertRaisesRegex(ValueError, "уже существует"):
            self.service.import_mail_topic(self.user_id, self.workspace_id, subject=self.topic, confirmed=True)

    def test_sent_message_retains_every_to_recipient_for_topic_import(self) -> None:
        """One sent message to two suppliers must later create two waiting contacts."""
        message = YandexMailProvider._parse_incoming(
            (
                b"From: buyer@example.com\r\n"
                b"To: first@example.com, second@example.com\r\n"
                + "Subject: [SD-1061] Проверка запроса\r\n".encode("utf-8")
                + b"Message-ID: <two-recipients@example.com>\r\n"
                + b"\r\n"
                + "Проверяем обоих адресатов.".encode("utf-8")
            ),
            email="buyer@example.com",
            uidvalidity="1",
            uid=77,
            folder="Sent",
            direction="outbound",
        )
        self.assertIsNotNone(message)
        assert message is not None
        self.assertEqual(message.recipient_emails, ("first@example.com", "second@example.com"))

    def test_topic_import_creates_one_waiting_supplier_per_sent_recipient(self) -> None:
        sent_to_many = IncomingMessage(
            provider_message_id="imap:Sent:1:two", message_id="<topic-two@example.com>",
            in_reply_to=None, references=None, from_email="buyer@example.com", to_email="first@example.com",
            subject=self.topic, body_text="Проверяем", body_html="<p>Проверяем</p>",
            received_at=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc), folder="Sent", direction="outbound",
            recipient_emails=("first@example.com", "second@example.com"),
        )
        self.provider.fetched = [sent_to_many]
        result = self.service.import_mail_topic(self.user_id, self.workspace_id, subject=self.topic, confirmed=True)
        self.assertEqual((result["imported"], result["linked_suppliers"], result["created_suppliers"]), (2, 2, 2))
        with self.repo.connect() as connection:
            rows = connection.execute(
                """SELECT s.email, state.status FROM request_supplier_states state
                   JOIN suppliers s ON s.id=state.supplier_id
                   WHERE state.request_id=? ORDER BY s.email""",
                (result["request_id"],),
            ).fetchall()
        self.assertEqual([(row["email"], row["status"]) for row in rows], [
            ("first@example.com", "sent"), ("second@example.com", "sent"),
        ])

    def test_topic_import_keeps_all_sixty_sent_recipients(self) -> None:
        recipients = tuple(f"supplier-{index}@example.com" for index in range(60))
        sent_to_many = IncomingMessage(
            provider_message_id="imap:Sent:1:sixty", message_id="<topic-sixty@example.com>",
            in_reply_to=None, references=None, from_email="buyer@example.com", to_email=recipients[0],
            subject=self.topic, body_text="Проверяем", body_html="<p>Проверяем</p>",
            received_at=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc), folder="Sent", direction="outbound",
            recipient_emails=recipients,
        )
        self.provider.fetched = [sent_to_many]
        result = self.service.import_mail_topic(self.user_id, self.workspace_id, subject=self.topic, confirmed=True)
        self.assertEqual((result["imported"], result["linked_suppliers"], result["created_suppliers"]), (60, 60, 60))
        with self.repo.connect() as connection:
            statuses = connection.execute(
                "SELECT status FROM request_supplier_states WHERE request_id=?",
                (result["request_id"],),
            ).fetchall()
        self.assertEqual(len(statuses), 60)
        self.assertTrue(all(row["status"] == "sent" for row in statuses))


if __name__ == "__main__":
    unittest.main()
