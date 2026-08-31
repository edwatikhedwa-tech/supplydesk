import tempfile
import unittest
from pathlib import Path

from mail.crypto import generate_key
from mail.pacing import PacingSettings
from mail.repository import ContinuationPlanConflictError, MailRepository
from mail.service import MailService
from mail.types import TokenSet


class CrossProviderRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "retry.sqlite3"
        self.repo = MailRepository(self.db_path)
        self.user = self.repo.seed_user("retry-owner@example.com", "correct-horse")
        self.service = MailService(
            self.repo, lambda *_args: (_ for _ in ()).throw(AssertionError("SMTP/provider must not be called")),
            generate_key(),
            pacing_settings=PacingSettings(
                min_interval_seconds=0, max_interval_seconds=0,
                max_per_hour=100, max_per_day=100,
                reservation_lease_seconds=120,
            ),
        )
        self.yandex_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("access", "refresh", 3600), email="edwatik@yandex.ru",
        )
        self.mailru_id = self.repo.save_app_password_mail_account(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            provider="mailru", email="edwatik@mail.ru", display_name="Mail.ru",
            credential_encrypted="test-secret-placeholder",
        )
        self.request_id = self.repo.create_request(
            self.user["workspace_id"], user_id=self.user["id"], name="Retry request",
            description="Safe retry test", positions=[{"name": "Item", "quantity": "1"}],
            sender_name="Buyer", company_name="Company",
        )
        self.settings = self.service.pacing_settings
        self.supplier = {
            "name": "Pechar", "email": "mail@pechar.ru", "host": "pechar.ru",
            "external_key": "pechar.ru",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _source(self, *, outcome: str = "permanent_rejected", evidence: bool = True) -> dict:
        supplier = self.supplier if outcome == "permanent_rejected" else {
            "name": outcome.title(), "email": f"{outcome}@example.com",
            "host": "example.com", "external_key": f"{outcome}.example.com",
        }
        queued = self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            request_id=self.request_id, supplier=supplier,
            subject="Offer request", body="Please send your offer.",
            idempotency_key=f"source-{outcome}-{evidence}", mail_account_id=self.yandex_id,
        )
        claimed = self.repo.claim_job(pacing=self.settings, only_job_id=queued["job_id"])
        self.assertIsNotNone(claimed)
        self.assertTrue(self.repo.enter_irreversible_stage(
            claimed["id"], claimed["claim_token"], claimed["pacing_reservation_token"],
        ))
        kwargs = {
            "reservation_token": claimed["pacing_reservation_token"],
            "outcome": outcome,
            "provider_classification": "spam-policy" if outcome == "permanent_rejected" else outcome,
            "error": "5.7.1 rejected under suspicion of SPAM" if outcome == "permanent_rejected" else outcome,
            "account_id": self.yandex_id,
        }
        if evidence:
            kwargs.update({
                "smtp_stage": "post_data", "smtp_code": 554,
                "smtp_enhanced_status": "5.7.1",
                "provider_response_safe": "5.7.1 Message rejected under suspicion of SPAM",
                "exception_class": "SMTPDataError",
            })
        self.assertTrue(self.repo.finish_send_attempt(**kwargs))
        if outcome == "accepted":
            self.assertTrue(self.repo.mark_job_sent(
                claimed["id"], claimed["message_id"], "provider-message",
                claimed["message_id_header"], "2026-08-30T00:00:00+00:00", claimed["claim_token"],
            ))
        elif outcome == "delivery_unknown":
            self.assertTrue(self.repo.mark_job_delivery_unknown(
                claimed["id"], claimed["message_id"], "Could not confirm", claimed["claim_token"],
            ))
        else:
            self.assertTrue(self.repo.fail_job(
                claimed["id"], claimed["message_id"], "5.7.1 rejected", claimed["claim_token"],
            ))
        with self.repo.connect() as connection:
            attempt = connection.execute(
                "SELECT id FROM mail_send_attempts WHERE job_id=? ORDER BY id DESC LIMIT 1",
                (queued["job_id"],),
            ).fetchone()
        return {**queued, "attempt_id": int(attempt["id"])}

    def _preview(self, source: dict) -> dict:
        return self.service.cross_provider_retry_preview(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            request_id=self.request_id, original_job_id=source["job_id"],
            original_message_id=source["message_id"], original_attempt_id=source["attempt_id"],
            target_mail_account_id=self.mailru_id,
        )

    def _apply(self, source: dict, preview: dict, key: str = "retry-1") -> dict:
        return self.service.apply_cross_provider_retry(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            request_id=self.request_id, original_job_id=source["job_id"],
            original_message_id=source["message_id"], original_attempt_id=source["attempt_id"],
            target_mail_account_id=self.mailru_id, idempotency_key=key,
            selection_fingerprint=preview["selection_fingerprint"], operator_confirmed=True,
            confirmation={
                "recipient_masked": preview["recipient_masked"],
                "original_provider": "yandex",
                "original_smtp_code": 554,
                "target_provider": "mailru",
                "reason": "proven_provider_rejection",
            },
        )

    def test_retry_01_job_with_durable_5xx_evidence_is_eligible(self) -> None:
        source = self._source()
        preview = self._preview(source)
        self.assertTrue(preview["eligible"])
        self.assertEqual(preview["blocked_reasons"], [])
        self.assertEqual(preview["source"]["provider"], "yandex")
        self.assertEqual(preview["source"]["smtp_evidence"]["smtp_code"], 554)
        self.assertEqual(preview["would_send_now"], 0)
        self.assertTrue(preview["requires_operator_confirmation"])

    def test_retry_02_missing_evidence_is_blocked(self) -> None:
        source = self._source(evidence=False)
        preview = self._preview(source)
        self.assertFalse(preview["eligible"])
        self.assertIn("missing_durable_smtp_evidence", preview["blocked_reasons"])

    def test_retry_03_accepted_and_unknown_source_outcomes_are_blocked(self) -> None:
        accepted = self._source(outcome="accepted")
        unknown = self._source(outcome="delivery_unknown")
        self.assertIn("original_accepted", self._preview(accepted)["blocked_reasons"])
        self.assertIn("original_delivery_unknown", self._preview(unknown)["blocked_reasons"])

    def test_retry_04_later_acceptance_is_blocked(self) -> None:
        source = self._source()
        later = self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            request_id=self.request_id, supplier=self.supplier, subject="Later",
            body="Later body", idempotency_key="later-accepted", allow_repeat=True,
            mail_account_id=self.yandex_id,
        )
        claimed = self.repo.claim_job(pacing=self.settings, only_job_id=later["job_id"])
        self.assertIsNotNone(claimed)
        self.assertTrue(self.repo.enter_irreversible_stage(
            claimed["id"], claimed["claim_token"], claimed["pacing_reservation_token"],
        ))
        self.assertTrue(self.repo.mark_job_sent(
            claimed["id"], claimed["message_id"], "provider-later", claimed["message_id_header"],
            "2026-08-30T00:01:00+00:00", claimed["claim_token"],
        ))
        self.assertTrue(self.repo.finish_send_attempt(
            reservation_token=claimed["pacing_reservation_token"], outcome="accepted",
            provider_classification="accepted", account_id=self.yandex_id,
            smtp_stage="post_data", smtp_code=250, smtp_enhanced_status="2.0.0",
            provider_response_safe="250 accepted",
        ))
        preview = self._preview(source)
        self.assertFalse(preview["eligible"])
        self.assertIn("later_accepted_send", preview["blocked_reasons"])

    def test_retry_04b_active_same_email_on_different_supplier_row_is_blocked(self) -> None:
        source = self._source()
        duplicate_supplier_id = self.repo.upsert_supplier(
            workspace_id=self.user["workspace_id"],
            external_key="retry-duplicate-identity",
            name="Duplicate identity",
            email=self.supplier["email"],
            host="duplicate.example",
            request_id=self.request_id,
        )
        queued = self.repo.create_queued_message(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            request_id=self.request_id, supplier_id=duplicate_supplier_id,
            account_id=self.yandex_id, from_email="edwatik@yandex.ru",
            to_email=self.supplier["email"], subject="Competing queued message",
            body_text="Competing queued message", body_html="<p>Competing queued message</p>",
            message_id_header="<competing-queued@example.com>", attachments=[],
        )

        preview = self._preview(source)

        self.assertFalse(preview["eligible"])
        self.assertIn("active_delivery_for_recipient", preview["blocked_reasons"])
        self.assertEqual(preview["active_delivery_for_recipient"], True)
        with self.repo.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT status FROM mail_jobs WHERE id=?", (queued["job_id"],)).fetchone()[0],
                "queued",
            )

    def test_retry_05_apply_creates_one_new_identity_and_preserves_source(self) -> None:
        source = self._source()
        with self.repo.connect() as connection:
            before = connection.execute(
                "SELECT status, message_id FROM mail_messages WHERE id=?", (source["message_id"],)
            ).fetchone()
        preview = self._preview(source)
        result = self._apply(source, preview)
        self.assertEqual(result["provider"], "mailru")
        self.assertEqual(result["smtp_data_calls"], 0)
        self.assertTrue(result["no_live_send"])
        self.assertNotEqual(result["message_id"], source["message_id"])
        with self.repo.connect() as connection:
            original = connection.execute(
                "SELECT status, message_id FROM mail_messages WHERE id=?", (source["message_id"],)
            ).fetchone()
            new_message = connection.execute(
                "SELECT m.status, m.mail_account_id, mi.resend_of_message_id, j.id AS job_id "
                "FROM mail_messages m JOIN mail_jobs j ON j.message_id=m.id "
                "JOIN mail_message_integrity mi ON mi.message_id=m.id WHERE m.id=?",
                (result["message_id"],),
            ).fetchone()
            plan = connection.execute(
                "SELECT status, original_job_id, original_message_id, target_provider FROM mail_cross_provider_retries WHERE id=?",
                (result["retry_plan_id"],),
            ).fetchone()
        self.assertEqual(tuple(original), tuple(before))
        self.assertEqual(new_message["status"], "queued")
        self.assertEqual(new_message["mail_account_id"], self.mailru_id)
        self.assertEqual(new_message["resend_of_message_id"], source["message_id"])
        self.assertEqual(new_message["job_id"], result["job_id"])
        self.assertEqual(plan["status"], "queued")
        self.assertEqual(plan["original_job_id"], source["job_id"])
        self.assertEqual(plan["original_message_id"], source["message_id"])
        self.assertEqual(plan["target_provider"], "mailru")

    def test_retry_06_idempotency_and_conflict(self) -> None:
        source = self._source()
        preview = self._preview(source)
        first = self._apply(source, preview, key="same-key")
        replay = self._apply(source, preview, key="same-key")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(first["job_id"], replay["job_id"])
        with self.assertRaises(ContinuationPlanConflictError):
            self.service.apply_cross_provider_retry(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                request_id=self.request_id, original_job_id=source["job_id"],
                original_message_id=source["message_id"], original_attempt_id=source["attempt_id"],
                target_mail_account_id=self.mailru_id, idempotency_key="same-key",
                selection_fingerprint="0" * 64, operator_confirmed=True,
                confirmation={"recipient_masked": preview["recipient_masked"], "original_provider": "yandex", "original_smtp_code": 554, "target_provider": "mailru", "reason": "proven_provider_rejection"},
            )

    def test_retry_07_second_retry_is_blocked_and_accepted_retry_stays_blocked(self) -> None:
        source = self._source()
        preview = self._preview(source)
        result = self._apply(source, preview)
        blocked = self._preview(source)
        self.assertFalse(blocked["eligible"])
        self.assertIn("retry_already_planned", blocked["blocked_reasons"])
        claimed = self.repo.claim_job(pacing=self.settings, only_job_id=result["job_id"])
        self.assertIsNotNone(claimed)
        self.assertTrue(self.repo.enter_irreversible_stage(
            claimed["id"], claimed["claim_token"], claimed["pacing_reservation_token"],
        ))
        self.assertTrue(self.repo.mark_job_sent(
            claimed["id"], claimed["message_id"], "mailru-provider", claimed["message_id_header"],
            "2026-08-30T00:02:00+00:00", claimed["claim_token"],
        ))
        self.assertTrue(self.repo.finish_send_attempt(
            reservation_token=claimed["pacing_reservation_token"], outcome="accepted",
            provider_classification="accepted", account_id=self.mailru_id,
            smtp_stage="post_data", smtp_code=250, smtp_enhanced_status="2.0.0",
            provider_response_safe="250 accepted",
        ))
        with self.repo.connect() as connection:
            retry_plan = connection.execute(
                "SELECT status FROM mail_cross_provider_retries WHERE id=?", (result["retry_plan_id"],)
            ).fetchone()
        self.assertEqual(retry_plan["status"], "accepted")
        self.assertIn("retry_already_planned", self._preview(source)["blocked_reasons"])

    def test_retry_08_suppression_and_answer_block(self) -> None:
        source = self._source()
        self.repo.add_blacklist(
            self.user["workspace_id"], self.user["id"], external_key="pechar.ru",
            company_name="Pechar", reason="operator suppression",
        )
        preview = self._preview(source)
        self.assertFalse(preview["eligible"])
        self.assertIn("suppressed", preview["blocked_reasons"])

    def test_retry_09_wrong_target_provider_and_confirmation_are_blocked(self) -> None:
        source = self._source()
        with self.assertRaises(Exception):
            self.service.cross_provider_retry_preview(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
                original_job_id=source["job_id"], original_message_id=source["message_id"],
                original_attempt_id=source["attempt_id"], target_mail_account_id=self.yandex_id,
            )
        preview = self._preview(source)
        with self.assertRaises(ValueError):
            self.service.apply_cross_provider_retry(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
                original_job_id=source["job_id"], original_message_id=source["message_id"],
                original_attempt_id=source["attempt_id"], target_mail_account_id=self.mailru_id,
                idempotency_key="bad-confirmation", selection_fingerprint=preview["selection_fingerprint"],
                operator_confirmed=True,
                confirmation={"recipient_masked": "wrong***@pechar.ru", "original_provider": "yandex", "original_smtp_code": 554, "target_provider": "mailru", "reason": "proven_provider_rejection"},
            )


if __name__ == "__main__":
    unittest.main()
