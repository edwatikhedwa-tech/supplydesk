from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.crypto import generate_key
from mail.providers.yandex import YandexMailProvider, _safe_smtp_response
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import OutgoingMessage, ProviderError, TokenSet


UTC = timezone.utc


class PhaseSMTP:
    def __init__(self, *, data_reply=(250, b"2.0.0 queued"), send_error: BaseException | None = None) -> None:
        self.data_reply = data_reply
        self.send_error = send_error
        self.replies = [(354, b"2.0.0 send data"), data_reply]
        self.commands: list[str] = []
        self.recipients: list[str] = []
        self.payload: bytes | None = None

    def mail(self, _sender: str):
        return 250, b"2.1.0 sender ok"

    def rcpt(self, recipient: str):
        self.recipients.append(recipient)
        return 250, b"2.1.5 recipient ok"

    def putcmd(self, command: str):
        self.commands.append(command)

    def getreply(self):
        return self.replies.pop(0)

    def send(self, payload: bytes):
        if self.send_error:
            raise self.send_error
        self.payload = payload


def _email_message(*, to_email: str = "recipient@example.com") -> object:
    return YandexMailProvider._build_email(
        OutgoingMessage(
            from_email="sender@yandex.ru",
            to_email=to_email,
            subject="Evidence test",
            body_text="A body",
            body_html="<p>A body</p>",
            message_id="<evidence@example.com>",
        ),
        "<evidence@example.com>",
    )


