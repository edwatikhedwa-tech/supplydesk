"""
Application configuration and environment-loading helpers, extracted from
supplier_app.py (TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903) as the
first, lowest-risk step of turning supplier_app.py into a thin composition
entrypoint. No behavior changed: every function/class below is moved
byte-for-byte from supplier_app.py, only the ROOT computation is adjusted to
this file's own location.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from mail.deliverability import RolloutSettings, campaign_max_recipients_from_env
from mail.pacing import PacingSettings
from mail.providers.mailru import MailRuProvider
from mail.providers.yandex import YandexMailProvider
from mail.repository import DEFAULT_SESSION_LIFETIME_SECONDS
from mail.runtime import RuntimeConfigurationError
from mail.types import ProviderError

ROOT = Path(__file__).resolve().parents[1]

SESSION_LIFETIME_MIN_SECONDS = 15 * 60
SESSION_LIFETIME_MAX_SECONDS = 90 * 24 * 60 * 60


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _bounded_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)) or default)
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _flag_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or ("1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            value = value.strip().strip('"').strip("'")
            # Accept values copied from placeholder documentation as <value>.
            if key in {"YANDEX_CLIENT_ID", "YANDEX_CLIENT_SECRET"} and value.startswith("<") and value.endswith(">"):
                value = value[1:-1]
            os.environ[key] = value


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    base_url: str
    redirect_uri: str
    db_path: str
    encryption_key: str | None
    app_user_email: str | None
    app_user_password: str | None
    session_cookie_secure: bool
    queue_concurrency: int
    max_retries: int
    daily_limit: int
    session_lifetime_seconds: int = DEFAULT_SESSION_LIFETIME_SECONDS
    pacing: PacingSettings = field(default_factory=PacingSettings.from_env)
    rollout: RolloutSettings = field(default_factory=RolloutSettings.from_env)
    campaign_max_recipients: int = field(default_factory=campaign_max_recipients_from_env)
    # Directly constructed configs in the unit suite are explicitly test
    # runtimes.  CLI/config-file production runs must provide the env var.
    environment: str = "test"
    canonical_db_path: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        environment = (os.getenv("SUPPLYDESK_ENV") or "").strip().lower()
        if environment not in {"production", "development", "test"}:
            raise RuntimeConfigurationError(
                "SUPPLYDESK_ENV must be exactly production, development, or test."
            )
        return cls(
            host=os.getenv("APP_HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8000")),
            base_url=base_url,
            redirect_uri=os.getenv("YANDEX_REDIRECT_URI", f"{base_url}/oauth/yandex/callback"),
            db_path=os.getenv("MAIL_DB_PATH", str(ROOT / "mail-data" / "supplier.sqlite3")),
            encryption_key=os.getenv("MAIL_TOKEN_ENCRYPTION_KEY"),
            app_user_email=os.getenv("APP_USER_EMAIL"),
            app_user_password=os.getenv("APP_USER_PASSWORD"),
            session_cookie_secure=base_url.startswith("https://"),
            queue_concurrency=max(1, min(int(os.getenv("MAIL_QUEUE_CONCURRENCY", "1")), 4)),
            max_retries=max(1, min(int(os.getenv("MAIL_MAX_RETRIES", "4")), 8)),
            daily_limit=max(1, min(int(os.getenv("MAIL_DAILY_RECIPIENT_LIMIT", "250")), 300)),
            session_lifetime_seconds=_bounded_int_env(
                "APP_SESSION_LIFETIME_SECONDS",
                DEFAULT_SESSION_LIFETIME_SECONDS,
                SESSION_LIFETIME_MIN_SECONDS,
                SESSION_LIFETIME_MAX_SECONDS,
            ),
            campaign_max_recipients=campaign_max_recipients_from_env(),
            pacing=PacingSettings.from_env(),
            rollout=RolloutSettings.from_env(),
            environment=environment,
            canonical_db_path=os.getenv("SUPPLYDESK_CANONICAL_DB_PATH"),
        )


def yandex_provider_factory(provider_name: str, credential: str | None = None):
    if provider_name == "mailru":
        return MailRuProvider(credential or "")
    if provider_name != "yandex":
        raise ProviderError("Этот почтовый провайдер пока не поддерживается.")
    # Yandex OAuth documentation uses angle brackets for placeholders. Users
    # sometimes copy them together with real credentials; never send those
    # delimiters to Yandex as part of client_id/client_secret.
    def oauth_credential(name: str) -> str:
        value = os.getenv(name, "").strip()
        if len(value) >= 2 and value.startswith("<") and value.endswith(">"):
            return value[1:-1].strip()
        return value

    return YandexMailProvider(
        oauth_credential("YANDEX_CLIENT_ID"),
        oauth_credential("YANDEX_CLIENT_SECRET"),
        oauth_scope=os.getenv("YANDEX_OAUTH_SCOPE", YandexMailProvider.default_oauth_scope),
    )
