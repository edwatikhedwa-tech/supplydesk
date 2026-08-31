from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from .pacing import PacingSettings
from .repository import MailRepository, utc_now
from .service import MailService
from .types import ProviderError
from .deliverability import classify_provider_error


log = logging.getLogger(__name__)
UTC = timezone.utc


class MailQueue:
    """Small SQLite-backed queue with bounded workers and retry backoff."""

    def __init__(self, repository: MailRepository, service: MailService, *, concurrency: int = 1, max_retries: int = 4, pacing: PacingSettings | None = None) -> None:
        self.repository = repository
        self.service = service
        self.concurrency = max(1, min(concurrency, 4))
        self.max_retries = max(1, max_retries)
        self.pacing = pacing or service.pacing_settings
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.recovery_thread: threading.Thread | None = None
        self.pause_lock = threading.Lock()
        self.paused_until = 0.0
        self._runtime_attempt_lock = threading.Lock()
        self._runtime_transport_attempts = 0
        raw_limit = os.getenv("MAIL_RUNTIME_MAX_TRANSPORT_ATTEMPTS", "").strip()
        try:
            self.runtime_max_transport_attempts = max(0, int(raw_limit)) if raw_limit else 0
        except ValueError:
            self.runtime_max_transport_attempts = 0
        raw_job_id = os.getenv("MAIL_RUNTIME_ONLY_JOB_ID", "").strip()
        try:
            self.runtime_only_job_id = int(raw_job_id) if raw_job_id else None
        except ValueError:
            self.runtime_only_job_id = None

    def start(self) -> None:
        if self.threads:
            return
        # Recovery gets one provider lookup opportunity, and an unknown result
        # is never reintroduced into the ordinary queue. It must not block the
        # HTTP listener: a stale Yandex/IMAP connection can otherwise make the
        # local server appear down before ThreadingHTTPServer is bound.
        self.recovery_thread = threading.Thread(
            target=self._run_startup_recovery, name="mail-recovery", daemon=True,
        )
        self.recovery_thread.start()
        for index in range(self.concurrency):
            thread = threading.Thread(target=self._run, name=f"mail-queue-{index + 1}", daemon=True)
            thread.start()
            self.threads.append(thread)

    def _run_startup_recovery(self) -> None:
        try:
            reconciliation = self.repository.reconcile_stale_started_reservations()
            if reconciliation["consumed"]:
                log.warning(
                    "Reconciled %d stale pacing reservations with known terminal outcomes.",
                    reconciliation["consumed"],
                )
        except Exception:  # noqa: BLE001 — reconciliation must not prevent the queue from starting
            log.warning("Stale pacing reservation reconciliation failed; no reservation was released.")
        try:
            self.service.recover_delivery_unknown()
        except Exception:  # noqa: BLE001 — recovery must not prevent the server from binding
            log.warning("Startup delivery-unknown recovery failed; no job was requeued.")

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()
        for thread in self.threads:
            thread.join(timeout=2)
        self.threads.clear()

    def wake(self) -> None:
        self.wake_event.set()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            if self._is_paused():
                self.wake_event.wait(timeout=1.0)
                self.wake_event.clear()
                continue
            # Do not claim/release the same queued job in a tight loop while
            # the global outgoing switch is disabled. This is only a worker
            # efficiency guard; send_claimed_job/_send_with_gate retain the
            # authoritative race-safe check immediately before provider DATA.
            if not self.service.outgoing_enabled():
                self.wake_event.wait(timeout=1.0)
                self.wake_event.clear()
                continue
            if self._runtime_limit_reached():
                # The controlled-run ceiling is process-local and deliberately
                # does not mutate queue state.  The operator watchdog turns
                # the durable global switch off after the allowed outcomes.
                self.wake_event.wait(timeout=60.0)
                self.wake_event.clear()
                continue
            job = self.repository.claim_job(pacing=self.pacing, only_job_id=self.runtime_only_job_id)
            if job is None:
                self.wake_event.wait(timeout=self.repository.next_pacing_wake_seconds(self.pacing, default=60.0))
                self.wake_event.clear()
                continue
            self._process(job)

    def _process(self, job: dict) -> None:
        reservation_token = job.get("pacing_reservation_token")
        try:
            self._wait_for_pacing_window(job)
            attempt = self.service.send_claimed_job(job, before_transport=self._record_transport_attempt)
            result = attempt.result
            try:
                committed = self.repository.mark_job_sent(
                    job["id"],
                    job["message_id"],
                    result.provider_message_id,
                    result.message_id,
                    result.sent_at.isoformat(),
                    claim_token=job.get("claim_token"),
                )
            except Exception:
                # SMTP already accepted the message. Try the external evidence
                # copy, persist uncertainty when possible, then stop: this is
                # not an ordinary retry opportunity.
                try:
                    self.repository.mark_job_delivery_unknown(
                        job["id"], job["message_id"],
                        "Провайдер принял письмо, но результат не удалось записать локально.",
                        job.get("claim_token"),
                    )
                except Exception:
                    # A second DB failure is recovered by the lease/startup
                    # path; it must never become permission to send again.
                    pass
                self.service.save_sent_copy(attempt, job_id=job["id"])
                self.repository.finish_send_attempt(
                    reservation_token=reservation_token, outcome="uncertain",
                    provider_classification="db-persistence-failure",
                    error="SMTP accepted but local result persistence failed.",
                    account_id=int(job["mail_account_id"]),
                    smtp_stage=result.smtp_stage,
                    smtp_code=result.smtp_code,
                    smtp_enhanced_status=result.smtp_enhanced_status,
                    provider_response_safe=result.provider_response_safe,
                    exception_class=result.exception_class,
                )
                self.repository.refresh_campaign_after_job(job["id"], rollout=self.service.rollout_settings)
                return
            if not committed:
                self.service.save_sent_copy(attempt, job_id=job["id"])
                self.repository.finish_send_attempt(
                    reservation_token=reservation_token, outcome="uncertain",
                    provider_classification="claim-lost-after-provider-acceptance",
                    error="Provider accepted the message but the local claim was no longer owned.",
                    account_id=int(job["mail_account_id"]),
                    smtp_stage=result.smtp_stage,
                    smtp_code=result.smtp_code,
                    smtp_enhanced_status=result.smtp_enhanced_status,
                    provider_response_safe=result.provider_response_safe,
                    exception_class=result.exception_class,
                )
                self.repository.refresh_campaign_after_job(job["id"], rollout=self.service.rollout_settings)
                return
            # The acceptance state is durable before this best-effort IMAP call.
            self.repository.finish_send_attempt(
                reservation_token=reservation_token, outcome="accepted",
                provider_classification="accepted", account_id=int(job["mail_account_id"]),
                smtp_stage=result.smtp_stage,
                smtp_code=result.smtp_code,
                smtp_enhanced_status=result.smtp_enhanced_status,
                provider_response_safe=result.provider_response_safe,
                exception_class=result.exception_class,
            )
            self.service.save_sent_copy(attempt, job_id=job["id"])
            self.repository.refresh_campaign_after_job(job["id"], rollout=self.service.rollout_settings)
        except ProviderError as exc:
            if exc.revoked:
                self.service.mark_refresh_error(job["mail_account_id"], exc)
            if exc.provider_code in {
                "outgoing-disabled", "operational_blocked_noncanonical_runtime",
                "integrity-gate", "pacing-wait", "campaign-paused",
            }:
                integrity = self.repository.get_job_integrity(job["id"])
                if exc.provider_code in {"outgoing-disabled", "operational_blocked_noncanonical_runtime"} and integrity and integrity.get("irreversible_at"):
                    # The final pre-DATA guard may observe the switch after
                    # the durable I1 gate. Keep that evidence, close the
                    # audit row, and use I1's neutral release path; never
                    # turn this deterministic no-network block into a send.
                    self.repository.finish_send_attempt(
                        reservation_token=reservation_token,
                        outcome="blocked_operational" if exc.provider_code == "operational_blocked_noncanonical_runtime" else "blocked_global",
                        provider_classification="canonical-runtime-guard" if exc.provider_code == "operational_blocked_noncanonical_runtime" else "global-kill-switch",
                        error=exc.message, account_id=int(job["mail_account_id"]),
                        smtp_stage=exc.smtp_stage,
                        smtp_code=exc.smtp_code,
                        smtp_enhanced_status=exc.smtp_enhanced_status,
                        provider_response_safe=exc.provider_response_safe,
                        exception_class=exc.exception_class,
                    )
                else:
                    self.repository.release_send_reservation(reservation_token, exc.provider_code or "blocked", reset_pacing=True)
                self.repository.release_claim(job["id"], job["message_id"], exc.message, job.get("claim_token"))
                if exc.provider_code in {"campaign-paused", "integrity-gate"}:
                    self.repository.cancel_stopped_campaign_job(job["id"], job["message_id"])
                return
            if exc.provider_code == "supplier-suppressed":
                self.repository.release_send_reservation(reservation_token, "supplier-suppressed", reset_pacing=True)
                self.repository.fail_claim_without_attempt(job["id"], job["message_id"], exc.message, job.get("claim_token"))
                self.repository.mark_campaign_target_excluded(job["id"], "suppressed")
                self.repository.refresh_campaign_after_job(job["id"], rollout=self.service.rollout_settings)
                return
            if exc.uncertain:
                self.repository.mark_job_delivery_unknown(
                    job["id"], job["message_id"], exc.message, job.get("claim_token"),
                )
                self.repository.finish_send_attempt(
                    reservation_token=reservation_token, outcome="uncertain",
                    provider_classification=exc.provider_code or "transport-uncertain",
                    error=exc.message, account_id=int(job["mail_account_id"]),
                    smtp_stage=exc.smtp_stage,
                    smtp_code=exc.smtp_code,
                    smtp_enhanced_status=exc.smtp_enhanced_status,
                    provider_response_safe=exc.provider_response_safe,
                    exception_class=exc.exception_class,
                )
                self.repository.refresh_campaign_after_job(job["id"], rollout=self.service.rollout_settings)
                return
            attempts = int(job.get("attempts") or 1)
            status = self.repository.pacing_status(int(job["mail_account_id"]), self.pacing)
            failure_level = int(status.get("cooldown_level") or 0)
            delay = self.pacing.cooldown_delay(failure_level) if exc.rate_limited else self.pacing.retry_delay(attempts)
            next_attempt = (utc_now() + timedelta(seconds=delay)).isoformat()
            pacing_result = self.repository.record_pre_gate_attempt(
                job=job, reservation_token=reservation_token,
                outcome="transient_rejected" if exc.transient else "permanent_rejected",
                provider_classification=exc.provider_code or ("transient" if exc.transient else "permanent"),
                error=exc.message, next_retry_at=next_attempt,
                transient=exc.transient, rate_limited=exc.rate_limited,
                revoked=exc.revoked, pacing=self.pacing,
                smtp_stage=exc.smtp_stage,
                smtp_code=exc.smtp_code,
                smtp_enhanced_status=exc.smtp_enhanced_status,
                provider_response_safe=exc.provider_response_safe,
                exception_class=exc.exception_class,
            )
            classification = classify_provider_error(exc)
            explicit_pause = None
            if classification == "provider-spam-policy":
                explicit_pause = "provider_spam_or_policy_rejection"
            elif classification == "authentication":
                explicit_pause = "authentication_failure"
            cooldown_until = pacing_result.get("cooldown_until")
            if cooldown_until and exc.transient:
                next_attempt = max(next_attempt, cooldown_until)
            if exc.transient and not exc.revoked and attempts < self.max_retries:
                self.repository.retry_job(job["id"], job["message_id"], exc.message, next_attempt, job.get("claim_token"))
                if exc.rate_limited:
                    self._pause_for(max(1, delay))
            else:
                self.repository.fail_job(job["id"], job["message_id"], exc.message, job.get("claim_token"))
            self.repository.refresh_campaign_after_job(
                job["id"], rollout=self.service.rollout_settings, pause_reason=explicit_pause,
            )
        except Exception as exc:
            # The raw exception is intentionally not logged: it may contain SMTP response data.
            integrity = self.repository.get_job_integrity(job["id"])
            if integrity and integrity.get("irreversible_at"):
                self.repository.mark_job_delivery_unknown(
                    job["id"], job["message_id"],
                    "Не удалось подтвердить результат передачи письма.", job.get("claim_token"),
                )
                self.repository.finish_send_attempt(
                    reservation_token=reservation_token, outcome="uncertain",
                    provider_classification="internal-uncertain",
                    error="Unable to confirm transport result.", account_id=int(job["mail_account_id"]),
                    smtp_stage="unknown", exception_class=type(exc).__name__,
                )
                self.repository.refresh_campaign_after_job(job["id"], rollout=self.service.rollout_settings)
            else:
                self.repository.release_send_reservation(reservation_token, "internal-error-before-gate", reset_pacing=True)
                self.repository.fail_claim_without_attempt(
                    job["id"],
                    job["message_id"],
                    "Неожиданная ошибка отправки. Письмо не было отмечено как отправленное.",
                    job.get("claim_token"),
                )

    @staticmethod
    def _seconds_until(value: object, now: datetime) -> float:
        if not value:
            return 0.0
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return 0.0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (parsed.astimezone(UTC) - now).total_seconds())

    def _wait_for_pacing_window(self, job: dict) -> None:
        """Wait for the already-claimed reservation's transport window.

        ``claim_job`` owns reservation creation.  This method only waits on
        the existing persisted deadlines and wakes on queue events, so it
        cannot create a second reservation or charge an attempt while waiting.
        """

        while not self.stop_event.is_set():
            if not self.service.outgoing_enabled():
                raise ProviderError(
                    "Исходящая почта временно отключена аварийным выключателем.",
                    provider_code="outgoing-disabled",
                )

            now = utc_now()
            pacing = self.repository.pacing_status(int(job["mail_account_id"]), self.pacing)
            waits = [
                self._seconds_until(job.get("pacing_scheduled_not_before"), now),
                self._seconds_until(job.get("next_attempt_at"), now),
                self._seconds_until(pacing.get("next_send_not_before"), now),
                self._seconds_until(pacing.get("cooldown_until"), now),
                self._seconds_until(pacing.get("breaker_until"), now),
            ]
            if pacing.get("breaker_state") == "open" and not waits[-1]:
                raise ProviderError(
                    "Лимитер почтового аккаунта временно заблокирован.",
                    provider_code="pacing-wait",
                )
            if pacing.get("reason") in {"hour_budget_wait", "day_budget_wait"}:
                raise ProviderError(
                    "Достигнут лимит отправок почтового аккаунта.",
                    provider_code="pacing-wait",
                )
            if pacing.get("reason") == "reservation_in_progress" and not job.get("pacing_reservation_token"):
                raise ProviderError(
                    "Для почтового аккаунта уже выполняется другая отправка.",
                    provider_code="pacing-wait",
                )
            wait_seconds = max(waits)
            if wait_seconds <= 0:
                return
            # A bounded wait keeps the worker responsive to a state change
            # even when an external caller cannot emit queue.wake().
            self.wake_event.wait(timeout=min(wait_seconds, 60.0))
            self.wake_event.clear()

        raise ProviderError(
            "Исходящая почта остановлена до начала отправки.",
            provider_code="outgoing-disabled",
        )

    def _pause_for(self, seconds: int) -> None:
        with self.pause_lock:
            self.paused_until = max(self.paused_until, time.monotonic() + seconds)

    def _is_paused(self) -> bool:
        with self.pause_lock:
            return time.monotonic() < self.paused_until

    def _record_transport_attempt(self) -> None:
        with self._runtime_attempt_lock:
            self._runtime_transport_attempts += 1

    def _runtime_limit_reached(self) -> bool:
        if not self.runtime_max_transport_attempts:
            return False
        with self._runtime_attempt_lock:
            return self._runtime_transport_attempts >= self.runtime_max_transport_attempts