class SmtpEvidenceTests(unittest.TestCase):
    def test_e01_safe_response_keeps_code_and_enhanced_status(self) -> None:
        with self.assertRaises(ProviderError) as context:
            YandexMailProvider._raise_smtp_response(
                421, "temporary", b"421 4.7.0 temporary policy delay",
                stage="post_data", exception_class="SMTPDataError",
            )
        error = context.exception
        self.assertEqual(error.smtp_stage, "post_data")
        self.assertEqual(error.smtp_code, 421)
        self.assertEqual(error.smtp_enhanced_status, "4.7.0")
        self.assertEqual(error.provider_response_safe, "421 4.7.0 temporary policy delay")
        self.assertEqual(error.exception_class, "SMTPDataError")

    def test_e02_auth_failure_records_auth_evidence(self) -> None:
        with self.assertRaises(ProviderError) as context:
            YandexMailProvider._raise_smtp_response(
                535, "auth failed", b"535 5.7.8 authentication credentials invalid",
                stage="auth", exception_class="SMTPAuthenticationError",
            )
        error = context.exception
        self.assertEqual(error.smtp_stage, "auth")
        self.assertEqual(error.smtp_code, 535)
        self.assertEqual(error.smtp_enhanced_status, "5.7.8")
        self.assertEqual(error.exception_class, "SMTPAuthenticationError")

    def test_e03_positive_post_data_response_is_evidence(self) -> None:
        smtp = PhaseSMTP()
        outcome = YandexMailProvider._smtp_send_message(smtp, _email_message())
        self.assertEqual(outcome.smtp_stage, "post_data")
        self.assertEqual(outcome.smtp_code, 250)
        self.assertEqual(outcome.smtp_enhanced_status, "2.0.0")
        self.assertIn("DATA", smtp.commands)
        self.assertTrue((smtp.payload or b"").endswith(b".\r\n"))

    def test_e03a_idn_recipient_uses_ascii_smtp_envelope(self) -> None:
        smtp = PhaseSMTP()
        YandexMailProvider._smtp_send_message(smtp, _email_message(to_email="info@печнойцентр73.рф"))
        expected_domain = "печнойцентр73.рф".encode("idna").decode("ascii")
        self.assertEqual(smtp.recipients, [f"info@{expected_domain}"])
        self.assertIn("DATA", smtp.commands)

    def test_e04_data_command_rejection_is_not_unknown(self) -> None:
        smtp = PhaseSMTP()
        smtp.replies = [(550, b"5.7.1 policy rejected at DATA")]
        with self.assertRaises(ProviderError) as context:
            YandexMailProvider._smtp_send_message(smtp, _email_message())
        error = context.exception
        self.assertFalse(error.uncertain)
        self.assertEqual(error.smtp_stage, "data_command")
        self.assertEqual(error.smtp_code, 550)
        self.assertEqual(error.provider_code, "spam-policy")

    def test_e05_post_data_rejection_has_post_data_stage(self) -> None:
        smtp = PhaseSMTP(data_reply=(554, b"5.7.1 policy rejected after data"))
        with self.assertRaises(ProviderError) as context:
            YandexMailProvider._smtp_send_message(smtp, _email_message())
        error = context.exception
        self.assertFalse(error.uncertain)
        self.assertEqual(error.smtp_stage, "post_data")
        self.assertEqual(error.smtp_code, 554)
        self.assertEqual(error.provider_code, "spam-policy")

    def test_e06_disconnect_during_body_is_uncertain(self) -> None:
        smtp = PhaseSMTP(send_error=ConnectionError("disconnected"))
        with self.assertRaises(ProviderError) as context:
            YandexMailProvider._smtp_send_message(smtp, _email_message())
        error = context.exception
        self.assertTrue(error.uncertain)
        self.assertEqual(error.smtp_stage, "data_body")
        self.assertEqual(error.provider_code, "smtp-transport-after-data")
        self.assertEqual(error.exception_class, "ConnectionError")

    def test_e07_repository_updates_evidence_for_the_same_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = MailRepository(Path(directory) / "evidence.sqlite3")
            user = repo.seed_user("evidence-owner@example.com", "correct-horse")
            service = MailService(repo, lambda _provider: None, generate_key(), daily_limit=100)
            account_id = service.save_oauth_tokens(
                user_id=user["id"], workspace_id=user["workspace_id"],
                token_set=TokenSet("access", "refresh", 3600), email="sender@yandex.ru",
            )
            with repo.connect() as connection:
                attempt_id = repo._insert_send_attempt(
                    connection,
                    job_id=None, message_id=None, reply_id=None, account_id=account_id,
                    reservation_token="evidence-token", attempt_number=1,
                    started_at=datetime.now(UTC).isoformat(), ended_at=None,
                    outcome="in_progress", provider_classification="irreversible-stage",
                    irreversible_reached=True, cooldown_triggered=False,
                    next_retry_at=None, error=None,
                )
            self.assertTrue(repo.finish_send_attempt(
                reservation_token="evidence-token", outcome="accepted",
                provider_classification="accepted", account_id=account_id,
                smtp_stage="post_data", smtp_code=250,
                smtp_enhanced_status="2.0.0",
                provider_response_safe="250 2.0.0 queued",
                exception_class=None,
            ))
            with repo.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM mail_send_attempt_evidence WHERE attempt_id=?", (attempt_id,)
                ).fetchone()
            self.assertEqual(row["smtp_stage"], "post_data")
            self.assertEqual(row["smtp_code"], 250)
            self.assertEqual(row["smtp_enhanced_status"], "2.0.0")

    def test_e08_new_attempt_gets_nullable_evidence_row_before_provider_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = MailRepository(Path(directory) / "evidence.sqlite3")
            user = repo.seed_user("evidence-owner@example.com", "correct-horse")
            service = MailService(repo, lambda _provider: None, generate_key(), daily_limit=100)
            account_id = service.save_oauth_tokens(
                user_id=user["id"], workspace_id=user["workspace_id"],
                token_set=TokenSet("access", "refresh", 3600), email="sender@yandex.ru",
            )
            with repo.connect() as connection:
                attempt_id = repo._insert_send_attempt(
                    connection,
                    job_id=None, message_id=None, reply_id=None, account_id=account_id,
                    reservation_token=None, attempt_number=1,
                    started_at=datetime.now(UTC).isoformat(), ended_at=None,
                    outcome="in_progress", provider_classification="irreversible-stage",
                    irreversible_reached=True, cooldown_triggered=False,
                    next_retry_at=None, error=None,
                )
                row = connection.execute(
                    "SELECT * FROM mail_send_attempt_evidence WHERE attempt_id=?", (attempt_id,)
                ).fetchone()
            self.assertIsNone(row["smtp_code"])
            self.assertIsNone(row["provider_response_safe"])

    def test_e09_safe_response_redacts_auth_material(self) -> None:
        safe = _safe_smtp_response(b"535 auth=Bearer very-secret-token 5.7.8 denied")
        self.assertNotIn("very-secret-token", safe or "")
        self.assertIn("[redacted]", safe or "")

    def test_e10_unqualified_5xx_is_not_called_spam_policy(self) -> None:
        with self.assertRaises(ProviderError) as context:
            YandexMailProvider._raise_smtp_response(
                550, "server error", b"550 5.0.0 transaction failed",
                stage="post_data", exception_class="SMTPDataError",
            )
        error = context.exception
        self.assertEqual(error.provider_code, "550")
        self.assertNotEqual(error.provider_code, "spam-policy")


if __name__ == "__main__":
    unittest.main()
