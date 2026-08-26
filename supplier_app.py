from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from mail.auth import new_token, token_hash
from mail.crypto import EncryptionConfigError
from mail.providers.yandex import YandexMailProvider
from mail.queue import MailQueue
from mail.repository import MailRepository
from mail.service import DEFAULT_TEMPLATE, MailService
from mail.types import ProviderError
from serp_parser import SerpCollector, read_lines
from xmlriver_client import XmlRiverClient

# Enrichment pipeline (email/INN/company data) — see docs/enrichment-and-cache.md.
# Reused as-is from the already-tested CLI tools; nothing here is new logic.
from checko_client import CheckoClient
from collect_inn import INN_PATHS, INN_URL_HINTS, extract_for_site, page_text
from contact_crawler import ContactCrawler, SiteResult
from email_extractor import is_contact_url
from inn_extractor import InnHit, is_requisites_url, validate_inn_checksum
from llm_fallback import LlmExtractor, api_key_present
from verify import registry_owns_site, registry_ownership_unknown, verify_email
from web_lookup import WebLookup

log = logging.getLogger("supplier_app")

ROOT = Path(__file__).resolve().parent


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

    @classmethod
    def from_env(cls) -> "Config":
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
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
        )


def yandex_provider_factory(provider_name: str) -> YandexMailProvider:
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
                self._json(200, {"items": self.app.repository.list_threads(session["workspace_id"])})
            return
        if parsed.path == "/api/mail/status":
            session = self._require_session()
            if session:
                self._json(200, self.app.service.status(session["user_id"], session["workspace_id"]))
            return
        if parsed.path == "/api/mail/inbox":
            session = self._require_session()
            if session:
                self._json(200, {"items": self.app.repository.list_unmatched_incoming(session["workspace_id"])})
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
        if parsed.path == "/api/mail/threads":
            session = self._require_session()
            if session:
                self._thread_messages(session, parse_qs(parsed.query))
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
            if parsed.path == "/api/mail/test":
                self.app.service.test_connection(session["user_id"], session["workspace_id"])
                self._json(200, {"ok": True, "message": "Соединение с Яндекс Почтой проверено."})
            elif parsed.path == "/api/mail/sync":
                self._json(200, self.app.service.sync_incoming(session["user_id"], session["workspace_id"]))
            elif parsed.path == "/api/mail/disconnect":
                self.app.service.disconnect(session["user_id"], session["workspace_id"])
                self._json(200, {"ok": True})
            elif parsed.path == "/api/mail/send":
                result = self.app.service.queue_one(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 1043)), supplier=body.get("supplier") or {},
                    subject=body.get("subject", ""), body=body.get("body", ""), attachments=body.get("attachments") or [],
                )
                self.app.queue.wake()
                self._json(202, {"ok": True, "queued": [result]})
            elif parsed.path == "/api/mail/send-bulk":
                results = self.app.service.queue_bulk(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    request_id=int(body.get("request_id", 1043)), suppliers=body.get("suppliers") or [],
                    subject=body.get("subject", ""), body=body.get("body", ""), attachments=body.get("attachments") or [],
                )
                self.app.queue.wake()
                self._json(202, {"ok": True, "queued": results})
            elif parsed.path == "/api/mail/inbox/reply":
                result = self.app.service.reply_to_inbox(
                    user_id=session["user_id"], workspace_id=session["workspace_id"],
                    inbox_message_id=int(body.get("inbox_message_id", 0)),
                    subject=body.get("subject", ""), body=body.get("body", ""), attachments=body.get("attachments") or [],
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
                    deadline=body.get("deadline", ""),
                )
                self._json(201, {"ok": True, "request_id": request_id})
            elif parsed.path == "/api/blacklist":
                supplier_id = body.get("supplier_id")
                self._json(201, {"ok": True, "entry_id": self.app.repository.add_blacklist(
                    session["workspace_id"], session["user_id"], external_key=body.get("external_key", ""),
                    company_name=body.get("company_name", ""), reason=body.get("reason", ""),
                    supplier_id=int(supplier_id) if supplier_id else None,
                )})
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
        except (ValueError, TypeError, ProviderError, EncryptionConfigError) as exc:
            message = exc.message if isinstance(exc, ProviderError) else str(exc)
            self._json(400 if not isinstance(exc, ProviderError) or not exc.transient else 503, {"error": message})
        except Exception:
            self._json(500, {"error": "Внутренняя ошибка сервера. Попробуйте ещё раз."})

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
            headers={"Set-Cookie": f"session_id={session_token}; Path=/; Max-Age=28800; HttpOnly; SameSite=Lax" + ("; Secure" if self.app.config.session_cookie_secure else "")},
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
        if not session:
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
                f"session_id={session_token}; Path=/; Max-Age=28800; HttpOnly; SameSite=Lax" + ("; Secure" if self.app.config.session_cookie_secure else ""),
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
            else:
                self.app.start_search(session["workspace_id"], request_id)
            self._json(202, {"ok": True, **result})
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
        if not session:
            self._json(401, {"error": "Требуется вход в личный кабинет."})
        return session

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
        if length > 25 * 1024 * 1024:
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
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
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
            # enrichment runs) to its global card. See docs/suppliers-screen.md.
            self.repository.backfill_global_suppliers(seeded_user["workspace_id"])
        self.service = MailService(
            self.repository,
            yandex_provider_factory,
            config.encryption_key,
            daily_limit=config.daily_limit,
        )
        self.queue = MailQueue(
            self.repository,
            self.service,
            concurrency=config.queue_concurrency,
            max_retries=config.max_retries,
        )
        self.rate_lock = threading.Lock()
        self.rate_events: dict[str, list[float]] = {}
        self.search_lock = threading.Lock()
        self.search_thread: threading.Thread | None = None
        # LLM fallback is the only paid, uncapped step in enrichment. A process-lifetime,
        # day-scoped counter is enough because at most one search runs at a time (search_lock).
        self.llm_budget_rub = float(os.getenv("LLM_DAILY_BUDGET_RUB", "50") or 0)
        self.llm_spent_rub = 0.0
        self.llm_spent_day = time.strftime("%Y-%m-%d")

    def start_search(self, workspace_id: int, request_id: int) -> None:
        with self.search_lock:
            if self.search_thread and self.search_thread.is_alive():
                raise ValueError("Другая заявка уже обрабатывается. Дождитесь завершения текущего поиска.")
            self.search_thread = threading.Thread(target=self._run_search, args=(workspace_id, request_id), name="supplier-search", daemon=True)
            self.search_thread.start()

    def _run_search(self, workspace_id: int, request_id: int) -> None:
        try:
            user = os.getenv("XMLRIVER_USER", "")
            key = os.getenv("XMLRIVER_KEY", "")
            if not user or not key:
                raise RuntimeError("Поиск не настроен: заполните XMLRIVER_USER и XMLRIVER_KEY в .env.")
            client = XmlRiverClient(user, key, engine="yandex", timeout=45, max_retries=3)
            positions = self.repository.request_positions(workspace_id, request_id)
            total = len(positions)
            # SERP_PAGES is configurable (not hardcoded) so a deeper Yandex pass can be
            # tried without a code change; default keeps today's behaviour unchanged.
            serp_pages = max(1, int(os.getenv("SERP_PAGES", "1") or 1))
            # Rule: everything SERP finds (after host-dedup and the stop-list) gets
            # processed — no silent truncation of a "long tail" the user never sees.
            # SERP_RESULTS_PER_POSITION still exists as an explicit opt-in ceiling for
            # when someone deliberately wants to bound cost/time; empty/unset = no cap.
            cap_raw = (os.getenv("SERP_RESULTS_PER_POSITION") or "").strip()
            results_cap = int(cap_raw) if cap_raw else None
            stop_domains = set(read_lines(ROOT / "stop_domains.txt")) if (ROOT / "stop_domains.txt").exists() else set()
            hosts: list[str] = []
            for index, position in enumerate(positions, start=1):
                collector = SerpCollector(client, pages=serp_pages, suffix="купить", delay=1.0, dedup="host", exclude_domains=stop_domains)
                rows = collector.collect_one(position["name"])
                selected = rows if results_cap is None else rows[:results_cap]
                for row in selected:
                    self.repository.upsert_search_result(workspace_id, request_id, position["position_key"], host=row.host, title=row.title, snippet=row.snippet)
                    hosts.append(row.host)
                self.repository.update_search_progress(workspace_id, request_id, index)
            self._enrich_suppliers(workspace_id, sorted(set(hosts)))
            self.repository.complete_request_search(workspace_id, request_id)
        except Exception as exc:
            self.repository.complete_request_search(workspace_id, request_id, error=str(exc)[:500])

    # ------------------------------------------------------- contact/INN enrichment
    #
    # SERP gives host/title/snippet only. Everything below turns that into an
    # actual email/ИНН by crawling each new host once, same pipeline already
    # proven from the CLI (contact_crawler + email_extractor + inn_extractor),
    # with the LLM and Checko registry lookup as capped, best-effort extras.
    # A crawl or extraction failure on one host must never break the batch.

    def _enrich_suppliers(self, workspace_id: int, hosts: list[str]) -> None:
        if not hosts:
            return
        # Skip hosts this workspace already has an email for from an earlier
        # заявка — no shared cache yet (see PROJECT_DOCUMENTATION.md §16), but at
        # least the same workspace doesn't re-crawl/re-pay for a site it already
        # solved. upsert_search_result() (called before this, per host, in
        # _run_search) already linked this request to that supplier either way.
        already_known = self.repository.suppliers_with_email(workspace_id, hosts)
        hosts_to_crawl = [h for h in hosts if h not in already_known]
        if already_known:
            log.info(
                "%d из %d сайтов уже имеют email из прошлых заявок — обход и веб-поиск пропущены: %s",
                len(already_known), len(hosts), ", ".join(sorted(already_known)),
            )
        # ...but a skipped host may still owe us its ЕГРЮЛ/финансы: its ИНН
        # could have been found before those columns existed, or on a day the
        # Checko quota was already spent. Without this pass the crawl skip
        # above would keep that supplier's registry data empty forever.
        self._enrich_registry_backlog(workspace_id, sorted(already_known))
        if not hosts_to_crawl:
            return
        try:
            crawler = ContactCrawler(
                max_pages=6, timeout=8.0, delay=0.3, respect_robots=True,
                check_mx=True, keep_html=True,
                extra_url_hints=INN_URL_HINTS, extra_paths=INN_PATHS,
            )
            # Lower than crawl_many's own default (8): fewer simultaneous requests
            # per target site is less likely to itself trigger rate-limiting.
            sites = crawler.crawl_many(hosts_to_crawl, workers=5)
        except Exception as exc:
            log.warning("Обход сайтов для обогащения не выполнен: %s", exc)
            return

        llm = LlmExtractor() if (self.llm_budget_rub > 0 and api_key_present()) else None
        checko: CheckoClient | None = None
        if os.getenv("CHECKO_KEY"):
            try:
                checko = CheckoClient()
            except ValueError:
                checko = None

        # Last-resort stage for sites the crawler couldn't reach at all (blocked by
        # an anti-bot system, rate-limited, DNS/connection failure — see
        # docs/enrichment-and-cache.md). Not a model with browsing bolted on: XMLRiver
        # search (already paid for, already used for SERP) plus the same cheap model
        # reading the search snippets — about 2.5 kopecks/query vs. a search-native
        # model like Perplexity Sonar at ~17 kopecks, and Yandex's index is the more
        # relevant one for Russian suppliers anyway. See web_lookup.py's own docstring.
        web_lookup: WebLookup | None = None
        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        if user and key:
            try:
                web_lookup = WebLookup(XmlRiverClient(user, key, engine="yandex", timeout=20, max_retries=2), llm=llm)
            except Exception as exc:  # noqa: BLE001 — degrade, don't break the batch
                log.warning("Резервный поиск в интернете не настроен: %s", exc)

        for site in sites:
            try:
                self._enrich_one(workspace_id, site, llm, checko, web_lookup)
            except Exception as exc:  # noqa: BLE001 — one bad site must not stop the rest
                log.warning("%s: обогащение не выполнено: %s", site.host, exc)

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
                # Same ownership guard as _enrich_one: a checksum-valid ИНН sitting
                # on a page is not proof the site belongs to that legal entity.
                owns = registry_owns_site(host, company.site, company.emails)
                unknown = registry_ownership_unknown(company.site, company.emails)
                if not owns and not unknown:
                    log.info("%s: ИНН %s зарегистрирован на другую компанию — данные реестра не применяю", host, inn)
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
                )
            except Exception as exc:  # noqa: BLE001 — one bad ИНН must not stop the rest
                log.warning("%s: догрузка ЕГРЮЛ не выполнена: %s", host, exc)

    def _enrich_one(
        self, workspace_id: int, site: SiteResult, llm: LlmExtractor | None,
        checko: CheckoClient | None, web_lookup: WebLookup | None = None,
    ) -> None:
        if site.status not in ("ok", "no_email"):
            if web_lookup is None:
                return  # nothing to fall back to
            finding = web_lookup.find_contacts(site.host)
            email_hits = list(finding.emails)
            inn_hit = web_lookup.find_inn(site.host)
            inn_hits = [inn_hit] if inn_hit else []
            if not email_hits and not inn_hits:
                return  # search found nothing either — leave the SERP-only record as is
        else:
            email_hits = list(site.hits)
            inn_hits = extract_for_site(site)
            if llm is not None and (not email_hits or not inn_hits) and site.html_pages:
                self._llm_fill(site, llm, email_hits, inn_hits)

        best_email = max(email_hits, key=lambda h: h.score) if email_hits else None
        if best_email is not None:
            verdict = verify_email(best_email, site.host)
            if not verdict.verified and best_email.confidence == "high":
                best_email.confidence = "medium"

        best_inn = max(inn_hits, key=lambda h: h.score) if inn_hits else None
        checko_company = None
        if best_inn is not None and validate_inn_checksum(best_inn.inn) and checko is not None:
            try:
                checko_company = checko.lookup(best_inn.inn)
            except Exception as exc:  # noqa: BLE001 — Checko outage degrades, doesn't break search
                log.info("Checko %s: %s", best_inn.inn, exc)
            # A checksum-valid number found on the page isn't proof the site belongs to
            # that legal entity — e.g. a payment processor's or a landlord's ИНН can
            # appear in a footer. Only trust the registry's name/phone/region for this
            # supplier if the registry itself points back at this domain (its listed
            # site or email lives on the same root domain), or ownership genuinely
            # can't be determined either way (small business on a free-mail address —
            # verify.py's registry_ownership_unknown exists precisely to not penalise
            # that case). A confirmed *mismatch* discards the Checko match entirely.
            if checko_company and checko_company.found:
                owns = registry_owns_site(site.host, checko_company.site, checko_company.emails)
                unknown = registry_ownership_unknown(checko_company.site, checko_company.emails)
                if not owns and not unknown:
                    log.info("%s: ИНН %s зарегистрирован на %s — сайт не подтверждён, данные реестра не применяю",
                              site.host, best_inn.inn, checko_company.name or checko_company.name_full)
                    checko_company = None

        email_value = best_email.email if best_email else ""
        if not email_value and checko_company and checko_company.found and checko_company.emails:
            email_value = checko_company.emails[0]

        finances = None
        if checko_company and checko_company.found and checko is not None:
            try:
                finances = checko.finances(best_inn.inn)
            except Exception as exc:  # noqa: BLE001 — finances is a nice-to-have, not core
                log.info("Checko finances %s: %s", best_inn.inn, exc)

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
        )

    def _llm_fill(self, site: SiteResult, llm: LlmExtractor, email_hits: list, inn_hits: list[InnHit]) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self.llm_spent_day:
            self.llm_spent_day = today
            self.llm_spent_rub = 0.0
        # At most 2 pages per site — page choice matters far more than model choice
        # (docs/enrichment-and-cache.md), so we prefer requisites/contact-shaped URLs.
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
        server = ThreadingHTTPServer((self.config.host, self.config.port), SupplierHandler)
        server.app = self  # type: ignore[attr-defined]
        print(f"Supplydesk server: http://{self.config.host}:{self.config.port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.queue.stop()
            server.server_close()


def main() -> None:
    load_dotenv(ROOT / ".env")
    config = Config.from_env()
    SupplierApp(config).run()


if __name__ == "__main__":
    main()
