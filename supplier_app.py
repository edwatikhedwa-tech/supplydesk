from __future__ import annotations

import base64
import hashlib
import json
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
from serp_parser import SerpCollector
from xmlriver_client import XmlRiverClient


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


def load_fixture_data() -> dict:
    """Read the current result fixture once so dashboard data is backed by SQLite."""
    html = (ROOT / "supplier_finder.html").read_text(encoding="utf-8")
    marker = "const DATA = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n\nconst $", start)
    return json.loads(html[start:end])


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

    def end_headers(self) -> None:
        # The HTML contains the application shell and inline JavaScript. Do not let a browser
        # keep an older shell after a deployment with changed API/UI behavior.
        if self.path.split("?", 1)[0] in {"/", "/supplier_finder.html"}:
            self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._redirect("/supplier_finder.html")
            return
        if parsed.path == "/api/auth/me":
            self._auth_me()
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
        if parsed.path == "/api/mail/yandex/start":
            self._oauth_start()
            return
        if parsed.path == "/oauth/yandex/callback":
            self._oauth_callback(parse_qs(parsed.query))
            return
        self.directory = str(ROOT)
        super().do_GET()

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
            elif parsed.path == "/api/requests":
                positions = body.get("positions") or []
                if isinstance(positions, str):
                    positions = [{"name": line.split("|", 1)[0].strip(), "quantity": line.split("|", 1)[1].strip() if "|" in line else ""} for line in positions.splitlines() if line.strip()]
                request_id = self.app.repository.create_request(
                    session["workspace_id"], user_id=session["user_id"], name=body.get("name", ""),
                    description=body.get("description", ""), positions=positions,
                    sender_name=body.get("sender_name", session.get("display_name", "")), company_name=body.get("company_name", ""),
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
            elif parsed.path.startswith("/api/requests/"):
                self._request_action(session, parsed.path)
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

    def _auth_me(self) -> None:
        session = self.app.repository.get_session(self._session_token())
        if not session:
            self._json(200, {"authenticated": False})
            return
        self._json(200, {"authenticated": True, "csrf_token": self._csrf_token_for_session(session), "user": self._public_user(session)})

    def _oauth_start(self) -> None:
        session = self._require_session()
        if not session:
            return
        try:
            provider = yandex_provider_factory("yandex")
            state = new_token(32)
            code_verifier = new_token(48)
            code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
            self.app.repository.create_oauth_state(
                state=state, session_token=self._session_token(), user_id=session["user_id"], workspace_id=session["workspace_id"],
                code_verifier=code_verifier, redirect_uri=self.app.config.redirect_uri,
            )
            self._redirect(provider.authorization_url(redirect_uri=self.app.config.redirect_uri, state=state, code_challenge=code_challenge))
        except ProviderError as exc:
            self._redirect("/supplier_finder.html?settings=mail&mail_error=not_configured")

    def _oauth_callback(self, query: dict[str, list[str]]) -> None:
        session_token = self._session_token()
        state = (query.get("state") or [""])[0]
        callback_state = self.app.repository.consume_oauth_state(state, session_token) if state else None
        if not callback_state:
            self._redirect("/supplier_finder.html?settings=mail&mail_error=invalid_state")
            return
        if query.get("error"):
            self._redirect("/supplier_finder.html?settings=mail&mail_error=access_denied")
            return
        code = (query.get("code") or [""])[0]
        if not code:
            self._redirect("/supplier_finder.html?settings=mail&mail_error=missing_code")
            return
        try:
            provider = yandex_provider_factory("yandex")
            tokens = provider.exchange_code(code, redirect_uri=callback_state["redirect_uri"], code_verifier=callback_state["code_verifier"])
            account = provider.get_account(tokens.access_token)
            self.app.service.save_oauth_tokens(
                user_id=callback_state["user_id"], workspace_id=callback_state["workspace_id"], token_set=tokens, email=account.email
            )
            self._redirect("/supplier_finder.html?settings=mail&connected=true")
        except (ProviderError, ValueError, EncryptionConfigError):
            self._redirect("/supplier_finder.html?settings=mail&mail_error=connection_failed")

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

    def _request_action(self, session: dict, path: str) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            request_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор заявки."})
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

    def _session_token(self) -> str:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        return cookie.get("session_id").value if cookie.get("session_id") else ""

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
            for index, position in enumerate(positions, start=1):
                collector = SerpCollector(client, pages=1, suffix="купить", delay=0, dedup="host")
                rows = collector.collect_one(position["name"])
                for row in rows[:30]:
                    self.repository.upsert_search_result(workspace_id, request_id, position["position_key"], host=row.host, title=row.title, snippet=row.snippet)
                self.repository.update_search_progress(workspace_id, request_id, index)
            self.repository.complete_request_search(workspace_id, request_id)
        except Exception as exc:
            self.repository.complete_request_search(workspace_id, request_id, error=str(exc)[:500])

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
        print(f"Supplydesk server: http://{self.config.host}:{self.config.port}/supplier_finder.html")
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
