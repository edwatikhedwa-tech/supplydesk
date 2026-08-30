"""Centralized, persisted-account pacing configuration.

The values in this module are application safety defaults.  They are not
claims about a provider's contractual limits.  Keeping parsing here prevents
worker, service, and operator paths from silently using different settings.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


@dataclass(frozen=True, slots=True)
class PacingSettings:
    """Typed defaults for one account-level outbound limiter."""

    min_interval_seconds: float = 30.0
    max_interval_seconds: float = 60.0
    max_per_hour: int = 100
    max_per_day: int = 100
    reservation_lease_seconds: int = 15 * 60
    cooldown_base_seconds: int = 5 * 60
    cooldown_max_seconds: int = 60 * 60
    breaker_failure_threshold: int = 3
    breaker_window_seconds: int = 15 * 60
    breaker_open_seconds: int = 60 * 60
    retry_base_seconds: int = 10
    retry_max_seconds: int = 15 * 60

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0 or self.max_interval_seconds < self.min_interval_seconds:
            raise ValueError("Pacing interval must be non-negative and ordered.")
        if self.max_per_hour < 1 or self.max_per_day < 1:
            raise ValueError("Pacing budgets must be positive.")

    @classmethod
    def from_env(cls) -> "PacingSettings":
        minimum = _env_float("MAIL_PACING_MIN_SECONDS", 30.0, minimum=0.0, maximum=24 * 60 * 60)
        maximum = _env_float("MAIL_PACING_MAX_SECONDS", 60.0, minimum=minimum, maximum=24 * 60 * 60)
        return cls(
            min_interval_seconds=minimum,
            max_interval_seconds=maximum,
            max_per_hour=_env_int("MAIL_MAX_PER_HOUR", 100, minimum=1, maximum=100_000),
            max_per_day=_env_int("MAIL_MAX_PER_DAY", 100, minimum=1, maximum=1_000_000),
            reservation_lease_seconds=_env_int("MAIL_PACING_RESERVATION_SECONDS", 900, minimum=30, maximum=24 * 60 * 60),
            cooldown_base_seconds=_env_int("MAIL_COOLDOWN_BASE_SECONDS", 300, minimum=1, maximum=24 * 60 * 60),
            cooldown_max_seconds=_env_int("MAIL_COOLDOWN_MAX_SECONDS", 3600, minimum=1, maximum=7 * 24 * 60 * 60),
            breaker_failure_threshold=_env_int("MAIL_BREAKER_FAILURE_THRESHOLD", 3, minimum=1, maximum=100),
            breaker_window_seconds=_env_int("MAIL_BREAKER_WINDOW_SECONDS", 900, minimum=1, maximum=7 * 24 * 60 * 60),
            breaker_open_seconds=_env_int("MAIL_BREAKER_OPEN_SECONDS", 3600, minimum=1, maximum=7 * 24 * 60 * 60),
            retry_base_seconds=_env_int("MAIL_RETRY_BASE_SECONDS", 10, minimum=1, maximum=24 * 60 * 60),
            retry_max_seconds=_env_int("MAIL_RETRY_MAX_SECONDS", 900, minimum=1, maximum=7 * 24 * 60 * 60),
        )

    def next_delay(self, rng: Any = random) -> float:
        """Return bounded base interval plus bounded jitter."""

        if self.max_interval_seconds == self.min_interval_seconds:
            return self.min_interval_seconds
        return self.min_interval_seconds + float(rng.uniform(0.0, self.max_interval_seconds - self.min_interval_seconds))

    def retry_delay(self, attempts: int, *, rate_limited: bool = False, rng: Any = random) -> int:
        """Return bounded exponential retry delay, with small bounded jitter."""

        exponent = max(0, min(int(attempts) - 1, 30))
        base = min(self.retry_max_seconds, self.retry_base_seconds * (2 ** exponent))
        jitter = int(rng.uniform(0.0, min(10.0, float(self.retry_base_seconds))))
        return min(self.retry_max_seconds, int(base) + jitter)

    def cooldown_delay(self, level: int) -> int:
        exponent = max(0, min(int(level), 30))
        return min(self.cooldown_max_seconds, self.cooldown_base_seconds * (2 ** exponent))
