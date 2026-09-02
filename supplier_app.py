from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mail.auth import new_token, token_hash
from mail.crypto import EncryptionConfigError
from mail.deliverability import DeliverabilityPreflightError, RolloutSettings, campaign_max_recipients_from_env
from mail.providers.yandex import YandexMailProvider
from mail.providers.mailru import MailRuProvider
from mail.pacing import PacingSettings
from mail.queue import MailQueue
from mail.repository import DEFAULT_SESSION_LIFETIME_SECONDS, DeliveryResolutionRequiredError, MailRepository
from mail.runtime import RuntimeConfigurationError, RuntimeSession
from mail.service import MailService
from mail.types import ProviderError
from serp_parser import SerpCollector, read_lines
from backend.integrations.search.xmlriver_client import XmlRiverClient

# Enrichment pipeline (email/INN/company data) — see Documents/28-8/enrichment-and-cache.md.
# Reused as-is from the already-tested CLI tools; nothing here is new logic.
from backend.integrations.registry.checko_client import CheckoClient
from collect_inn import (
    INN_PATHS,
    INN_URL_HINTS,
    extract_for_site,
    extract_legal_ids_for_site,
    page_text,
)
from contact_crawler import ContactCrawler, SiteResult
from backend.domain.supplier_identity.email_extractor import is_contact_url, root_domain
from backend.domain.supplier_identity.inn_extractor import (
    InnHit,
    LegalIdHit,
    is_requisites_url,
    validate_inn_checksum,
)
from backend.domain.supplier_identity.inn_resolver import (
    collect_name_hints_from_pages,
    resolve_inn_by_legal_ids,
    resolve_inn_by_registry,
)
from backend.integrations.llm.llm_fallback import LlmExtractor, api_key_present
from backend.domain.supplier_identity.verify import (
    registry_owns_site,
    registry_ownership_unknown,
    verify_email,
)
from backend.integrations.search.web_lookup import WebLookup

log = logging.getLogger("supplier_app")

ROOT = Path(__file__).resolve().parent

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


def _strict_optional_bool(payload: dict, field: str) -> bool | None:
    """Accept only JSON booleans; omitted remains the backend default."""
    if field not in payload:
        return None
    value = payload[field]
    if type(value) is not bool:
        raise ValueError(f"{field} должен быть логическим значением true или false.")
    return value


@dataclass
class EnrichmentOutcome:
    """Что осталось после одного прохода по поставщику."""

    retry_stage: str = ""          # crawl | registry | web | finance
    error: str = ""
    retry_after_seconds: int = 60
    context: dict[str, object] = field(default_factory=dict)

    @property
    def needs_retry(self) -> bool:
        return bool(self.retry_stage)


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


# The built React SPA (frontend/npm run build). Its assets are hashed and public;
# nothing under ROOT besides this directory and the font files below is servable.
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Extensions that only ever belong to server-side source or config. A React
# Router path never ends in one of these, so such a request is either a probe
# or a typo — both deserve a plain 404 rather than the SPA shell.
_SOURCE_SUFFIXES = (
    ".py", ".pyc", ".sql", ".env", ".ini", ".cfg", ".toml", ".yaml", ".yml",
    ".sqlite3", ".db", ".log", ".sh", ".ps1", ".bak", ".pem", ".key",
)


def _looks_like_source_path(path: str) -> bool:
    tail = path.rsplit("/", 1)[-1].lower()
    return tail.startswith(".env") or tail.endswith(_SOURCE_SUFFIXES)


def load_fixture_data() -> dict:
    """Read the demo supplier catalog once so a fresh workspace has seed data."""
    return json.loads((ROOT / "fixtures" / "demo_catalog.json").read_text(encoding="utf-8"))


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


