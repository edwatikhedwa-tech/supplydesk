from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from mail.crypto import generate_key
from mail.repository import MailRepository
from mail.service import MailService
from mail.providers.yandex import YandexMailProvider
from mail.types import IncomingBatch, IncomingMessage, TokenSet


class FakeSentProvider:
    def __init__(self, message: IncomingMessage) -> None:
        self.message = message
        self.preview_calls = 0
        self.fetch_calls = 0
        self.subject_markers: list[str | None] = []

    def preview_sent(self, _email: str, _token: str, *, subject_marker: str | None = None) -> dict[str, object]:
        self.preview_calls += 1
        self.subject_markers.append(subject_marker)
        return {"folder": "Sent", "marked_count": 1, "min_uid": 81, "max_uid": 81}

    def fetch_sent(self, _email: str, _token: str, *, uidvalidity: str | None, last_uid: int, max_messages: int, subject_marker: str | None = None) -> IncomingBatch:
        self.fetch_calls += 1
        self.subject_markers.append(subject_marker)
        self.assert_max(max_messages)
        return IncomingBatch("sent-validity", 81, [self.message], 1, "Sent")

    @staticmethod
    def assert_max(value: int) -> None:
        if value > 25:
            raise AssertionError("Sent import must remain bounded")


class SentMailSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "sent.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        self.request_id = self.repo.create_request(
            self.user["workspace_id"], user_id=self.user["id"], name="Кирпич", description="",
            positions=[{"name": "Кирпич", "quantity": "1000"}], sender_name="", company_name="",
        )
        now = "2026-09-13T10:00:00+00:00"
        with self.repo.connect() as connection:
            connection.execute(
                "INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.user["workspace_id"], "supplier.example", "Поставщик", "supplier@example.com", "supplier.example", now, now),
            )
            self.supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "INSERT INTO request_suppliers(request_id, supplier_id, updated_at) VALUES (?, ?, ?)",
                (self.request_id, self.supplier_id, now),
            )
        self.message = IncomingMessage(
            provider_message_id="imap:Sent:sent-validity:81",
            message_id="<sent-81@example.com>",
            in_reply_to=None,
            references=None,
            from_email="buyer@example.com",
            to_email="supplier@example.com",
            subject=f"[SD-{self.request_id}] Кирпич",
            body_text="Прошу КП",
            body_html="<p>Прошу КП</p>",
            received_at=datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc),
            folder="Sent",
            direction="outbound",
        )
        self.provider = FakeSentProvider(self.message)
        self.service = MailService(self.repo, lambda _provider: self.provider, generate_key())
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("access-secret", "refresh-secret", 3600), email="buyer@example.com",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_preview_is_read_only_and_import_requires_confirmation(self) -> None:
        preview = self.service.preview_sent(self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id)
        self.assertEqual(preview["marked_count"], 1)
        with self.assertRaisesRegex(ValueError, "подтвердите импорт"):
            self.service.sync_sent(self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_sent_messages").fetchone()[0], 0)

    def test_explicit_reference_links_request_and_is_idempotent(self) -> None:
        result = self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id, confirmed=True,
        )
        self.assertEqual((result["imported"], result["linked"], result["history_imported"]), (1, 1, 1))
        repeated = self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id, confirmed=True,
        )
        self.assertEqual((repeated["imported"], repeated["skipped"]), (0, 1))
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_sent_messages WHERE request_id=?", (self.request_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 1)
            state = connection.execute("SELECT folder, last_uid FROM mail_folder_sync_states WHERE mail_account_id=?", (self.account_id,)).fetchone()
        self.assertEqual((state["folder"], state["last_uid"]), ("Sent", 81))

    def test_resync_backfills_all_recipients_of_already_imported_sent_message(self) -> None:
        """A request imported before multi-recipient support must be repairable."""
        self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id, confirmed=True,
        )
        recipients = ("supplier@example.com", *(f"supplier-{index}@example.com" for index in range(59)))
        self.provider.message = replace(self.message, recipient_emails=recipients)

        self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id,
            request_id=self.request_id, confirmed=True,
        )

        with self.repo.connect() as connection:
            supplier_count = connection.execute(
                "SELECT COUNT(*) FROM request_suppliers WHERE request_id=?", (self.request_id,),
            ).fetchone()[0]
            sent_count = connection.execute(
                "SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,),
            ).fetchone()[0]
        self.assertEqual((supplier_count, sent_count), (60, 60))

    def test_request_scoped_preview_and_import_use_only_that_requests_marker(self) -> None:
        preview = self.service.preview_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id, request_id=self.request_id,
        )
        result = self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id,
            request_id=self.request_id, confirmed=True,
        )

        self.assertEqual(preview["email_reference"], f"SD-{self.request_id}")
        self.assertEqual(result["email_reference"], f"SD-{self.request_id}")
        self.assertEqual(self.provider.subject_markers, [f"SD-{self.request_id}", f"SD-{self.request_id}"])
        with self.repo.connect() as connection:
            state = connection.execute("SELECT folder FROM mail_folder_sync_states WHERE mail_account_id=?", (self.account_id,)).fetchone()
        self.assertEqual(state["folder"], f"Sent:SD-{self.request_id}")

    def test_request_scoped_import_rejects_a_different_valid_marker(self) -> None:
        other_request_id = self.repo.create_request(
            self.user["workspace_id"], user_id=self.user["id"], name="Другая заявка", description="",
            positions=[{"name": "Другая позиция", "quantity": "1"}], sender_name="", company_name="",
        )
        self.provider.message = IncomingMessage(
            provider_message_id="sent-other-request",
            message_id="<sent-other-request@example.com>",
            in_reply_to="",
            references="",
            from_email="buyer@example.com",
            to_email="supplier@example.com",
            subject=f"[SD-{other_request_id}] Не эта заявка",
            body_text="Проверка границы",
            body_html="",
            received_at=datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc),
        )

        result = self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id,
            request_id=self.request_id, confirmed=True,
        )

        self.assertEqual((result["imported"], result["skipped"]), (0, 1))
        with self.repo.connect() as connection:
            linked = connection.execute(
                "SELECT COUNT(*) FROM mail_sent_messages WHERE request_id=?", (other_request_id,),
            ).fetchone()[0]
        self.assertEqual(linked, 0)

    def test_unknown_reference_is_not_imported(self) -> None:
        self.provider.message = replace(
            self.message,
            provider_message_id="imap:Sent:sent-validity:82",
            message_id="<sent-82@example.com>",
            subject="[SD-999999] чужая заявка",
        )
        result = self.service.sync_sent(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id, confirmed=True,
        )
        self.assertEqual((result["imported"], result["invalid"]), (0, 1))

    def test_background_sent_sync_requires_explicit_opt_in(self) -> None:
        disabled = self.service.sync_sent_automatically(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id,
        )
        self.assertEqual(disabled["reason"], "sent_sync_disabled")
        self.assertEqual(self.provider.fetch_calls, 0)

        updated = self.service.set_sent_sync_enabled(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            mail_account_id=self.account_id, enabled=True,
        )
        self.assertTrue(updated["account"]["sent_sync_enabled"])
        result = self.service.sync_sent_automatically(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id,
        )
        self.assertEqual((result["imported"], result["linked"]), (1, 1))
        self.assertEqual(self.provider.subject_markers[-1], "[SD-")
        with self.repo.connect() as connection:
            state = connection.execute(
                "SELECT folder FROM mail_folder_sync_states WHERE mail_account_id=?", (self.account_id,),
            ).fetchone()
        self.assertEqual(state["folder"], "Sent:auto")

    def test_schema_can_be_reopened_after_sent_consent_column_exists(self) -> None:
        """Canonical SQLite is opened on every owner-server restart."""
        reopened = MailRepository(Path(self.temp.name) / "sent.sqlite3")
        self.assertIsNotNone(reopened.get_request(self.user["workspace_id"], self.request_id))


