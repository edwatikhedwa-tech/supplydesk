from __future__ import annotations

import imaplib
import smtplib
import socket
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from mail.crypto import decrypt, generate_key
from mail.providers.mailru import MailRuProvider
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import OutgoingMessage, ProviderError


class DummySMTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.login_args = None
        self.data_calls = 0

    def ehlo(self):
        return 250, b"250 smtp.mail.ru ready"

    def login(self, email, password):
        self.login_args = (email, password)
        return 235, b"2.7.0 authenticated"

    def noop(self):
        return 250, b"2.0.0 ok"

    def quit(self):
        return 221, b"bye"


class DummyIMAP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.login_args = None
        self.select_args = None

    def login(self, email, password):
        self.login_args = (email, password)
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=True):
        self.select_args = (mailbox, readonly)
        return "OK", [b"0"]

    def logout(self):
        return "BYE", [b"logged out"]


class PhaseSMTP(DummySMTP):
    def __init__(self, host, port, timeout, *, data_reply=(250, b"2.0.0 queued"), send_error=None, rcpt_reply=(250, b"2.1.5 recipient ok")):
        super().__init__(host, port, timeout)
        self.data_reply = data_reply
        self.send_error = send_error
        self.rcpt_reply = rcpt_reply
        self.replies = [(354, b"2.0.0 send data"), data_reply]
        self.commands: list[str] = []
        self.payload: bytes | None = None

    def mail(self, _sender):
        return 250, b"2.1.0 sender ok"

    def rcpt(self, _recipient):
        return self.rcpt_reply

    def putcmd(self, command):
        self.commands.append(command)

    def getreply(self):
        return self.replies.pop(0)

    def send(self, payload):
        if self.send_error:
            raise self.send_error
        self.payload = payload


def outgoing_message() -> OutgoingMessage:
    return OutgoingMessage(
        from_email="buyer@mail.ru",
        to_email="supplier@example.com",
        subject="Mail.ru evidence",
        body_text="A body",
        body_html="<p>A body</p>",
        message_id="<mailru-evidence@example.com>",
    )


