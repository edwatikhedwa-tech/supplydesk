from __future__ import annotations

import random
import threading
import time
from datetime import timedelta

from .repository import MailRepository, iso_now, utc_now
from .service import MailService
from .types import ProviderError


class MailQueue:
    """Small SQLite-backed queue with bounded workers and retry backoff."""

    def __init__(self, repository: MailRepository, service: MailService, *, concurrency: int = 1, max_retries: int = 4) -> None:
        self.repository = repository
        self.service = service
        self.concurrency = max(1, min(concurrency, 4))
        self.max_retries = max(1, max_retries)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.pause_lock = threading.Lock()
        self.paused_until = 0.0

    def start(self) -> None:
        if self.threads:
            return
        for index in range(self.concurrency):
            thread = threading.Thread(target=self._run, name=f"mail-queue-{index + 1}", daemon=True)
            thread.start()
            self.threads.append(thread)

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
            job = self.repository.claim_job()
            if job is None:
                self.wake_event.wait(timeout=0.7)
                self.wake_event.clear()
                continue
            self._process(job)

    def _process(self, job: dict) -> None:
        try:
            if self.repository.count_sent_today(job["mail_account_id"]) >= self.service.daily_limit:
                raise ProviderError(
                    "Достигнут безопасный дневной предел отправки. Оставшиеся письма сохранены в очереди.",
                    transient=True,
                    rate_limited=True,
                    provider_code="local-daily-limit",
                )
            result = self.service.send_claimed_job(job)
            self.repository.mark_job_sent(
                job["id"],
                job["message_id"],
                result.provider_message_id,
                result.message_id,
                result.sent_at.isoformat(),
            )
        except ProviderError as exc:
            if exc.revoked:
                self.service.mark_refresh_error(job["mail_account_id"], exc)
            attempts = int(job.get("attempts") or 1)
            if exc.transient and attempts < self.max_retries:
                delay = 3600 if exc.rate_limited else min(900, (2 ** attempts) * 10 + random.randint(0, 10))
                next_attempt = (utc_now() + timedelta(seconds=delay)).isoformat()
                self.repository.retry_job(job["id"], job["message_id"], exc.message, next_attempt)
                if exc.rate_limited:
                    self._pause_for(delay)
            else:
                self.repository.fail_job(job["id"], job["message_id"], exc.message)
        except Exception:
            # The raw exception is intentionally not logged: it may contain SMTP response data.
            self.repository.fail_job(
                job["id"],
                job["message_id"],
                "Неожиданная ошибка отправки. Письмо не было отмечено как отправленное.",
            )

    def _pause_for(self, seconds: int) -> None:
        with self.pause_lock:
            self.paused_until = max(self.paused_until, time.monotonic() + seconds)

    def _is_paused(self) -> bool:
        with self.pause_lock:
            return time.monotonic() < self.paused_until
