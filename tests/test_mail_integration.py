from __future__ import annotations

import base64
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import supplier_app
from mail.content import clean_email_text
from mail.crypto import decrypt, generate_key, load_key
from mail.providers.yandex import YandexMailProvider
from mail.queue import MailQueue
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import IncomingMessage, OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.sent: list[OutgoingMessage] = []
        self.refresh_calls = 0
        self.connection_tokens: list[str] = []
        self.fail_with: ProviderError | None = None

    def exchange_code(self, code: str, *, redirect_uri: str, code_verifier: str) -> TokenSet:
        return TokenSet("access", "refresh", 3600)

    def refresh_token(self, refresh_token: str) -> TokenSet:
        self.refresh_calls += 1
        return TokenSet("access-refreshed", "refresh-new", 3600)

    def get_account(self, access_token: str) -> ProviderAccount:
        return ProviderAccount("user@example.com")

    def test_connection(self, email: str, access_token: str) -> None:
        self.connection_tokens.append(access_token)
        return None

    def send_message(self, access_token: str, message: OutgoingMessage) -> SendResult:
        if self.fail_with:
            raise self.fail_with
        self.sent.append(message)
        return SendResult(message.message_id or "<generated@example.com>", None, datetime.now(timezone.utc))


class MailIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "test.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        self.provider = FakeProvider()
        self.service = MailService(self.repo, lambda _: self.provider, generate_key())
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("access-secret", "refresh-secret", 3600), email="user@example.com",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_email_text_removes_css_artifact_but_keeps_message(self) -> None:
        body = ".mail-address a,\n.mail-address a[href] {\ntext-decoration: none !important;\ncolor: #000000 !important;\n}\n\nЗдравствуйте, Эдуард!"
        self.assertEqual(clean_email_text(body), "Здравствуйте, Эдуард!")

    def test_html_email_text_ignores_style_nodes(self) -> None:
        self.assertEqual(
            clean_email_text(".mail-address { color: red; }", "<style>.mail-address{color:red}</style><p>Ответ поставщика</p>"),
            "Ответ поставщика",
        )

    def test_email_text_removes_minified_nested_css(self) -> None:
        body = "Эти акции только у нас! 96 * { } body { } :root { color-scheme: light dark; } @media screen and (max-width: 480px) { .mobshow { display: inline-block !important; } } Уникальные предложения от застройщиков"
        self.assertEqual(clean_email_text(body), "Эти акции только у нас! 96\n\nУникальные предложения от застройщиков")

    def test_tokens_are_encrypted_and_oauth_state_is_one_time_and_bound(self) -> None:
        account = self.repo.get_mail_account(self.user["id"], self.user["workspace_id"])
        self.assertNotIn("access-secret", account["access_token_encrypted"])
        self.assertNotEqual(account["refresh_token_encrypted"], "refresh-secret")
        session, _csrf = self.repo.create_session(self.user["id"], self.user["workspace_id"])
        self.repo.create_oauth_state(
            state="state-1", session_token=session, user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            code_verifier="verifier", redirect_uri="http://localhost/callback",
        )
        self.assertIsNone(self.repo.consume_oauth_state("state-1", "another-session"))
        consumed = self.repo.consume_oauth_state("state-1", session)
        self.assertEqual(consumed["code_verifier"], "verifier")
        self.assertIsNone(self.repo.consume_oauth_state("state-1", session))

    def test_incoming_parser_keeps_the_senders_own_html(self) -> None:
        # Regression: the parser used to discard the text/html part and rebuild
        # "HTML" from the hard-wrapped plain text, which destroyed every link.
        message = EmailMessage()
        message["From"] = "noreply@id.yandex.ru"
        message["To"] = "buyer@example.com"
        message["Subject"] = "Настройки изменены"
        message["Message-ID"] = "<rich@yandex>"
        message.set_content("Вы обновили настройки приложения «\nB2B Platform Mail Access\n» на сервисе.")
        message.add_alternative(
            '<p>Вы обновили настройки приложения '
            '<a href="https://oauth.yandex.ru/client/1">B2B Platform Mail Access</a> на сервисе.</p>'
            "<ul><li>посмотреть историю входов</li><li>сменить пароль</li></ul>",
            subtype="html",
        )
        parsed = YandexMailProvider._parse_incoming(
            message.as_bytes(), email="buyer@example.com", uidvalidity="1", uid=7
        )
        self.assertIsNotNone(parsed)
        self.assertIn('href="https://oauth.yandex.ru/client/1"', parsed.body_html)
        self.assertIn("<li>", parsed.body_html)
        # And the sanitized form still keeps that structure for the reader.
        from mail.content import sanitize_email_html

        cleaned = sanitize_email_html(parsed.body_html)
        self.assertIn("<li>", cleaned)
        self.assertIn("oauth.yandex.ru", cleaned)

    def test_email_html_is_allowlisted_and_keeps_readable_structure(self) -> None:
        from mail.content import email_has_remote_images, sanitize_email_html

        for payload in (
            "<script>alert(1)</script>",
            '<img src="x" onerror="alert(1)">',
            '<iframe src="https://evil"></iframe>',
            '<form action="https://evil"><input name="pw"></form>',
            "<svg onload=alert(1)></svg>",
            '<p style="position:fixed">x</p>',
        ):
            cleaned = sanitize_email_html(payload).lower()
            for forbidden in ("script", "onerror", "onload", "<iframe", "<form", "<svg", "style="):
                self.assertNotIn(forbidden, cleaned)

        cleaned = sanitize_email_html('<a href="javascript:alert(1)">click</a>')
        self.assertNotIn("javascript:", cleaned)
        self.assertIn("click", cleaned)

        # Structure a reader depends on survives, and links are hardened.
        rich = sanitize_email_html('<p>Настройки <a href="https://oauth.yandex.ru">приложения</a></p><ul><li>первое</li></ul>')
        self.assertIn("<ul>", rich)
        self.assertIn("<li>", rich)
        self.assertIn('href="https://oauth.yandex.ru"', rich)
        self.assertIn("noopener", rich)

        # Tracking pixels are withheld until the reader opts in.
        pixel = '<p>текст</p><img src="https://track.example/p.gif">'
        self.assertTrue(email_has_remote_images(pixel))
        self.assertNotIn("<img", sanitize_email_html(pixel))
        self.assertIn("<img", sanitize_email_html(pixel, allow_remote_images=True))

    def test_stored_message_exposes_both_html_and_text_renderings(self) -> None:
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "ООО Тест", "email": "one@example.com", "host": "one.example"},
            subject="Запрос", body="Здравствуйте!",
        )
        supplier = next(item for item in self.repo.list_suppliers(self.user["workspace_id"], None) if item["host"] == "one.example")
        messages = self.repo.thread_messages(self.user["workspace_id"], 1043, supplier["id"])
        self.assertTrue(messages)
        self.assertIn("body_html", messages[0])
        self.assertIn("has_remote_images", messages[0])
        self.assertIn("Здравствуйте", messages[0]["body_text"])

    def test_oauth_login_state_is_one_time_and_not_bound_to_a_session(self) -> None:
        self.repo.create_oauth_login_state(state="login-state-1", code_verifier="verifier", redirect_uri="http://localhost/callback")
        self.assertIsNone(self.repo.consume_oauth_login_state("wrong-state"))
        consumed = self.repo.consume_oauth_login_state("login-state-1")
        self.assertEqual(consumed["code_verifier"], "verifier")
        self.assertIsNone(self.repo.consume_oauth_login_state("login-state-1"))

    def test_yandex_login_finds_or_creates_a_user_without_a_usable_password(self) -> None:
        created = self.repo.get_or_create_oauth_user("New.Buyer@Example.com", "Новый снабженец")
        self.assertIsNone(self.repo.authenticate("new.buyer@example.com", ""))
        self.assertIsNone(self.repo.authenticate("new.buyer@example.com", "any-guessed-password"))
        again = self.repo.get_or_create_oauth_user("new.buyer@example.com", "Новый снабженец")
        self.assertEqual(created["id"], again["id"])
        self.assertEqual(created["workspace_id"], again["workspace_id"])
        self.assertNotEqual(created["workspace_id"], self.user["workspace_id"])

    def test_queue_creates_separate_thread_and_message_for_each_supplier(self) -> None:
        result = self.service.queue_bulk(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            suppliers=[
                {"name": "ООО Первый", "email": "one@example.com", "host": "one.example"},
                {"name": "ООО Второй", "email": "two@example.com", "host": "two.example"},
            ],
            subject="Запрос КП", body="Здравствуйте, {{supplier_name}}!\n{{request_name}}",
        )
        self.assertEqual(len(result), 2)
        first = self.repo.claim_job()
        second = self.repo.claim_job()
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first["to_email"], second["to_email"])
        self.assertTrue(first["message_id_header"].startswith("<"))
        for job in (first, second):
            send_result = self.service.send_claimed_job(job)
            self.repo.mark_job_sent(job["id"], job["message_id"], None, send_result.message_id, send_result.sent_at.isoformat())
        statuses = self.repo.request_statuses(self.user["workspace_id"], 1043)
        self.assertEqual({item["status"] for item in statuses}, {"sent"})
        self.assertEqual(len(self.provider.sent), 2)
        self.assertIn("ООО Первый", self.provider.sent[0].body_text + self.provider.sent[1].body_text)

    def test_invalid_recipient_and_attachment_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.queue_one(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
                supplier={"name": "Bad", "email": "not-an-email", "host": "bad"}, subject="x", body="y",
            )
        with self.assertRaises(ValueError):
            self.service.queue_one(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
                supplier={"name": "Good", "email": "good@example.com", "host": "good"}, subject="x", body="y",
                attachments=[{"filename": "secret.exe", "mime_type": "application/octet-stream", "content_base64": base64.b64encode(b"x").decode()}],
            )

    def test_expired_access_token_is_refreshed_before_connection_test(self) -> None:
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_accounts SET token_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (self.account_id,))
        self.service.test_connection(self.user["id"], self.user["workspace_id"])
        self.assertEqual(self.provider.refresh_calls, 1)
        self.assertEqual(self.provider.connection_tokens, ["access-refreshed"])
        refreshed = self.repo.get_mail_account_by_id(self.account_id)
        self.assertNotIn("refresh-new", refreshed["refresh_token_encrypted"])

    def test_disconnected_account_cannot_queue_message(self) -> None:
        self.service.disconnect(self.user["id"], self.user["workspace_id"])
        with self.assertRaises(ProviderError):
            self.service.queue_one(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
                supplier={"name": "Good", "email": "good@example.com", "host": "good"}, subject="x", body="y",
            )

    def test_repeated_send_reuses_request_supplier_thread(self) -> None:
        kwargs = dict(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "Good", "email": "good@example.com", "host": "good"}, subject="Запрос", body="Повтор",
        )
        first = self.service.queue_one(**kwargs)
        second = self.service.queue_one(**kwargs)
        self.assertEqual(first["thread_id"], second["thread_id"])
        self.assertNotEqual(first["message_id"], second["message_id"])

    def test_transient_send_failure_is_requeued_with_bounded_retry(self) -> None:
        self.provider.fail_with = ProviderError("Временная ошибка", transient=True)
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "Good", "email": "good@example.com", "host": "good"}, subject="Запрос", body="Текст",
        )
        job = self.repo.claim_job()
        MailQueue(self.repo, self.service, max_retries=2)._process(job)
        self.assertEqual(self.repo.queue_stats(self.user["workspace_id"]), {"queued": 1})

    def test_yandex_message_builds_message_id_and_reply_headers(self) -> None:
        message = YandexMailProvider._build_email(
            OutgoingMessage(
                from_email="user@yandex.ru", to_email="supplier@example.com", subject="Subject",
                body_text="Hello", body_html="<p>Hello</p>", message_id="<id@example.com>",
                in_reply_to="<parent@example.com>", references="<parent@example.com>",
            ),
            "<id@example.com>",
        )
        self.assertEqual(message["Message-ID"], "<id@example.com>")
        self.assertEqual(message["In-Reply-To"], "<parent@example.com>")
        self.assertEqual(message["References"], "<parent@example.com>")

    def test_incoming_reply_is_linked_and_deduplicated(self) -> None:
        queued = self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "Supplier", "email": "supplier@example.com", "host": "supplier.example"},
            subject="Запрос", body="Текст",
        )
        job = self.repo.claim_job()
        MailQueue(self.repo, self.service)._process(job)
        incoming = IncomingMessage(
            provider_message_id="imap:INBOX:123:9", message_id="<reply@example.com>",
            in_reply_to="<generated@example.com>", references="<generated@example.com>",
            from_email="supplier@example.com", to_email="user@example.com", subject="Re: Запрос",
            body_text="Ответ поставщика", body_html="<p>Ответ поставщика</p>", received_at=datetime.now(timezone.utc),
        )
        result = self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id, messages=[incoming],
        )
        self.assertEqual(result["imported"], 1)
        with self.repo.connect() as connection:
            supplier = connection.execute("SELECT id FROM suppliers WHERE external_key='supplier.example'").fetchone()
        messages = self.repo.thread_messages(self.user["workspace_id"], 1043, supplier["id"])
        self.assertEqual(messages[-1]["direction"], "inbound")
        self.assertEqual(messages[-1]["status"], "received")
        status = next(item for item in self.repo.request_statuses(self.user["workspace_id"], 1043) if item["external_key"] == "supplier.example")
        self.assertEqual(status["status"], "replied")
        duplicate = self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id, messages=[incoming],
        )
        self.assertEqual(duplicate["skipped"], 1)

    def test_unmatched_incoming_is_kept_in_inbox_and_deduplicated(self) -> None:
        incoming = IncomingMessage(
            provider_message_id="imap:INBOX:123:10", message_id="<unmatched@example.com>",
            in_reply_to=None, references=None, from_email="unknown@example.com", to_email="user@example.com",
            subject="Новое письмо", body_text="Письмо без известной заявки", body_html="<p>Письмо без известной заявки</p>",
            received_at=datetime.now(timezone.utc),
        )
        result = self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id, messages=[incoming],
        )
        self.assertEqual(result["unmatched"], 1)
        self.assertEqual(self.repo.list_unmatched_incoming(self.user["workspace_id"])[0]["subject"], "Новое письмо")
        duplicate = self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id, messages=[incoming],
        )
        self.assertEqual(duplicate["skipped"], 1)

    def test_yandex_incoming_parser_keeps_plain_text_and_headers(self) -> None:
        message = EmailMessage()
        message["From"] = "Supplier <supplier@example.com>"
        message["To"] = "user@example.com"
        message["Subject"] = "Re: Запрос"
        message["Message-ID"] = "<reply@example.com>"
        message["In-Reply-To"] = "<parent@example.com>"
        message.set_content("Ответ поставщика")
        parsed = YandexMailProvider._parse_incoming(message.as_bytes(), email="user@example.com", uidvalidity="1", uid=2)
        self.assertEqual(parsed.from_email, "supplier@example.com")
        self.assertEqual(parsed.in_reply_to, "<parent@example.com>")
        self.assertEqual(parsed.body_text, "Ответ поставщика")

    def test_yandex_imap_fetch_uses_xoauth2_and_uid_cursor(self) -> None:
        message = EmailMessage()
        message["From"] = "Supplier <supplier@example.com>"
        message["To"] = "user@example.com"
        message["Subject"] = "Re: Запрос"
        message["Message-ID"] = "<reply-2@example.com>"
        message.set_content("Новый ответ")

        class DummyIMAP:
            def __init__(self, *args, **kwargs):
                self.auth_mechanism = None
                self.auth_value = None
                self.search_args = None

            def authenticate(self, mechanism, callback):
                self.auth_mechanism = mechanism
                self.auth_value = callback(None)
                return "OK", [b"authenticated"]

            def select(self, mailbox, readonly=True):
                return "OK", [b"1"]

            def response(self, code):
                return b"OK", [b"77"]

            def uid(self, command, *args):
                if command == "SEARCH":
                    self.search_args = args
                    return "OK", [b"2"]
                return "OK", [(b"BODY[]", message.as_bytes()), b")"]

            def logout(self):
                return "BYE", [b"logged out"]

        with patch("mail.providers.yandex.imaplib.IMAP4_SSL", DummyIMAP):
            provider = YandexMailProvider("client-id", "client-secret")
            batch = provider.fetch_incoming("user@example.com", "access-token", uidvalidity="77", last_uid=1, max_messages=10)
        self.assertEqual(batch.scanned_count, 1)
        self.assertEqual(batch.messages[0].body_text, "Новый ответ")

    def test_yandex_authorization_url_uses_smtp_imap_email_state_and_pkce(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        query = parse_qs(urlparse(provider.authorization_url(
            redirect_uri="http://localhost/callback", state="state", code_challenge="challenge"
        )).query)
        self.assertEqual(query["scope"], ["mail:smtp mail:imap_full login:email"])
        self.assertEqual(query["state"], ["state"])
        self.assertEqual(query["code_challenge_method"], ["S256"])

    def test_yandex_factory_strips_documentation_angle_brackets(self) -> None:
        with patch.dict(
            "os.environ",
            {"YANDEX_CLIENT_ID": "<client-id>", "YANDEX_CLIENT_SECRET": "<client-secret>"},
            clear=False,
        ):
            provider = supplier_app.yandex_provider_factory("yandex")
        self.assertEqual(provider.client_id, "client-id")
        self.assertEqual(provider.client_secret, "client-secret")

    def test_yandex_xoauth2_callback_returns_text_for_smtplib(self) -> None:
        class DummySMTP:
            def __init__(self, *args, **kwargs):
                self.auth_response = None

            def ehlo(self):
                return 250, b"ok"

            def auth(self, mechanism, auth_object, initial_response_ok=True):
                self.auth_response = auth_object(None)
                return 235, b"ok"

        dummy = DummySMTP()
        with patch("mail.providers.yandex.smtplib.SMTP_SSL", return_value=dummy):
            connection = YandexMailProvider("client-id", "client-secret")._smtp_connection("user@yandex.ru", "access-token")
        self.assertIs(connection, dummy)
        self.assertIsInstance(dummy.auth_response, str)
        self.assertIn("auth=Bearer access-token", dummy.auth_response)


if __name__ == "__main__":
    unittest.main()
