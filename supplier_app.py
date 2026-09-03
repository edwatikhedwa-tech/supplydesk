from __future__ import annotations

import gzip
import io
import json
import logging
import os
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mail.auth import new_token, token_hash
from mail.crypto import EncryptionConfigError
from mail.deliverability import DeliverabilityPreflightError
from mail.queue import MailQueue
from mail.repository import DeliveryResolutionRequiredError, MailRepository
from mail.runtime import RuntimeSession
from mail.service import MailService
from mail.types import ProviderError
from backend.app_config import (  # noqa: F401 -- Config/load_dotenv re-exported for api/index.py and operator scripts
    Config,
    SESSION_LIFETIME_MAX_SECONDS,
    SESSION_LIFETIME_MIN_SECONDS,
    _bounded_int_env,
    load_dotenv,
    yandex_provider_factory,
)
from backend.http_static import (  # noqa: F401 -- load_fixture_data re-exported for tests
    FRONTEND_DIST,
    _looks_like_source_path,
    load_fixture_data,
)

# Enrichment pipeline (email/INN/company data) — see Documents/28-8/enrichment-and-cache.md.
# Reused as-is from the already-tested CLI tools; nothing here is new logic. The
# pipeline's own orchestration methods live in EnrichmentOrchestratorMixin,
# composed into SupplierApp below.
from backend.integrations.registry.checko_client import CheckoClient
from backend.domain.supplier_identity.inn_extractor import validate_inn_checksum
from backend.domain.supplier_enrichment.orchestrator import EnrichmentOrchestratorMixin
from backend.http_auth import AuthHandlerMixin

log = logging.getLogger("supplier_app")

ROOT = Path(__file__).resolve().parent


def _strict_optional_bool(payload: dict, field: str) -> bool | None:
    """Accept only JSON booleans; omitted remains the backend default."""
    if field not in payload:
        return None
    value = payload[field]
    if type(value) is not bool:
        raise ValueError(f"{field} должен быть логическим значением true или false.")
    return value


class SupplierHandler(AuthHandlerMixin, SimpleHTTPRequestHandler):
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

    def _serve_app_shell(self) -> None:
        body = (FRONTEND_DIST / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # Do not let a browser cache the shell across deploys; hashed asset URLs inside it change.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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


class SupplierApp(EnrichmentOrchestratorMixin):
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