class SupplierHandler(SimpleHTTPRequestHandler):
    server_version = "SupplydeskMail/1.0"

    @property
    def app(self) -> "SupplierApp":
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        # Do not log query strings: OAuth callbacks and user email data can be present there.
        print(f"[{self.log_date_time_string()}] {self.command} {self.path.split('?', 1)[0]} {args[1] if len(args) > 1 else ''}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/assets/"):
            self.directory = str(FRONTEND_DIST)
            super().do_GET()
            return
        if parsed.path in {"/fonts/ProcureSans-Regular.otf", "/fonts/ProcureSans-Semibold.otf"}:
            self.directory = str(ROOT)
            super().do_GET()
            return
        if parsed.path == "/api/auth/me":
            self._auth_me()
            return

        if parsed.path == "/api/auth/yandex/start":
            self._auth_yandex_start()
            return
        if parsed.path == "/api/dashboard/summary":
            session = self._require_session()
            if session:
                self._json(200, self.app.repository.dashboard_summary(session["workspace_id"]))
            return
        if parsed.path == "/api/requests":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.list_requests(session["workspace_id"])})
            return
        if parsed.path.startswith("/api/requests/"):
            session = self._require_session()
            if session:
                self._request_route(session, parsed.path, parse_qs(parsed.query))
            return
        if parsed.path == "/api/suppliers":
            session = self._require_session()
            if session:
                try:
                    query = parse_qs(parsed.query)
                    request_id_value = (query.get("request_id") or [""])[0]
                    request_id = int(request_id_value) if request_id_value else None
                    items = self.app.repository.list_suppliers(
                        session["workspace_id"], request_id,
                        query=(query.get("q") or [""])[0],
                        region=(query.get("region") or [""])[0],
                        kind=(query.get("kind") or [""])[0],
                        role=(query.get("role") or [""])[0],
                    )
                    self._json(200, {"items": items})
                except ValueError:
                    self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        if parsed.path == "/api/blacklist":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.list_blacklist(session["workspace_id"])})
            return
        if parsed.path == "/api/global-suppliers":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.list_global_suppliers(session["workspace_id"])})
            return
        if parsed.path.startswith("/api/global-suppliers/"):
            session = self._require_session()
            if session:
                self._global_supplier_route(session, parsed.path)
            return
        if parsed.path == "/api/correspondence":
            session = self._require_session()
            if session:
                # Забрать новую почту перед выдачей списка, чтобы обновления
                # страницы было достаточно — раньше письмо появлялось только
                # после ручного нажатия «Синхронизировать» в «Настройках».
                # Вызов ограничен по частоте, поэтому повторные F5 не ждут IMAP.
                self.app.maybe_sync_incoming(session["user_id"], session["workspace_id"])
                self._json(200, {"items": self.app.repository.list_threads(session["workspace_id"])})
            return
        if parsed.path == "/api/mail/template":
            session = self._require_session()
            if session:
                self._json(200, self.app.service.template(session["workspace_id"]))
            return
        if parsed.path == "/api/mail/status":
            session = self._require_session()
            if session:
                self._json(200, self.app.service.status(session["user_id"], session["workspace_id"]))
            return
        if parsed.path == "/api/mail/runtime/outgoing":
            session = self._require_session()
            if session:
                self._json(200, {
                    "durable_outgoing_enabled": self.app.repository.outgoing_enabled(),
                    "effective_outgoing_enabled": self.app.service.outgoing_enabled(),
                })
            return
        if parsed.path == "/api/mail/accounts":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.service.accounts(session["user_id"], session["workspace_id"])})
            return
        if parsed.path == "/api/mail/inbox":
            session = self._require_session()
            if session:
                self.app.maybe_sync_incoming(session["user_id"], session["workspace_id"])
                self._json(200, {"items": self.app.repository.list_unmatched_incoming(session["workspace_id"])})
            return
        if parsed.path == "/api/mail/inbox/requests":
            session = self._require_session()
            if session:
                query = parse_qs(parsed.query)
                search = (query.get("q") or [""])[0]
                self._json(200, {"items": self.app.repository.list_manual_link_requests(session["workspace_id"], search)})
            return
        if parsed.path == "/api/mail/inbox/preview":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.list_unmatched_incoming_preview(session["workspace_id"])})
            return
        if parsed.path == "/api/mail/request-status":
            session = self._require_session()
            if session:
                try:
                    request_id = int(parse_qs(parsed.query).get("request_id", [1043])[0])
                    self._json(200, {"items": self.app.repository.request_statuses(session["workspace_id"], request_id)})
                except ValueError:
                    self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        if parsed.path == "/api/mail/queue":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.queue_stats(session["workspace_id"])})
            return
        if parsed.path == "/api/mail/queue/messages":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.list_outbox_threads(session["workspace_id"])})
            return
        if parsed.path.startswith("/api/mail/campaigns/"):
            session = self._require_session()
            if session:
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) != 4:
                    self._json(404, {"error": "Campaign не найдена."})
                    return
                try:
                    campaign_id = int(parts[3])
                except ValueError:
                    self._json(400, {"error": "Некорректный идентификатор campaign."})
                    return
                summary = self.app.repository.campaign_summary(session["workspace_id"], campaign_id)
                if not summary:
                    self._json(404, {"error": "Campaign не найдена."})
                    return
                self._json(200, summary)
            return
        if parsed.path == "/api/mail/threads":
            session = self._require_session()
            if session:
                self._thread_messages(session, parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/mail/inbox/") and parsed.path.endswith("/suggestions"):
            session = self._require_session()
            if session:
                try:
                    inbox_id = int(parsed.path.split("/")[4])
                except (IndexError, ValueError):
                    self._json(400, {"error": "Некорректный идентификатор письма."})
                    return
                self._json(200, {"items": self.app.repository.suggest_requests_for_inbox(session["workspace_id"], inbox_id)})
            return
        if parsed.path == "/api/mail/inbox/conversation":
            session = self._require_session()
            if session:
                try:
                    message_id = int(parse_qs(parsed.query).get("inbox_message_id", [0])[0])
                except ValueError:
                    self._json(400, {"error": "Некорректный идентификатор письма."})
                    return
                conversation = self.app.repository.inbox_conversation(session["workspace_id"], message_id)
                if not conversation:
                    self._json(404, {"error": "Письмо не найдено."})
                    return
                self._json(200, conversation)
            return
        if parsed.path == "/api/mail/yandex/start":
            self._oauth_start()
            return
        if parsed.path == "/oauth/yandex/callback":
            self._oauth_callback(parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/") or parsed.path.startswith("/oauth/"):
            self._json(404, {"error": "Не найдено."})
            return
        # A path that looks like a source or config file is never a client-side
        # route. The shell is not sensitive, so answering it with 200 leaks
        # nothing today — but it makes /.env and /supplier_app.py *look* like
        # they exist to any scanner, and it would quietly mask a future
        # whitelist mistake instead of failing loudly. Answer honestly: 404.
        if _looks_like_source_path(parsed.path):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        # Anything else is a client-side route (React Router) — serve the SPA shell
        # and let the browser router resolve it. Auth is decided client-side via
        # /api/auth/me so this response never needs to vary by session.
        self._serve_app_shell()

    def send_head(self):
        """Serve hashed frontend assets with compression and immutable caching."""
        if not self.path.split("?", 1)[0].startswith("/assets/"):
            return super().send_head()

        self.directory = str(FRONTEND_DIST)
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            return super().send_head()

        body = path.read_bytes()
        content_encoding = None
        accepted_encodings = self.headers.get("Accept-Encoding", "")
        if path.suffix.lower() in {".js", ".css", ".html", ".svg", ".json"} and "gzip" in accepted_encodings.lower():
            body = gzip.compress(body, compresslevel=6, mtime=0)
            content_encoding = "gzip"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", self.guess_type(str(path)))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Vary", "Accept-Encoding")
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        self.end_headers()
        return io.BytesIO(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json()
        if body is None:
            return
        if parsed.path == "/api/auth/login":
            self._login(body)
            return
        if parsed.path == "/api/auth/logout":
            session = self._require_session()
            if session and self._require_csrf(session):
                self.app.repository.delete_session(self._session_token())
                self._json(
                    200,
                    {"ok": True},
                    headers={"Set-Cookie": "session_id=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"},
                )
            return
        session = self._require_session()
        if not session or not self._require_csrf(session):
            return
        if not self.app.allow_api_request(self._session_token()):
            self._json(429, {"error": "Слишком много запросов. Попробуйте через минуту."})
            return
        try:
            if parsed.path == "/api/enrichment/step":
                self._json(200, {"ok": True, **self.app.process_enrichment_retry_step(session["workspace_id"])})
            elif parsed.path == "/api/mail/runtime/outgoing":
                enabled = _strict_optional_bool(body, "enabled")
                if enabled is None:
                    raise ValueError("enabled должен быть указан явно.")
                confirmation = _strict_optional_bool(body, "confirmation")
                result = self.app.service.set_outgoing_enabled(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    enabled=enabled, confirmation=bool(confirmation),
                )
                self.app.queue.wake()
                self._json(200, result)
            elif parsed.path == "/api/mail/test":
                account_id = int(body["mail_account_id"]) if body.get("mail_account_id") is not None else None
                self.app.service.test_connection(session["user_id"], session["workspace_id"], mail_account_id=account_id)
                self._json(200, {"ok": True, "message": "Соединение почтового аккаунта проверено."})
            elif parsed.path == "/api/mail/accounts/mailru/connect":
                account = self.app.service.connect_mailru(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    email=str(body.get("email") or ""), app_password=str(body.get("app_password") or ""),
                )
                self._json(201, {"ok": True, "account": account})
            elif parsed.path.startswith("/api/mail/accounts/") and parsed.path.endswith("/test"):
                account_id = int(parsed.path.split("/")[4])
                self.app.service.test_connection(session["user_id"], session["workspace_id"], mail_account_id=account_id)
                self._json(200, {"ok": True, "message": "Соединение почтового аккаунта проверено."})
            elif parsed.path == "/api/mail/sync":
                account_id = int(body["mail_account_id"]) if body.get("mail_account_id") is not None else None
                result = self.app.service.sync_incoming(session["user_id"], session["workspace_id"], mail_account_id=account_id) if account_id is not None else self.app.service.sync_all_incoming(session["user_id"], session["workspace_id"])
                self._json(200, result)
            elif parsed.path == "/api/mail/disconnect":
                account_id = int(body["mail_account_id"]) if body.get("mail_account_id") is not None else None
                self.app.service.disconnect(session["user_id"], session["workspace_id"], mail_account_id=account_id)
                self._json(200, {"ok": True})
            elif parsed.path == "/api/mail/template":
                template = self.app.service.save_template(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    subject=body.get("subject", ""), body=body.get("body", ""),
                    attachments=body.get("attachments") or [],
                )
                self._json(200, {"ok": True, **template})
            elif parsed.path in {"/api/mail/deliverability/preflight", "/api/mail/deliverability/preview"}:
                manual_stage_approval = _strict_optional_bool(body, "manual_stage_approval")
                allow_repeat = _strict_optional_bool(body, "allow_repeat")
                result = self.app.service.preflight_bulk(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 1043)),
                    suppliers=body.get("suppliers") or [],
                    subject=str(body.get("subject", "")), body=body.get("body"),
                    body_text=body.get("body_text"), body_html=body.get("body_html"),
                    attachments=body.get("attachments") or [],
                    manual_stage_approval=manual_stage_approval,
                    allow_repeat=bool(allow_repeat),
                    mail_account_id=int(body["mail_account_id"]) if body.get("mail_account_id") is not None else None,
                )
                self._json(200, {
                    "ok": True,
                    "dry_run": True,
                    "preview": parsed.path.endswith("/preview"),
                    "preview_contract": {
                        "frozen": False,
                        "renderer": "operation_target_snapshot",
                        "snapshot_frozen_on": "send-bulk operation assembly",
                        "rerun_if_source_data_changed": True,
                    },
                    **result,
                })
            elif parsed.path == "/api/mail/send":
                idempotency_key = str(body.get("idempotency_key") or self.headers.get("Idempotency-Key") or "").strip() or None
                allow_repeat = _strict_optional_bool(body, "allow_repeat")
                result = self.app.service.queue_one(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 1043)), supplier=body.get("supplier") or {},
                    subject=body.get("subject", ""), body=body.get("body"),
                    body_text=body.get("body_text"), body_html=body.get("body_html"),
                    attachments=body.get("attachments") or [],
                    idempotency_key=idempotency_key,
                    allow_repeat=bool(allow_repeat),
                    mail_account_id=int(body["mail_account_id"]) if body.get("mail_account_id") is not None else None,
                )
                self.app.queue.wake()
                self._json(202, {"ok": True, "queued": [result]})
            elif parsed.path == "/api/mail/send-bulk":
                idempotency_key = str(body.get("idempotency_key") or self.headers.get("Idempotency-Key") or "").strip() or None
                manual_stage_approval = _strict_optional_bool(body, "manual_stage_approval")
                allow_repeat = _strict_optional_bool(body, "allow_repeat")
                results = self.app.service.queue_bulk(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 1043)), suppliers=body.get("suppliers") or [],
                    subject=body.get("subject", ""), body=body.get("body"),
                    body_text=body.get("body_text"), body_html=body.get("body_html"),
                    attachments=body.get("attachments") or [],
                    idempotency_key=idempotency_key,
                    manual_stage_approval=manual_stage_approval,
                    allow_repeat=bool(allow_repeat),
                    mail_account_id=int(body["mail_account_id"]) if body.get("mail_account_id") is not None else None,
                )
                self.app.queue.wake()
                self._json(202, {"ok": True, "queued": results})
            elif parsed.path == "/api/mail/cross-provider-retry/preview":
                original_attempt_id = (
                    int(body["original_attempt_id"])
                    if body.get("original_attempt_id") is not None else None
                )
                self._json(200, self.app.service.cross_provider_retry_preview(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 0)),
                    original_job_id=int(body.get("original_job_id", 0)),
                    original_message_id=int(body.get("original_message_id", 0)),
                    target_mail_account_id=int(body.get("mail_account_id", 0)),
                    original_attempt_id=original_attempt_id,
                ))
            elif parsed.path == "/api/mail/cross-provider-retry/apply":
                original_attempt_id = (
                    int(body["original_attempt_id"])
                    if body.get("original_attempt_id") is not None else None
                )
                result = self.app.service.apply_cross_provider_retry(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 0)),
                    original_job_id=int(body.get("original_job_id", 0)),
                    original_message_id=int(body.get("original_message_id", 0)),
                    target_mail_account_id=int(body.get("mail_account_id", 0)),
                    original_attempt_id=original_attempt_id,
                    idempotency_key=str(body.get("idempotency_key") or ""),
                    selection_fingerprint=str(body.get("selection_fingerprint") or ""),
                    operator_confirmed=body.get("operator_confirmed") is True,
                    confirmation=body.get("confirmation") if isinstance(body.get("confirmation"), dict) else None,
                )
                self.app.queue.wake()
                self._json(201, result)
            elif parsed.path.startswith("/api/mail/campaigns/"):
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) != 5:
                    self._json(404, {"error": "Действие campaign не найдено."})
                    return
                try:
                    campaign_id = int(parts[3])
                except ValueError:
                    self._json(400, {"error": "Некорректный идентификатор campaign."})
                    return
                action = parts[4]
                if action == "continuation-dry-run":
                    target_account_id = int(body.get("mail_account_id", 0))
                    self._json(200, self.app.service.continuation_dry_run(
                        user_id=session["user_id"], workspace_id=session["workspace_id"],
                        campaign_id=campaign_id, mail_account_id=target_account_id,
                        limit=int(body["limit"]) if body.get("limit") is not None else None,
                    ))
                    return
                if action == "continuation-apply":
                    target_account_id = int(body.get("mail_account_id", 0))
                    result = self.app.service.apply_campaign_continuation(
                        user_id=session["user_id"], workspace_id=session["workspace_id"],
                        campaign_id=campaign_id, mail_account_id=target_account_id,
                        limit=int(body.get("limit", 0)),
                        idempotency_key=str(body.get("idempotency_key") or ""),
                        selection_fingerprint=str(body.get("selection_fingerprint") or ""),
                        operator_confirmed=body.get("operator_confirmed") is True,
                        selected_targets=body.get("selected_targets") if isinstance(body.get("selected_targets"), list) else None,
                    )
                    self._json(201, result)
                    return
                if action == "pause":
                    result = self.app.repository.pause_campaign(
                        session["workspace_id"], campaign_id, str(body.get("reason") or "manual_pause"),
                    )
                elif action == "resume":
                    result = self.app.repository.resume_campaign(
                        session["workspace_id"], campaign_id, rollout=self.app.service.rollout_settings,
                    )
                    self.app.queue.wake()
                elif action == "stop":
                    result = self.app.repository.stop_campaign(session["workspace_id"], campaign_id)
                else:
                    self._json(404, {"error": "Действие campaign не найдено."})
                    return
                if not result:
                    self._json(404, {"error": "Campaign не найдена."})
                    return
                self._json(200, {"ok": True, **result})
            elif parsed.path.startswith("/api/mail/messages/") and parsed.path.endswith("/verify"):
                message_id = int(parsed.path.split("/")[4])
                self._json(200, self.app.service.verify_delivery(
                    user_id=session["user_id"], workspace_id=session["workspace_id"], message_id=message_id,
                ))
            elif parsed.path.startswith("/api/mail/messages/") and parsed.path.endswith("/resend"):
                message_id = int(parsed.path.split("/")[4])
                result = self.app.service.resend_delivery_unknown(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    message_id=message_id, confirmed=bool(body.get("confirmed", False)),
                )
                if result.get("resent"):
                    self.app.queue.wake()
                self._json(200, result)
            elif parsed.path.startswith("/api/mail/messages/") and parsed.path.endswith("/resolve"):
                message_id = int(parsed.path.split("/")[4])
                self._json(200, self.app.repository.resolve_delivery_unknown(
                    session["workspace_id"], session["user_id"], message_id, str(body.get("comment", "")),
                ))
            elif parsed.path == "/api/mail/inbox/manual-link":
                supplier_value = body.get("supplier_id")
                supplier_id = int(supplier_value) if supplier_value not in (None, "") else None
                self._json(200, self.app.repository.manually_link_inbox_message(
                    session["workspace_id"], session["user_id"],
                    int(body.get("inbox_message_id", 0)),
                    int(body.get("request_id", 0)),
                    supplier_id,
                    confirmed=body.get("confirmed") is True,
                ))
            elif parsed.path == "/api/mail/inbox/manual-unlink":
                self._json(200, self.app.repository.unlink_manual_inbox_message(
                    session["workspace_id"], session["user_id"], int(body.get("inbox_message_id", 0)),
                ))
            elif parsed.path == "/api/mail/inbox/attach":
                # Ручная привязка письма к заявке — для случая, когда поставщик
                # написал новое письмо, а не ответил на наше: заголовков ответа
                # нет, тема своя, автоматическое сопоставление не срабатывает.
                self._json(200, self.app.repository.attach_inbox_message(
                    session["workspace_id"], session["user_id"],
                    int(body.get("inbox_message_id", 0)),
                    int(body.get("request_id", 0)),
                    int(body.get("supplier_id", 0)),
                ))
            elif parsed.path == "/api/mail/inbox/reply":
                result = self.app.service.reply_to_inbox(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    inbox_message_id=int(body.get("inbox_message_id", 0)),
                    subject=body.get("subject", ""), body=body.get("body"),
                    body_text=body.get("body_text"), body_html=body.get("body_html"),
                    attachments=body.get("attachments") or [],
                )
                self._json(200, {"ok": True, **result})
            elif parsed.path == "/api/requests":
                positions = body.get("positions") or []
                if isinstance(positions, str):
                    positions = [{"name": line.split("|", 1)[0].strip(), "quantity": line.split("|", 1)[1].strip() if "|" in line else ""} for line in positions.splitlines() if line.strip()]
                request_id = self.app.repository.create_request(
                    session["workspace_id"], user_id=session["user_id"], name=body.get("name", ""),
                    description=body.get("description", ""), positions=positions,
                    sender_name=body.get("sender_name", session.get("display_name", "")), company_name=body.get("company_name", ""),
                    deadline=body.get("deadline", ""), search_depth=body.get("search_depth", 1),
                )
                self._json(201, {"ok": True, "request_id": request_id})
            elif parsed.path == "/api/blacklist":
                supplier_id = body.get("supplier_id")
                self._json(201, {"ok": True, "entry_id": self.app.repository.add_blacklist(
                    session["workspace_id"], session["user_id"], external_key=body.get("external_key", ""),
                    company_name=body.get("company_name", ""), reason=body.get("reason", ""),
                    supplier_id=int(supplier_id) if supplier_id else None,
                )})
            elif parsed.path == "/api/mail/suppression":
                supplier_id = body.get("supplier_id")
                email = str(body.get("email") or "").strip().lower()
                external_key = str(body.get("external_key") or "").strip().lower()
                if not email and not external_key:
                    raise ValueError("Укажите external_key или email для suppression.")
                reason = body.get("reason", "do_not_contact")
                if email:
                    entry_id = self.app.repository.add_email_suppression(
                        session["workspace_id"], session["user_id"], email=email,
                        company_name=body.get("company_name", ""),
                        reason=reason,
                        supplier_id=int(supplier_id) if supplier_id else None,
                    )
                else:
                    entry_id = self.app.repository.add_blacklist(
                        session["workspace_id"], session["user_id"], external_key=external_key,
                        company_name=body.get("company_name", ""), reason=reason,
                        supplier_id=int(supplier_id) if supplier_id else None,
                    )
                self._json(201, {"ok": True, "entry_id": entry_id})
            elif parsed.path == "/api/irrelevant":
                request_id = int(body.get("request_id", 1043))
                external_key = str(body.get("external_key", "")).strip().lower()
                supplier = next((item for item in self.app.repository.list_suppliers(session["workspace_id"], None, include_excluded=True) if item["external_key"] == external_key), None)
                if not supplier:
                    raise ValueError("Поставщик не найден.")
                self.app.repository.set_irrelevant(session["workspace_id"], session["user_id"], request_id, supplier["id"], bool(body.get("value", True)))
                self._json(200, {"ok": True})
            elif parsed.path.startswith("/api/blacklist/") and parsed.path.endswith("/restore"):
                entry_id = int(parsed.path.split("/")[3])
                self.app.repository.restore_blacklist(session["workspace_id"], session["user_id"], entry_id)
                self._json(200, {"ok": True})
            elif parsed.path.startswith("/api/global-suppliers/"):
                self._global_supplier_action(session, parsed.path, body)
            elif parsed.path.startswith("/api/requests/"):
                self._request_action(session, parsed.path, body)
            else:
                self._json(404, {"error": "Маршрут не найден."})
        except DeliverabilityPreflightError as exc:
            self._json(409, {"error": str(exc), "preflight": exc.result})
        except PermissionError as exc:
            self._json(403, {"error": str(exc)})
        except (ValueError, TypeError, ProviderError, EncryptionConfigError) as exc:
            message = exc.message if isinstance(exc, ProviderError) else str(exc)
            self._json(400 if not isinstance(exc, ProviderError) or not exc.transient else 503, {"error": message})
        except Exception:
            self._json(500, {"error": "Внутренняя ошибка сервера. Попробуйте ещё раз."})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/mail/accounts/"):
            session = self._require_session()
            if not session or not self._require_csrf(session):
                return
            if not self.app.allow_api_request(self._session_token()):
                self._json(429, {"error": "Слишком много запросов. Попробуйте через минуту."})
                return
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 4:
                self._json(404, {"error": "Маршрут почтового аккаунта не найден."})
                return
            try:
                account_id = int(parts[3])
                self.app.service.disconnect(session["user_id"], session["workspace_id"], mail_account_id=account_id)
            except (ValueError, ProviderError) as exc:
                self._json(400, {"error": exc.message if isinstance(exc, ProviderError) else str(exc)})
                return
            self._json(200, {"ok": True})
            return
        if not parsed.path.startswith("/api/requests/"):
            self._json(404, {"error": "Маршрут не найден."})
            return
        session = self._require_session()
        if not session or not self._require_csrf(session):
            return
        if not self.app.allow_api_request(self._session_token()):
            self._json(429, {"error": "Слишком много запросов. Попробуйте через минуту."})
            return
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 3:
            self._json(404, {"error": "Маршрут заявки не найден."})
            return
        try:
            request_id = int(parts[2])
        except ValueError:
            self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        try:
            self.app.repository.delete_request(session["workspace_id"], request_id, session["user_id"])
        except DeliveryResolutionRequiredError as exc:
            self._json(409, {"error": str(exc)})
            return
        except ValueError:
            self._json(404, {"error": "Заявка не найдена."})
            return
        except Exception:
            self._json(500, {"error": "Не удалось удалить заявку. Попробуйте ещё раз."})
            return
        self._json(200, {"ok": True})

    def _login(self, body: dict) -> None:
        if not self.app.config.app_user_email or not self.app.config.app_user_password:
            self._json(503, {"error": "Локальная учётная запись не настроена. Заполните APP_USER_EMAIL и APP_USER_PASSWORD в .env."})
            return
        user = self.app.repository.authenticate(str(body.get("email", "")), str(body.get("password", "")))
        if not user:
            self._json(401, {"error": "Неверный email или пароль."})
            return
        session_token, csrf_token = self.app.repository.create_session(user["id"], user["workspace_id"])
        self._json(
            200,
            {"authenticated": True, "csrf_token": csrf_token, "user": self._public_user(user)},
            headers={"Set-Cookie": self._session_cookie_header(session_token)},
        )

    def _serve_app_shell(self) -> None:
        body = (FRONTEND_DIST / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # Do not let a browser cache the shell across deploys; hashed asset URLs inside it change.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_me(self) -> None:
        session = self.app.repository.get_session(self._session_token())
        if not session or not self._keep_session_alive(session):
            self._json(200, {"authenticated": False})
            return
        self._json(200, {"authenticated": True, "csrf_token": self._csrf_token_for_session(session), "user": self._public_user(session)})

    def _pkce_pair(self) -> tuple[str, str]:
        code_verifier = new_token(48)
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        return code_verifier, code_challenge

    def _auth_yandex_start(self) -> None:
        """Begin 'Sign in with Yandex'. No existing session is required or possible yet."""
        try:
            provider = yandex_provider_factory("yandex")
            state = new_token(32)
            code_verifier, code_challenge = self._pkce_pair()
            self.app.repository.create_oauth_login_state(state=state, code_verifier=code_verifier, redirect_uri=self.app.config.redirect_uri)
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", provider.authorization_url(redirect_uri=self.app.config.redirect_uri, state=state, code_challenge=code_challenge))
            self.send_header(
                "Set-Cookie",
                f"oauth_login_state={state}; Path=/oauth/yandex/callback; Max-Age=600; HttpOnly; SameSite=Lax"
                + ("; Secure" if self.app.config.session_cookie_secure else ""),
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        except ProviderError:
            self._redirect("/login?error=not_configured")

    def _oauth_start(self) -> None:
        session = self._require_session()
        if not session:
            return
        try:
            provider = yandex_provider_factory("yandex")
            code_verifier, code_challenge = self._pkce_pair()
            state = new_token(32)
            self.app.repository.create_oauth_state(
                state=state, session_token=self._session_token(), user_id=session["user_id"], workspace_id=session["workspace_id"],
                code_verifier=code_verifier, redirect_uri=self.app.config.redirect_uri,
            )
            self._redirect(provider.authorization_url(redirect_uri=self.app.config.redirect_uri, state=state, code_challenge=code_challenge))
        except ProviderError:
            self._redirect("/settings?mail_error=not_configured")

    def _oauth_callback(self, query: dict[str, list[str]]) -> None:
        state = (query.get("state") or [""])[0]
        session_token = self._session_token()
        connect_state = self.app.repository.consume_oauth_state(state, session_token) if state and session_token else None
        if connect_state:
            self._finish_mail_connect_callback(connect_state, query)
            return
        login_cookie_state = self._cookie("oauth_login_state")
        login_state = self.app.repository.consume_oauth_login_state(state) if state and login_cookie_state and login_cookie_state == state else None
        if login_state:
            self._finish_login_callback(login_state, query)
            return
        self._redirect("/login?error=invalid_state")

    def _finish_mail_connect_callback(self, callback_state: dict, query: dict[str, list[str]]) -> None:
        if query.get("error"):
            self._redirect("/settings?mail_error=access_denied")
            return
        code = (query.get("code") or [""])[0]
        if not code:
            self._redirect("/settings?mail_error=missing_code")
            return
        try:
            provider = yandex_provider_factory("yandex")
            tokens = provider.exchange_code(code, redirect_uri=callback_state["redirect_uri"], code_verifier=callback_state["code_verifier"])
            account = provider.get_account(tokens.access_token)
            self.app.service.save_oauth_tokens(
                user_id=callback_state["user_id"], workspace_id=callback_state["workspace_id"], token_set=tokens, email=account.email
            )
            self._redirect("/settings?connected=true")
        except (ProviderError, ValueError, EncryptionConfigError):
            self._redirect("/settings?mail_error=connection_failed")

    def _finish_login_callback(self, login_state: dict, query: dict[str, list[str]]) -> None:
        clear_cookie = "oauth_login_state=; Path=/oauth/yandex/callback; Max-Age=0; HttpOnly; SameSite=Lax"
        if query.get("error"):
            self._redirect_with_cookie("/login?error=access_denied", clear_cookie)
            return
        code = (query.get("code") or [""])[0]
        if not code:
            self._redirect_with_cookie("/login?error=missing_code", clear_cookie)
            return
        try:
            provider = yandex_provider_factory("yandex")
            tokens = provider.exchange_code(code, redirect_uri=login_state["redirect_uri"], code_verifier=login_state["code_verifier"])
            account = provider.get_account(tokens.access_token)
            user = self.app.repository.get_or_create_oauth_user(account.email, account.display_name)
            session_token, _csrf_token = self.app.repository.create_session(user["id"], user["workspace_id"])
            try:
                # A bonus of logging in with Yandex: the same OAuth grant connects the mailbox.
                # Login must still succeed even if encryption isn't configured for mail storage.
                self.app.service.save_oauth_tokens(user_id=user["id"], workspace_id=user["workspace_id"], token_set=tokens, email=account.email)
            except (ProviderError, ValueError, EncryptionConfigError):
                pass
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie",
                self._session_cookie_header(session_token),
            )
            self.send_header("Set-Cookie", clear_cookie)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        except (ProviderError, ValueError, EncryptionConfigError):
            self._redirect_with_cookie("/login?error=connection_failed", clear_cookie)

    def _thread_messages(self, session: dict, query: dict[str, list[str]]) -> None:
        try:
            request_id = int((query.get("request_id") or [1043])[0])
            supplier_id = int((query.get("supplier_id") or [0])[0])
        except ValueError:
            self._json(400, {"error": "Некорректные идентификаторы переписки."})
            return
        if supplier_id <= 0:
            self._json(200, {"items": self.app.repository.list_threads(session["workspace_id"])})
            return
        self._json(200, {"items": self.app.repository.thread_messages(session["workspace_id"], request_id, supplier_id)})

    def _request_route(self, session: dict, path: str, query: dict[str, list[str]]) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            request_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        if len(parts) == 3:
            request = self.app.repository.get_request(session["workspace_id"], request_id)
            if not request:
                self._json(404, {"error": "Заявка не найдена."})
                return
            self._json(200, {"request": request, "positions": self.app.repository.request_positions(session["workspace_id"], request_id), "items": self.app.repository.list_suppliers(session["workspace_id"], request_id)})
            return
        if len(parts) == 4 and parts[3] == "suppliers":
            self._json(200, {"items": self.app.repository.list_suppliers(session["workspace_id"], request_id)})
            return
        self._json(404, {"error": "Маршрут заявки не найден."})

    def _request_action(self, session: dict, path: str, body: dict) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            request_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "inn":
            try:
                supplier_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор поставщика."})
                return
            result = self.app.update_supplier_inn(
                session["workspace_id"], session["user_id"], request_id, supplier_id,
                str(body.get("inn", "")),
            )
            self._json(200, result)
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "rating":
            try:
                supplier_id = int(parts[4])
                rating = int(body.get("rating", 0))
            except (ValueError, TypeError):
                self._json(400, {"error": "Некорректная оценка."})
                return
            self.app.repository.set_deal_rating(session["workspace_id"], session["user_id"], request_id, supplier_id, rating)
            self._json(200, {"ok": True})
            return
        if len(parts) == 3:
            self.app.repository.update_request(
                session["workspace_id"], request_id, session["user_id"],
                name=body.get("name"), description=body.get("description"), deadline=body.get("deadline"),
            )
            self._json(200, {"ok": True})
            return
        if len(parts) == 4 and parts[3] == "search":
            result = self.app.repository.start_request_search(session["workspace_id"], request_id, session["user_id"])
            if request_id == 1043:
                # The existing page is a completed, enriched fixture; keep it available for the current workspace.
                self.app.repository.complete_request_search(session["workspace_id"], request_id)
                result["status"] = "completed"
                result["search_progress"] = result["search_total"]
            self._json(202, {"ok": True, **result})
            return
        if len(parts) == 5 and parts[3] == "search" and parts[4] == "step":
            result = self.app.process_search_step(session["workspace_id"], request_id)
            self._json(200, {"ok": True, **result})
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "irrelevant":
            try:
                supplier_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор поставщика."})
                return
            self.app.repository.set_irrelevant(session["workspace_id"], session["user_id"], request_id, supplier_id, True)
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "Действие заявки не найдено."})

    def _global_supplier_route(self, session: dict, path: str) -> None:
        """GET /api/global-suppliers/<id> — card detail (history + issues)."""
        parts = [part for part in path.split("/") if part]
        try:
            global_supplier_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор поставщика."})
            return
        if len(parts) != 3:
            self._json(404, {"error": "Маршрут не найден."})
            return
        detail = self.app.repository.global_supplier_detail(session["workspace_id"], global_supplier_id)
        if not detail:
            self._json(404, {"error": "Поставщик не найден."})
            return
        self._json(200, detail)

    def _global_supplier_action(self, session: dict, path: str, body: dict) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            global_supplier_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор поставщика."})
            return
        if len(parts) == 3:
            note = body.get("note")
            self.app.repository.update_global_supplier(session["workspace_id"], global_supplier_id, note=str(note) if note is not None else None)
            self._json(200, {"ok": True})
            return
        if len(parts) == 4 and parts[3] == "relationship":
            try:
                self.app.repository.set_global_supplier_relationship(
                    session["workspace_id"], session["user_id"], global_supplier_id,
                    str(body.get("status", "none")), reason=str(body.get("reason", "")),
                )
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"ok": True})
            return
        if len(parts) == 4 and parts[3] == "issues":
            reason = str(body.get("reason", "other"))
            issue_id = self.app.repository.add_global_supplier_issue(
                session["workspace_id"], session["user_id"], global_supplier_id,
                reason=reason, comment=str(body.get("comment", "")),
                correct_inn=str(body.get("correct_inn", "")), source="manual",
            )
            if bool(body.get("blacklist")):
                # Store the issue's own reason code (not a translated label) — the
                # frontend already has issueReasonLabels for display, and reusing it
                # keeps one source of truth for "what does this code mean".
                self.app.repository.set_global_supplier_relationship(
                    session["workspace_id"], session["user_id"], global_supplier_id, "blacklisted", reason=reason,
                )
            self._json(201, {"ok": True, "issue_id": issue_id})
            return
        self._json(404, {"error": "Действие не найдено."})

    def _require_session(self) -> dict | None:
        session = self.app.repository.get_session(self._session_token())
        if not session or not self._keep_session_alive(session):
            self._json(401, {"error": "Требуется вход в личный кабинет."})
            return None
        return session

    def _keep_session_alive(self, session: dict) -> bool:
        """Extend an active browser session and refresh its persistent cookie."""
        token = self._session_token()
        expires_at = self.app.repository.touch_session(
            token,
            lifetime_seconds=self.app.config.session_lifetime_seconds,
        )
        if not expires_at:
            return False
        session["expires_at"] = expires_at
        self._session_refresh_cookie = self._session_cookie_header(token)
        return True

    def _session_cookie_header(self, token: str, *, max_age: int | None = None) -> str:
        age = max_age if max_age is not None else self.app.config.session_lifetime_seconds
        cookie = f"session_id={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax"
        if self.app.config.session_cookie_secure:
            cookie += "; Secure"
        return cookie

    def _require_csrf(self, session: dict) -> bool:
        header = self.headers.get("X-CSRF-Token", "")
        if not header or token_hash(header) != session["csrf_hash"]:
            self._json(403, {"error": "CSRF-проверка не пройдена. Обновите страницу."})
            return False
        return True

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Некорректная длина запроса."})
            return None
        # 20 MiB of validated binary attachments expand to about 26.7 MiB in
        # base64. Keep a narrow JSON allowance above that real service limit.
        if length > 30 * 1024 * 1024:
            self._json(413, {"error": "Запрос слишком большой."})
            return None
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "Ожидался корректный JSON."})
            return None
        if not isinstance(data, dict):
            self._json(400, {"error": "Ожидался JSON-объект."})
            return None
        return data

    def _cookie(self, name: str) -> str:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        return cookie.get(name).value if cookie.get(name) else ""

    def _session_token(self) -> str:
        return self._cookie("session_id")

    def _csrf_token_for_session(self, session: dict) -> str:
        # The token is derived from the opaque session cookie and is never persisted in plaintext.
        return token_hash(self._session_token() + ":csrf")

    def _public_user(self, user: dict) -> dict:
        return {"email": user["email"], "display_name": user["display_name"], "workspace_name": user["workspace_name"]}

    def _json(self, status: int, payload: dict, *, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        response_headers = dict(headers or {})
        if "Set-Cookie" not in response_headers:
            refreshed_cookie = getattr(self, "_session_refresh_cookie", None)
            if refreshed_cookie:
                response_headers["Set-Cookie"] = refreshed_cookie
        self.send_response(status)
        for name, value in response_headers.items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        refreshed_cookie = getattr(self, "_session_refresh_cookie", None)
        if refreshed_cookie:
            self.send_header("Set-Cookie", refreshed_cookie)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _redirect_with_cookie(self, location: str, cookie: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", cookie)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


class SupplierApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.repository = MailRepository(config.db_path)
        seeded_user = self.repository.seed_user(config.app_user_email, config.app_user_password)
        if seeded_user:
            try:
                self.repository.seed_fixture_catalog(seeded_user["workspace_id"], load_fixture_data())
            except (ValueError, KeyError, json.JSONDecodeError):
                # The static page remains usable even if a local fixture was edited incorrectly.
                pass
            # Idempotent: links any supplier that already has an ИНН (fixture, earlier
            # enrichment runs) to its global card. See Documents/28-8/suppliers-screen.md.
            self.repository.backfill_global_suppliers(seeded_user["workspace_id"])
        self.runtime = RuntimeSession.start(
            environment=config.environment,
            db_path=config.db_path,
            canonical_db_path=config.canonical_db_path,
            repository=self.repository,
            root=ROOT,
        )
        self.service = MailService(
            self.repository,
            yandex_provider_factory,
            config.encryption_key,
            daily_limit=config.daily_limit,
            pacing_settings=config.pacing,
            rollout_settings=config.rollout,
            campaign_max_recipients=config.campaign_max_recipients,
            runtime=self.runtime,
        )
        self.queue = MailQueue(
            self.repository,
            self.service,
            concurrency=config.queue_concurrency,
            max_retries=config.max_retries,
            pacing=config.pacing,
        )
        self.rate_lock = threading.Lock()
        self.rate_events: dict[str, list[float]] = {}
        # Фоновая синхронизация входящих. Без неё отбойник (письмо не
        # доставлено) попадал в систему, только когда пользователь сам нажимал
        # «Синхронизировать входящие» на «Настройках»: до этого поставщик
        # оставался в статусе «Отправлен», хотя письмо уже вернулось. Отказ
        # приходит через минуты после отправки, поэтому 5 минут по умолчанию —
        # достаточно часто, чтобы статус был правдой, и достаточно редко, чтобы
        # не долбить IMAP. 0 отключает фоновый опрос.
        self.mail_sync_interval = max(0, int(os.getenv("MAIL_SYNC_INTERVAL_SECONDS", "300") or 0))
        self.mail_sync_stop = threading.Event()
        self.mail_sync_thread: threading.Thread | None = None
        # Синхронизация при открытии экрана переписки, не чаще раза в N секунд
        # (см. maybe_sync_incoming). 0 отключает — тогда работает только
        # фоновый поток выше.
        self.mail_sync_on_view_seconds = max(0, int(os.getenv("MAIL_SYNC_ON_VIEW_SECONDS", "45") or 0))
        # Сколько запрос готов подождать эту синхронизацию, прежде чем отдать
        # список как есть. Небольшое значение: при здоровом IMAP хватает, при
        # недоступном экран не ждёт.
        self.mail_sync_wait_seconds = max(0.0, float(os.getenv("MAIL_SYNC_WAIT_SECONDS", "4") or 0))
        self.mail_sync_view_lock = threading.Lock()
        self.mail_sync_view_at: dict[tuple[int, int], float] = {}
        # Локальный сервер не должен зависеть от открытой вкладки: незавершённые
        # crawl/registry/web/finance jobs продолжаются в фоне. На Vercel поток
        # бессмысленен (invocation замораживается), там остаётся UI heartbeat.
        retry_default = 0 if os.getenv("VERCEL") else 15
        self.enrichment_retry_interval = _bounded_int_env(
            "ENRICHMENT_RETRY_INTERVAL_SECONDS", retry_default, 0, 3600,
        )
        self.enrichment_retry_stop = threading.Event()
        self.enrichment_retry_thread: threading.Thread | None = None
        # LLM fallback is the only paid, uncapped step in enrichment. A process-lifetime,
        # day-scoped counter protects the process-local LLM budget; production
        # search itself is coordinated by the durable job lease in Postgres.
        self.llm_budget_rub = float(os.getenv("LLM_DAILY_BUDGET_RUB", "50") or 0)
        self.llm_spent_rub = 0.0
        self.llm_spent_day = time.strftime("%Y-%m-%d")

    def maybe_sync_incoming(self, user_id: int, workspace_id: int) -> None:
        """Забрать новую почту при открытии экрана переписки — но не чаще, чем раз в N секунд.

        Смысл в том, чтобы обновления страницы (F5) хватало для получения новых
        писем: раньше почта появлялась только после ручного нажатия
        «Синхронизировать входящие» в «Настройках».

        Синхронизация идёт в отдельном потоке, а запрос ждёт её не дольше
        MAIL_SYNC_WAIT_SECONDS. Так получаются оба нужных свойства: при
        здоровом IMAP письма успевают прийти к этому же обновлению страницы, а
        при недоступном (Яндекс отвечает таймаутом секунд за двадцать) экран
        всё равно открывается сразу — сама синхронизация при этом продолжается
        в фоне и её результат виден при следующем обновлении.

        Ограничение по частоте обязательно: без него каждое обновление
        страницы открывало бы новое IMAP-соединение, а частые подключения
        Яндекс начинает отклонять.

        Любая ошибка синхронизации проглатывается: не показать новое письмо
        неприятно, но уронить весь экран переписки из-за недоступного IMAP —
        заметно хуже.
        """
        if self.mail_sync_on_view_seconds <= 0:
            return
        key = (user_id, workspace_id)
        now = time.monotonic()
        with self.mail_sync_view_lock:
            last = self.mail_sync_view_at.get(key, 0.0)
            if now - last < self.mail_sync_on_view_seconds:
                return
            self.mail_sync_view_at[key] = now

        def run() -> None:
            try:
                self.service.sync_all_incoming(user_id, workspace_id)
            except Exception as exc:  # noqa: BLE001 — экран переписки должен открыться в любом случае
                log.info("Синхронизация при открытии переписки не выполнена: %s", exc)

        worker = threading.Thread(target=run, name="mail-sync-on-view", daemon=True)
        worker.start()
        worker.join(timeout=self.mail_sync_wait_seconds)

    def update_supplier_inn(
        self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, raw_inn: str,
    ) -> dict[str, object]:
        """Save a user-entered ИНН and immediately enrich it through Checko."""
        inn = "".join(ch for ch in str(raw_inn or "") if ch.isdigit())
        if not validate_inn_checksum(inn):
            raise ValueError("Проверьте ИНН: нужно корректное 10- или 12-значное число.")

        context = self.repository.request_supplier(workspace_id, request_id, supplier_id)
        if not context:
            raise ValueError("Поставщик не найден в этой заявке.")
        saved = self.repository.set_supplier_manual_inn(
            workspace_id, user_id, request_id, supplier_id, inn,
        )
        checko_status = "unavailable"
        checko_error = ""
        company = None

        if not os.getenv("CHECKO_KEY"):
            checko_error = "CHECKO_KEY не настроен. ИНН сохранён, данные можно обновить позже."
        else:
            try:
                checko = CheckoClient()
                company = checko.lookup(inn)
                if company.found:
                    self.repository.apply_supplier_enrichment(
                        workspace_id, str(context["host"]),
                        email=(company.emails[0] if company.emails else ""),
                        inn=inn,
                        phone=(company.phones[0] if company.phones else ""),
                        region=company.region,
                        role=company.role,
                        company_name=(company.name_full or company.name),
                        registry_ogrn=company.ogrn,
                        registry_status=company.status,
                        registry_active=company.active,
                        registry_registered_at=company.registered,
                        risks=company.risks,
                    )
                    finance = checko.finances(inn)
                    if finance.found:
                        self.repository.apply_supplier_enrichment(
                            workspace_id, str(context["host"]), inn=inn,
                            finance_report_year=finance.report_year,
                            finance_revenue=finance.revenue,
                            finance_profit=finance.profit,
                            finance_history=finance.history,
                        )
                    checko_status = "loaded"
                    checko_error = "" if finance.found else (finance.error or "Финансы пока недоступны.")
                else:
                    checko_status = "not_found" if not company.error or "не найден" in company.error.lower() else "unavailable"
                    checko_error = company.error or "Компания по этому ИНН не найдена в Checko."
            except (ValueError, TypeError) as exc:
                checko_error = str(exc)

        evidence = [{
            "field_name": "inn",
            "field_value": inn,
            "source_type": "manual",
            "source_url": "",
            "strength": "strong",
            "score": 100,
            "decision": "accepted",
            "details": {"entered_by": "user", "checko_status": checko_status},
        }]
        if company is not None and company.found:
            evidence.append({
                "field_name": "inn",
                "field_value": inn,
                "source_type": "checko",
                "source_url": f"https://checko.ru/{'entrepreneur' if len(company.ogrn) == 15 else 'company'}/{company.ogrn}" if company.ogrn else "",
                "strength": "strong",
                "score": 100,
                "decision": "confirmed",
                "details": {"name": company.name_full or company.name, "ogrn": company.ogrn},
            })
        self.repository.record_supplier_evidence(workspace_id, str(context["host"]), evidence)
        return {
            "ok": True,
            "inn": inn,
            "inn_source": "manual",
            "checko_status": checko_status,
            "checko_error": checko_error,
            "global_supplier_id": saved["global_supplier_id"],
        }

    def _run_mail_sync_loop(self) -> None:
        """Периодически забирать входящие для всех подключённых ящиков.

        Ошибка одного прохода (сеть, истёкший токен) не должна останавливать
        цикл: следующий заход попробует снова. Пишем в лог только осмысленные
        события, чтобы фоновая задача не засоряла вывод каждые 5 минут.
        """
        while not self.mail_sync_stop.wait(self.mail_sync_interval):
            try:
                accounts = self.repository.list_active_mail_accounts()
            except Exception as exc:  # noqa: BLE001 — фоновая задача не падает
                log.warning("Фоновая синхронизация: не удалось получить список ящиков: %s", exc)
                continue
            for account in accounts:
                try:
                    result = self.service.sync_incoming(
                        account["user_id"], account["workspace_id"],
                        mail_account_id=int(account["id"]),
                    )
                    if result.get("imported") or result.get("unmatched"):
                        log.info(
                            "Фоновая синхронизация: импортировано %s, без привязки %s",
                            result.get("imported", 0), result.get("unmatched", 0),
                        )
                except Exception as exc:  # noqa: BLE001 — один ящик не ломает остальные
                    log.info("Фоновая синхронизация ящика %s: %s", account.get("email", "?"), exc)

    def _run_enrichment_retry_loop(self) -> None:
        """Локально продолжать только due-ступени, не удерживая заявку searching."""
        while not self.enrichment_retry_stop.wait(self.enrichment_retry_interval):
            try:
                workspace_ids = self.repository.enrichment_workspace_ids()
            except Exception as exc:  # noqa: BLE001 — фоновая задача не роняет сервер
                log.warning("Очередь обогащения: не удалось прочитать due jobs: %s", exc)
                continue
            for workspace_id in workspace_ids:
                if self.enrichment_retry_stop.is_set():
                    return
                try:
                    result = self.process_enrichment_retry_step(workspace_id)
                    if result.get("processed"):
                        log.info("Фоновое обогащение workspace %s: %s", workspace_id, result)
                except Exception as exc:  # noqa: BLE001 — lease сохранит повтор
                    log.warning("Фоновое обогащение workspace %s: %s", workspace_id, exc)

    def process_search_step(self, workspace_id: int, request_id: int) -> dict[str, object]:
        """Process one durable search step and persist the cursor before returning.

        This intentionally does not start a daemon thread. A Vercel function may
        be frozen as soon as its HTTP response is sent, so every unit of work
        must finish inside the request that invoked it and leave a resumable
        cursor in Postgres. The frontend calls this endpoint while the request
        is open; a 120-second lease makes an interrupted step retryable.
        """
        job = self.repository.claim_request_search_job(workspace_id, request_id)
        if not job:
            request = self.repository.get_request(workspace_id, request_id)
            return {"processed": False, "status": request["status"] if request else "not_found"}
        try:
            if job["stage"] == "serp":
                return self._process_serp_step(job)
            if job["stage"] == "enrich":
                return self._process_enrich_step(job)
            raise RuntimeError(f"Неизвестный этап поиска: {job['stage']}")
        except Exception as exc:  # noqa: BLE001 — state is surfaced in the request card
            message = str(exc)[:500] or "Поиск завершился с неизвестной ошибкой."
            self.repository.fail_request_search_job(job, message)
            return {"processed": True, "status": "error", "error": message}

    def _process_serp_step(self, job: dict[str, object]) -> dict[str, object]:
        workspace_id = int(job["workspace_id"])
        request_id = int(job["request_id"])
        positions = self.repository.request_positions(workspace_id, request_id)
        position_index = int(job["position_index"] or 0)
        hosts = self._job_hosts(job)

        if position_index >= len(positions):
            if hosts:
                self.repository.advance_request_search_job(
                    job, stage="enrich", position_index=position_index,
                    hosts=hosts, enrich_index=0,
                )
                return {"processed": True, "status": "searching", "stage": "enrich", "search_progress": position_index, "search_total": len(positions)}
            completed = self.repository.finish_request_search_job(job)
            return {"processed": True, "status": "completed" if completed else "searching", "search_progress": len(positions), "search_total": len(positions)}

        user = os.getenv("XMLRIVER_USER", "")
        key = os.getenv("XMLRIVER_KEY", "")
        if not user or not key:
            raise RuntimeError("Поиск не настроен: заполните XMLRIVER_USER и XMLRIVER_KEY в .env.")
        # Keep one serverless step comfortably below Vercel's 60-second limit.
        # A failed request remains leased and is retried by the next step, so a
        # short bounded attempt is safer than waiting for 3 × 45 seconds.
        serp_timeout = max(5.0, float(os.getenv("XMLRIVER_STEP_TIMEOUT_SECONDS", "12") or 12))
        serp_retries = max(1, min(2, int(os.getenv("XMLRIVER_STEP_MAX_RETRIES", "2") or 2)))
        client = XmlRiverClient(user, key, engine="yandex", timeout=serp_timeout, max_retries=serp_retries)
        # New requests persist their own depth. Legacy requests without an
        # option keep the environment fallback for compatibility.
        serp_pages = self.repository.request_search_depth(workspace_id, request_id)
        if serp_pages is None:
            serp_pages = max(1, int(os.getenv("SERP_PAGES", "1") or 1))
        # Empty/unset means no cap. A cap remains an explicit cost/time control.
        cap_raw = (os.getenv("SERP_RESULTS_PER_POSITION") or "").strip()
        results_cap = int(cap_raw) if cap_raw else None
        stop_domains = set(read_lines(ROOT / "stop_domains.txt")) if (ROOT / "stop_domains.txt").exists() else set()
        position = positions[position_index]
        collector = SerpCollector(client, pages=serp_pages, suffix="купить", delay=1.0, dedup="host", exclude_domains=stop_domains)
        rows = collector.collect_one(position["name"])
        selected = rows if results_cap is None else rows[:results_cap]
        for row in selected:
            host = str(row.host).strip().lower()
            self.repository.upsert_search_result(
                workspace_id, request_id, position["position_key"], host=host,
                title=row.title, snippet=row.snippet, url=row.url,
            )
            if host and host not in hosts:
                hosts.append(host)
        next_index = position_index + 1
        advanced = self.repository.advance_request_search_job(
            job, stage="serp", position_index=next_index,
            hosts=hosts, enrich_index=0,
        )
        if advanced:
            self.repository.update_search_progress(workspace_id, request_id, next_index)
        return {"processed": True, "status": "searching", "stage": "serp", "search_progress": next_index, "search_total": len(positions)}

    def _process_enrich_step(self, job: dict[str, object]) -> dict[str, object]:
        workspace_id = int(job["workspace_id"])
        hosts = self._job_hosts(job)
        enrich_index = int(job["enrich_index"] or 0)
        if enrich_index >= len(hosts):
            completed = self.repository.finish_request_search_job(job, enrich_index=len(hosts))
            return {"processed": True, "status": "completed" if completed else "searching", "stage": "enrich"}

        # Раньше один HTTP-step обрабатывал ровно один домен. Для заявки №1058
        # это означало 41 последовательный сетевой обход, хотя ContactCrawler
        # уже умеет безопасно обходить разные сайты параллельно. Пакет ограничен
        # сверху, чтобы invocation оставался короче serverless-лимита.
        batch_size = _bounded_int_env("ENRICH_HOSTS_PER_STEP", 6, 1, 8)
        batch = hosts[enrich_index:enrich_index + batch_size]
        started = time.monotonic()
        outcomes = self._enrich_suppliers(workspace_id, batch)
        elapsed = round(time.monotonic() - started, 3)
        deferred = sum(1 for outcome in outcomes.values() if outcome.needs_retry)
        next_index = enrich_index + len(batch)
        log.info(
            "Заявка %s: пакет обогащения %s–%s из %s выполнен за %.1f с; в глубокую очередь: %s",
            job["request_id"], enrich_index + 1, next_index, len(hosts), elapsed, deferred,
        )
        if next_index >= len(hosts):
            completed = self.repository.finish_request_search_job(job, enrich_index=next_index)
            return {
                "processed": True, "status": "completed" if completed else "searching",
                "stage": "enrich", "enrich_progress": next_index,
                "enrich_total": len(hosts), "batch_size": len(batch),
                "deferred": deferred, "elapsed_seconds": elapsed,
            }
        self.repository.advance_request_search_job(
            job, stage="enrich", position_index=int(job["position_index"] or 0),
            hosts=hosts, enrich_index=next_index,
        )
        return {
            "processed": True, "status": "searching", "stage": "enrich",
            "enrich_progress": next_index, "enrich_total": len(hosts),
            "batch_size": len(batch), "deferred": deferred,
            "elapsed_seconds": elapsed,
        }

    @staticmethod
    def _job_hosts(job: dict[str, object]) -> list[str]:
        try:
            decoded = json.loads(str(job.get("enrich_hosts_json") or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(decoded, list):
            return []
        return list(dict.fromkeys(str(host).strip().lower() for host in decoded if str(host).strip()))

    def _enqueue_enrichment_outcome(self, workspace_id: int, host: str, outcome: EnrichmentOutcome) -> None:
        if not outcome.needs_retry:
            return
        self.repository.enqueue_enrichment_job(
            workspace_id, host, outcome.retry_stage,
            context=outcome.context, error=outcome.error,
            retry_after_seconds=outcome.retry_after_seconds,
        )

    def process_enrichment_retry_step(self, workspace_id: int) -> dict[str, object]:
        """Выполнить одну due-ступень общей durable очереди обогащения."""
        job = self.repository.claim_enrichment_job(workspace_id)
        if not job:
            return {"processed": False, "status": "idle"}
        try:
            stage = str(job["stage"])
            host = str(job["host"])
            if stage == "crawl":
                if int(job.get("attempts") or 0) >= 3:
                    # Два глубоких обхода уже не помогли: не молотим закрытый
                    # сайт двенадцать раз, а переключаемся на индекс поиска.
                    outcome = self._resume_web_enrichment(workspace_id, host, job.get("context") or {})
                else:
                    outcome = self._enrich_suppliers(
                        workspace_id, [host], enqueue_failures=False, deep=True,
                    ).get(host, EnrichmentOutcome())
            elif stage == "registry":
                outcome = self._resume_registry_enrichment(workspace_id, host, job.get("context") or {})
            elif stage == "web":
                outcome = self._resume_web_enrichment(workspace_id, host, job.get("context") or {})
            elif stage == "finance":
                outcome = self._resume_finance_enrichment(workspace_id, host, job.get("context") or {})
            else:
                raise ValueError(f"Неизвестный этап обогащения: {stage}")

            if outcome.needs_retry:
                if outcome.retry_stage != stage:
                    # Текущая ступень уже завершилась, но следующая временно
                    # недоступна. Не повторяем выполненную работу.
                    self.repository.complete_enrichment_job(job)
                    self._enqueue_enrichment_outcome(workspace_id, host, outcome)
                    return {"processed": True, "status": "queued", "stage": outcome.retry_stage}
                retrying = self.repository.retry_enrichment_job(
                    job, outcome.error,
                    retry_after_seconds=outcome.retry_after_seconds,
                    max_attempts=30 if outcome.retry_after_seconds >= 3600 else 12,
                )
                return {
                    "processed": True,
                    "status": "queued" if retrying else "failed",
                    "stage": stage,
                }

            self.repository.complete_enrichment_job(job)
            return {"processed": True, "status": "completed", "stage": stage}
        except Exception as exc:  # noqa: BLE001 — lease/job survives one bad invocation
            retrying = self.repository.retry_enrichment_job(
                job, str(exc), retry_after_seconds=60, max_attempts=12,
            )
            log.warning("Повторное обогащение %s/%s: %s", job.get("host"), job.get("stage"), exc)
            return {"processed": True, "status": "queued" if retrying else "failed", "error": str(exc)[:500]}

    def _resume_registry_enrichment(
        self, workspace_id: int, host: str, context: dict[str, object],
    ) -> EnrichmentOutcome:
        if not os.getenv("CHECKO_KEY"):
            return EnrichmentOutcome("registry", "CHECKO_KEY не настроен", 10 * 60, context)
        try:
            checko = CheckoClient()
        except ValueError as exc:
            return EnrichmentOutcome("registry", str(exc), 10 * 60, context)

        legal_hits: list[LegalIdHit] = []
        for item in context.get("legal_ids") or []:
            if not isinstance(item, dict):
                continue
            try:
                legal_hits.append(LegalIdHit(
                    value=str(item.get("value") or ""),
                    kind=str(item.get("kind") or ""),
                    source_url=str(item.get("source_url") or ""),
                    method=str(item.get("method") or "labeled"),
                    evidence=str(item.get("evidence") or ""),
                    checksum_ok=bool(item.get("checksum_ok")),
                    score=int(item.get("score") or 0),
                ))
            except (TypeError, ValueError):
                continue
        name_hints = tuple(str(value) for value in (context.get("name_hints") or []) if str(value).strip())
        known_email = str(context.get("known_email") or "")
        error_cursor = len(checko.errors)
        resolved = resolve_inn_by_legal_ids(legal_hits, checko) if legal_hits else None
        company = None
        best_inn: InnHit | None = None

        candidate_inn = str(context.get("candidate_inn") or "")
        if resolved is not None:
            company = checko.lookup(resolved.inn)
            best_inn = InnHit(
                inn=resolved.inn, source_url=f"реестр Checko: {resolved.explain()}",
                method="registry_legal_id", evidence=resolved.explain(),
                checksum_ok=True, kind=resolved.kind, domain_confirmed=True,
            )
        elif candidate_inn and validate_inn_checksum(candidate_inn):
            company = checko.lookup(candidate_inn)
            if company.found:
                owns = registry_owns_site(host, company.site, company.emails)
                unknown = registry_ownership_unknown(company.site, company.emails)
                weak_web = str(context.get("candidate_method") or "") == "web" and not bool(context.get("domain_confirmed"))
                if (owns or unknown) and not (weak_web and not owns):
                    best_inn = InnHit(
                        inn=candidate_inn, source_url="durable registry retry",
                        method="registry", evidence="реестр подтвердил кандидата",
                        checksum_ok=True, domain_confirmed=owns,
                    )
        elif not legal_hits:
            resolved = resolve_inn_by_registry(
                host, checko, name_hints=name_hints, known_email=known_email,
            )
            if resolved is not None:
                company = checko.lookup(resolved.inn)
                best_inn = InnHit(
                    inn=resolved.inn, source_url=f"реестр Checko: {resolved.explain()}",
                    method="registry", evidence=resolved.explain(),
                    checksum_ok=True, kind=resolved.kind, domain_confirmed=True,
                )

        if best_inn is None or company is None or not company.found:
            retry = self._checko_retry_since(checko, error_cursor, context)
            if retry.needs_retry:
                return retry
            # Name-search — только генератор кандидата. Если он ничего не
            # подтвердил, последняя ступень смотрит домен в поисковом индексе;
            # основной поиск заявки при этом уже не ждёт этот сетевой вызов.
            if not legal_hits:
                return EnrichmentOutcome("web", "реестр не подтвердил владельца домена", 1, context)
            return EnrichmentOutcome()

        self.repository.apply_supplier_enrichment(
            workspace_id, host, email=known_email, inn=best_inn.inn,
            phone=(company.phones[0] if company.phones else ""),
            region=company.region, role=company.role,
            company_name=(company.name_full or company.name),
            registry_ogrn=company.ogrn, registry_status=company.status,
            registry_active=company.active, registry_registered_at=company.registered,
            risks=company.risks,
        )
        self.repository.record_supplier_evidence(
            workspace_id, host,
            self._evidence_items(
                email_hits=[], inn_hits=[], legal_hits=legal_hits,
                name_hints=name_hints, best_email=None,
                best_inn=best_inn, resolved=resolved,
            ),
        )

        finance_cursor = len(checko.errors)
        finances = checko.finances(best_inn.inn)
        if finances.found:
            self.repository.apply_supplier_enrichment(
                workspace_id, host, inn=best_inn.inn,
                finance_report_year=finances.report_year,
                finance_revenue=finances.revenue, finance_profit=finances.profit,
                finance_history=finances.history,
            )
            return EnrichmentOutcome()
        retry = self._checko_retry_since(checko, finance_cursor, {"inn": best_inn.inn}, stage="finance")
        return retry if retry.needs_retry else EnrichmentOutcome()

    def _resume_web_enrichment(
        self, workspace_id: int, host: str, context: dict[str, object],
    ) -> EnrichmentOutcome:
        """Последний резерв: один ограниченный запрос к поисковому индексу."""
        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        if not user or not key:
            return EnrichmentOutcome("web", "XMLRiver не настроен", 10 * 60, context)
        timeout = max(5.0, min(float(os.getenv("ENRICH_WEB_TIMEOUT_SECONDS", "12") or 12), 20.0))
        web_lookup = WebLookup(
            XmlRiverClient(user, key, engine="yandex", timeout=timeout, max_retries=1),
            llm=None, pages=1, max_queries=1,
        )
        checko = None
        if os.getenv("CHECKO_KEY"):
            try:
                checko = CheckoClient()
            except ValueError:
                checko = None
        site = SiteResult(
            host=host, root=root_domain(host), status="unreachable",
            error=str(context.get("crawl_error") or "глубокий веб-поиск"),
        )
        return self._enrich_one(
            workspace_id, site, None, checko, web_lookup,
            defer_weak_fallbacks=False, allow_registry_name_fallback=False,
            retry_unreachable=False,
        )

    def _resume_finance_enrichment(
        self, workspace_id: int, host: str, context: dict[str, object],
    ) -> EnrichmentOutcome:
        inn = str(context.get("inn") or "")
        if not validate_inn_checksum(inn):
            return EnrichmentOutcome()
        if not os.getenv("CHECKO_KEY"):
            return EnrichmentOutcome("finance", "CHECKO_KEY не настроен", 10 * 60, context)
        checko = CheckoClient()
        cursor = len(checko.errors)
        finances = checko.finances(inn)
        if finances.found:
            self.repository.apply_supplier_enrichment(
                workspace_id, host, inn=inn,
                finance_report_year=finances.report_year,
                finance_revenue=finances.revenue, finance_profit=finances.profit,
                finance_history=finances.history,
            )
            return EnrichmentOutcome()
        retry = self._checko_retry_since(checko, cursor, context, stage="finance")
        return retry if retry.needs_retry else EnrichmentOutcome()

    # ------------------------------------------------------- contact/INN enrichment
    #
    # SERP gives host/title/snippet only. Everything below turns that into an
    # actual email/ИНН by crawling each new host once, same pipeline already
    # proven from the CLI (contact_crawler + email_extractor + inn_extractor),
    # with the LLM and Checko registry lookup as capped, best-effort extras.
    # A crawl or extraction failure on one host must never break the batch.

    def _enrich_suppliers(
        self, workspace_id: int, hosts: list[str], *, enqueue_failures: bool = True,
        deep: bool = False,
    ) -> dict[str, EnrichmentOutcome]:
        outcomes: dict[str, EnrichmentOutcome] = {}
        if not hosts:
            return outcomes
        # Маркетплейс в чёрном списке — не поставщик по определению (его ИНН
        # принадлежит площадке, не продавцу со страницы товара), поэтому
        # отсекается ДО обхода/Checko/LLM, а не только прячется в списке
        # постфактум — иначе на am.ozon.com тратятся реальные деньги на
        # каждой заявке. Восстановление из чёрного списка снова включит его
        # в обогащение со следующей заявки.
        blacklisted = self.repository.blacklisted_hosts(workspace_id, hosts)
        if blacklisted:
            log.info("%d сайтов из чёрного списка исключены из обогащения: %s", len(blacklisted), ", ".join(sorted(blacklisted)))
            hosts = [h for h in hosts if h not in blacklisted]
        if not hosts:
            return outcomes
        # Skip hosts this workspace already has an email for from an earlier
        # заявка — no shared cache yet (see Documents/28-8/PROJECT_DOCUMENTATION.md §16), but at
        # least the same workspace doesn't re-crawl/re-pay for a site it already
        # solved. upsert_search_result() (called before this, per host, in
        # the SERP step already linked this request to that supplier either way.
        already_known = self.repository.suppliers_with_email(workspace_id, hosts)
        # Email сам по себе не означает «обогащение завершено». Именно этот
        # shortcut навсегда оставлял and-elektrika.ru без ИНН: при следующих
        # проходах сайт уже не открывался, потому что почта была сохранена.
        missing_inn = {host for host, _email in self.repository.suppliers_missing_inn(workspace_id, hosts)}
        hosts_to_crawl = [h for h in hosts if h not in already_known or h in missing_inn]
        if already_known:
            log.info(
                "%d из %d сайтов уже имеют email из прошлых заявок — обход и веб-поиск пропущены: %s",
                len(already_known), len(hosts), ", ".join(sorted(already_known)),
            )
        # Известный ИНН без карточки ЕГРЮЛ больше не блокирует быстрый проход.
        # Такая догрузка — независимая durable-ступень: заявка завершается, а
        # реестр/финансы дозаполняются с сохранённого ИНН.
        for known_host, known_inn in self.repository.suppliers_missing_registry(
            workspace_id, sorted(already_known),
        ):
            deferred = EnrichmentOutcome(
                "registry", "отложенная догрузка ЕГРЮЛ", 1,
                {"candidate_inn": known_inn, "candidate_method": "stored"},
            )
            outcomes[known_host] = deferred
            if enqueue_failures:
                self._enqueue_enrichment_outcome(workspace_id, known_host, deferred)
        # ...и отдельно — те, у кого почта есть, а ИНН нет вовсе: их не чинит
        # ни обход (пропущен), ни догрузка реестра (ей нужен готовый ИНН).
        # Сайты с email, но без ИНН теперь входят в hosts_to_crawl: сначала
        # получаем сильные first-party ОГРН/ОГРНИП/name hints, а не тратим
        # реестровую квоту на слабую догадку из домена.
        if not hosts_to_crawl:
            return outcomes
        try:
            if deep:
                max_pages = _bounded_int_env("ENRICH_DEEP_MAX_PAGES", 6, 4, 10)
                timeout = _bounded_float_env("ENRICH_DEEP_REQUEST_TIMEOUT_SECONDS", 8.0, 3.0, 15.0)
                max_elapsed = _bounded_float_env("ENRICH_DEEP_SITE_TIMEOUT_SECONDS", 30.0, 12.0, 45.0)
                delay = _bounded_float_env("ENRICH_DEEP_DELAY_SECONDS", 0.15, 0.0, 0.5)
                max_pdfs = _bounded_int_env("ENRICH_DEEP_MAX_PDFS", 2, 0, 3)
            else:
                max_pages = _bounded_int_env("ENRICH_FAST_MAX_PAGES", 4, 3, 6)
                timeout = _bounded_float_env("ENRICH_FAST_REQUEST_TIMEOUT_SECONDS", 5.0, 2.0, 10.0)
                max_elapsed = _bounded_float_env("ENRICH_FAST_SITE_TIMEOUT_SECONDS", 12.0, 6.0, 25.0)
                delay = _bounded_float_env("ENRICH_FAST_DELAY_SECONDS", 0.05, 0.0, 0.3)
                # PDF остаётся полной частью воронки, но не задерживает первое
                # появление поставщиков: ссылка сохраняется и запускает deep job.
                max_pdfs = 0
            crawler = ContactCrawler(
                max_pages=max_pages, timeout=timeout, delay=delay,
                respect_robots=True, check_mx=_flag_env("ENRICH_CHECK_MX", True),
                keep_html=True, max_pdfs=max_pdfs, max_elapsed=max_elapsed,
                extra_url_hints=INN_URL_HINTS, extra_paths=INN_PATHS,
            )
            workers = min(
                len(hosts_to_crawl),
                _bounded_int_env("ENRICH_CRAWL_WORKERS", 6, 1, 8),
            )
            sites = crawler.crawl_many(hosts_to_crawl, workers=workers)
        except Exception as exc:
            log.warning("Обход сайтов для обогащения не выполнен: %s", exc)
            for host in hosts_to_crawl:
                outcome = EnrichmentOutcome("crawl", str(exc), 60, {})
                outcomes[host] = outcome
                if enqueue_failures:
                    self._enqueue_enrichment_outcome(workspace_id, host, outcome)
            return outcomes

        # LLM раньше запускался внутри каждого быстрого пакета и на живой
        # заявке №1058 добавил ~40 секунд после уже завершённого HTTP-crawl.
        # Основная воронка детерминированная; модель — только явный opt-in.
        llm = (
            LlmExtractor()
            if _flag_env("ENRICH_SYNC_LLM_FALLBACK", False)
            and self.llm_budget_rub > 0 and api_key_present()
            else None
        )
        checko: CheckoClient | None = None
        if os.getenv("CHECKO_KEY"):
            try:
                checko = CheckoClient()
            except ValueError:
                checko = None

        # Синхронный веб-fallback выключен по умолчанию: раньше каждый пустой
        # сайт добавлял ещё один последовательный запрос к XMLRiver и тормозил
        # всю заявку. Он не удалён, а перенесён в durable web-ступень.
        web_lookup: WebLookup | None = None
        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        sync_web_fallback = _flag_env("ENRICH_SYNC_WEB_FALLBACK", False)
        if sync_web_fallback and user and key:
            try:
                web_lookup = WebLookup(
                    XmlRiverClient(user, key, engine="yandex", timeout=12, max_retries=1),
                    llm=llm, pages=1, max_queries=1,
                )
            except Exception as exc:  # noqa: BLE001 — degrade, don't break the batch
                log.warning("Резервный поиск в интернете не настроен: %s", exc)

        for site in sites:
            try:
                outcome = self._enrich_one(
                    workspace_id, site, llm, checko, web_lookup,
                    defer_weak_fallbacks=not sync_web_fallback,
                    documents_deferred=not deep,
                )
                outcomes[site.host] = outcome
                if outcome.needs_retry and enqueue_failures:
                    self._enqueue_enrichment_outcome(workspace_id, site.host, outcome)
            except Exception as exc:  # noqa: BLE001 — one bad site must not stop the rest
                log.warning("%s: обогащение не выполнено: %s", site.host, exc)
                outcome = EnrichmentOutcome("crawl", str(exc), 60, {})
                outcomes[site.host] = outcome
                if enqueue_failures:
                    self._enqueue_enrichment_outcome(workspace_id, site.host, outcome)
        return outcomes

    def _enrich_registry_backlog(self, workspace_id: int, hosts: list[str]) -> None:
        """Checko-only pass for hosts we skip crawling but whose ЕГРЮЛ data is missing.

        Cheap by design: no crawl, no LLM, no web search — one registry lookup
        (plus one finances lookup) per ИНН, and only for ИНН we already have.
        """
        if not hosts or not os.getenv("CHECKO_KEY"):
            return
        pending = self.repository.suppliers_missing_registry(workspace_id, hosts)
        if not pending:
            return
        try:
            checko = CheckoClient()
        except ValueError:
            return
        log.info("Догружаю данные ЕГРЮЛ для %d ранее найденных поставщиков", len(pending))
        for host, inn in pending:
            try:
                if not validate_inn_checksum(inn):
                    continue
                company = checko.lookup(inn)
                if not company.found:
                    continue
                # Same ownership guard as _enrich_one, but stricter: this pass
                # doesn't know whether the stored ИНН came from a direct crawl
                # or a web-search fallback, so "не опровергнуто" isn't enough —
                # require Checko to positively confirm the domain. Otherwise a
                # bad ИНН stored earlier (e.g. from a name-coincidence hit in a
                # directory listing) just gets a wrong company's name/phone/
                # region grafted onto it here instead of being caught.
                owns = registry_owns_site(host, company.site, company.emails)
                if not owns:
                    log.info("%s: ИНН %s не подтверждён Checko для этого домена — данные реестра не применяю", host, inn)
                    continue
                finances = checko.finances(inn)
                self.repository.apply_supplier_enrichment(
                    workspace_id, host, inn=inn,
                    company_name=(company.name_full or company.name),
                    phone=(company.phones[0] if company.phones else ""),
                    region=company.region, role=company.role,
                    registry_ogrn=company.ogrn, registry_status=company.status,
                    registry_active=company.active, registry_registered_at=company.registered,
                    finance_report_year=(finances.report_year if finances.found else None),
                    finance_revenue=(finances.revenue if finances.found else None),
                    finance_profit=(finances.profit if finances.found else None),
                    finance_history=(finances.history if finances.found else None),
                    risks=company.risks,
                )
            except Exception as exc:  # noqa: BLE001 — one bad ИНН must not stop the rest
                log.warning("%s: догрузка ЕГРЮЛ не выполнена: %s", host, exc)

    def _resolve_missing_inn(self, workspace_id: int, hosts: list[str]) -> None:
        """Найти ИНН через реестр для сайтов, у которых есть почта, но нет ИНН.

        Дороже прохода по реестру выше (до 6 запросов на сайт, см.
        inn_resolver.resolve_inn_by_registry), поэтому ограничен сверху по
        числу сайтов за раз: лучше починить часть за прогон, чем выжечь
        дневную квоту на одной заявке.
        """
        if not hosts or not os.getenv("CHECKO_KEY"):
            return
        pending = self.repository.suppliers_missing_inn(workspace_id, hosts)
        if not pending:
            return
        try:
            checko = CheckoClient()
        except ValueError:
            return
        budget = 8  # сайтов за один прогон
        log.info("Ищу ИНН в реестре для %d поставщиков без юрлица (обработаю до %d)", len(pending), budget)
        for host, email in pending[:budget]:
            try:
                resolved = resolve_inn_by_registry(host, checko, known_email=email)
                if resolved is None:
                    continue
                company = checko.lookup(resolved.inn)
                if not company.found:
                    continue
                finances = checko.finances(resolved.inn)
                self.repository.apply_supplier_enrichment(
                    workspace_id, host, inn=resolved.inn,
                    company_name=(company.name_full or company.name),
                    phone=(company.phones[0] if company.phones else ""),
                    region=company.region, role=company.role,
                    registry_ogrn=company.ogrn, registry_status=company.status,
                    registry_active=company.active, registry_registered_at=company.registered,
                    finance_report_year=(finances.report_year if finances.found else None),
                    finance_revenue=(finances.revenue if finances.found else None),
                    finance_profit=(finances.profit if finances.found else None),
                    finance_history=(finances.history if finances.found else None),
                    risks=company.risks,
                )
                log.info("%s: ИНН %s найден в реестре (%s)", host, resolved.inn, resolved.evidence)
            except Exception as exc:  # noqa: BLE001 — один сайт не должен ронять проход
                log.warning("%s: поиск ИНН в реестре не выполнен: %s", host, exc)

    def _resolve_missing_email(self, workspace_id: int, hosts: list[str]) -> None:
        """Обратный случай: ИНН есть, а почты нет вовсе.

        Checko здесь — последний источник, не первый (прямое указание
        владельца проекта: «чекко это самое последнее место откуда брать
        почты, если другие инструменты не нашли»). Применяется только когда
        домен адреса из реестра совпадает с доменом сайта — иначе легко
        подставить почту постороннего юрлица с тем же ИНН по ошибке реестра
        (живой пример: farpost.ru был привязан к чужому ИНН ещё до фикса
        определения ИНН, и его запись в Checko несёт почту vl.ru, а не
        farpost.ru — простое «взять company.emails[0]» подставило бы чужой
        адрес).
        """
        if not hosts or not os.getenv("CHECKO_KEY"):
            return
        pending = self.repository.suppliers_missing_email(workspace_id, hosts)
        if not pending:
            return
        try:
            checko = CheckoClient()
        except ValueError:
            return
        for host, inn in pending:
            try:
                company = checko.lookup(inn)
                if not company.found or not company.emails:
                    continue
                root = root_domain(host)
                own_domain_emails = [e for e in company.emails if root_domain(e.partition("@")[2]) == root]
                if not own_domain_emails:
                    log.info("%s: у Checko для ИНН %s есть почта, но не на этом домене — не применяю", host, inn)
                    continue
                self.repository.apply_supplier_enrichment(workspace_id, host, email=own_domain_emails[0])
                log.info("%s: почта %s взята из Checko как последний резерв", host, own_domain_emails[0])
            except Exception as exc:  # noqa: BLE001 — один сайт не должен ронять проход
                log.warning("%s: подбор почты из Checko не выполнен: %s", host, exc)

    def _enrich_one(
        self, workspace_id: int, site: SiteResult, llm: LlmExtractor | None,
        checko: CheckoClient | None, web_lookup: WebLookup | None = None,
        *, defer_weak_fallbacks: bool = False,
        allow_registry_name_fallback: bool = True,
        retry_unreachable: bool = True,
        documents_deferred: bool = False,
    ) -> EnrichmentOutcome:
        outcome = EnrichmentOutcome()
        legal_hits: list[LegalIdHit] = []
        name_hints: tuple[str, ...] = ()
        if site.status not in ("ok", "no_email"):
            if web_lookup is None:
                if retry_unreachable and site.status in {"unreachable", "rate_limited"}:
                    return EnrichmentOutcome(
                        "crawl", site.error or site.status, 30,
                        {"crawl_error": site.error or site.status},
                    )
                return outcome
            finding = web_lookup.find_contacts(site.host)
            email_hits = list(finding.emails)
            inn_hit = web_lookup.find_inn(site.host)
            inn_hits = [inn_hit] if inn_hit else []
            if not email_hits and not inn_hits:
                if retry_unreachable and site.status in {"unreachable", "rate_limited"}:
                    return EnrichmentOutcome(
                        "crawl", site.error or site.status, 30,
                        {"crawl_error": site.error or site.status},
                    )
                return outcome
        else:
            email_hits = list(site.hits)
            inn_hits = extract_for_site(site)
            legal_hits = extract_legal_ids_for_site(site)
            name_hints = collect_name_hints_from_pages(site.html_pages)
            if llm is not None and (not email_hits or not inn_hits) and site.html_pages:
                self._llm_fill(site, llm, email_hits, inn_hits)
            # Сайт обошли успешно (и почту нашли), но ИНН нигде на обойдённых
            # страницах не встретился — не запись реестра, значит нам не в чём
            # проверять принадлежность, но попробовать веб-поиск как последний
            # источник дешевле, чем оставлять карточку без юрлица вовсе.
            if not inn_hits and web_lookup is not None:
                inn_hit = web_lookup.find_inn(site.host)
                if inn_hit:
                    inn_hits = [inn_hit]

        best_email = max(email_hits, key=lambda h: h.score) if email_hits else None
        if best_email is not None:
            verdict = verify_email(best_email, site.host)
            if not verdict.verified and best_email.confidence == "high":
                best_email.confidence = "medium"

        best_inn = max(inn_hits, key=lambda h: h.score) if inn_hits else None
        checko_company = None
        resolved = None

        # Сильнейший путь идёт первым: подписанный ОГРН/ОГРНИП с исходного
        # домена → прямой lookup Checko → точное совпадение идентификатора.
        # Он и быстрее name search, и не зависит от совпадения названий.
        if legal_hits and checko is not None:
            error_cursor = len(checko.errors)
            resolved = resolve_inn_by_legal_ids(legal_hits, checko)
            if resolved is not None:
                best_inn = InnHit(
                    inn=resolved.inn,
                    source_url=f"реестр Checko: {resolved.explain()}",
                    method="registry_legal_id",
                    evidence=resolved.explain(), checksum_ok=True,
                    kind=resolved.kind, domain_confirmed=True,
                )
                checko_company = checko.lookup(resolved.inn)
            else:
                # Наличие точного ОГРН/ОГРНИП запрещает принимать рядом
                # найденный ИНН, пока реестр не подтвердил эту точную связь.
                best_inn = None
                retry = self._checko_retry_since(checko, error_cursor, {
                    "legal_ids": [self._legal_id_context(hit) for hit in legal_hits],
                    "name_hints": list(name_hints),
                    "known_email": (best_email.email if best_email else ""),
                })
                if retry.needs_retry:
                    outcome = retry
                    # Не сохраняем непроверенный ИНН рядом с точным ОГРН,
                    # пока реестр временно недоступен.
                    best_inn = None

        if (
            not legal_hits and best_inn is not None
            and validate_inn_checksum(best_inn.inn) and checko is not None
        ):
            error_cursor = len(checko.errors)
            try:
                checko_company = checko.lookup(best_inn.inn)
            except Exception as exc:  # noqa: BLE001 — Checko outage degrades, doesn't break search
                log.info("Checko %s: %s", best_inn.inn, exc)
            if not checko_company or not checko_company.found:
                retry = self._checko_retry_since(checko, error_cursor, {
                    "candidate_inn": best_inn.inn,
                    "candidate_method": best_inn.method,
                    "domain_confirmed": best_inn.domain_confirmed,
                    "known_email": (best_email.email if best_email else ""),
                    "name_hints": list(name_hints),
                })
                if retry.needs_retry:
                    outcome = retry
                    best_inn = None
            # A checksum-valid number found on the page isn't proof the site belongs to
            # that legal entity — e.g. a payment processor's or a landlord's ИНН can
            # appear in a footer. Only trust the registry's name/phone/region for this
            # supplier if the registry itself points back at this domain (its listed
            # site or email lives on the same root domain), or ownership genuinely
            # can't be determined either way (small business on a free-mail address —
            # verify.py's registry_ownership_unknown exists precisely to not penalise
            # that case). A confirmed *mismatch* discards the Checko match entirely.
            if best_inn is not None and checko_company and checko_company.found:
                owns = registry_owns_site(site.host, checko_company.site, checko_company.emails)
                unknown = registry_ownership_unknown(checko_company.site, checko_company.emails)
                # ИНН, добытый веб-поиском (а не найденный прямо на странице
                # сайта), — заведомо более слабая улика: справочники вроде
                # Rusprofile хранят однофамильцев-юрлиц с похожим названием
                # (см. случай master-water.ru, где так подставился чужой ИНН).
                # Раз это не первоисточник, «не опровергнуто» здесь недостаточно
                # — принимаем запись реестра, только если Checko явно
                # подтверждает домен, либо ИНН нашёлся именно на самом домене
                # компании (domain_confirmed).
                web_hit = best_inn.method == "web"
                weak_evidence = web_hit and not best_inn.domain_confirmed
                if (not owns and not unknown) or (weak_evidence and not owns):
                    # Раз реестр не подтверждает принадлежность — это не ИНН
                    # этого поставщика вообще, а не только «имя не наше»:
                    # отбрасываем сам ИНН, иначе он всё равно ляжет в профиль
                    # ниже (apply_supplier_enrichment пишет inn независимо от
                    # checko_company) и подпишет карточку чужим юрлицом.
                    log.info("%s: ИНН %s (%s) не подтверждён достаточно — не применяю",
                              site.host, best_inn.inn,
                              "веб-поиск без привязки к домену" if weak_evidence else
                              (checko_company.name or checko_company.name_full))
                    checko_company = None
                    best_inn = None

        # Имя — только поиск кандидатов. Если точный legal ID был опубликован,
        # но не сошёлся, подменять его однофамильцем через name search запрещено.
        if (
            allow_registry_name_fallback and not defer_weak_fallbacks
            and best_inn is None and not legal_hits and checko is not None
            and not outcome.needs_retry
        ):
            error_cursor = len(checko.errors)
            resolved = resolve_inn_by_registry(
                site.host, checko,
                name_hints=name_hints,
                known_email=(best_email.email if best_email else ""),
            )
            if resolved is not None:
                best_inn = InnHit(
                    inn=resolved.inn, source_url=f"реестр Checko: {resolved.explain()}",
                    method="registry", evidence=resolved.explain(),
                    checksum_ok=True, kind=resolved.kind, domain_confirmed=True,
                )
                checko_company = checko.lookup(resolved.inn)
            else:
                retry = self._checko_retry_since(checko, error_cursor, {
                    "name_hints": list(name_hints),
                    "known_email": (best_email.email if best_email else ""),
                })
                if retry.needs_retry:
                    outcome = retry

        # Web-кандидат без реестрового подтверждения никогда не становится
        # фактом только потому, что название похоже.
        if best_inn is not None and best_inn.method == "web" and not best_inn.domain_confirmed and checko_company is None:
            best_inn = None

        email_value = best_email.email if best_email else ""
        if not email_value and checko_company and checko_company.found and checko_company.emails:
            own_domain_emails = [
                email for email in checko_company.emails
                if root_domain(email.partition("@")[2]) == root_domain(site.host)
            ]
            if own_domain_emails:
                email_value = own_domain_emails[0]

        finances = None
        if checko_company and checko_company.found and checko is not None and best_inn is not None:
            error_cursor = len(checko.errors)
            try:
                finances = checko.finances(best_inn.inn)
            except Exception as exc:  # noqa: BLE001 — finances is a nice-to-have, not core
                log.info("Checko finances %s: %s", best_inn.inn, exc)
            if not finances or (not finances.found and finances.error):
                retry = self._checko_retry_since(checko, error_cursor, {"inn": best_inn.inn}, stage="finance")
                if retry.needs_retry:
                    outcome = retry

        if not outcome.needs_retry and defer_weak_fallbacks:
            retry_context = {
                "legal_ids": [self._legal_id_context(hit) for hit in legal_hits],
                "name_hints": list(name_hints),
                "known_email": (best_email.email if best_email else ""),
            }
            if documents_deferred and site.document_candidates and not legal_hits and not inn_hits:
                outcome = EnrichmentOutcome(
                    "crawl", "реквизиты могут находиться в PDF", 1,
                    {**retry_context, "document_candidates": site.document_candidates[:3]},
                )
            elif site.timed_out and not legal_hits and not inn_hits:
                outcome = EnrichmentOutcome(
                    "crawl", site.error or "быстрый обход не завершён", 1, retry_context,
                )
            elif best_inn is None and not legal_hits:
                if checko is not None or os.getenv("CHECKO_KEY"):
                    outcome = EnrichmentOutcome(
                        "registry", "поиск владельца по имени отложен", 1, retry_context,
                    )
                elif os.getenv("XMLRIVER_USER") and os.getenv("XMLRIVER_KEY"):
                    outcome = EnrichmentOutcome(
                        "web", "резервный поиск отложен", 1, retry_context,
                    )
            elif legal_hits and checko is None:
                outcome = EnrichmentOutcome(
                    "registry", "точный ОГРН/ОГРНИП ожидает проверки реестром", 1,
                    retry_context,
                )

        self.repository.apply_supplier_enrichment(
            workspace_id, site.host,
            email=email_value,
            inn=best_inn.inn if best_inn else "",
            phone=(checko_company.phones[0] if checko_company and checko_company.phones else ""),
            region=(checko_company.region if checko_company else ""),
            role=(checko_company.role if checko_company else ""),
            company_name=(checko_company.name_full or checko_company.name) if checko_company and checko_company.found else "",
            registry_ogrn=(checko_company.ogrn if checko_company and checko_company.found else ""),
            registry_status=(checko_company.status if checko_company and checko_company.found else ""),
            registry_active=(checko_company.active if checko_company and checko_company.found else None),
            registry_registered_at=(checko_company.registered if checko_company and checko_company.found else ""),
            finance_report_year=(finances.report_year if finances and finances.found else None),
            finance_revenue=(finances.revenue if finances and finances.found else None),
            finance_profit=(finances.profit if finances and finances.found else None),
            finance_history=(finances.history if finances and finances.found else None),
            risks=(checko_company.risks if checko_company and checko_company.found else None),
        )
        self.repository.record_supplier_evidence(
            workspace_id, site.host,
            self._evidence_items(
                email_hits=email_hits, inn_hits=inn_hits, legal_hits=legal_hits,
                name_hints=name_hints, best_email=best_email,
                best_inn=best_inn, resolved=resolved,
            ),
        )
        return outcome

    @staticmethod
    def _legal_id_context(hit: LegalIdHit) -> dict[str, object]:
        return {
            "value": hit.value, "kind": hit.kind, "source_url": hit.source_url,
            "method": hit.method, "evidence": hit.evidence,
            "checksum_ok": hit.checksum_ok, "score": hit.score,
        }

    @staticmethod
    def _checko_retry_since(
        checko: CheckoClient, cursor: int, context: dict[str, object], *, stage: str = "registry",
    ) -> EnrichmentOutcome:
        errors = checko.errors[cursor:]
        if not errors:
            return EnrichmentOutcome()
        for kind, message in reversed(errors):
            if kind == "quota":
                return EnrichmentOutcome(stage, message, 6 * 60 * 60, context)
            if kind in {"network", "transient"}:
                return EnrichmentOutcome(stage, message, 60, context)
        return EnrichmentOutcome()

    @staticmethod
    def _evidence_items(
        *, email_hits: list, inn_hits: list[InnHit], legal_hits: list[LegalIdHit],
        name_hints: tuple[str, ...], best_email, best_inn: InnHit | None, resolved,
    ) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for hit in email_hits:
            items.append({
                "field_name": "email", "field_value": hit.email,
                "source_type": "website", "source_url": hit.source_url,
                "strength": "strong" if hit is best_email and hit.confidence == "high" else "medium",
                "score": hit.score,
                "decision": "accepted" if hit is best_email else "observed",
                "details": {"confidence": hit.confidence},
            })
        for hit in inn_hits:
            items.append({
                "field_name": "inn", "field_value": hit.inn,
                "source_type": "pdf" if str(hit.source_url).lower().endswith(".pdf") else hit.method,
                "source_url": hit.source_url,
                "strength": "strong" if best_inn and hit.inn == best_inn.inn else "medium",
                "score": hit.score,
                "decision": "accepted" if best_inn and hit.inn == best_inn.inn else "observed",
                "details": {"checksum_ok": hit.checksum_ok, "evidence": hit.evidence[:500]},
            })
        for hit in legal_hits:
            accepted = bool(resolved and resolved.evidence == hit.kind and resolved.registry_site == hit.value)
            items.append({
                "field_name": hit.kind, "field_value": hit.value,
                "source_type": "pdf" if hit.source_url.lower().endswith(".pdf") else hit.method,
                "source_url": hit.source_url, "strength": "strong",
                "score": hit.score, "decision": "accepted" if accepted else "observed",
                "details": {"checksum_ok": hit.checksum_ok, "evidence": hit.evidence[:500]},
            })
        for hint in name_hints:
            items.append({
                "field_name": "company_name_hint", "field_value": hint,
                "source_type": "website", "source_url": "",
                "strength": "weak", "score": 20, "decision": "observed",
                "details": {"rule": "search-only; never ownership proof"},
            })
        if best_inn and best_inn.method.startswith("registry"):
            items.append({
                "field_name": "inn", "field_value": best_inn.inn,
                "source_type": best_inn.method, "source_url": best_inn.source_url,
                "strength": "strong", "score": 100, "decision": "accepted",
                "details": {"evidence": best_inn.evidence},
            })
        return items

    def _llm_fill(self, site: SiteResult, llm: LlmExtractor, email_hits: list, inn_hits: list[InnHit]) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self.llm_spent_day:
            self.llm_spent_day = today
            self.llm_spent_rub = 0.0
        # At most 2 pages per site — page choice matters far more than model choice
        # (Documents/28-8/enrichment-and-cache.md), so we prefer requisites/contact-shaped URLs.
        candidates = sorted(
            site.html_pages.items(),
            key=lambda kv: (is_requisites_url(kv[0]) or is_contact_url(kv[0]), len(kv[1])),
            reverse=True,
        )[:2]
        for url, html in candidates:
            if self.llm_spent_rub >= self.llm_budget_rub:
                return
            text = page_text(html)
            if not inn_hits:
                before = llm.cost_rub()
                hit = llm.extract_inn(site.host, text, url)
                self.llm_spent_rub += llm.cost_rub() - before
                if hit:
                    inn_hits.append(hit)
            if self.llm_spent_rub >= self.llm_budget_rub:
                return
            if not email_hits:
                before = llm.cost_rub()
                hit = llm.extract_email(site.host, text, url)
                self.llm_spent_rub += llm.cost_rub() - before
                if hit:
                    email_hits.append(hit)

    def allow_api_request(self, session_token: str, *, limit: int = 30, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        with self.rate_lock:
            events = [timestamp for timestamp in self.rate_events.get(session_token, []) if now - timestamp < window_seconds]
            if len(events) >= limit:
                self.rate_events[session_token] = events
                return False
            events.append(now)
            self.rate_events[session_token] = events
            return True
    def run(self) -> None:
        self.queue.start()
        if self.mail_sync_interval > 0:
            self.mail_sync_thread = threading.Thread(
                target=self._run_mail_sync_loop, name="mail-sync", daemon=True
            )
            self.mail_sync_thread.start()
            log.info("Фоновая синхронизация входящих: раз в %d с", self.mail_sync_interval)
        if self.enrichment_retry_interval > 0:
            self.enrichment_retry_thread = threading.Thread(
                target=self._run_enrichment_retry_loop,
                name="enrichment-retry", daemon=True,
            )
            self.enrichment_retry_thread.start()
            log.info("Фоновое обогащение: одна due-ступень раз в %d с", self.enrichment_retry_interval)
        server: ThreadingHTTPServer | None = None
        try:
            server = ThreadingHTTPServer((self.config.host, self.config.port), SupplierHandler)
            server.app = self  # type: ignore[attr-defined]
            print(f"Supplydesk server: http://{self.config.host}:{self.config.port}/")
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.mail_sync_stop.set()
            self.enrichment_retry_stop.set()
            self.queue.stop()
            if server is not None:
                server.server_close()
            self.runtime.close()


def main() -> None:
    load_dotenv(ROOT / ".env")
    # Без этой настройки logging молчал: log.info() в фоновых задачах (очередь
    # писем, синхронизация входящих, обогащение) не выводился никуда, и
    # единственным способом узнать, что фоновый поток вообще работает, был
    # запрос в базу. Уровень задаётся LOG_LEVEL, по умолчанию INFO.
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    config = Config.from_env()
    SupplierApp(config).run()


if __name__ == "__main__":
    main()
