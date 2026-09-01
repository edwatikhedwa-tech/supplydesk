from __future__ import annotations

import base64
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from email.parser import BytesParser
from email import policy
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import supplier_app
from mail.content import clean_email_text
from mail.crypto import generate_key
from mail.providers.yandex import YandexMailProvider
from mail.queue import MailQueue
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import IncomingBatch, IncomingMessage, OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.sent: list[OutgoingMessage] = []
        self.refresh_calls = 0
        self.connection_tokens: list[str] = []
        self.incoming_tokens: list[str] = []
        self.fail_with: ProviderError | None = None
        self.incoming_batch = IncomingBatch("77", 7, [], 0)

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

    def fetch_incoming(self, email: str, access_token: str, *, uidvalidity: str | None, last_uid: int, max_messages: int) -> IncomingBatch:
        self.incoming_tokens.append(access_token)
        return self.incoming_batch

    def send_message(self, access_token: str, message: OutgoingMessage, *, before_irreversible=None) -> SendResult:
        if self.fail_with:
            raise self.fail_with
        if before_irreversible is not None:
            before_irreversible()
        self.sent.append(message)
        return SendResult(message.message_id or "<generated@example.com>", None, datetime.now(timezone.utc))

    def save_sent_copy(self, access_token: str, message: OutgoingMessage, result: SendResult) -> None:
        return None


class FakeSentIMAP:
    """Read-only/test double for authoritative Sent verification."""

    def __init__(
        self,
        search_status: str = "OK",
        search_data: list[bytes] | None = None,
        select_data: list[bytes] | None = None,
        fetch_status: str = "NO",
        fetch_data: list[object] | None = None,
    ) -> None:
        self.search_status = search_status
        self.search_data = search_data if search_data is not None else [b""]
        self.select_data = select_data if select_data is not None else [b"1"]
        self.fetch_status = fetch_status
        self.fetch_data = fetch_data if fetch_data is not None else [b"[UNAVAILABLE] FETCH not configured"]
        self.search_args = None
        self.fetch_args = None
        self.append_args = None

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "Sent"']

    def select(self, mailbox, readonly=True):
        return "OK", self.select_data

    def search(self, *args):
        self.search_args = args
        return self.search_status, self.search_data

    def fetch(self, *args):
        self.fetch_args = args
        return self.fetch_status, self.fetch_data

    def append(self, *args):
        self.append_args = args
        return "OK", [b"APPEND completed"]

    def logout(self):
        return "BYE", [b"logged out"]


class MailIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "test.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        # The production default is fail-closed; this fixture explicitly
        # enables its temporary fake transport for positive-path tests.
        self.repo.set_outgoing_enabled(True)
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

    def test_incoming_parser_resolves_cid_images_without_external_fetches(self) -> None:
        message = EmailMessage()
        message["From"] = "supplier@example.com"
        message["To"] = "buyer@example.com"
        message["Subject"] = "Логотип поставщика"
        message["Message-ID"] = "<cid@example.com>"
        message.set_content("Логотип поставщика")
        message.add_alternative('<p>Здравствуйте</p><img src="cid:logo@example.com" width="32">', subtype="html")
        html_part = message.get_payload()[1]
        html_part.add_related(b"\x89PNG\r\n\x1a\n", maintype="image", subtype="png", cid="<logo@example.com>")

        parsed = YandexMailProvider._parse_incoming(
            message.as_bytes(), email="buyer@example.com", uidvalidity="1", uid=8
        )
        self.assertIsNotNone(parsed)
        self.assertIn("data:image/png;base64", parsed.body_html)
        self.assertNotIn("cid:logo@example.com", parsed.body_html)

    def test_email_html_is_allowlisted_and_keeps_readable_structure(self) -> None:
        from mail.content import email_has_remote_images, sanitize_email_html

        for payload in (
            "<script>alert(1)</script>",
            '<img src="x" onerror="alert(1)">',
            '<iframe src="https://evil"></iframe>',
            '<form action="https://evil"><input name="pw"></form>',
            "<svg onload=alert(1)></svg>",
            '<p style="position:fixed;color:red">x</p>',
        ):
            cleaned = sanitize_email_html(payload).lower()
            for forbidden in ("script", "onerror", "onload", "<iframe", "<form", "<svg", "position:fixed"):
                self.assertNotIn(forbidden, cleaned)

        styled = sanitize_email_html(
            '<style>.card { background: #06f; color: white; } @import url(https://evil.example/x.css); .bad { position: fixed; background-image: url(https://evil.example/pixel); }</style>'
            '<table class="card" role="presentation" width="640" style="border-radius:12px;background:#f6f8fb;padding:24px"><tr><td>Карточка</td></tr></table>'
            '<button class="cta" style="background:#06f;color:white;border-radius:8px;padding:12px 20px">Открыть</button>'
        )
        self.assertIn("<style>", styled)
        self.assertIn(".card{background:#06f;color:white}", styled)
        self.assertIn('class="card"', styled)
        self.assertIn("background:#f6f8fb", styled)
        self.assertIn('<button class="cta"', styled)
        self.assertIn("padding:12px 20px", styled)
        self.assertNotIn("@import", styled)
        self.assertNotIn("position:fixed", styled)
        self.assertNotIn("url(", styled)

        blocked_background = sanitize_email_html(
            '<table style="background-image:url(https://cdn.example/card.png);border-radius:16px;color:white"><tr><td>Карточка</td></tr></table>'
        )
        self.assertIn('data-remote-background="https://cdn.example/card.png"', blocked_background)
        self.assertNotIn("background-image", blocked_background)
        self.assertNotIn("url(", blocked_background)

        blocked_body_background = sanitize_email_html(
            '<html><body style="background-image:url(https://cdn.example/page.png)"><table><tr><td>Заголовок</td></tr></table></body></html>'
        )
        self.assertIn('data-remote-body-background="https://cdn.example/page.png"', blocked_body_background)
        self.assertNotIn("background-image", blocked_body_background)
        self.assertNotIn("url(", blocked_body_background)

        responsive = sanitize_email_html(
            '<style>@media screen and (max-width: 600px) { .card { padding: 4px; } }</style><div class="card">Адаптивная карточка</div>'
        )
        self.assertIn("@media screen and (max-width: 600px)", responsive)
        self.assertIn(".card{padding:4px}", responsive)

        escaped_resource = sanitize_email_html(r'<div style="background:u\\72l(https://evil.example/pixel)">Без загрузки</div><style>.x{background:u\\72l(https://evil.example/pixel)}</style>')
        self.assertNotIn("url", escaped_resource.lower())

        cleaned = sanitize_email_html('<a href="javascript:alert(1)">click</a>')
        self.assertNotIn("javascript:", cleaned)
        self.assertIn("click", cleaned)

        # Structure a reader depends on survives, and links are hardened.
        rich = sanitize_email_html('<p>Настройки <a href="https://oauth.yandex.ru">приложения</a></p><ul><li>первое</li></ul>')
        self.assertIn("<ul>", rich)
        self.assertIn("<li>", rich)
        self.assertIn('href="https://oauth.yandex.ru"', rich)
        self.assertIn("noopener", rich)

        # Tracking pixels are withheld until the reader opts in. The URL survives
        # as data-remote-src (already vetted by the scheme allowlist) so a
        # per-message "show images" click can restore it client-side without a
        # second server round trip through a second copy of the message.
        pixel = '<p>текст</p><img src="https://track.example/p.gif">'
        self.assertTrue(email_has_remote_images(pixel))
        blocked = sanitize_email_html(pixel)
        # "-src=" is a substring of "data-remote-src=", so the real check is the
        # attribute name's own boundary: a space (or tag-open) right before it.
        self.assertNotIn(' src="https://track.example/p.gif"', blocked)
        self.assertIn('data-remote-src="https://track.example/p.gif"', blocked)
        allowed = sanitize_email_html(pixel, allow_remote_images=True)
        self.assertIn(' src="https://track.example/p.gif"', allowed)
        self.assertNotIn("data-remote-src", allowed)

        # A broken/unusable src (bad scheme, no attribute_filter match) removes
        # the element entirely rather than leaving a bare <img> with nothing to
        # show and no data-remote-src to recover from.
        self.assertNotIn("<img", sanitize_email_html('<img src=x onerror="alert(1)">'))
        self.assertNotIn("<img", sanitize_email_html('<img src="relative.png">'))

        # More vectors nh3 must still refuse, plus the ones the img/src rules were
        # rewritten around: inline data: images must survive; a data: *link*
        # must not, since target="_blank" would open it as a fresh, unsandboxed
        # document that can carry its own <script>.
        for payload in (
            '<meta http-equiv="refresh" content="0;url=https://evil">',
            '<object data="https://evil"></object>',
            '<embed src="https://evil">',
            "<p>ok<svg><script>alert(1)</script></svg></p>",
        ):
            cleaned = sanitize_email_html(payload).lower()
            for forbidden in ("<meta", "<object", "<embed", "<svg", "script"):
                self.assertNotIn(forbidden, cleaned)

        self.assertIn('src="data:image/png;base64,iVBOR"', sanitize_email_html('<img src="data:image/png;base64,iVBOR">'))
        attack = sanitize_email_html('<a href="data:text/html,<script>alert(1)</script>">click</a>')
        self.assertNotIn("data:", attack)
        self.assertNotIn("<script", attack)

    def test_quoted_history_is_collapsed_behind_a_toggle(self) -> None:
        from mail.content import collapse_quoted_html, collapse_quoted_text, sanitize_email_html

        reply_html = (
            "<p>Спасибо, посмотрю.</p>"
            "<p>22 авг. 2026 г. в 10:37, &lt;buyer@example.com&gt; написал(а):</p>"
            "<blockquote><p>Первое сообщение, отправленное ранее по этой заявке.</p></blockquote>"
        )
        folded = collapse_quoted_html(sanitize_email_html(reply_html))
        self.assertIn("Спасибо, посмотрю.", folded)
        self.assertIn('<details class="mail-quote">', folded)
        self.assertIn("<blockquote>", folded)  # the quoted structure is preserved, just wrapped
        self.assertLess(folded.index("</summary>"), folded.index("<blockquote>"))

        # A message with nothing quoted must not gain a toggle it doesn't need.
        plain_reply = sanitize_email_html("<p>Согласны, ждём предложение.</p>")
        self.assertEqual(collapse_quoted_html(plain_reply), plain_reply)

        reply_text = (
            "Спасибо, посмотрю.\n\n"
            "22 авг. 2026 г. в 10:37, buyer@example.com написал(а):\n"
            "> Первое сообщение\n> отправленное ранее"
        )
        visible = collapse_quoted_text(reply_text)
        self.assertIn("Спасибо, посмотрю.", visible)
        self.assertNotIn("Первое сообщение", visible)

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

    def test_explicit_html_contract_keeps_one_selected_company_to_one_message(self) -> None:
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={
                "name": "ООО Четыре контакта", "email": "sales@example.com", "host": "example.com",
                "contacts": [
                    {"email": "sales@example.com"}, {"email": "info@example.com"},
                    {"email": "buy@example.com"}, {"email": "office@example.com"},
                ],
            },
            subject="Запрос", body_text="Rendered text", body_html="<p>Rendered <strong>HTML</strong></p>",
            idempotency_key="html-single-company",
        )
        job = self.repo.claim_job()
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job["body_text"], "Rendered HTML")
        self.assertIn("<strong>HTML</strong>", job["body_html"])

        self.service.send_claimed_job(job)
        self.assertEqual(len(self.provider.sent), 1)
        mime = BytesParser(policy=policy.default).parsebytes(
            YandexMailProvider._build_email(self.provider.sent[0], self.provider.sent[0].message_id).as_bytes()
        )
        alternatives = {part.get_content_type(): part.get_content() for part in mime.walk() if part.get_content_type() in {"text/plain", "text/html"}}
        self.assertEqual(alternatives["text/plain"], "Rendered HTML\n")
        self.assertIn("<strong>HTML</strong>", alternatives["text/html"])

    def test_explicit_html_is_sanitized_before_it_reaches_the_queue_and_mime(self) -> None:
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "ООО Безопасность", "email": "safe@example.com", "host": "safe.example"},
            subject="Запрос", body_html=(
                '<p>Добрый день</p><script>alert(1)</script>'
                '<a href="javascript:alert(1)" onclick="alert(2)">ссылка</a>'
                '<img src="https://tracker.example/pixel.gif" onerror="alert(3)">'
            ), idempotency_key="html-sanitization",
        )
        job = self.repo.claim_job()
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job["body_text"], "Добрый день\nссылка")
        self.assertNotIn("<script", job["body_html"].lower())
        self.assertNotIn("javascript:", job["body_html"].lower())
        self.assertNotIn("onclick", job["body_html"].lower())
        self.assertIn("data-remote-src", job["body_html"])

    def test_plain_text_contract_remains_literal_in_html_alternative(self) -> None:
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "ООО Plain", "email": "plain@example.com", "host": "plain.example"},
            subject="Запрос", body_text="Hello <world> & test", idempotency_key="plain-contract",
        )
        job = self.repo.claim_job()
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job["body_text"], "Hello <world> & test")
        self.assertIn("&lt;world&gt; &amp; test", job["body_html"])

    def test_rich_content_fingerprint_prevents_duplicate_retry_and_detects_changed_html(self) -> None:
        kwargs = {
            "user_id": self.user["id"], "workspace_id": self.user["workspace_id"], "request_id": 1043,
            "supplier": {"name": "ООО Retry", "email": "retry@example.com", "host": "retry.example"},
            "subject": "Запрос", "body_text": "Версия письма", "body_html": "<p>Версия <strong>письма</strong></p>",
            "idempotency_key": "rich-retry-key",
        }
        first = self.service.queue_one(**kwargs)
        second = self.service.queue_one(**kwargs)
        self.assertEqual(first, second)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            self.service.queue_one(**{**kwargs, "body_html": "<p>Другая версия</p>"})

    def test_unmatched_inbox_reply_accepts_explicit_html_contract(self) -> None:
        message_id = self._seed_unmatched_inbox_message()
        self.service.reply_to_inbox(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], inbox_message_id=message_id,
            subject="Re: Письмо", body_text="fallback", body_html="<p>Ответ <em>готов</em></p>",
        )
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(self.provider.sent[0].body_text, "Ответ готов")
        self.assertIn("<em>готов</em>", self.provider.sent[0].body_html)
        conversation = self.repo.inbox_conversation(self.user["workspace_id"], message_id)
        self.assertIn("<em>готов</em>", conversation["replies"][0]["body_html"])

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
            idempotency_key="integration-bulk-1",
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

    def test_workspace_mail_template_is_saved_replaced_and_personalized(self) -> None:
        encoded = base64.b64encode(b"%PDF-1.4 test requisites").decode("ascii")
        saved = self.service.save_template(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            subject="КП — {{request_name}}",
            body="Здравствуйте, {{supplier_name}}!\nПишет {{company_name}}.",
            attachments=[{
                "filename": "Реквизиты.pdf", "mime_type": "application/pdf",
                "size": len(b"%PDF-1.4 test requisites"), "content_base64": encoded,
            }],
        )
        self.assertEqual(saved["subject"], "КП — {{request_name}}")
        self.assertEqual(saved["attachments"][0]["content_base64"], encoded)

        queued = self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=1043,
            supplier={"name": "ООО Кабель", "email": "cable@example.com", "host": "cable.example"},
            subject=saved["subject"], body=saved["body"], attachments=saved["attachments"],
        )
        self.assertIn("job_id", queued)
        job = self.repo.claim_job()
        request = self.repo.get_request(self.user["workspace_id"], 1043)
        self.assertEqual(job["subject"], f"КП — {request['name']}")
        self.assertIn("ООО Кабель", job["body_text"])
        self.assertIn(request["company_name"], job["body_text"])

        replaced = self.service.save_template(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            subject="Новая тема", body="Новый текст", attachments=[],
        )
        self.assertEqual(replaced["attachments"], [])
        self.assertEqual(self.repo.get_mail_template(self.user["workspace_id"])["attachments"], [])

        with self.assertRaisesRegex(ValueError, "Тип вложения не разрешён"):
            self.service.save_template(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                subject="Тема", body="Текст",
                attachments=[{
                    "filename": "script.exe", "mime_type": "application/octet-stream",
                    "size": 1, "content_base64": base64.b64encode(b"x").decode("ascii"),
                }],
            )

    def test_expired_access_token_is_refreshed_before_connection_test(self) -> None:
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_accounts SET token_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (self.account_id,))
        self.service.test_connection(self.user["id"], self.user["workspace_id"])
        self.assertEqual(self.provider.refresh_calls, 1)
        self.assertEqual(self.provider.connection_tokens, ["access-refreshed"])
        refreshed = self.repo.get_mail_account_by_id(self.account_id)
        self.assertNotIn("refresh-new", refreshed["refresh_token_encrypted"])

    def test_successful_incoming_sync_clears_current_error_and_exposes_health(self) -> None:
        self.repo.mark_mail_sync_error(self.account_id, "Старое IMAP-соединение не удалось.")
        self.repo.mark_mail_error(self.account_id, "Старое IMAP-соединение не удалось.", status="connected")

        result = self.service.sync_incoming(self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id)

        self.assertTrue(result["ok"])
        account = self.repo.get_mail_account_by_id(self.account_id)
        state = self.repo.get_mail_sync_state(self.account_id)
        public = self.service.accounts(self.user["id"], self.user["workspace_id"])[0]
        self.assertIsNone(account["last_error_at"])
        self.assertIsNone(account["last_error_message"])
        self.assertIsNone(state["last_error_at"])
        self.assertIsNone(state["last_error_message"])
        self.assertEqual(public["incoming_health"], "healthy")
        self.assertIsNotNone(public["incoming_last_success_at"])
        self.assertIsNone(public["incoming_last_error"])

    def test_incoming_sync_does_not_require_outgoing_account_flag(self) -> None:
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE mail_account_profiles SET outgoing_enabled=0 WHERE account_id=?",
                (self.account_id,),
            )
            connection.execute(
                "UPDATE mail_runtime_controls SET outgoing_enabled=0 WHERE id=1",
            )

        result = self.service.sync_incoming(
            self.user["id"], self.user["workspace_id"], mail_account_id=self.account_id,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(self.provider.refresh_calls, 0)
        self.assertEqual(self.provider.incoming_tokens, ["access-secret"])

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
        second = self.service.queue_one(**kwargs, allow_repeat=True)
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

    def test_imap_1_search_no_with_diagnostic_payload_is_unavailable(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP("NO", [b"[UNAVAILABLE] SEARCH Backend error. sc=test"])
        message_id = "<imap-no@example.com>"
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "unavailable")

    def test_imap_2_search_ok_empty_is_not_found(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP("OK", [b""])
        message_id = "<imap-empty@example.com>"
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "not_found")

    def test_imap_3_search_ok_exact_result_is_found(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP("OK", [b"41"])
        message_id = "<imap-found@example.com>"
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "found")

    def test_imap_4_message_id_is_passed_as_one_search_criterion(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP("OK", [b"41"])
        message_id = "<imap-quoted@example.com>"
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "found")
        self.assertEqual(imap.search_args, (None, "HEADER", "Message-ID", message_id))
        self.assertEqual(imap.search_args[-1], "<imap-quoted@example.com>")

    def test_imap_5_sent_copy_mime_keeps_database_message_id(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP()
        message_id = "<imap-mime@example.com>"
        outgoing = OutgoingMessage(
            from_email="user@yandex.ru", to_email="recipient@example.com",
            subject="Sent copy", body_text="Body", body_html="<p>Body</p>",
            message_id=message_id,
        )
        result = SendResult(message_id, None, datetime.now(timezone.utc))
        with patch.object(provider, "_imap_connection", return_value=imap):
            provider.save_sent_copy("access-token", outgoing, result)
        self.assertIsNotNone(imap.append_args)
        self.assertEqual(imap.append_args[0], '"Sent"')
        parsed = BytesParser(policy=policy.default).parsebytes(imap.append_args[3])
        self.assertEqual(parsed["Message-ID"], message_id)

    @staticmethod
    def _header_bytes(message_id: str, subject: str = "Subject", to: str = "recipient@example.com") -> bytes:
        message = EmailMessage()
        message["Message-ID"] = message_id
        message["Subject"] = subject
        message["To"] = to
        message["Date"] = "Fri, 28 Aug 2026 17:46:16 +0300"
        message["From"] = "user@yandex.ru"
        return message.as_bytes()

    def test_imap_6_search_no_fetch_exact_message_id_is_found(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        message_id = "<imap-fetch-found@example.com>"
        imap = FakeSentIMAP(
            "NO",
            [b"[UNAVAILABLE] SEARCH Backend error"],
            select_data=[b"41"],
            fetch_status="OK",
            fetch_data=[(b"41 (BODY[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE FROM TO)] {123})", self._header_bytes(message_id)), b")"],
        )
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "found")
        self.assertIn("FETCH fallback", result.reason)
        self.assertEqual(imap.fetch_args[0], "1:*")
        self.assertIn("BODY.PEEK[HEADER.FIELDS", imap.fetch_args[1])

    def test_imap_7_search_no_fetch_without_exact_message_id_is_unavailable(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        message_id = "<imap-fetch-missing@example.com>"
        imap = FakeSentIMAP(
            "NO",
            [b"[UNAVAILABLE] SEARCH Backend error"],
            select_data=[b"41"],
            fetch_status="OK",
            fetch_data=[(b"41 (BODY[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE FROM TO)] {123})", self._header_bytes("<other@example.com>")), b")"],
        )
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "unavailable")
        self.assertIn("не найден", result.reason)

    def test_imap_8_search_no_fetch_error_is_unavailable(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP(
            "NO",
            [b"[UNAVAILABLE] SEARCH Backend error"],
            select_data=[b"41"],
            fetch_status="NO",
            fetch_data=[b"[UNAVAILABLE] FETCH Backend error"],
        )
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", "<imap-fetch-error@example.com>")
        self.assertEqual(result.outcome, "unavailable")

    def test_imap_9_search_ok_empty_is_not_found_without_fetch_fallback(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP("OK", [b""], fetch_status="OK", fetch_data=[])
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", "<imap-no-fallback@example.com>")
        self.assertEqual(result.outcome, "not_found")
        self.assertIsNone(imap.fetch_args)

    def test_imap_10_search_ok_exact_result_is_found_without_fetch_fallback(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        imap = FakeSentIMAP("OK", [b"41"], fetch_status="NO")
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", "<imap-search-found@example.com>")
        self.assertEqual(result.outcome, "found")
        self.assertIsNone(imap.fetch_args)

    def test_imap_11_similar_subject_and_recipient_without_exact_message_id_is_not_found(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        message_id = "<imap-exact-only@example.com>"
        imap = FakeSentIMAP(
            "NO",
            [b"[UNAVAILABLE] SEARCH Backend error"],
            select_data=[b"41"],
            fetch_status="OK",
            fetch_data=[
                (b"41 (BODY[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE FROM TO)] {123})", self._header_bytes("<different@example.com>", "Same subject", "same@example.com")),
                b")",
            ],
        )
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "unavailable")

    def test_imap_12_fetch_fallback_is_bounded_to_last_50_messages(self) -> None:
        provider = YandexMailProvider("client-id", "client-secret")
        message_id = "<imap-fetch-window@example.com>"
        imap = FakeSentIMAP(
            "NO",
            [b"[UNAVAILABLE] SEARCH Backend error"],
            select_data=[b"75"],
            fetch_status="OK",
            fetch_data=[(b"75 (BODY[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE FROM TO)] {123})", self._header_bytes(message_id)), b")"],
        )
        with patch.object(provider, "_imap_connection", return_value=imap):
            result = provider.verify_sent_message("access-token", "user@example.com", message_id)
        self.assertEqual(result.outcome, "found")
        self.assertEqual(imap.fetch_args[0], "26:*")

    def _seed_unmatched_inbox_message(self) -> int:
        incoming = IncomingMessage(
            provider_message_id="imap:INBOX:1:99", message_id="<original@lad-academy.ru>",
            in_reply_to=None, references=None, from_email="info@lad-academy.ru", to_email="user@example.com",
            subject="Бесплатный практикум", body_text="Подключайтесь сейчас", body_html="<p>Подключайтесь сейчас</p>",
            received_at=datetime.now(timezone.utc),
        )
        self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id, messages=[incoming],
        )
        return self.repo.list_unmatched_incoming(self.user["workspace_id"])[0]["id"]

    def test_reply_to_unmatched_inbox_message_sends_and_threads_without_a_supplier(self) -> None:
        # The whole point of this flow: a sender with no заявка/поставщик can
        # still get a reply, without a fake supplier/request being invented for them.
        message_id = self._seed_unmatched_inbox_message()
        with self.repo.connect() as connection:
            supplier_count_before = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
            request_count_before = connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        result = self.service.reply_to_inbox(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            inbox_message_id=message_id, subject="", body="Спасибо, не сейчас.",
        )
        self.assertIn("thread_id", result)
        sent = self.provider.sent[0]
        self.assertEqual(sent.to_email, "info@lad-academy.ru")
        self.assertEqual(sent.subject, "Re: Бесплатный практикум")
        self.assertEqual(sent.in_reply_to, "<original@lad-academy.ru>")
        self.assertIn("<original@lad-academy.ru>", sent.references)

        conversation = self.repo.inbox_conversation(self.user["workspace_id"], message_id)
        self.assertEqual(len(conversation["replies"]), 1)
        self.assertEqual(conversation["replies"][0]["status"], "sent")
        self.assertIn("Спасибо", conversation["replies"][0]["body_text"])

        with self.repo.connect() as connection:
            supplier_count = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
            request_count = connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        self.assertEqual(supplier_count, supplier_count_before)
        self.assertEqual(request_count, request_count_before)

    def test_reply_to_missing_inbox_message_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.reply_to_inbox(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                inbox_message_id=999999, subject="Re: тест", body="Текст",
            )

    def test_reply_to_inbox_respects_the_daily_send_limit(self) -> None:
        message_id = self._seed_unmatched_inbox_message()
        self.service.daily_limit = 0
        with self.assertRaises(ProviderError) as ctx:
            self.service.reply_to_inbox(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                inbox_message_id=message_id, subject="Re: тест", body="Текст",
            )
        self.assertTrue(ctx.exception.rate_limited)
        self.assertEqual(len(self.provider.sent), 0)

    def test_reply_to_inbox_failure_is_recorded_and_token_not_marked_sent(self) -> None:
        message_id = self._seed_unmatched_inbox_message()
        self.provider.fail_with = ProviderError("СМТП недоступен", transient=True)
        with self.assertRaises(ProviderError):
            self.service.reply_to_inbox(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                inbox_message_id=message_id, subject="Re: тест", body="Текст",
            )
        conversation = self.repo.inbox_conversation(self.user["workspace_id"], message_id)
        self.assertEqual(conversation["replies"][0]["status"], "failed")

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
