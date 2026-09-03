"""
Auth/session/OAuth HTTP handler methods, extracted from SupplierHandler in
supplier_app.py (TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903) as part of
turning supplier_app.py into a thin composition entrypoint.

AuthHandlerMixin is composed into SupplierHandler via multiple inheritance
(`class SupplierHandler(AuthHandlerMixin, SimpleHTTPRequestHandler): ...`),
so every method below still resolves `self.app` (the SupplierApp property),
`self._json`/`self._redirect`/`self._redirect_with_cookie` (generic response
helpers that stay on SupplierHandler) and the underlying
BaseHTTPRequestHandler surface (`self.headers`, `self.rfile`, `self.wfile`,
`self.send_response`, ...) exactly as before. do_GET/do_POST/do_DELETE and
their route ordering are unchanged and untouched by this extraction. No
behavior changed: every method body below is moved byte-for-byte.
"""

from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
from http.cookies import SimpleCookie

from mail.auth import new_token, token_hash
from mail.crypto import EncryptionConfigError
from mail.types import ProviderError
from backend.app_config import yandex_provider_factory


class AuthHandlerMixin:
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
