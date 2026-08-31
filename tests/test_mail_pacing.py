from __future__ import annotations

import multiprocessing
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from mail.crypto import encrypt, generate_key
from mail.pacing import PacingSettings
from mail.queue import MailQueue
from mail.repository import ContinuationPlanConflictError, MailRepository, iso_now
from mail.service import MailService
from mail.types import DeliveryCheck, IncomingMessage, ProviderError, SendResult, TokenSet


UTC = timezone.utc


class PacingProvider:
    def __init__(self) -> None:
        self.send_calls = 0
        self.sent: list[str] = []
        self.failure: ProviderError | None = None
        self.fail_after_gate = False
        self.before_final_callback = None

    def send_message(self, _access_token: str, message, *, before_irreversible=None) -> SendResult:
        self.send_calls += 1
        if self.failure and not self.fail_after_gate:
            raise self.failure
        if self.before_final_callback:
            self.before_final_callback()
        if before_irreversible:
            before_irreversible()
        if self.failure:
            raise self.failure
        message_id = message.message_id or "<pacing@example.test>"
        self.sent.append(message_id)
        return SendResult(message_id=message_id, provider_message_id=f"provider:{self.send_calls}", sent_at=datetime.now(UTC))

    def save_sent_copy(self, *_args, **_kwargs) -> None:
        return None

    def verify_sent_message(self, *_args, **_kwargs) -> DeliveryCheck:
        return DeliveryCheck("unavailable", None, "test provider does not verify")


def _claim_in_process(db_path: str, result_queue) -> None:
    repo = MailRepository(db_path)
    settings = PacingSettings(min_interval_seconds=0, max_interval_seconds=0, max_per_hour=100, max_per_day=100)
    result_queue.put(bool(repo.claim_job(pacing=settings)))


class MailPacingAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "pacing.sqlite3"
        self.repo = MailRepository(self.db_path)
        self.user = self.repo.seed_user("pacing-owner@example.com", "correct-horse")
        # Positive-path pacing tests use a fake provider and must opt in to
        # the now fail-closed durable switch explicitly.
        self.repo.set_outgoing_enabled(True)
        self.provider = PacingProvider()
        self.settings = PacingSettings(
            min_interval_seconds=0, max_interval_seconds=0, max_per_hour=100, max_per_day=100,
            reservation_lease_seconds=120, cooldown_base_seconds=2, cooldown_max_seconds=8,
            breaker_failure_threshold=3, breaker_window_seconds=60, breaker_open_seconds=30,
            retry_base_seconds=1, retry_max_seconds=8,
        )
        self.encryption_key = generate_key()
        self.service = MailService(
            self.repo, lambda _provider, _credential=None: self.provider, self.encryption_key,
            daily_limit=1000, pacing_settings=self.settings,
        )
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("access", "refresh", 3600), email="pacing-owner@example.com",
        )
        self.request_id = self.repo.create_request(
            self.user["workspace_id"], user_id=self.user["id"], name="Pacing request",
            description="Pacing acceptance", positions=[{"name": "Item", "quantity": "1"}],
            sender_name="Buyer", company_name="Company",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _job(self, key: str, *, external_key: str | None = None, email: str | None = None) -> dict:
        return self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
            supplier={
                "name": "Supplier", "email": email or f"{key}@example.com",
                "host": "example.com", "external_key": external_key or key,
            }, subject="Pacing", body="Body", idempotency_key=key,
        )

    def _set_state(self, account_id: int, **values) -> None:
        self.repo.pacing_status(account_id, self.settings)
        assignments = ", ".join(f"{key}=?" for key in values)
        with self.repo.connect() as connection:
            connection.execute(
                f"UPDATE mail_account_outbound_state SET {assignments}, updated_at=? WHERE mail_account_id=?",
                (*values.values(), iso_now(), account_id),
            )

    def _insert_attempt(self, account_id: int, started_at: str) -> None:
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_send_attempts(mail_account_id, attempt_number, started_at, ended_at, outcome)
                   VALUES (?, 1, ?, ?, 'accepted')""",
                (account_id, started_at, started_at),
            )

    def _status(self, job_id: int) -> tuple[str, int, str | None]:
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT status, attempts, next_attempt_at FROM mail_jobs WHERE id=?", (job_id,)
            ).fetchone()
        return row["status"], int(row["attempts"]), row["next_attempt_at"]

    def _stale_started_job(self, outcome: str, *, job_status: str, message_status: str) -> dict:
        """Create a forensic fixture without calling a provider."""

        queued = self._job(f"stale-{outcome}-{job_status}-{message_status}")
        claimed = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(claimed)
        self.assertTrue(
            self.repo.enter_irreversible_stage(
                claimed["id"], claimed["claim_token"], claimed["pacing_reservation_token"],
            )
        )
        with self.repo.connect() as connection:
            connection.execute(
                """UPDATE mail_send_reservations
                   SET expires_at='2000-01-01T00:00:00+00:00'
                   WHERE reservation_token=?""",
                (claimed["pacing_reservation_token"],),
            )
            connection.execute(
                """UPDATE mail_send_attempts
                   SET outcome=?, ended_at='2000-01-01T00:00:00+00:00'
                   WHERE reservation_token=?""",
                (outcome, claimed["pacing_reservation_token"]),
            )
            connection.execute(
                "UPDATE mail_jobs SET status=?, next_attempt_at=? WHERE id=?",
                (job_status, iso_now(), claimed["id"]),
            )
            connection.execute(
                "UPDATE mail_messages SET status=? WHERE id=?",
                (message_status, claimed["message_id"]),
            )
            connection.execute(
                "UPDATE request_supplier_states SET status=? WHERE last_message_id=?",
                (job_status, claimed["message_id"]),
            )
            connection.execute(
                """UPDATE mail_job_integrity
                   SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL
                   WHERE job_id=?""",
                (claimed["id"],),
            )
        return claimed

    def _reservation_status(self, token: str) -> str:
        with self.repo.connect() as connection:
            return connection.execute(
                "SELECT status FROM mail_send_reservations WHERE reservation_token=?", (token,)
            ).fetchone()[0]

    def test_p01_two_workers_one_account_get_one_permission(self) -> None:
        first = self._job("p01-first")
        self._job("p01-second")
        repos = [MailRepository(self.db_path), MailRepository(self.db_path)]
        results: list[dict | None] = []
        lock = threading.Lock()

        def claim(repo: MailRepository) -> None:
            result = repo.claim_job(pacing=self.settings)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=claim, args=(repo,)) for repo in repos]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(result is not None for result in results), 1)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_reservations WHERE status='reserved'",).fetchone()[0], 1)

    def test_p02_two_threads_respect_pacing_slot(self) -> None:
        self._job("p02-first")
        self._job("p02-second")
        interval_settings = PacingSettings(min_interval_seconds=30, max_interval_seconds=60, max_per_hour=100, max_per_day=100)
        first = self.repo.claim_job(pacing=interval_settings)
        second = self.repo.claim_job(pacing=interval_settings)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        with self.repo.connect() as connection:
            next_send_not_before = connection.execute(
                "SELECT next_send_not_before FROM mail_account_outbound_state WHERE mail_account_id=?",
                (self.account_id,),
            ).fetchone()[0]
        self.assertIsNotNone(next_send_not_before)
        self.assertGreaterEqual(
            datetime.fromisoformat(next_send_not_before),
            datetime.now(UTC) + timedelta(seconds=29),
        )

    def test_p03_two_processes_sqlite_one_permission(self) -> None:
        self._job("p03-first")
        self._job("p03-second")
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        processes = [context.Process(target=_claim_in_process, args=(str(self.db_path), output)) for _ in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
        self.assertTrue(all(process.exitcode == 0 for process in processes))
        self.assertEqual(sum(bool(output.get(timeout=2)) for _ in processes), 1)

    def test_zr1_started_transient_is_consumed_and_cooldown_persists(self) -> None:
        queued = self._job("zr1")
        job = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(job)
        self.provider.failure = ProviderError("Transient after gate", transient=True, provider_code="451")
        self.provider.fail_after_gate = True
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)

        status, attempts, next_attempt_at = self._status(queued["job_id"])
        self.assertEqual((status, attempts), ("queued", 1))
        self.assertIsNotNone(next_attempt_at)
        self.assertEqual(self._reservation_status(job["pacing_reservation_token"]), "consumed")
        pacing = self.repo.pacing_status(self.account_id, self.settings)
        self.assertEqual(pacing["reason"], "account_cooldown")
        self.assertGreater(datetime.fromisoformat(pacing["cooldown_until"]), datetime.now(UTC))

    def test_zr2_cooldown_blocks_new_reservation_not_zombie_reservation(self) -> None:
        queued = self._job("zr2")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.failure = ProviderError("Transient after gate", transient=True, provider_code="451")
        self.provider.fail_after_gate = True
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)
        self.assertEqual(self._reservation_status(job["pacing_reservation_token"]), "consumed")
        self.assertIsNone(
            self.repo.reserve_send_slot(
                self.account_id, owner_type="job", owner_id=queued["job_id"], pacing=self.settings,
            )
        )
        self.assertEqual(self.repo.pacing_status(self.account_id, self.settings)["reason"], "account_cooldown")

    def test_zr3_after_cooldown_retry_gets_new_reservation(self) -> None:
        queued = self._job("zr3")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.failure = ProviderError("Transient after gate", transient=True, provider_code="451")
        self.provider.fail_after_gate = True
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)
        past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE mail_account_outbound_state SET cooldown_until=?, next_send_not_before=? WHERE mail_account_id=?",
                (past, past, self.account_id),
            )
            connection.execute(
                "UPDATE mail_jobs SET next_attempt_at=? WHERE id=?", (past, queued["job_id"]),
            )
        retried = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(retried)
        self.assertNotEqual(retried["pacing_reservation_token"], job["pacing_reservation_token"])

    def test_zr4_expired_reserved_is_still_expired(self) -> None:
        queued = self._job("zr4")
        reservation = self.repo.reserve_send_slot(
            self.account_id, owner_type="job", owner_id=queued["job_id"], pacing=self.settings,
        )
        self.assertIsNotNone(reservation)
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE mail_send_reservations SET expires_at='2000-01-01T00:00:00+00:00' WHERE reservation_token=?",
                (reservation["reservation_token"],),
            )
            connection.execute("BEGIN IMMEDIATE")
            self.repo._expire_pacing_reservations(connection)
            connection.commit()
        self.assertEqual(self._reservation_status(reservation["reservation_token"]), "expired")

    def test_zr5_expired_started_in_progress_is_not_cleared(self) -> None:
        job = self._stale_started_job("in_progress", job_status="sending", message_status="sending")
        token = job["pacing_reservation_token"]
        result = self.repo.reconcile_stale_started_reservations()
        self.assertEqual(result["consumed"], 0)
        self.assertEqual(self._reservation_status(token), "started")
        self.assertEqual(self._status(job["id"])[0], "sending")

    def test_zr6_expired_started_uncertain_without_terminal_owner_is_not_released(self) -> None:
        job = self._stale_started_job("uncertain", job_status="sending", message_status="sending")
        token = job["pacing_reservation_token"]
        before = self._status(job["id"])
        result = self.repo.reconcile_stale_started_reservations()
        self.assertEqual(result["consumed"], 0)
        self.assertEqual(self._reservation_status(token), "started")
        self.assertEqual(self._status(job["id"]), before)

    def test_u1_uncertain_delivery_unknown_consumes_stale_reservation_on_recovery(self) -> None:
        job = self._stale_started_job("uncertain", job_status="delivery_unknown", message_status="delivery_unknown")
        token = job["pacing_reservation_token"]
        queue = MailQueue(self.repo, self.service, pacing=self.settings)

        queue._run_startup_recovery()

        with self.repo.connect() as connection:
            states = connection.execute(
                """SELECT j.status AS job_status, m.status AS message_status,
                          a.outcome, r.status AS reservation_status
                   FROM mail_jobs j
                   JOIN mail_messages m ON m.id=j.message_id
                   JOIN mail_send_attempts a ON a.job_id=j.id
                   JOIN mail_send_reservations r ON r.reservation_token=a.reservation_token
                   WHERE j.id=?""",
                (job["id"],),
            ).fetchone()
        self.assertEqual(tuple(states), ("delivery_unknown", "delivery_unknown", "uncertain", "consumed"))
        self.assertEqual(self._reservation_status(token), "consumed")
        self.assertIsNone(self.repo.claim_job(pacing=self.settings))

    def test_u2_other_job_same_mailbox_can_proceed_after_unknown_recovery(self) -> None:
        self._stale_started_job("uncertain", job_status="delivery_unknown", message_status="delivery_unknown")
        second = self._job("u2-independent")
        MailQueue(self.repo, self.service, pacing=self.settings)._run_startup_recovery()

        claimed = self.repo.claim_job(pacing=self.settings)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], second["job_id"])

    def test_u3_original_unknown_never_retries_after_restart(self) -> None:
        original = self._stale_started_job("uncertain", job_status="delivery_unknown", message_status="delivery_unknown")
        original_message_id = original["message_id"]
        with self.repo.connect() as connection:
            before_count = connection.execute(
                "SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'"
            ).fetchone()[0]

        restarted = MailRepository(self.db_path)
        restarted_service = MailService(
            restarted, lambda _provider: self.provider, self.encryption_key,
            daily_limit=1000, pacing_settings=self.settings,
        )
        MailQueue(restarted, restarted_service, pacing=self.settings)._run_startup_recovery()

        self.assertIsNone(restarted.claim_job(pacing=self.settings))
        with restarted.connect() as connection:
            state = connection.execute(
                "SELECT status FROM mail_jobs WHERE id=?", (original["id"],)
            ).fetchone()[0]
            after_count = connection.execute(
                "SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'"
            ).fetchone()[0]
            same_message = connection.execute(
                "SELECT COUNT(*) FROM mail_messages WHERE id=?", (original_message_id,)
            ).fetchone()[0]
        self.assertEqual(state, "delivery_unknown")
        self.assertEqual(after_count, before_count)
        self.assertEqual(same_message, 1)

    def test_u4_restart_keeps_unknown_inactive_and_allows_independent_job(self) -> None:
        self._stale_started_job("uncertain", job_status="delivery_unknown", message_status="delivery_unknown")
        second = self._job("u4-independent")
        restarted = MailRepository(self.db_path)
        restarted_service = MailService(
            restarted, lambda _provider: self.provider, self.encryption_key,
            daily_limit=1000, pacing_settings=self.settings,
        )
        MailQueue(restarted, restarted_service, pacing=self.settings)._run_startup_recovery()

        claimed = restarted.claim_job(pacing=self.settings)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], second["job_id"])

    def test_u5_accepted_stale_reservation_is_consumed_without_retry(self) -> None:
        job = self._stale_started_job("accepted", job_status="sent", message_status="sent")
        token = job["pacing_reservation_token"]
        result = self.repo.reconcile_stale_started_reservations()

        self.assertEqual(result["consumed"], 1)
        self.assertEqual(self._reservation_status(token), "consumed")
        self.assertEqual(self._status(job["id"])[0], "sent")
        self.assertIsNone(self.repo.claim_job(pacing=self.settings))

    def test_u6_known_transient_regression_still_retries_only_after_cooldown(self) -> None:
        queued = self._job("u6-transient")
        job = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(job)
        self.provider.failure = ProviderError("Transient after gate", transient=True, provider_code="451")
        self.provider.fail_after_gate = True
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)

        self.assertEqual(self._reservation_status(job["pacing_reservation_token"]), "consumed")
        self.assertEqual(self._status(queued["job_id"])[0], "queued")
        self.assertEqual(self.repo.pacing_status(self.account_id, self.settings)["reason"], "account_cooldown")

    def test_u7_uncertain_is_not_converted_to_transient(self) -> None:
        job = self._stale_started_job("uncertain", job_status="delivery_unknown", message_status="delivery_unknown")
        MailQueue(self.repo, self.service, pacing=self.settings)._run_startup_recovery()

        with self.repo.connect() as connection:
            outcome = connection.execute(
                "SELECT outcome FROM mail_send_attempts WHERE job_id=? ORDER BY id DESC LIMIT 1",
                (job["id"],),
            ).fetchone()[0]
        self.assertEqual(outcome, "uncertain")
        self.assertEqual(self._status(job["id"])[0], "delivery_unknown")

    def test_u8_two_independent_jobs_still_have_one_account_reservation(self) -> None:
        self._stale_started_job("uncertain", job_status="delivery_unknown", message_status="delivery_unknown")
        self._job("u8-first")
        self._job("u8-second")
        MailQueue(self.repo, self.service, pacing=self.settings)._run_startup_recovery()
        repos = [MailRepository(self.db_path), MailRepository(self.db_path)]
        results: list[dict | None] = []
        lock = threading.Lock()

        def claim(repo: MailRepository) -> None:
            result = repo.claim_job(pacing=self.settings)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=claim, args=(repo,)) for repo in repos]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sum(result is not None for result in results), 1)
        with self.repo.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM mail_send_reservations WHERE mail_account_id=? AND status IN ('reserved','started')",
                    (self.account_id,),
                ).fetchone()[0],
                1,
            )

    def test_zr7_stale_started_terminal_transient_is_consumed_without_job_changes(self) -> None:
        job = self._stale_started_job("transient_rejected", job_status="queued", message_status="queued")
        token = job["pacing_reservation_token"]
        before = self._status(job["id"])
        result = self.repo.reconcile_stale_started_reservations()
        self.assertEqual(result["consumed"], 1)
        self.assertEqual(self._reservation_status(token), "consumed")
        self.assertEqual(self._status(job["id"]), before)

    def test_zr8_restart_reconciles_known_terminal_stale_reservation(self) -> None:
        job = self._stale_started_job("transient_rejected", job_status="queued", message_status="queued")
        token = job["pacing_reservation_token"]
        restarted = MailRepository(self.db_path)
        restarted_service = MailService(
            restarted, lambda _provider: self.provider, generate_key(),
            daily_limit=1000, pacing_settings=self.settings,
        )
        MailQueue(restarted, restarted_service, pacing=self.settings)._run_startup_recovery()
        with restarted.connect() as connection:
            status = connection.execute(
                "SELECT status FROM mail_send_reservations WHERE reservation_token=?", (token,)
            ).fetchone()[0]
        self.assertEqual(status, "consumed")
        claimed = restarted.claim_job(pacing=self.settings)
        self.assertIsNotNone(claimed)

    def test_zr8b_stale_started_terminal_permanent_is_consumed_without_requeue(self) -> None:
        job = self._stale_started_job("permanent_rejected", job_status="failed", message_status="failed")
        token = job["pacing_reservation_token"]
        result = self.repo.reconcile_stale_started_reservations()
        self.assertEqual(result["consumed"], 1)
        self.assertEqual(self._reservation_status(token), "consumed")
        self.assertEqual(self._status(job["id"])[0:2], ("failed", 1))

    def test_zr9_accepted_stale_reservation_is_closed_without_resend(self) -> None:
        job = self._stale_started_job("accepted", job_status="sent", message_status="sent")
        token = job["pacing_reservation_token"]
        result = self.repo.reconcile_stale_started_reservations()
        self.assertEqual(result["consumed"], 1)
        self.assertEqual(self._reservation_status(token), "consumed")
        self.assertEqual(self._status(job["id"])[0:2], ("sent", 1))
        self.assertEqual(self.provider.send_calls, 0)

    def test_zr10_recovery_keeps_one_account_reservation_under_concurrency(self) -> None:
        first = self._stale_started_job("transient_rejected", job_status="queued", message_status="queued")
        self.repo.reconcile_stale_started_reservations()
        self._job("zr10-second")
        repos = [MailRepository(self.db_path), MailRepository(self.db_path)]
        results: list[dict | None] = []
        lock = threading.Lock()

        def claim(repo: MailRepository) -> None:
            result = repo.claim_job(pacing=self.settings)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=claim, args=(repo,)) for repo in repos]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertNotEqual(self._status(first["id"])[0], "delivery_unknown")

    def test_zr_reply_known_transient_closes_started_reservation(self) -> None:
        incoming = self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id="imap:zr-reply", message_id="<zr-reply-in@example.com>",
                in_reply_to=None, references=None, from_email="reply@example.com",
                to_email="pacing-owner@example.com", subject="Question", body_text="Hi",
                body_html="<p>Hi</p>", received_at=datetime.now(UTC),
            )],
        )
        inbox_id = self.repo.list_unmatched_incoming(self.user["workspace_id"])[0]["id"]
        self.provider.failure = ProviderError("Transient reply refusal", transient=True, provider_code="451")
        self.provider.fail_after_gate = True
        with self.assertRaises(ProviderError):
            self.service.reply_to_inbox(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                inbox_message_id=inbox_id, subject="Re: Question", body="Answer",
            )
        with self.repo.connect() as connection:
            reply = connection.execute(
                "SELECT id, status FROM mail_inbox_replies ORDER BY id DESC LIMIT 1",
            ).fetchone()
            reservation = connection.execute(
                "SELECT status FROM mail_send_reservations WHERE owner_type='reply' AND owner_id=?",
                (reply["id"],),
            ).fetchone()
        self.assertEqual(reply["status"], "failed")
        self.assertEqual(reservation["status"], "consumed")

    def test_p04_future_next_send_does_not_charge_attempt(self) -> None:
        queued = self._job("p04")
        future = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        self._set_state(self.account_id, next_send_not_before=future)
        self.assertIsNone(self.repo.claim_job(pacing=self.settings))
        self.assertEqual(self._status(queued["job_id"])[1], 0)

    def test_p05_disabled_wait_has_no_claim_churn(self) -> None:
        queued = self._job("p05")
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at=? WHERE id=1", (iso_now(),))
        queue = MailQueue(self.repo, self.service, pacing=self.settings)
        before = self._status(queued["job_id"])
        queue.start()
        time.sleep(0.25)
        queue.stop()
        after = self._status(queued["job_id"])
        self.assertEqual(before, after)
        self.assertEqual(self.provider.send_calls, 0)

    def test_p06_global_switch_blocks_provider(self) -> None:
        queued = self._job("p06")
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at=? WHERE id=1", (iso_now(),))
        job = self.repo.claim_job()
        MailQueue(self.repo, self.service, pacing=self.settings)._process(job)
        self.assertEqual(self.provider.send_calls, 0)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("queued", 0))

    def test_p07_jitter_is_bounded(self) -> None:
        settings = PacingSettings()
        values = [settings.next_delay() for _ in range(500)]
        self.assertGreaterEqual(min(values), 30)
        self.assertLessEqual(max(values), 60)
        self.assertEqual(settings.max_per_hour, 100)
        self.assertEqual(settings.max_per_day, 100)

    def test_p08_hour_budget_blocks_smtp(self) -> None:
        queued = self._job("p08")
        self._insert_attempt(self.account_id, (datetime.now(UTC) - timedelta(minutes=10)).isoformat())
        limited = PacingSettings(min_interval_seconds=0, max_interval_seconds=0, max_per_hour=1, max_per_day=100)
        self.assertIsNone(self.repo.claim_job(pacing=limited))
        self.assertEqual(self._status(queued["job_id"])[1], 0)
        self.assertEqual(self.provider.send_calls, 0)

    def test_p09_day_budget_blocks_smtp(self) -> None:
        queued = self._job("p09")
        self._insert_attempt(self.account_id, (datetime.now(UTC) - timedelta(hours=2)).isoformat())
        limited = PacingSettings(min_interval_seconds=0, max_interval_seconds=0, max_per_hour=100, max_per_day=1)
        self.assertIsNone(self.repo.claim_job(pacing=limited))
        self.assertEqual(self._status(queued["job_id"])[1], 0)

    def test_p10_expired_rolling_window_allows_send(self) -> None:
        self._job("p10")
        self._insert_attempt(self.account_id, (datetime.now(UTC) - timedelta(days=2)).isoformat())
        limited = PacingSettings(min_interval_seconds=0, max_interval_seconds=0, max_per_hour=1, max_per_day=1)
        self.assertIsNotNone(self.repo.claim_job(pacing=limited))

    def test_p11_restart_keeps_next_send_not_before(self) -> None:
        self._job("p11")
        future = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        self._set_state(self.account_id, next_send_not_before=future)
        restarted = MailRepository(self.db_path)
        self.assertIsNone(restarted.claim_job(pacing=self.settings))
        self.assertEqual(restarted.pacing_status(self.account_id, self.settings)["next_send_not_before"], future)

    def test_p12_restart_keeps_cooldown(self) -> None:
        self._job("p12")
        future = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        self._set_state(self.account_id, cooldown_until=future, cooldown_reason="throttle", cooldown_level=2)
        restarted = MailRepository(self.db_path)
        self.assertIsNone(restarted.claim_job(pacing=self.settings))
        self.assertEqual(restarted.pacing_status(self.account_id, self.settings)["cooldown_until"], future)

    def test_p13_restart_keeps_budget_history(self) -> None:
        self._insert_attempt(self.account_id, datetime.now(UTC).isoformat())
        restarted = MailRepository(self.db_path)
        status = restarted.pacing_status(self.account_id, self.settings)
        self.assertEqual(status["hour_count"], 1)
        self.assertEqual(status["day_count"], 1)

    def test_p14_transient_refusal_uses_bounded_backoff(self) -> None:
        queued = self._job("p14")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.failure = ProviderError("Temporary refusal", transient=True, provider_code="451")
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)
        status, attempts, next_attempt = self._status(queued["job_id"])
        self.assertEqual((status, attempts), ("queued", 1))
        self.assertIsNotNone(next_attempt)
        with self.repo.connect() as connection:
            audit = connection.execute("SELECT outcome, next_retry_at FROM mail_send_attempts WHERE job_id=?", (queued["job_id"],)).fetchone()
        self.assertEqual(audit["outcome"], "transient_rejected")
        self.assertIsNotNone(audit["next_retry_at"])

    def test_p15_backoff_increases_to_cap(self) -> None:
        values = [self.settings.retry_delay(attempts) for attempts in range(1, 20)]
        self.assertEqual(values[-1], self.settings.retry_max_seconds)
        self.assertTrue(all(value <= self.settings.retry_max_seconds for value in values))
        self.assertLessEqual(values[0], values[1])

    def test_p16_permanent_refusal_is_terminal(self) -> None:
        queued = self._job("p16")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.failure = ProviderError("Permanent refusal", provider_code="550")
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("failed", 1))
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT outcome FROM mail_send_attempts WHERE job_id=?", (queued["job_id"],)).fetchone()[0], "permanent_rejected")

    def test_pre_gate_provider_setup_failure_audits_no_irreversible_stage(self) -> None:
        queued = self._job("p16-pre-gate")
        job = self.repo.claim_job(pacing=self.settings)

        def fail_provider(_provider: str):
            raise ProviderError("Provider setup failed", transient=True, provider_code="provider-setup")

        self.service.provider_factory = fail_provider
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)
        with self.repo.connect() as connection:
            audit = connection.execute(
                "SELECT outcome, irreversible_reached FROM mail_send_attempts WHERE job_id=?",
                (queued["job_id"],),
            ).fetchone()
        self.assertEqual(audit["outcome"], "transient_rejected")
        self.assertEqual(audit["irreversible_reached"], 0)

    def test_p17_uncertain_is_never_requeued(self) -> None:
        queued = self._job("p17")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.failure = ProviderError("Uncertain", uncertain=True, provider_code="smtp-transport-after-data")
        self.provider.fail_after_gate = True
        MailQueue(self.repo, self.service, max_retries=3, pacing=self.settings)._process(job)
        self.assertEqual(self._status(queued["job_id"])[0], "delivery_unknown")
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT outcome FROM mail_send_attempts WHERE job_id=?", (queued["job_id"],)).fetchone()[0], "uncertain")

    def test_p18_auth_failure_opens_account_state(self) -> None:
        queued = self._job("p18")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.failure = ProviderError("Authentication rejected", revoked=True, provider_code="auth")
        MailQueue(self.repo, self.service, pacing=self.settings)._process(job)
        state = self.repo.pacing_status(self.account_id, self.settings)
        self.assertEqual(state["breaker_state"], "open")
        self.assertEqual(self._status(queued["job_id"])[0], "failed")

    def test_p19_open_breaker_blocks_new_attempts(self) -> None:
        self._set_state(self.account_id, breaker_state="open", breaker_until=(datetime.now(UTC) + timedelta(minutes=5)).isoformat())
        queued = self._job("p19")
        self.assertIsNone(self.repo.claim_job(pacing=self.settings))
        self.assertEqual(self._status(queued["job_id"])[1], 0)

    def test_p20_breaker_recovery_state_is_persisted(self) -> None:
        until = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        self._set_state(self.account_id, breaker_state="open", breaker_until=until, breaker_reason="test")
        restarted = MailRepository(self.db_path)
        status = restarted.pacing_status(self.account_id, self.settings)
        self.assertEqual((status["breaker_state"], status["breaker_until"]), ("open", until))

    def test_p21_suppression_is_checked_after_queue_creation(self) -> None:
        queued = self._job("p21")
        with self.repo.connect() as connection:
            supplier_id = connection.execute("SELECT supplier_id FROM mail_messages WHERE id=?", (queued["message_id"],)).fetchone()[0]
        self.repo.add_blacklist(self.user["workspace_id"], self.user["id"], external_key="p21", company_name="Supplier", reason="hard bounce", supplier_id=supplier_id)
        job = self.repo.claim_job(pacing=self.settings)
        MailQueue(self.repo, self.service, pacing=self.settings)._process(job)
        self.assertEqual(self.provider.send_calls, 0)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("failed", 0))

    def test_p22_waiting_does_not_charge_attempts_or_audit(self) -> None:
        queued = self._job("p22")
        self._set_state(self.account_id, next_send_not_before=(datetime.now(UTC) + timedelta(minutes=10)).isoformat())
        self.repo.claim_job(pacing=self.settings)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT attempts FROM mail_jobs WHERE id=?", (queued["job_id"],)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_attempts").fetchone()[0], 0)

    def test_p23_kill_switch_after_reservation_is_final_guarded(self) -> None:
        queued = self._job("p23")
        job = self.repo.claim_job(pacing=self.settings)
        self.provider.before_final_callback = lambda: self._disable_switch()
        MailQueue(self.repo, self.service, pacing=self.settings)._process(job)
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self._status(queued["job_id"])[0:2], ("queued", 0))
        with self.repo.connect() as connection:
            row = connection.execute("SELECT irreversible_at FROM mail_job_integrity WHERE job_id=?", (queued["job_id"],)).fetchone()
            audit = connection.execute("SELECT outcome FROM mail_send_attempts WHERE job_id=?", (queued["job_id"],)).fetchone()
        self.assertIsNotNone(row["irreversible_at"])
        self.assertEqual(audit["outcome"], "blocked_global")

    def _disable_switch(self) -> None:
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at=? WHERE id=1", (iso_now(),))

    def test_p24_account_cooldown_does_not_stop_account_b(self) -> None:
        other = self.repo.seed_user("p24-other@example.com", "correct-horse")
        other_account = self.service.save_oauth_tokens(user_id=other["id"], workspace_id=other["workspace_id"], token_set=TokenSet("a", "b", 3600), email="p24-other@example.com")
        self._set_state(self.account_id, cooldown_until=(datetime.now(UTC) + timedelta(minutes=5)).isoformat())
        request_b = self.repo.create_request(other["workspace_id"], user_id=other["id"], name="B", description="B", positions=[{"name": "B", "quantity": "1"}], sender_name="B", company_name="B")
        self.service.queue_one(user_id=other["id"], workspace_id=other["workspace_id"], request_id=request_b, supplier={"name": "B", "email": "p24@example.com", "host": "p24.example", "external_key": "p24"}, subject="B", body="B", idempotency_key="p24")
        claimed = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["mail_account_id"], other_account)

    def test_p25_account_budget_does_not_consume_account_b(self) -> None:
        other = self.repo.seed_user("p25-other@example.com", "correct-horse")
        other_account = self.service.save_oauth_tokens(user_id=other["id"], workspace_id=other["workspace_id"], token_set=TokenSet("a", "b", 3600), email="p25-other@example.com")
        self._insert_attempt(self.account_id, datetime.now(UTC).isoformat())
        request_b = self.repo.create_request(other["workspace_id"], user_id=other["id"], name="B", description="B", positions=[{"name": "B", "quantity": "1"}], sender_name="B", company_name="B")
        self.service.queue_one(user_id=other["id"], workspace_id=other["workspace_id"], request_id=request_b, supplier={"name": "B", "email": "p25@example.com", "host": "p25.example", "external_key": "p25"}, subject="B", body="B", idempotency_key="p25")
        limited = PacingSettings(min_interval_seconds=0, max_interval_seconds=0, max_per_hour=1, max_per_day=100)
        claimed = self.repo.claim_job(pacing=limited)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["mail_account_id"], other_account)

    def test_p26_idempotency_replay_creates_no_reservation(self) -> None:
        first = self._job("p26")
        second = self._job("p26")
        self.assertEqual(first, second)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_reservations").fetchone()[0], 0)

    def test_p27_manual_resend_uses_account_limiter(self) -> None:
        original = self._job("p27-original")
        job = self.repo.claim_job()
        self.repo.mark_job_delivery_unknown(job["id"], job["message_id"], "unknown", job["claim_token"])
        self._set_state(self.account_id, next_send_not_before=(datetime.now(UTC) + timedelta(minutes=5)).isoformat())
        result = self.service.resend_delivery_unknown(user_id=self.user["id"], workspace_id=self.user["workspace_id"], message_id=original["message_id"], confirmed=True)
        self.assertNotEqual(result["queued"]["message_id"], original["message_id"])
        self.assertIsNone(self.repo.claim_job(pacing=self.settings))

    def test_p28_sync_reply_uses_same_reservation_table(self) -> None:
        incoming = self.repo.import_incoming_messages(
            workspace_id=self.user["workspace_id"], user_id=self.user["id"], account_id=self.account_id,
            messages=[IncomingMessage(provider_message_id="imap:p28", message_id="<p28-in@example.com>", in_reply_to=None, references=None, from_email="reply@example.com", to_email="pacing-owner@example.com", subject="Question", body_text="Hi", body_html="<p>Hi</p>", received_at=datetime.now(UTC))],
        )
        inbox_id = self.repo.list_unmatched_incoming(self.user["workspace_id"])[0]["id"]
        reply_id = self.service.reply_to_inbox(user_id=self.user["id"], workspace_id=self.user["workspace_id"], inbox_message_id=inbox_id, subject="Re: Question", body="Answer")["reply_id"]
        with self.repo.connect() as connection:
            row = connection.execute("SELECT status FROM mail_send_reservations WHERE owner_type='reply' AND owner_id=?", (reply_id,)).fetchone()
            audit = connection.execute("SELECT reply_id, outcome FROM mail_send_attempts WHERE reply_id=?", (reply_id,)).fetchone()
        self.assertEqual(row["status"], "consumed")
        self.assertEqual((audit["reply_id"], audit["outcome"]), (reply_id, "accepted"))

    def test_p29_attachment_over_limit_is_rejected_before_queue(self) -> None:
        self.service.max_attachment_bytes = 1
        with self.assertRaises(ValueError):
            self.service.queue_one(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
                supplier={"name": "P29", "email": "p29@example.com", "host": "p29.example", "external_key": "p29"},
                subject="P29", body="P29", idempotency_key="p29",
                attachments=[{"filename": "too.bin", "mime_type": "application/octet-stream", "content_base64": "AAEC"}],
            )
        self.assertEqual(self.provider.send_calls, 0)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_jobs").fetchone()[0], 0)

    def test_p30_waiting_job_has_no_audit_spam(self) -> None:
        queued = self._job("p30")
        self._set_state(self.account_id, next_send_not_before=(datetime.now(UTC) + timedelta(minutes=10)).isoformat())
        queue = MailQueue(self.repo, self.service, pacing=self.settings)
        queue.start()
        time.sleep(0.35)
        queue.stop()
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_attempts").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT attempts FROM mail_jobs WHERE id=?", (queued["job_id"],)).fetchone()[0], 0)

    def test_pace_w1_scheduled_not_before_is_a_hard_transport_lower_bound(self) -> None:
        settings = PacingSettings(
            min_interval_seconds=30, max_interval_seconds=30,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        queued = self._job("pace-w1")
        job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(job)
        scheduled = datetime.fromisoformat(job["pacing_scheduled_not_before"])
        wait_calls: list[float] = []

        def wait(timeout: float | None = None) -> bool:
            wait_calls.append(float(timeout or 0))
            self.assertEqual(self.provider.send_calls, 0)
            return False

        worker = MailQueue(self.repo, self.service, pacing=settings)
        with patch("mail.queue.utc_now", side_effect=[scheduled - timedelta(seconds=30), scheduled + timedelta(seconds=1)]), \
             patch.object(worker.wake_event, "wait", side_effect=wait):
            worker._process(job)
        self.assertTrue(wait_calls and wait_calls[0] >= 29)
        self.assertEqual(self.provider.send_calls, 1)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("sent", 1))

    def test_pace_w2_after_scheduled_time_can_start_transport(self) -> None:
        queued = self._job("pace-w2")
        job = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(job)
        past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        job["pacing_scheduled_not_before"] = past
        self._set_state(self.account_id, next_send_not_before=past)
        MailQueue(self.repo, self.service, pacing=self.settings)._process(job)
        self.assertEqual(self.provider.send_calls, 1)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("sent", 1))

    def test_pace_w3_kill_switch_during_wait_releases_without_smtp(self) -> None:
        queued = self._job("pace-w3")
        settings = PacingSettings(
            min_interval_seconds=30, max_interval_seconds=30,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(job)
        started = threading.Event()
        release = threading.Event()

        def wait(*, timeout: float | None = None) -> bool:
            started.set()
            release.wait(timeout=2)
            return True

        worker = MailQueue(self.repo, self.service, pacing=settings)
        with patch.object(worker.wake_event, "wait", side_effect=wait):
            thread = threading.Thread(target=worker._process, args=(job,))
            thread.start()
            self.assertTrue(started.wait(timeout=2))
            self._disable_switch()
            release.set()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.provider.send_calls, 0)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("queued", 0))
        with self.repo.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM mail_send_reservations WHERE status IN ('reserved','started')"
                ).fetchone()[0],
                0,
            )

    def test_pace_w4_suppression_during_wait_is_checked_before_provider(self) -> None:
        settings = PacingSettings(
            min_interval_seconds=30, max_interval_seconds=30,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        queued = self._job("pace-w4")
        with self.repo.connect() as connection:
            supplier_id = int(connection.execute(
                "SELECT supplier_id FROM mail_messages WHERE id=?", (queued["message_id"],)
            ).fetchone()[0])
        job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(job)
        scheduled = datetime.fromisoformat(job["pacing_scheduled_not_before"])
        suppression_added = False

        def wait(*, timeout: float | None = None) -> bool:
            nonlocal suppression_added
            if not suppression_added:
                self.repo.add_blacklist(
                    self.user["workspace_id"], self.user["id"], external_key="pace-w4",
                    company_name="Supplier", reason="during pacing wait", supplier_id=supplier_id,
                )
                suppression_added = True
            return False

        worker = MailQueue(self.repo, self.service, pacing=settings)
        with patch("mail.queue.utc_now", side_effect=[scheduled - timedelta(seconds=30), scheduled + timedelta(seconds=1)]), \
             patch.object(worker.wake_event, "wait", side_effect=wait):
            worker._process(job)
        self.assertEqual(self.provider.send_calls, 0)
        self.assertEqual(self._status(queued["job_id"])[0:2], ("failed", 0))

    def test_pace_w5_restart_keeps_future_claim_and_reservation_unspent(self) -> None:
        settings = PacingSettings(
            min_interval_seconds=30, max_interval_seconds=30,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        queued = self._job("pace-w5")
        job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(job)
        restarted = MailRepository(self.db_path)
        self.assertIsNone(restarted.claim_job(pacing=settings))
        self.assertEqual(self._status(queued["job_id"])[0:2], ("sending", 0))
        with restarted.connect() as connection:
            reservation = connection.execute(
                "SELECT status, scheduled_not_before FROM mail_send_reservations WHERE reservation_token=?",
                (job["pacing_reservation_token"],),
            ).fetchone()
        self.assertEqual(reservation["status"], "reserved")
        self.assertGreater(datetime.fromisoformat(reservation["scheduled_not_before"]), datetime.now(UTC))

    def test_pace_w6_wait_does_not_increment_attempt_or_audit(self) -> None:
        settings = PacingSettings(
            min_interval_seconds=30, max_interval_seconds=30,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        queued = self._job("pace-w6")
        job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(job)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT attempts FROM mail_jobs WHERE id=?", (queued["job_id"],)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_attempts").fetchone()[0], 0)

    def test_pace_w7_future_wait_uses_event_wait_without_busy_loop(self) -> None:
        settings = PacingSettings(
            min_interval_seconds=30, max_interval_seconds=30,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        queued = self._job("pace-w7")
        job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(job)
        scheduled = datetime.fromisoformat(job["pacing_scheduled_not_before"])
        wait_calls: list[float] = []

        def wait(timeout: float | None = None) -> bool:
            wait_calls.append(float(timeout or 0))
            return False

        worker = MailQueue(self.repo, self.service, pacing=settings)
        with patch("mail.queue.utc_now", side_effect=[scheduled - timedelta(seconds=30), scheduled + timedelta(seconds=1)]), \
             patch.object(worker.wake_event, "wait", side_effect=wait):
            worker._process(job)
        self.assertEqual(len(wait_calls), 1)
        self.assertEqual(self.provider.send_calls, 1)
        self.assertEqual(self._status(queued["job_id"])[0], "sent")

    def test_pace_w8_sequential_accepted_transports_respect_configured_interval(self) -> None:
        settings = PacingSettings(
            min_interval_seconds=0.10, max_interval_seconds=0.10,
            max_per_hour=100, max_per_day=100, reservation_lease_seconds=120,
        )
        first = self._job("pace-w8-first")
        second = self._job("pace-w8-second")
        starts: list[float] = []
        original_send = self.provider.send_message

        def send(*args, **kwargs):
            starts.append(time.monotonic())
            return original_send(*args, **kwargs)

        self.provider.send_message = send
        worker = MailQueue(self.repo, self.service, pacing=settings)
        first_job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(first_job)
        worker._process(first_job)
        time.sleep(0.14)
        second_job = self.repo.claim_job(pacing=settings)
        self.assertIsNotNone(second_job)
        worker._process(second_job)
        self.assertEqual(len(starts), 2)
        self.assertGreaterEqual(starts[1] - starts[0], 0.08)
        self.assertEqual(self._status(first["job_id"])[0:2], ("sent", 1))
        self.assertEqual(self._status(second["job_id"])[0:2], ("sent", 1))

    def test_provider_switch_dry_run_is_provider_neutral_and_repeatable(self) -> None:
        queued = self.service.queue_bulk(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
            suppliers=[
                {"name": "Switch Supplier 1", "email": "switch-1@example.com", "host": "switch-1.example", "external_key": "switch-1"},
                {"name": "Switch Supplier 2", "email": "switch-2@example.com", "host": "switch-2.example", "external_key": "switch-2"},
            ], subject="Switch", body="Body", idempotency_key="provider-switch", manual_stage_approval=False,
        )
        campaign_id = queued[0]["campaign_id"]
        with self.repo.connect() as connection:
            supplier_id = int(connection.execute(
                "SELECT supplier_id FROM mail_messages WHERE id=?", (queued[0]["message_id"],)
            ).fetchone()[0])
        encrypted = encrypt(
            "mailru-test-secret",
            self.service._encryption_key,
            associated_data=self.service._aad(self.user["id"], self.user["workspace_id"], "app_password"),
        )
        mailru_id = self.repo.save_app_password_mail_account(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], provider="mailru",
            email="switch@mail.ru", display_name="Mail.ru", credential_encrypted=encrypted,
        )
        accepted = self.repo.create_queued_message(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
            supplier_id=supplier_id, account_id=mailru_id, from_email="switch@mail.ru",
            to_email="switch-1@example.com", subject="Mail.ru continuation", body_text="Body",
            body_html="<p>Body</p>", message_id_header="<switch-mailru@example.com>", attachments=[],
        )
        accepted_job = self.repo.claim_job(pacing=self.settings, only_job_id=accepted["job_id"])
        self.assertIsNotNone(accepted_job)
        self.assertTrue(self.repo.enter_irreversible_stage(
            accepted_job["id"], accepted_job["claim_token"], accepted_job["pacing_reservation_token"],
        ))
        accepted_at = iso_now()
        self.assertTrue(self.repo.mark_job_sent(
            accepted_job["id"], accepted_job["message_id"], "mailru-provider-id",
            "<switch-mailru@example.com>", accepted_at, accepted_job["claim_token"],
        ))
        self.repo.finish_send_attempt(
            reservation_token=accepted_job["pacing_reservation_token"], outcome="accepted",
            provider_classification="accepted", account_id=mailru_id,
            smtp_stage="post_data", smtp_code=250,
        )

        summary = self.repo.campaign_summary(self.user["workspace_id"], campaign_id)
        self.assertEqual((summary["accepted"], summary["accepted_in_campaign"], summary["accepted_by_provider"]), (1, 0, {"mailru": 1}))
        self.assertEqual((summary["remaining"], summary["queued_provider_neutral"]), (1, 1))
        dry_runs = [self.repo.campaign_continuation_dry_run(self.user["workspace_id"], campaign_id, mailru_id) for _ in range(2)]
        self.assertEqual(dry_runs[0], dry_runs[1])
        self.assertEqual(
            {key: dry_runs[0][key] for key in ("eligible_untouched", "would_create", "accepted_not_repeated", "queued_in_current_campaign")},
            {"eligible_untouched": 1, "would_create": 1, "accepted_not_repeated": 1, "queued_in_current_campaign": 1},
        )

    def _mailru_account(self) -> int:
        encrypted = encrypt(
            "mailru-continuation-secret",
            self.service._encryption_key,
            associated_data=self.service._aad(self.user["id"], self.user["workspace_id"], "app_password"),
        )
        return self.repo.save_app_password_mail_account(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], provider="mailru",
            email="continuation@mail.ru", display_name="Mail.ru", credential_encrypted=encrypted,
        )

    def _continuation_campaign(self, count: int = 6, *, body: str = "Continuation body", body_html: str | None = None) -> tuple[int, int]:
        queued = self.service.queue_bulk(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"], request_id=self.request_id,
            suppliers=[
                {
                    "name": f"Continuation Supplier {index}",
                    "email": f"continuation-{index}@example.com",
                    "host": f"continuation-{index}.example",
                    "external_key": f"continuation-{index}",
                }
                for index in range(count)
            ],
            subject="Continuation subject", body_text=body, body_html=body_html,
            idempotency_key=f"continuation-source-{count}",
            manual_stage_approval=False,
        )
        return int(queued[0]["campaign_id"]), self._mailru_account()

    def test_continuation_preserves_rich_content_snapshot(self) -> None:
        campaign_id, mailru_id = self._continuation_campaign(
            count=1, body="fallback text", body_html="<p>Frozen <strong>HTML</strong></p>",
        )
        dry_run = self.service.continuation_dry_run(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=1,
        )
        result = self.service.apply_campaign_continuation(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=1,
            idempotency_key="continuation-rich-content", selection_fingerprint=dry_run["selection_fingerprint"],
            operator_confirmed=True,
        )
        target = self.repo.get_send_operation_targets(result["operation_id"])[0]
        self.assertEqual(target["body_text"], "Frozen HTML")
        self.assertIn("<strong>HTML</strong>", target["body_html"])

    def test_continuation_apply_is_bounded_atomic_and_idempotent(self) -> None:
        campaign_id, mailru_id = self._continuation_campaign()
        before = self.repo.campaign_summary(self.user["workspace_id"], campaign_id)
        dry_run = self.service.continuation_dry_run(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=5,
        )
        result = self.service.apply_campaign_continuation(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=5,
            idempotency_key="continuation-apply-1",
            selection_fingerprint=dry_run["selection_fingerprint"], operator_confirmed=True,
        )
        self.assertEqual((result["created_count"], result["skipped_count"], result["smtp_data_calls"]), (5, 0, 0))
        self.assertTrue(result["no_live_send"])
        self.assertEqual(self.provider.send_calls, 0)
        after = self.repo.campaign_summary(self.user["workspace_id"], campaign_id)
        self.assertEqual(after["status"], before["status"])
        self.assertEqual(after["updated_at"], before["updated_at"])
        with self.repo.connect() as connection:
            operation_jobs = connection.execute(
                """SELECT COUNT(*) FROM mail_jobs j
                   JOIN mail_job_integrity ji ON ji.job_id=j.id
                   WHERE ji.operation_id=? AND j.mail_account_id=? AND j.status='queued'""",
                (result["operation_id"], mailru_id),
            ).fetchone()[0]
            campaign_targets = connection.execute(
                "SELECT COUNT(*) FROM mail_campaign_targets WHERE campaign_id=?", (campaign_id,)
            ).fetchone()[0]
        self.assertEqual((operation_jobs, campaign_targets), (5, 6))

        remaining = self.service.continuation_dry_run(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=5,
        )
        self.assertEqual((remaining["eligible_untouched"], remaining["would_create"]), (1, 1))
        replay = self.service.apply_campaign_continuation(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=5,
            idempotency_key="continuation-apply-1",
            selection_fingerprint=dry_run["selection_fingerprint"], operator_confirmed=True,
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["operation_id"], result["operation_id"])
        with self.assertRaises(ContinuationPlanConflictError):
            self.service.apply_campaign_continuation(
                user_id=self.user["id"], workspace_id=self.user["workspace_id"],
                campaign_id=campaign_id, mail_account_id=mailru_id, limit=4,
                idempotency_key="continuation-apply-1",
                selection_fingerprint=dry_run["selection_fingerprint"], operator_confirmed=True,
            )

    def test_continuation_job_can_run_while_source_campaign_is_paused(self) -> None:
        campaign_id, mailru_id = self._continuation_campaign(count=2)
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE mail_campaigns SET status='paused_for_health', pause_reason='provider_policy' WHERE id=?",
                (campaign_id,),
            )
        dry_run = self.service.continuation_dry_run(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=1,
        )
        result = self.service.apply_campaign_continuation(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=1,
            idempotency_key="continuation-paused-source", selection_fingerprint=dry_run["selection_fingerprint"],
            operator_confirmed=True,
        )
        claimed = self.repo.claim_job(pacing=self.settings)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["mail_account_id"], mailru_id)
        MailQueue(self.repo, self.service, pacing=self.settings)._process(claimed)
        self.assertEqual(self._status(result["jobs"][0]["job_id"])[0:2], ("sent", 1))

    def test_continuation_apply_revalidates_suppression_before_creating_job(self) -> None:
        campaign_id, mailru_id = self._continuation_campaign(count=2)
        dry_run = self.service.continuation_dry_run(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=2,
        )
        first = dry_run["selected_targets"][0]
        self.repo.add_email_suppression(
            self.user["workspace_id"], self.user["id"],
            email=first["normalized_email"], supplier_id=first["supplier_id"],
        )
        result = self.service.apply_campaign_continuation(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            campaign_id=campaign_id, mail_account_id=mailru_id, limit=2,
            idempotency_key="continuation-apply-suppressed",
            selection_fingerprint=dry_run["selection_fingerprint"], operator_confirmed=True,
            selected_targets=dry_run["selected_targets"],
        )
        self.assertEqual((result["created_count"], result["skipped_count"]), (1, 1))
        self.assertIn("suppressed", result["skipped_targets"][0]["reasons"])
        self.assertEqual(self.provider.send_calls, 0)


if __name__ == "__main__":
    unittest.main()
