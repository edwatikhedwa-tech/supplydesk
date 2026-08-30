from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from mail.crypto import generate_key
from mail.deliverability import (
    RolloutSettings,
    campaign_max_recipients_from_env,
    classify_provider_error,
    estimate_duration_seconds,
    transient_health_metrics,
)
from mail.pacing import PacingSettings
from mail.providers.yandex import YandexMailProvider
from mail.queue import MailQueue
from mail.repository import MailRepository, iso_now
from mail.service import MailService
from mail.types import DeliveryCheck, IncomingMessage, ProviderError, SendResult, TokenSet


UTC = timezone.utc


class DeliverabilityFakeProvider:
    def __init__(self) -> None:
        self.send_calls = 0
        self.sent: list[str] = []
        self.failure: ProviderError | None = None

    def send_message(self, _access_token: str, message, *, before_irreversible=None) -> SendResult:
        self.send_calls += 1
        if self.failure and not self.failure.uncertain:
            raise self.failure
        if before_irreversible:
            before_irreversible()
        if self.failure:
            raise self.failure
        self.sent.append(message.message_id)
        return SendResult(
            message_id=message.message_id,
            provider_message_id=f"fake:{self.send_calls}",
            sent_at=datetime.now(UTC),
        )

    def save_sent_copy(self, *_args, **_kwargs) -> None:
        return None

    def verify_sent_message(self, *_args, **_kwargs) -> DeliveryCheck:
        return DeliveryCheck("unavailable", None, "fake provider")


class MailDeliverabilityAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "deliverability.sqlite3"
        self.repo = MailRepository(self.db_path)
        self.user = self.repo.seed_user("deliverability@example.com", "correct-horse")
        # Positive-path rollout tests use a fake provider and must explicitly
        # enable the temporary durable switch now that production defaults are
        # fail-closed.
        self.repo.set_outgoing_enabled(True)
        self.provider = DeliverabilityFakeProvider()
        self.pacing = PacingSettings(
            min_interval_seconds=0, max_interval_seconds=0,
            max_per_hour=100, max_per_day=100,
            reservation_lease_seconds=120,
            cooldown_base_seconds=1, cooldown_max_seconds=4,
            breaker_failure_threshold=3, breaker_window_seconds=60,
            breaker_open_seconds=30, retry_base_seconds=1, retry_max_seconds=4,
        )
        self.rollout = RolloutSettings(
            stage_1=2, stage_2=4, stage_3=6, manual_stage_approval=True,
            max_permanent_failure_rate=0.20, max_unknown_rate=0.10,
            max_transient_failures=3, max_provider_rejections=1,
            similarity_warning_ratio=0.80,
        )
        self.service = MailService(
            self.repo, lambda _provider: self.provider, generate_key(),
            daily_limit=1000, pacing_settings=self.pacing, rollout_settings=self.rollout,
        )
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("access", "refresh", 3600), email="deliverability@example.com",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def workspace_id(self) -> int:
        return int(self.user["workspace_id"])

    @property
    def user_id(self) -> int:
        return int(self.user["id"])

    def suppliers(self, count: int, *, same_name: bool = False) -> list[dict[str, str]]:
        return [
            {
                "name": "Same supplier" if same_name else f"Supplier {index}",
                "email": f"supplier-{index}@example.com",
                "host": f"supplier-{index}.example.com",
                "external_key": f"supplier-{index}",
            }
            for index in range(count)
        ]

    def preflight(self, suppliers: list[dict], *, subject: str = "Request", body: str = "Body") -> dict:
        return self.service.preflight_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            suppliers=suppliers, subject=subject, body=body, attachments=[],
        )

    def queue(self, key: str, count: int = 1, *, subject: str = "Request", body: str = "Body", manual_stage_approval: bool | None = None, recipient_offset: int = 0) -> list[dict]:
        suppliers = self.suppliers(count)
        if recipient_offset:
            for index, supplier in enumerate(suppliers):
                recipient_index = recipient_offset + index
                supplier["email"] = f"supplier-{recipient_index}@example.com"
                supplier["host"] = f"supplier-{recipient_index}.example.com"
                supplier["external_key"] = f"supplier-{recipient_index}"
        return self.service.queue_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            suppliers=suppliers, subject=subject, body=body,
            attachments=[], idempotency_key=key, manual_stage_approval=manual_stage_approval,
        )

    def campaign_for(self, queued: list[dict]) -> dict:
        campaign = self.repo.get_campaign_by_operation(int(queued[0]["operation_id"]), self.workspace_id)
        self.assertIsNotNone(campaign)
        return campaign

    def target_rows(self, campaign_id: int) -> list[dict]:
        with self.repo.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT ct.*, j.status AS job_status, j.attempts FROM mail_campaign_targets ct LEFT JOIN mail_jobs j ON j.id=ct.job_id WHERE ct.campaign_id=? ORDER BY ct.ordinal",
                (campaign_id,),
            ).fetchall()]

    def queue_and_claim(self, key: str, count: int = 1) -> tuple[list[dict], dict]:
        queued = self.queue(key, count)
        claimed = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(claimed)
        return queued, claimed

    def _process_jobs(self, worker: MailQueue, count: int) -> None:
        for _ in range(count):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)

    def _prepare_operator_cap_stage_two(self, key: str, *, total: int = 30) -> tuple[int, RolloutSettings, MailQueue]:
        no_cap = replace(
            self.rollout,
            stage_1=10,
            stage_2=25,
            stage_3=50,
            manual_stage_approval=False,
            operator_stage_cap_campaign_id=None,
            operator_stage_cap=None,
        )
        self.service.rollout_settings = no_cap
        queued = self.queue(key, count=total, manual_stage_approval=False)
        campaign_id = int(self.campaign_for(queued)["id"])
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        self._process_jobs(worker, 10)
        stage_two = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual((stage_two["stage"], stage_two["stage_limit"]), (2, 25))
        cap = replace(
            no_cap,
            operator_stage_cap_campaign_id=campaign_id,
            operator_stage_cap=2,
        )
        self.service.rollout_settings = cap
        return campaign_id, cap, worker

    def test_c01_preflight_is_read_only_and_does_not_send(self) -> None:
        before = self.repo.queue_stats(self.workspace_id)
        result = self.preflight(self.suppliers(2), subject="Request", body="Please quote {{request_name}}.")
        after = self.repo.queue_stats(self.workspace_id)
        self.assertIn(result["status"], {"PASS", "WARNING"})
        self.assertEqual(before, after)
        self.assertEqual(self.provider.send_calls, 0)

    def test_m01_explicit_true_is_persisted_on_campaign(self) -> None:
        queued = self.queue("m01", manual_stage_approval=True)
        campaign = self.campaign_for(queued)
        self.assertEqual(bool(campaign["manual_stage_approval"]), True)
        self.assertTrue(self.repo.campaign_summary(self.workspace_id, campaign["id"])["manual_stage_approval"])

    def test_m02_explicit_false_is_persisted_on_campaign(self) -> None:
        queued = self.queue("m02", manual_stage_approval=False)
        campaign = self.campaign_for(queued)
        self.assertEqual(bool(campaign["manual_stage_approval"]), False)

    def test_m03_missing_mode_uses_backend_default(self) -> None:
        self.service.rollout_settings = replace(self.service.rollout_settings, manual_stage_approval=True)
        queued = self.queue("m03")
        self.assertTrue(self.campaign_for(queued)["manual_stage_approval"])

    def test_m04_direct_service_rejects_non_boolean_mode_without_writes(self) -> None:
        before = self.repo.queue_stats(self.workspace_id)
        with self.assertRaisesRegex(ValueError, "логическим"):
            self.service.queue_bulk(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
                suppliers=self.suppliers(1), subject="Request", body="Body", attachments=[],
                idempotency_key="m04", manual_stage_approval="true",  # type: ignore[arg-type]
            )
        self.assertEqual(before, self.repo.queue_stats(self.workspace_id))

    def test_m05_same_key_same_true_mode_replays_same_operation(self) -> None:
        first = self.queue("m05", manual_stage_approval=True)
        second = self.queue("m05", manual_stage_approval=True)
        self.assertEqual(first, second)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_campaigns").fetchone()[0], 1)

    def test_m06_same_key_same_false_mode_replays_same_operation(self) -> None:
        first = self.queue("m06", manual_stage_approval=False)
        second = self.queue("m06", manual_stage_approval=False)
        self.assertEqual(first, second)

    def test_m07_same_key_changed_mode_is_conflict(self) -> None:
        self.queue("m07", manual_stage_approval=True)
        with self.assertRaisesRegex(ValueError, "режима кампании"):
            self.queue("m07", manual_stage_approval=False)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_campaigns").fetchone()[0], 1)

    def test_m08_replay_same_mode_after_ambiguous_client_retry_creates_no_duplicates(self) -> None:
        first = self.queue("m08", count=2, manual_stage_approval=True)
        second = self.queue("m08", count=2, manual_stage_approval=True)
        self.assertEqual(first, second)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_operations").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_campaigns").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_jobs").fetchone()[0], 2)

    def test_m09_persisted_true_survives_default_change_and_replay(self) -> None:
        first = self.queue("m09", manual_stage_approval=True)
        self.service.rollout_settings = replace(self.service.rollout_settings, manual_stage_approval=False)
        second = self.queue("m09")
        self.assertEqual(first, second)
        self.assertTrue(self.campaign_for(first)["manual_stage_approval"])

    def test_m10_persisted_false_survives_default_change_and_replay(self) -> None:
        first = self.queue("m10", manual_stage_approval=False)
        self.service.rollout_settings = replace(self.service.rollout_settings, manual_stage_approval=True)
        second = self.queue("m10")
        self.assertEqual(first, second)
        self.assertFalse(self.campaign_for(first)["manual_stage_approval"])

    def test_m11_true_mode_pauses_after_completed_stage(self) -> None:
        queued = self.queue("m11", count=3, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        for _ in range(2):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["status"], "paused_for_review")

    def test_m12_false_mode_advances_after_completed_stage(self) -> None:
        queued = self.queue("m12", count=3, manual_stage_approval=False)
        campaign_id = self.campaign_for(queued)["id"]
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        for _ in range(2):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["status"], "active")
        self.assertEqual(summary["stage"], 2)

    def test_m13_persisted_manual_mode_is_read_after_restart(self) -> None:
        queued = self.queue("m13", manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id, "stage_review")
        restarted = MailRepository(self.db_path)
        self.assertTrue(restarted.campaign_summary(self.workspace_id, campaign_id)["manual_stage_approval"])

    def test_m14_resume_does_not_requeue_sent_or_unknown(self) -> None:
        queued = self.queue("m14", count=3, manual_stage_approval=True)
        first_job = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(first_job)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(first_job)
        second_job = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(second_job)
        self.repo.mark_job_delivery_unknown(second_job["id"], second_job["message_id"], "unknown", second_job["claim_token"])
        self.repo.finish_send_attempt(
            reservation_token=second_job["pacing_reservation_token"], outcome="uncertain",
            provider_classification="transport-uncertain", error="unknown", account_id=self.account_id,
        )
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id, "stage_review")
        self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=self.rollout)
        claimed_ids = []
        while True:
            job = self.repo.claim_job(pacing=self.pacing)
            if job is None:
                break
            claimed_ids.append(job["id"])
        self.assertNotIn(first_job["id"], claimed_ids)
        self.assertNotIn(second_job["id"], claimed_ids)

    def test_m15_campaign_modes_are_independent_but_share_account_limiter(self) -> None:
        true_batch = self.queue("m15-true", manual_stage_approval=True)
        false_batch = self.queue("m15-false", manual_stage_approval=False, recipient_offset=1)
        self.assertTrue(self.campaign_for(true_batch)["manual_stage_approval"])
        self.assertFalse(self.campaign_for(false_batch)["manual_stage_approval"])
        self.assertIsNotNone(self.repo.claim_job(pacing=PacingSettings(min_interval_seconds=30, max_interval_seconds=30, max_per_hour=100, max_per_day=100)))
        self.assertIsNone(self.repo.claim_job(pacing=PacingSettings(min_interval_seconds=30, max_interval_seconds=30, max_per_hour=100, max_per_day=100)))

    def test_r1_manual_pause_resume_preserves_stage_and_limit(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r1", count=25, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        for _ in range(3):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)

        self.repo.pause_campaign(self.workspace_id, campaign_id, "manual_pause")
        summary = self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=rollout)
        self.assertEqual(summary["status"], "active")
        self.assertEqual(summary["stage"], 1)
        self.assertEqual(summary["stage_limit"], 10)

    def test_r2_manual_resume_does_not_make_next_stage_eligible(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r2", count=25, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id, "manual_pause")
        self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=rollout)
        rows = self.target_rows(campaign_id)
        self.assertTrue(all(row["status"] != "eligible" for row in rows if int(row["ordinal"]) > 10))

    def test_r3_stage_review_resume_advances_only_after_completed_stage(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r3", count=25, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        for _ in range(10):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)
        paused = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(paused["status"], "paused_for_review")
        self.assertEqual(paused["pause_reason"], "stage_review")
        self.assertEqual((paused["stage"], paused["stage_limit"]), (1, 10))

        resumed = self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=rollout)
        self.assertEqual(resumed["status"], "active")
        self.assertEqual((resumed["stage"], resumed["stage_limit"]), (2, 25))

    def test_r4_repeated_manual_pause_resume_does_not_skip_stage(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r4", count=25, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        for _ in range(2):
            self.repo.pause_campaign(self.workspace_id, campaign_id, "manual_pause")
            summary = self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=rollout)
            self.assertEqual(summary["status"], "active")
            self.assertEqual(summary["stage"], 1)
            self.assertEqual(summary["stage_limit"], 10)

    def test_r5_manual_approval_still_requires_stage_review(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r5", count=25, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        for _ in range(10):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["status"], "paused_for_review")
        self.assertEqual(summary["pause_reason"], "stage_review")

    def test_r6_automatic_rollout_still_advances_after_completed_stage(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r6", count=25, manual_stage_approval=False)
        campaign_id = self.campaign_for(queued)["id"]
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        for _ in range(10):
            job = self.repo.claim_job(pacing=self.pacing)
            self.assertIsNotNone(job)
            worker._process(job)
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["status"], "active")
        self.assertEqual((summary["stage"], summary["stage_limit"]), (2, 25))

    def test_h1_operator_cap_holds_automatic_campaign_at_stage_two(self) -> None:
        campaign_id, cap, worker = self._prepare_operator_cap_stage_two("h1", total=30)
        self._process_jobs(worker, 15)
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["status"], "paused_for_review")
        self.assertEqual(summary["pause_reason"], "operator_stage_cap")
        self.assertEqual((summary["stage"], summary["stage_limit"]), (2, 25))
        self.assertEqual(bool(summary["manual_stage_approval"]), False)
        rows = self.target_rows(campaign_id)
        self.assertTrue(all(row["status"] == "waiting" for row in rows if int(row["ordinal"]) > 25))
        self.assertTrue(cap.blocks_stage_advancement(campaign_id, 3))

    def test_h2_without_operator_cap_preserves_automatic_stage_three(self) -> None:
        rollout = replace(
            self.rollout,
            stage_1=10,
            stage_2=25,
            stage_3=50,
            manual_stage_approval=False,
            operator_stage_cap_campaign_id=None,
            operator_stage_cap=None,
        )
        self.service.rollout_settings = rollout
        queued = self.queue("h2", count=30, manual_stage_approval=False)
        campaign_id = int(self.campaign_for(queued)["id"])
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        self._process_jobs(worker, 25)
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["status"], "active")
        self.assertEqual((summary["stage"], summary["stage_limit"]), (3, 30))
        self.assertTrue(all(row["status"] == "eligible" for row in self.target_rows(campaign_id) if int(row["ordinal"]) > 25))

    def test_h3_operator_cap_is_campaign_specific(self) -> None:
        rollout = replace(
            self.rollout,
            stage_1=2,
            stage_2=4,
            stage_3=6,
            manual_stage_approval=False,
            operator_stage_cap_campaign_id=None,
            operator_stage_cap=None,
        )
        self.service.rollout_settings = rollout
        first = self.queue("h3-a", count=6, manual_stage_approval=False)
        second = self.queue("h3-b", count=6, manual_stage_approval=False, recipient_offset=6)
        campaign_a = int(self.campaign_for(first)["id"])
        campaign_b = int(self.campaign_for(second)["id"])
        self.service.rollout_settings = replace(
            rollout,
            operator_stage_cap_campaign_id=campaign_a,
            operator_stage_cap=2,
        )
        worker = MailQueue(self.repo, self.service, pacing=self.pacing)
        self._process_jobs(worker, 8)
        summary_a = self.repo.campaign_summary(self.workspace_id, campaign_a)
        summary_b = self.repo.campaign_summary(self.workspace_id, campaign_b)
        self.assertEqual((summary_a["status"], summary_a["stage"], summary_a["stage_limit"]), ("paused_for_review", 2, 4))
        self.assertEqual((summary_b["status"], summary_b["stage"], summary_b["stage_limit"]), ("active", 3, 6))

    def test_h4_resume_does_not_bypass_active_operator_cap(self) -> None:
        campaign_id, cap, worker = self._prepare_operator_cap_stage_two("h4", total=30)
        self._process_jobs(worker, 15)
        held = self.repo.campaign_summary(self.workspace_id, campaign_id)
        resumed = self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=cap)
        self.assertEqual(resumed["status"], "paused_for_review")
        self.assertEqual(resumed["pause_reason"], "operator_stage_cap")
        self.assertEqual((resumed["stage"], resumed["stage_limit"]), (2, 25))
        self.assertEqual(resumed["updated_at"], held["updated_at"])

    def test_h5_removing_operator_cap_allows_normal_resume(self) -> None:
        campaign_id, cap, worker = self._prepare_operator_cap_stage_two("h5", total=30)
        self._process_jobs(worker, 15)
        no_cap = replace(cap, operator_stage_cap_campaign_id=None, operator_stage_cap=None)
        resumed = self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=no_cap)
        self.assertEqual(resumed["status"], "active")
        self.assertEqual((resumed["stage"], resumed["stage_limit"]), (3, 30))
        self.assertTrue(all(row["status"] == "eligible" for row in self.target_rows(campaign_id) if int(row["ordinal"]) > 25))

    def test_h6_operator_cap_does_not_mutate_campaign_intent_or_snapshot(self) -> None:
        campaign_id, cap, worker = self._prepare_operator_cap_stage_two("h6", total=30)
        with self.repo.connect() as connection:
            operation = dict(connection.execute(
                "SELECT id, content_fingerprint, idempotency_key FROM mail_send_operations WHERE id=(SELECT operation_id FROM mail_campaigns WHERE id=?)",
                (campaign_id,),
            ).fetchone())
            campaign = dict(connection.execute(
                "SELECT id, operation_id, manual_stage_approval FROM mail_campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone())
            headers_before = [row[0] for row in connection.execute(
                "SELECT message_id_header FROM mail_send_operation_targets WHERE operation_id=? ORDER BY id",
                (operation["id"],),
            ).fetchall()]
        self._process_jobs(worker, 15)
        with self.repo.connect() as connection:
            operation_after = dict(connection.execute(
                "SELECT id, content_fingerprint, idempotency_key FROM mail_send_operations WHERE id=?",
                (operation["id"],),
            ).fetchone())
            campaign_after = dict(connection.execute(
                "SELECT id, operation_id, manual_stage_approval FROM mail_campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone())
            headers_after = [row[0] for row in connection.execute(
                "SELECT message_id_header FROM mail_send_operation_targets WHERE operation_id=? ORDER BY id",
                (operation["id"],),
            ).fetchall()]
        self.assertEqual(operation_after, operation)
        self.assertEqual(campaign_after, campaign)
        self.assertEqual(headers_after, headers_before)
        self.assertEqual(cap.operator_stage_cap_for(campaign_id), 2)

    def test_h7_process_cap_is_explicit_and_not_persisted_across_restart(self) -> None:
        with patch.dict(
            os.environ,
            {"MAIL_CAMPAIGN_STAGE_CAP_ID": "2", "MAIL_CAMPAIGN_STAGE_CAP": "2"},
        ):
            configured = RolloutSettings.from_env()
        self.assertEqual(configured.operator_stage_cap_for(2), 2)
        self.assertIsNone(configured.operator_stage_cap_for(3))
        with patch.dict(
            os.environ,
            {"MAIL_CAMPAIGN_STAGE_CAP_ID": "", "MAIL_CAMPAIGN_STAGE_CAP": ""},
        ):
            restarted_without_cap = RolloutSettings.from_env()
        self.assertIsNone(restarted_without_cap.operator_stage_cap_campaign_id)
        self.assertIsNone(restarted_without_cap.operator_stage_cap)

    def test_r7_health_pause_resume_does_not_expand_stage(self) -> None:
        rollout = replace(self.rollout, stage_1=10, stage_2=25, stage_3=50)
        self.service.rollout_settings = rollout
        queued = self.queue("r7", count=25, manual_stage_approval=True)
        campaign_id = self.campaign_for(queued)["id"]
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE mail_campaigns SET status='paused_for_health', pause_reason='provider_spam_or_policy_rejection' WHERE id=?",
                (campaign_id,),
            )

        summary = self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=rollout)
        self.assertEqual(summary["status"], "active")
        self.assertEqual(summary["stage"], 1)
        self.assertEqual(summary["stage_limit"], 10)
        rows = self.target_rows(campaign_id)
        self.assertTrue(all(row["status"] != "eligible" for row in rows if int(row["ordinal"]) > 10))

    def test_c02_duplicate_recipients_are_reported(self) -> None:
        suppliers = self.suppliers(2)
        suppliers[1]["email"] = suppliers[0]["email"]
        result = self.preflight(suppliers)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("duplicate_recipient", result["blocks"])

    def test_c03_suppressed_recipient_is_excluded(self) -> None:
        self.repo.add_blacklist(self.workspace_id, self.user_id, external_key="blocked", company_name="Blocked", reason="do_not_contact")
        result = self.preflight([{"name": "Blocked", "email": "blocked@example.com", "host": "blocked.example.com", "external_key": "blocked"}])
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("suppressed", result["recipient_results"][0]["reasons"])

    def test_c04_invalid_email_is_blocked(self) -> None:
        result = self.preflight([{"name": "Bad", "email": "not-an-email", "host": "bad.example.com"}])
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("invalid_email", result["blocks"])

    def test_c05_broken_placeholder_is_blocked(self) -> None:
        result = self.preflight(self.suppliers(1), body="Hello {{unknown_supplier_fact}}")
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("broken_placeholder", result["blocks"])

    def test_c06_preview_equals_persisted_snapshot(self) -> None:
        suppliers = self.suppliers(1)
        preview = self.preflight(suppliers, subject="Hello {{supplier_name}}", body="RFQ for {{request_name}}")
        queued = self.queue("c06", 1, subject="Hello {{supplier_name}}", body="RFQ for {{request_name}}")
        target = self.repo.get_operation_target(int(queued[0]["operation_id"]), suppliers[0]["email"])
        rendered = preview["previews"][0]
        self.assertEqual(rendered["subject"], target["subject"])
        self.assertEqual(rendered["body_text"], target["body_text"])

    def test_c07_personalization_is_deterministic_not_random(self) -> None:
        suppliers = self.suppliers(1)
        first = self.preflight(suppliers, subject="Request", body="Hello {{supplier_name}}")
        second = self.preflight(suppliers, subject="Request", body="Hello {{supplier_name}}")
        self.assertEqual(first["previews"][0]["body_text"], second["previews"][0]["body_text"])
        self.assertNotIn("random", first["previews"][0]["body_text"].lower())

    def test_c08_similarity_warning_for_nearly_identical_batch(self) -> None:
        result = self.preflight(self.suppliers(10, same_name=True), body="Please send a quote.")
        self.assertGreaterEqual(result["similarity_ratio"], 0.80)
        self.assertIn("high_content_similarity", result["warnings"])

    def test_c09_similarity_warning_does_not_block_by_itself(self) -> None:
        result = self.preflight(self.suppliers(10, same_name=True), body="Please send a quote.")
        self.assertNotIn("high_content_similarity", result["blocks"])

    def test_c10_yandex_large_batch_has_policy_warning(self) -> None:
        result = self.preflight(self.suppliers(10), body="Please send a quote.")
        self.assertIsNotNone(result["provider_warning"])
        self.assertIn("provider_policy_warning", result["warnings"])

    def test_c300_1_preflight_accepts_exact_campaign_limit(self) -> None:
        result = self.preflight(self.suppliers(300), subject="Request", body="Please send a quote.")
        self.assertNotIn("campaign_size_out_of_range", result["blocks"])
        self.assertEqual(result["campaign_limits"]["max_recipients"], 300)
        self.assertEqual(result["planned"], 300)

    def test_c300_2_preflight_blocks_one_over_campaign_limit(self) -> None:
        result = self.preflight(self.suppliers(301), subject="Request", body="Please send a quote.")
        self.assertIn("campaign_size_out_of_range", result["blocks"])

    def test_c300_3_queue_bulk_accepts_exact_campaign_limit_without_smtp(self) -> None:
        queued = self.queue("c300-3", 300, subject="Request", body="Please send a quote.")
        self.assertEqual(len(queued), 300)
        self.assertEqual(self.provider.send_calls, 0)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_jobs").fetchone()[0], 300)

    def test_c300_4_queue_bulk_rejects_one_over_limit_before_transport_work(self) -> None:
        with self.assertRaisesRegex(ValueError, "от 1 до 300"):
            self.queue("c300-4", 301, subject="Request", body="Please send a quote.")
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_operations").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_jobs").fetchone()[0], 0)
        self.assertEqual(self.provider.send_calls, 0)

    def test_c300_5_preflight_and_queue_share_the_same_effective_maximum(self) -> None:
        limited = MailService(
            self.repo, lambda _provider: self.provider, generate_key(),
            daily_limit=1000, pacing_settings=self.pacing, rollout_settings=self.rollout,
            campaign_max_recipients=7,
        )
        preflight = limited.preflight_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            suppliers=self.suppliers(8), subject="Request", body="Body", attachments=[],
        )
        self.assertEqual(preflight["campaign_limits"]["max_recipients"], 7)
        self.assertIn("campaign_size_out_of_range", preflight["blocks"])
        with self.assertRaisesRegex(ValueError, "от 1 до 7"):
            limited.queue_bulk(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
                suppliers=self.suppliers(8), subject="Request", body="Body", attachments=[],
                idempotency_key="c300-5",
            )

    def test_c300_6_campaign_max_env_is_bounded_and_invalid_values_fall_back(self) -> None:
        with patch.dict("os.environ", {"MAIL_CAMPAIGN_MAX_RECIPIENTS": "300"}):
            self.assertEqual(campaign_max_recipients_from_env(), 300)
        with patch.dict("os.environ", {"MAIL_CAMPAIGN_MAX_RECIPIENTS": "not-a-number"}):
            self.assertEqual(campaign_max_recipients_from_env(), 300)
        with patch.dict("os.environ", {"MAIL_CAMPAIGN_MAX_RECIPIENTS": "0"}):
            self.assertEqual(campaign_max_recipients_from_env(), 300)
        with patch.dict("os.environ", {"MAIL_CAMPAIGN_MAX_RECIPIENTS": "999"}):
            self.assertEqual(campaign_max_recipients_from_env(), 500)

    def test_d1_duration_contract_is_numeric_object(self) -> None:
        duration = estimate_duration_seconds(120, 30, 60)
        self.assertEqual(set(duration), {"minimum", "average", "maximum"})
        self.assertTrue(all(isinstance(value, int) for value in duration.values()))

    def test_d2_duration_for_120_recipients_matches_pacing_math(self) -> None:
        self.assertEqual(estimate_duration_seconds(120, 30, 60), {"minimum": 3570, "average": 5355, "maximum": 7140})

    def test_d5_campaign_over_daily_budget_has_wait_warning(self) -> None:
        result = self.preflight(self.suppliers(120), subject="Request", body="Please send a quote.")
        self.assertEqual(result["account_budget"]["max_per_day"], 100)
        self.assertIn("campaign_exceeds_daily_budget", result["warnings"])
        self.assertIn("24-часовой", result["budget_warning"])

    def test_missing_supplier_context_is_explained_as_warning(self) -> None:
        result = self.preflight([{"email": "context@example.com", "host": "context.example.com"}])
        self.assertIn("missing_supplier_context", result["warnings"])
        self.assertEqual(result["status"], "WARNING")

    def test_c11_stage_one_limits_eligible_targets(self) -> None:
        queued = self.queue("c11", 6)
        rows = self.target_rows(self.campaign_for(queued)["id"])
        self.assertEqual(sum(row["status"] == "eligible" for row in rows), 2)
        self.assertEqual(sum(row["status"] == "waiting" for row in rows), 4)

    def test_rollout_uses_cumulative_stage_ceilings(self) -> None:
        settings = RolloutSettings(stage_1=10, stage_2=25, stage_3=50)
        self.assertEqual(settings.cumulative_limit(1, 100), 10)
        self.assertEqual(settings.next_stage(1, 100), (2, 25))
        self.assertEqual(settings.next_stage(2, 100), (3, 50))
        self.assertEqual(settings.next_stage(3, 100), (4, 100))

    def test_small_campaign_keeps_stage_two_semantics(self) -> None:
        settings = RolloutSettings(stage_1=10, stage_2=25, stage_3=50)
        self.assertEqual(settings.cumulative_limit(1, 18), 10)
        self.assertEqual(settings.next_stage(1, 18), (2, 18))
        self.assertIsNone(settings.next_stage(2, 18))

    def test_c12_remaining_recipients_are_persisted(self) -> None:
        queued = self.queue("c12", 6)
        summary = self.repo.campaign_summary(self.workspace_id, self.campaign_for(queued)["id"])
        self.assertEqual(summary["planned"], 6)
        self.assertEqual(summary["remaining"], 6)

    def test_c13_manual_approval_pause_survives_restart(self) -> None:
        queued = self.queue("c13", 3)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id, "stage_review")
        restarted = MailRepository(self.db_path)
        self.assertEqual(restarted.campaign_summary(self.workspace_id, campaign_id)["status"], "paused_for_review")

    def test_c14_resume_exposes_only_unsent_targets(self) -> None:
        queued, claimed = self.queue_and_claim("c14", 3)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=self.rollout)
        rows = self.target_rows(campaign_id)
        sent_ids = {int(queued[0]["job_id"])}
        self.assertEqual([row["job_status"] for row in rows if row["job_id"] in sent_ids], ["sent"])
        self.assertTrue(any(row["status"] == "eligible" for row in rows[1:]))

    def test_c15_resume_does_not_repeat_sent_job(self) -> None:
        queued, claimed = self.queue_and_claim("c15", 3)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=self.rollout)
        next_claim = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(next_claim)
        self.assertNotEqual(next_claim["id"], claimed["id"])

    def test_c16_resume_does_not_repeat_delivery_unknown(self) -> None:
        queued, claimed = self.queue_and_claim("c16", 1)
        self.repo.mark_job_delivery_unknown(claimed["id"], claimed["message_id"], "uncertain", claimed["claim_token"])
        self.repo.finish_send_attempt(
            reservation_token=claimed["pacing_reservation_token"], outcome="uncertain",
            provider_classification="transport-uncertain", error="uncertain", account_id=self.account_id,
        )
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.refresh_campaign_after_job(claimed["id"], rollout=self.rollout)
        self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=self.rollout)
        self.assertIsNone(self.repo.claim_job(pacing=self.pacing))

    def test_c17_stop_remaining_does_not_change_sent(self) -> None:
        queued, claimed = self.queue_and_claim("c17", 3)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        campaign_id = self.campaign_for(queued)["id"]
        before = self.repo.get_job_integrity(claimed["id"])
        self.repo.stop_campaign(self.workspace_id, campaign_id)
        after = self.repo.get_job_integrity(claimed["id"])
        self.assertEqual(self.repo.get_outbound_message(self.workspace_id, claimed["message_id"])["job_status"], "sent")
        self.assertEqual(before["irreversible_at"], after["irreversible_at"])

    def test_c18_stop_remaining_does_not_change_delivery_unknown(self) -> None:
        queued, claimed = self.queue_and_claim("c18", 3)
        self.repo.mark_job_delivery_unknown(claimed["id"], claimed["message_id"], "uncertain", claimed["claim_token"])
        self.repo.finish_send_attempt(
            reservation_token=claimed["pacing_reservation_token"], outcome="uncertain",
            provider_classification="transport-uncertain", error="uncertain", account_id=self.account_id,
        )
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.stop_campaign(self.workspace_id, campaign_id)
        self.assertEqual(self.repo.get_outbound_message(self.workspace_id, claimed["message_id"])["job_status"], "delivery_unknown")

    def test_c19_suppression_added_between_stages_is_applied_at_send(self) -> None:
        queued, claimed = self.queue_and_claim("c19", 3)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.resume_campaign(self.workspace_id, campaign_id, rollout=self.rollout)
        self.repo.add_blacklist(self.workspace_id, self.user_id, external_key="supplier-1", company_name="Supplier 1", reason="do_not_contact")
        second = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(second)
        calls = self.provider.send_calls
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(second)
        self.assertEqual(self.provider.send_calls, calls)
        row = next(row for row in self.target_rows(campaign_id) if row["job_id"] == second["id"])
        self.assertEqual(row["status"], "excluded")
        summary = self.repo.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(summary["excluded_targets"][0]["email"], "supplier-1@example.com")
        self.assertEqual(summary["excluded_targets"][0]["reason"], "suppressed")

    def test_c20_hard_bounce_contributes_to_campaign_health(self) -> None:
        queued, claimed = self.queue_and_claim("c20", 1)
        self.repo.fail_job(claimed["id"], claimed["message_id"], "hard bounce", claimed["claim_token"])
        campaign_id = self.campaign_for(queued)["id"]
        summary = self.repo.refresh_campaign_after_job(claimed["id"], rollout=self.rollout)
        self.assertEqual(summary["health"]["hard_bounces"], 1)
        self.assertEqual(summary["status"], "paused_for_health")

    def test_hard_bounce_creates_workspace_email_suppression_for_later_request(self) -> None:
        self.queue("hard-bounce-a", 1)
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="imap:hard-bounce-a",
                message_id="<hard-bounce-a@example.net>",
                in_reply_to=None,
                references=None,
                from_email="mailer-daemon@yandex.ru",
                to_email="deliverability@example.com",
                subject="Mail delivery failed",
                body_text="Final-Recipient: rfc822; supplier-0@example.com\n550 5.1.1 No such user",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        self.assertTrue(self.repo.is_suppressed(self.workspace_id, email="SUPPLIER-0@EXAMPLE.COM"))
        result = self.preflight([{
            "name": "Same recipient, new external key",
            "email": "SUPPLIER-0@EXAMPLE.COM",
            "host": "other-host.example.com",
            "external_key": "new-external-key",
        }])
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("suppressed", result["recipient_results"][0]["reasons"])
        self.assertEqual(self.provider.send_calls, 0)

    def test_soft_bounce_does_not_create_permanent_suppression(self) -> None:
        self.queue("soft-bounce", 1)
        self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="imap:soft-bounce",
                message_id="<soft-bounce@example.net>",
                in_reply_to=None,
                references=None,
                from_email="mailer-daemon@yandex.ru",
                to_email="deliverability@example.com",
                subject="Delivery Status Notification",
                body_text="Final-Recipient: rfc822; supplier-0@example.com\n450 4.2.0 Mailbox temporarily unavailable",
                body_html="",
                received_at=datetime.now(UTC),
            )],
        )
        self.assertFalse(self.repo.is_suppressed(self.workspace_id, email="supplier-0@example.com"))
        with self.repo.connect() as connection:
            state = connection.execute(
                "SELECT status FROM request_supplier_states WHERE request_id=? AND supplier_id=(SELECT id FROM suppliers WHERE email=?)",
                (1043, "supplier-0@example.com"),
            ).fetchone()
        self.assertEqual(state["status"], "queued")

    def test_hard_bounce_suppression_identity_is_normalized(self) -> None:
        self.repo.add_email_suppression(
            self.workspace_id, self.user_id, email="Sales@Example.com", reason="hard_bounce",
        )
        self.assertTrue(self.repo.is_suppressed(self.workspace_id, email="sales@example.com"))

    def test_email_suppression_does_not_apply_gmail_dot_plus_aliases(self) -> None:
        self.repo.add_email_suppression(
            self.workspace_id, self.user_id, email="User.Name+tag@gmail.com", reason="do_not_contact",
        )
        self.assertTrue(self.repo.is_suppressed(self.workspace_id, email="user.name+tag@gmail.com"))
        self.assertFalse(self.repo.is_suppressed(self.workspace_id, email="username@gmail.com"))

    def test_c21_spam_policy_rejection_pauses_campaign(self) -> None:
        queued, claimed = self.queue_and_claim("c21", 1)
        self.provider.failure = ProviderError("provider policy refusal", provider_code="spam-policy")
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        summary = self.repo.campaign_summary(self.workspace_id, self.campaign_for(queued)["id"])
        self.assertEqual(summary["status"], "paused_for_health")
        self.assertEqual(summary["pause_reason"], "provider_spam_or_policy_rejection")

    def test_c22_auth_failure_pauses_campaign_and_account(self) -> None:
        queued, claimed = self.queue_and_claim("c22", 1)
        self.provider.failure = ProviderError("auth failure", revoked=True, provider_code="535")
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        summary = self.repo.campaign_summary(self.workspace_id, self.campaign_for(queued)["id"])
        self.assertEqual(summary["status"], "paused_for_health")
        self.assertEqual(summary["pause_reason"], "authentication_failure")

    def test_c23_transient_throttling_uses_existing_cooldown(self) -> None:
        queued, claimed = self.queue_and_claim("c23", 1)
        self.provider.failure = ProviderError("throttled", transient=True, rate_limited=True, provider_code="451")
        MailQueue(self.repo, self.service, max_retries=2, pacing=self.pacing)._process(claimed)
        state = self.repo.pacing_status(self.account_id, self.pacing)
        self.assertIsNotNone(state["cooldown_until"])
        self.assertEqual(self.repo.campaign_summary(self.workspace_id, self.campaign_for(queued)["id"])["attempted"], 1)

    def test_c24_campaign_pause_does_not_change_account_limiter(self) -> None:
        queued = self.queue("c24")
        campaign_id = self.campaign_for(queued)["id"]
        before = self.repo.pacing_status(self.account_id, self.pacing)
        self.repo.pause_campaign(self.workspace_id, campaign_id)
        after = self.repo.pacing_status(self.account_id, self.pacing)
        self.assertEqual(before["next_send_not_before"], after["next_send_not_before"])

    def test_campaign_pause_race_is_finally_blocked_before_provider(self) -> None:
        queued, claimed = self.queue_and_claim("c24-race")
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        self.assertEqual(self.provider.send_calls, 0)
        with self.repo.connect() as connection:
            row = connection.execute("SELECT status, attempts FROM mail_jobs WHERE id=?", (claimed["id"],)).fetchone()
        self.assertEqual((row["status"], row["attempts"]), ("queued", 0))

    def test_c25_two_campaigns_share_one_account_pacing_reservation(self) -> None:
        self.queue("c25-a")
        self.queue("c25-b", recipient_offset=1)
        first = self.repo.claim_job(pacing=self.pacing)
        second = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_c26_paused_account_a_does_not_block_account_b(self) -> None:
        queued_a = self.queue("c26-a")
        self.repo.pause_campaign(self.workspace_id, self.campaign_for(queued_a)["id"])
        other = self.repo.seed_user("other-deliverability@example.com", "correct-horse")
        service_b = MailService(
            self.repo, lambda _provider: self.provider, generate_key(),
            daily_limit=1000, pacing_settings=self.pacing, rollout_settings=self.rollout,
        )
        service_b.save_oauth_tokens(
            user_id=other["id"], workspace_id=other["workspace_id"],
            token_set=TokenSet("b-access", "b-refresh", 3600), email="other-deliverability@example.com",
        )
        request_b = self.repo.create_request(
            other["workspace_id"], user_id=other["id"], name="Request B", description="B",
            positions=[{"name": "B", "quantity": "1"}], sender_name="Buyer B", company_name="Company B",
        )
        service_b.queue_one(
            user_id=other["id"], workspace_id=other["workspace_id"], request_id=request_b,
            supplier={"name": "B", "email": "other-recipient@example.com", "host": "other.example.com"},
            subject="Request", body="Body", idempotency_key="c26-b",
        )
        claimed = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(claimed)
        self.assertNotEqual(claimed["mail_account_id"], self.account_id)

    def test_c27_idempotency_replay_creates_no_campaign_or_stage(self) -> None:
        first = self.queue("c27")
        second = self.queue("c27")
        self.assertEqual(first, second)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_campaigns").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_jobs").fetchone()[0], 1)

    def test_idempotency_replay_preserves_paused_and_stopped_campaign_state(self) -> None:
        queued = self.queue("replay-state", 3)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id, "manual_pause")
        self.assertEqual(self.queue("replay-state", 3), queued)
        self.assertEqual(self.repo.campaign_summary(self.workspace_id, campaign_id)["status"], "paused_for_review")
        self.repo.stop_campaign(self.workspace_id, campaign_id)
        self.assertEqual(self.queue("replay-state", 3), queued)
        self.assertEqual(self.repo.campaign_summary(self.workspace_id, campaign_id)["status"], "stopped")

    def test_campaign_pause_is_checked_atomically_at_irreversible_gate(self) -> None:
        queued = self.queue("atomic-pause-gate")
        claimed = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(claimed)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.pause_campaign(self.workspace_id, campaign_id, "race")
        self.assertFalse(self.repo.enter_irreversible_stage(
            claimed["id"], claimed["claim_token"], claimed["pacing_reservation_token"],
        ))
        integrity = self.repo.get_job_integrity(claimed["id"])
        self.assertIsNone(integrity["irreversible_at"])
        self.assertEqual(self.provider.send_calls, 0)

    def test_stop_remaining_cancels_claim_released_after_stop(self) -> None:
        queued = self.queue("stop-claimed", 1)
        claimed = self.repo.claim_job(pacing=self.pacing)
        self.assertIsNotNone(claimed)
        campaign_id = self.campaign_for(queued)["id"]
        self.repo.stop_campaign(self.workspace_id, campaign_id)
        MailQueue(self.repo, self.service, pacing=self.pacing)._process(claimed)
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT status, attempts FROM mail_jobs WHERE id=?", (claimed["id"],)
            ).fetchone()
            target = connection.execute(
                "SELECT status FROM mail_campaign_targets WHERE job_id=?", (claimed["id"],)
            ).fetchone()
        self.assertEqual((row["status"], row["attempts"]), ("cancelled", 0))
        self.assertEqual(target["status"], "cancelled")
        self.assertEqual(self.provider.send_calls, 0)
        self.assertIsNone(self.repo.claim_job(pacing=self.pacing))

    def test_c28_restart_preserves_stage_state_and_counters(self) -> None:
        queued, claimed = self.queue_and_claim("c28", 1)
        self.repo.fail_job(claimed["id"], claimed["message_id"], "permanent", claimed["claim_token"])
        campaign_id = self.campaign_for(queued)["id"]
        before = self.repo.refresh_campaign_after_job(claimed["id"], rollout=self.rollout)
        restarted = MailRepository(self.db_path)
        after = restarted.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(after["status"], before["status"])
        self.assertEqual(after["attempted"], before["attempted"])

    def test_c29_no_tracking_pixel_is_inserted(self) -> None:
        result = self.preflight(self.suppliers(1), body="Please send a quote.")
        body = result["previews"][0]["body_html"].lower()
        self.assertNotIn("<img", body)
        self.assertNotIn("tracking", body)

    def test_c30_validation_does_not_probe_smtp(self) -> None:
        self.preflight(self.suppliers(3))
        self.assertEqual(self.provider.send_calls, 0)

    @staticmethod
    def _health_summary(outcomes: list[str]) -> dict:
        return {
            "provider_rejection_count": 0,
            "health": {
                "hard_bounces": 0,
                "permanent_failure_rate": 0.0,
                "unknown_rate": 0.0,
                **transient_health_metrics(outcomes),
            },
        }

    def test_htrans1_resolved_lifetime_transients_do_not_pause_health(self) -> None:
        outcomes = ["transient_rejected", "accepted", "transient_rejected", "accepted", "transient_rejected", "accepted"]
        metrics = transient_health_metrics(outcomes)
        reason = self.repo._campaign_health_pause_reason(self._health_summary(outcomes), self.rollout)
        self.assertEqual(metrics["consecutive_transient_failures"], 0)
        self.assertIsNone(reason)
        self.assertEqual(outcomes.count("transient_rejected"), 3)  # audit history is retained

    def test_htrans2_three_fresh_consecutive_transients_pause(self) -> None:
        outcomes = ["accepted", "transient_rejected", "transient_rejected", "transient_rejected"]
        metrics = transient_health_metrics(outcomes)
        self.assertEqual(metrics["consecutive_transient_failures"], 3)
        self.assertEqual(
            self.repo._campaign_health_pause_reason(self._health_summary(outcomes), self.rollout),
            "repeated_transient_failures",
        )

    def test_htrans3_two_transients_in_eight_are_below_ratio_sample(self) -> None:
        outcomes = ["accepted"] * 6 + ["transient_rejected"] * 2
        metrics = transient_health_metrics(outcomes)
        self.assertEqual(metrics["recent_attempt_count"], 8)
        self.assertEqual(metrics["recent_transient_count"], 2)
        self.assertEqual(metrics["recent_transient_ratio"], 0.25)
        self.assertIsNone(self.repo._campaign_health_pause_reason(self._health_summary(outcomes), self.rollout))

    def test_htrans4_five_of_last_ten_transients_pause(self) -> None:
        outcomes = ["accepted"] * 5 + ["transient_rejected"] * 5
        metrics = transient_health_metrics(outcomes)
        self.assertEqual(metrics["recent_attempt_count"], 10)
        self.assertEqual(metrics["recent_transient_count"], 5)
        self.assertEqual(metrics["recent_transient_ratio"], 0.5)
        self.assertEqual(
            self.repo._campaign_health_pause_reason(self._health_summary(outcomes), self.rollout),
            "repeated_transient_failures",
        )

    def test_htrans5_three_of_last_ten_transients_do_not_ratio_pause(self) -> None:
        outcomes = [
            "accepted", "transient_rejected", "accepted", "accepted", "transient_rejected",
            "accepted", "accepted", "accepted", "transient_rejected", "accepted",
        ]
        metrics = transient_health_metrics(outcomes)
        self.assertEqual(metrics["recent_transient_ratio"], 0.3)
        self.assertIsNone(self.repo._campaign_health_pause_reason(self._health_summary(outcomes), self.rollout))

    def test_htrans6_accepted_resets_transient_streak(self) -> None:
        self.assertEqual(
            transient_health_metrics(["transient_rejected", "accepted"])["consecutive_transient_failures"],
            0,
        )

    def test_htrans7_authentication_evidence_is_not_downgraded_to_transient(self) -> None:
        error = ProviderError("auth failure", revoked=True, provider_code="535")
        self.assertEqual(classify_provider_error(error), "authentication")

    def test_htrans8_provider_policy_evidence_keeps_explicit_classification(self) -> None:
        error = ProviderError("provider policy refusal", provider_code="spam-policy")
        self.assertEqual(classify_provider_error(error), "provider-spam-policy")

    def test_htrans9_uncertain_is_not_a_transient_health_signal(self) -> None:
        metrics = transient_health_metrics(["accepted", "uncertain"])
        self.assertEqual(metrics["consecutive_transient_failures"], 0)
        self.assertEqual(metrics["recent_transient_count"], 0)
        self.assertEqual(metrics["recent_transient_ratio"], 0.0)

    def test_htrans10_health_recalculation_is_stable_after_restart(self) -> None:
        outcomes = ["transient_rejected", "accepted", "transient_rejected", "accepted", "transient_rejected", "accepted"]
        queued = self.queue("htrans10", count=len(outcomes), manual_stage_approval=True)
        campaign_id = int(self.campaign_for(queued)["id"])
        with self.repo.connect() as connection:
            target_rows = connection.execute(
                "SELECT job_id FROM mail_campaign_targets WHERE campaign_id=? ORDER BY ordinal",
                (campaign_id,),
            ).fetchall()
            timestamp = datetime.now(UTC).isoformat()
            for row, outcome in zip(target_rows, outcomes):
                job = connection.execute("SELECT message_id FROM mail_jobs WHERE id=?", (row["job_id"],)).fetchone()
                connection.execute(
                    """INSERT INTO mail_send_attempts(
                           job_id, message_id, mail_account_id, attempt_number,
                           started_at, ended_at, outcome, provider_classification,
                           irreversible_reached
                       ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, 1)""",
                    (row["job_id"], job["message_id"], self.account_id, timestamp, timestamp, outcome, outcome),
                )
        before = self.repo.campaign_summary(self.workspace_id, campaign_id)
        restarted = MailRepository(self.db_path)
        after = restarted.campaign_summary(self.workspace_id, campaign_id)
        self.assertEqual(before["failed_transient"], 3)
        self.assertEqual(before["health"], after["health"])
        self.assertIsNone(restarted._campaign_health_pause_reason(after, self.rollout))
        with restarted.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM mail_send_attempts a JOIN mail_campaign_targets ct ON ct.job_id=a.job_id WHERE ct.campaign_id=?",
                    (campaign_id,),
                ).fetchone()[0],
                len(outcomes),
            )

    def test_provider_policy_classification_requires_explicit_evidence(self) -> None:
        with self.assertRaises(ProviderError) as policy:
            YandexMailProvider._raise_smtp_response(550, "SMTP", b"550 spam policy")
        self.assertEqual(policy.exception.provider_code, "spam-policy")
        with self.assertRaises(ProviderError) as ordinary:
            YandexMailProvider._raise_smtp_response(550, "SMTP", b"550 mailbox error")
        self.assertEqual(ordinary.exception.provider_code, "recipient-invalid")


if __name__ == "__main__":
    unittest.main()