class MailRuMvpTests(unittest.TestCase):
    def test_connection_uses_ssl_465_and_993_and_never_sends_data(self):
        smtp = DummySMTP("", 0, 0)
        imap = DummyIMAP("", 0, 0)
        with patch("mail.providers.mailru.smtplib.SMTP_SSL", return_value=smtp) as smtp_factory, \
             patch("mail.providers.mailru.imaplib.IMAP4_SSL", return_value=imap) as imap_factory:
            MailRuProvider("app-secret").test_connection("buyer@mail.ru", "app-secret")
        smtp_factory.assert_called_once_with("smtp.mail.ru", 465, timeout=20.0)
        imap_factory.assert_called_once_with("imap.mail.ru", 993, timeout=20.0)
        self.assertEqual(smtp.login_args, ("buyer@mail.ru", "app-secret"))
        self.assertEqual(imap.login_args, ("buyer@mail.ru", "app-secret"))
        self.assertEqual(imap.select_args, ("INBOX", True))
        self.assertEqual(smtp.data_calls, 0)

    def test_invalid_app_password_is_safe_auth_failure(self):
        class AuthFailSMTP(DummySMTP):
            def login(self, _email, _password):
                raise smtplib.SMTPAuthenticationError(535, b"535 5.7.8 auth=Bearer not-a-real-secret")

        with patch("mail.providers.mailru.smtplib.SMTP_SSL", return_value=AuthFailSMTP("", 0, 0)):
            with self.assertRaises(ProviderError) as context:
                MailRuProvider("app-secret").test_connection("buyer@mail.ru", "app-secret")
        error = context.exception
        self.assertTrue(error.revoked)
        self.assertEqual(error.smtp_stage, "auth")
        self.assertEqual(error.smtp_code, 535)
        self.assertNotIn("not-a-real-secret", str(error))

    def test_imap_auth_failure_is_safe_and_does_not_disable_outgoing_contract(self):
        class AuthFailIMAP(DummyIMAP):
            def login(self, _email, _password):
                raise imaplib.IMAP4.error(b"NO auth failed not-a-real-secret")

        with patch("mail.providers.mailru.smtplib.SMTP_SSL", return_value=DummySMTP("", 0, 0)), \
             patch("mail.providers.mailru.imaplib.IMAP4_SSL", return_value=AuthFailIMAP("", 0, 0)):
            with self.assertRaises(ProviderError) as context:
                MailRuProvider("app-secret").test_connection("buyer@mail.ru", "app-secret")
        error = context.exception
        self.assertTrue(error.revoked)
        self.assertEqual(error.provider_code, "imap-auth")
        self.assertNotIn("not-a-real-secret", str(error))

    def test_mailru_inherited_smtp_contract_preserves_phases_and_message_id(self):
        smtp = PhaseSMTP("smtp.mail.ru", 465, 20)
        result = MailRuProvider._smtp_send_message(smtp, MailRuProvider._build_email(outgoing_message(), outgoing_message().message_id))
        self.assertEqual((result.smtp_stage, result.smtp_code), ("post_data", 250))
        self.assertEqual(result.smtp_enhanced_status, "2.0.0")
        self.assertIn("DATA", smtp.commands)
        self.assertTrue((smtp.payload or b"").endswith(b".\r\n"))

    def test_mailru_rcpt_rejection_is_permanent_recipient_evidence(self):
        smtp = PhaseSMTP("smtp.mail.ru", 465, 20, rcpt_reply=(550, b"550 5.1.1 user unknown"))
        with self.assertRaises(ProviderError) as context:
            MailRuProvider._smtp_send_message(smtp, MailRuProvider._build_email(outgoing_message(), outgoing_message().message_id))
        error = context.exception
        self.assertFalse(error.uncertain)
        self.assertEqual(error.provider_code, "recipient-invalid")
        self.assertEqual(error.smtp_stage, "rcpt_to")

    def test_mailru_post_data_timeout_is_delivery_unknown(self):
        smtp = PhaseSMTP("smtp.mail.ru", 465, 20, send_error=socket.timeout("timeout"))
        with self.assertRaises(ProviderError) as context:
            MailRuProvider._smtp_send_message(smtp, MailRuProvider._build_email(outgoing_message(), outgoing_message().message_id))
        error = context.exception
        self.assertTrue(error.uncertain)
        self.assertEqual(error.smtp_stage, "data_body")
        self.assertEqual(error.provider_code, "smtp-transport-after-data")

    def test_mailru_post_data_policy_rejection_is_not_uncertain(self):
        smtp = PhaseSMTP("smtp.mail.ru", 465, 20, data_reply=(554, b"554 5.7.1 policy rejected"))
        with self.assertRaises(ProviderError) as context:
            MailRuProvider._smtp_send_message(smtp, MailRuProvider._build_email(outgoing_message(), outgoing_message().message_id))
        error = context.exception
        self.assertFalse(error.uncertain)
        self.assertEqual(error.provider_code, "spam-policy")
        self.assertEqual(error.smtp_stage, "post_data")

    def test_mailru_fallback_message_id_uses_mailru_domain(self):
        message = EmailMessage()
        message["From"] = "supplier@example.com"
        message["To"] = "buyer@mail.ru"
        message["Subject"] = "Reply"
        message.set_content("Reply body")
        parsed = MailRuProvider._parse_incoming(message.as_bytes(), email="buyer@mail.ru", uidvalidity="77", uid=5)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message_id, "<imap-77-5@mail.ru>")

    def test_mailru_oauth_is_explicitly_not_supported(self):
        provider = MailRuProvider("app-secret")
        with self.assertRaisesRegex(ProviderError, "OAuth Mail.ru"):
            provider.exchange_code("code", redirect_uri="https://example.test/callback", code_verifier="verifier")

    def test_smtp_response_is_safe_and_classified(self):
        with self.assertRaises(ProviderError) as context:
            MailRuProvider._raise_smtp_response(
                421,
                "temporary",
                b"421 4.7.0 temporary delay auth=Bearer should-not-leak",
                stage="post_data",
                exception_class="SMTPDataError",
            )
        error = context.exception
        self.assertTrue(error.transient)
        self.assertEqual(error.smtp_stage, "post_data")
        self.assertEqual(error.smtp_code, 421)
        self.assertNotIn("should-not-leak", error.provider_response_safe or "")

    def test_app_password_is_encrypted_and_not_returned_in_public_account(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = MailRepository(Path(directory) / "mailru.sqlite3")
            user = repo.seed_user("owner@example.com", "correct-horse")
            key = generate_key()
            fake = type("Provider", (), {"test_connection": lambda self, email, password: None})()
            service = MailService(repo, lambda provider, credential=None: fake, key)
            with patch.object(fake, "test_connection", return_value=None):
                account = service.connect_mailru(
                    user_id=user["id"], workspace_id=user["workspace_id"],
                    email="buyer@mail.ru", app_password="app-secret",
                )
            self.assertEqual(account["auth_mode"], "app_password")
            self.assertNotIn("app-secret", str(account))
            raw = repo.get_mail_account_by_id(account["id"])
            self.assertNotIn("app-secret", str(raw))
            encrypted = repo.get_mail_account_secret(account["id"])
            self.assertIsNotNone(encrypted)
            self.assertEqual(
                decrypt(encrypted, service._encryption_key, associated_data=service._aad(user["id"], user["workspace_id"], "app_password")),
                "app-secret",
            )

    def test_account_selection_is_owner_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = MailRepository(Path(directory) / "scope.sqlite3")
            owner = repo.seed_user("owner@example.com", "correct-horse")
            other = repo.seed_user("other@example.com", "correct-horse")
            account_id = repo.save_app_password_mail_account(
                user_id=owner["id"], workspace_id=owner["workspace_id"], provider="mailru",
                email="owner@mail.ru", display_name="Mail.ru", credential_encrypted="encrypted",
            )
            service = MailService(repo, lambda provider, credential=None: object(), generate_key())
            self.assertIsNone(repo.get_mail_account_for_owner(account_id, other["id"], other["workspace_id"]))
            with self.assertRaises(ProviderError):
                service._get_account_for_queue(other["id"], other["workspace_id"], mail_account_id=account_id)


if __name__ == "__main__":
    unittest.main()