class SentFolderProviderTests(unittest.TestCase):
    def test_yandex_reads_only_marked_sent_folder(self) -> None:
        message = EmailMessage()
        message["From"] = "buyer@example.com"
        message["To"] = "supplier@example.com"
        message["Subject"] = "[SD-1043] Запрос"
        message["Message-ID"] = "<sent-folder@example.com>"
        message.set_content("Прошу КП")

        class Imap:
            def list(self):
                return "OK", [b'(\\HasNoChildren \\Sent) "/" "Sent"']

            def select(self, mailbox, readonly=True):
                self.mailbox = mailbox
                self.readonly = readonly
                return "OK", [b"1"]

            def response(self, key):
                return key, [b"sent-validity"]

            def uid(self, command, *args):
                if command == "SEARCH":
                    self.search_args = args
                    return "OK", [b"81"]
                if command == "FETCH":
                    return "OK", [(b"81 (BODY[])", message.as_bytes())]
                raise AssertionError(command)

            def logout(self):
                return "BYE", [b"bye"]

        imap = Imap()
        provider = YandexMailProvider("client", "secret")
        with patch.object(provider, "_imap_connection", return_value=imap):
            preview = provider.preview_sent("buyer@example.com", "token")
        self.assertEqual((preview["folder"], preview["marked_count"]), ("Sent", 1))
        with patch.object(provider, "_imap_connection", return_value=imap):
            batch = provider.fetch_sent("buyer@example.com", "token", uidvalidity=None, last_uid=0, max_messages=25)
        self.assertEqual((batch.folder, batch.messages[0].direction, batch.messages[0].provider_message_id), ("Sent", "outbound", "imap:Sent:sent-validity:81"))
        self.assertIn('HEADER Subject "SD-"', imap.search_args)

    def test_yandex_accepts_unquoted_imap_sent_mailbox(self) -> None:
        class Imap:
            def list(self):
                return "OK", [b'(\\HasNoChildren \\Sent) "/" Sent']

        self.assertEqual(YandexMailProvider._resolve_sent_folder(Imap()), "Sent")

    def test_yandex_can_search_one_request_marker(self) -> None:
        class Imap:
            def list(self):
                return "OK", [b'(\\HasNoChildren \\Sent) "/" "Sent"']

            def select(self, _mailbox, readonly=True):
                return "OK", [b"1"]

            def uid(self, command, *args):
                self.search_args = args
                return "OK", [b""]

            def logout(self):
                return "BYE", [b"bye"]

        imap = Imap()
        provider = YandexMailProvider("client", "secret")
        with patch.object(provider, "_imap_connection", return_value=imap):
            provider.preview_sent("buyer@example.com", "token", subject_marker="SD-1043")
        self.assertIn('HEADER Subject "SD-1043"', imap.search_args)

    def test_yandex_topic_search_uses_utf8_charset_for_cyrillic_subject(self) -> None:
        class Imap:
            capabilities = ()
            _encoding = "ascii"

            def uid(self, command, *args):
                self.args = (command, *args)
                return "OK", [b""]

        imap = Imap()
        YandexMailProvider._topic_search(
            imap, criterion='HEADER Subject "Проверка"', subject="Проверка",
        )
        self.assertEqual(imap.args[:3], ("SEARCH", "CHARSET", "UTF-8"))
        self.assertEqual(imap._encoding, "ascii")

    def test_yandex_topic_search_uses_sd_marker_to_collect_all_cyrillic_subjects(self) -> None:
        first = EmailMessage()
        first["From"] = "buyer@example.com"
        first["To"] = "supplier@example.com"
        first["Subject"] = "[SD-1061]проверка запроса"
        first["Message-ID"] = "<topic-1@example.com>"
        first.set_content("Первое")
        second = EmailMessage()
        second["From"] = "buyer@example.com"
        second["To"] = "supplier@example.com"
        second["Subject"] = "[SD-1061]проверка запроса"
        second["Message-ID"] = "<topic-2@example.com>"
        second.set_content("Второе")

        class Imap:
            def list(self):
                return "OK", [b'(\\HasNoChildren \\Sent) "/" "Sent"']

            def select(self, _mailbox, readonly=True):
                self.mailbox = _mailbox
                return "OK", [b"2"]

            def response(self, key):
                return key, [b"topic-validity"]

            def uid(self, command, *args):
                if command == "SEARCH":
                    self.search_args.append(args)
                    return "OK", [b"1 2"] if self.mailbox == "Sent" and "SD-1061" in str(args[-1]) else [b""]
                if command == "FETCH":
                    return "OK", [(b"BODY[]", first.as_bytes() if args[0] == "1" else second.as_bytes())]
                raise AssertionError(command)

            def logout(self):
                return "BYE", [b"bye"]

            search_args: list[tuple[object, ...]] = []

        imap = Imap()
        provider = YandexMailProvider("client", "secret")
        with patch.object(provider, "_imap_connection", return_value=imap):
            messages = provider.preview_topic("buyer@example.com", "token", subject="[SD-1061]проверка запроса", max_messages=200)
        self.assertEqual(len(messages), 2)
        self.assertTrue(any('[SD-1061]' in str(args[-1]) for args in imap.search_args))


if __name__ == "__main__":
    unittest.main()
