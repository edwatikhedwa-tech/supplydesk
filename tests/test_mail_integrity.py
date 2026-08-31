from __future__ import annotations

import os
import http.client
import json
import smtplib
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import supplier_app
from mail.auth import token_hash
from mail.crypto import generate_key
from mail.providers.yandex import YandexMailProvider
from mail.pacing import PacingSettings
from mail.queue import MailQueue
from mail.repository import DeliveryResolutionRequiredError, MailRepository
from mail.service import MailService
from mail.types import DeliveryCheck, IncomingMessage, OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet


class IntegrityProvider:
    """Deterministic provider double for the Step 9 state-machine tests."""

    name = "fake-integrity"

    def __init__(self) -> None:
        self.sent: list[OutgoingMessage] = []
        self.copy_calls = 0
        self.send_calls = 0
        self.verify_calls = 0
        self.mode = "success"
        self.verify_outcome = "not_found"
        self.copy_error = False
        self.before_irreversible_hook = None

    def exchange_code(self, code: str, *, redirect_uri: str, code_verifier: str) -> TokenSet:
        return TokenSet("access", "refresh", 3600)

    def refresh_token(self, refresh_token: str) -> TokenSet:
        return TokenSet("access-refreshed", "refresh-new", 3600)

    def get_account(self, access_token: str) -> ProviderAccount:
        return ProviderAccount("user@example.com")

    def test_connection(self, email: str, access_token: str) -> None:
        return None

    def send_message(self, access_token: str, message: OutgoingMessage, *, before_irreversible=None) -> SendResult:
        self.send_calls += 1
        if self.mode == "refused":
            raise ProviderError("Явный отказ сервера", transient=True)
        if self.mode == "pre_data":
            raise ProviderError(
                "Не удалось сформировать письмо.",
                provider_code="message-encoding",
                smtp_stage="pre_data",
                exception_class="UnicodeEncodeError",
            )
        if self.before_irreversible_hook is not None:
            self.before_irreversible_hook()
        if before_irreversible is not None:
            before_irreversible()
        if self.mode == "uncertain":
            raise ProviderError("Соединение оборвалось после начала передачи", transient=True, uncertain=True)
        self.sent.append(message)
        return SendResult(message.message_id or "<missing@example.com>", None, datetime.now(timezone.utc))

    def save_sent_copy(self, access_token: str, message: OutgoingMessage, result: SendResult) -> None:
        self.copy_calls += 1
        if self.copy_error:
            raise RuntimeError("copy failed")

    def verify_sent_message(self, access_token: str, email: str, message_id: str | None) -> DeliveryCheck:
        self.verify_calls += 1
        return DeliveryCheck(self.verify_outcome, message_id)


class MailEndpointHarness:
    """Small real HTTP harness for auth/CSRF/workspace isolation tests."""

    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.config = supplier_app.Config(
            host="127.0.0.1",
            port=0,
            base_url="http://127.0.0.1",
            redirect_uri="http://127.0.0.1/oauth/yandex/callback",
            db_path=str(Path(self.temp.name) / "endpoint.sqlite3"),
            encryption_key=generate_key(),
            app_user_email="endpoint-owner@example.com",
            app_user_password="correct-horse",
            session_cookie_secure=False,
            queue_concurrency=1,
            max_retries=2,
            daily_limit=1000,
        )
        self.app = supplier_app.SupplierApp(self.config)
        self.user = self.app.repository.seed_user("endpoint-owner@example.com", "correct-horse")
        self.account_id = self.app.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("endpoint-access", "endpoint-refresh", 3600), email="owner@example.com",
        )
        self.session_token, self.csrf_token = self.app.repository.create_session(
            self.user["id"], self.user["workspace_id"],
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), supplier_app.SupplierHandler)
        self.server.app = self.app  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = int(self.server.server_address[1])

    def post(
        self,
        path: str,
        payload: dict,
        *,
        authenticated: bool,
        csrf: bool = True,
    ) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Cookie"] = f"session_id={self.session_token}"
            if csrf:
                headers["X-CSRF-Token"] = self.csrf_token
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("POST", path, body=json.dumps(payload), headers=headers)
            response = connection.getresponse()
            body = response.read()
            return int(response.status), json.loads(body.decode("utf-8"))
        finally:
            connection.close()

    def get(self, path: str, *, authenticated: bool) -> tuple[int, dict, dict[str, str]]:
        headers = {}
        if authenticated:
            headers["Cookie"] = f"session_id={self.session_token}"
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            body = response.read()
            return int(response.status), json.loads(body.decode("utf-8")), dict(response.getheaders())
        finally:
            connection.close()

    def counts(self) -> dict[str, int]:
        with self.app.repository.connect() as connection:
            return {
                "operations": connection.execute("SELECT COUNT(*) FROM mail_send_operations").fetchone()[0],
                "messages": connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0],
                "jobs": connection.execute("SELECT COUNT(*) FROM mail_jobs").fetchone()[0],
                "suppliers": connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
            }

    def create_foreign_outbound_message(self) -> int:
        foreign_user = self.app.repository.seed_user("other@example.com", "correct-horse")
        foreign_request_id = self.app.repository.create_request(
            foreign_user["workspace_id"], user_id=foreign_user["id"],
            name="Чужая заявка", description="Чужие данные", positions=[{"name": "Позиция", "quantity": "1"}],
            sender_name="Другой пользователь", company_name="Другая компания",
        )
        foreign_account = self.app.service.save_oauth_tokens(
            user_id=foreign_user["id"], workspace_id=foreign_user["workspace_id"],
            token_set=TokenSet("foreign-access", "foreign-refresh", 3600), email="other@example.com",
        )
        self.assert_account_exists(foreign_account)
        queued = self.app.service.queue_one(
            user_id=foreign_user["id"], workspace_id=foreign_user["workspace_id"], request_id=foreign_request_id,
            supplier={"name": "Other", "email": "other-recipient@example.com", "host": "other.example"},
            subject="Other", body="Other", idempotency_key="foreign-message",
        )
        return int(queued["message_id"])

    @staticmethod
    def assert_account_exists(account_id: int) -> None:
        if not account_id:
            raise AssertionError("mail account was not created")

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()


class MailIntegrityAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "integrity.sqlite3"
        self.repo = MailRepository(self.db_path)
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        # The production default is fail-closed; this fixture explicitly
        # enables its temporary fake transport for positive-path tests.
        self.repo.set_outgoing_enabled(True)
        self.provider = IntegrityProvider()
        self.service = MailService(self.repo, lambda _: self.provider, generate_key(), daily_limit=1000)
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.user["workspace_id"],
            token_set=TokenSet("access-secret", "refresh-secret", 3600), email="user@example.com",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def workspace_id(self) -> int:
        return int(self.user["workspace_id"])

    @property
    def user_id(self) -> int:
        return int(self.user["id"])

    def _bulk(self, *, key: str, suppliers: list[dict] | None = None, subject: str = "Запрос", body: str = "Текст") -> list[dict]:
        return self.service.queue_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=1043,
            suppliers=suppliers or [{"name": "Good", "email": "good@example.com", "host": "good.example"}],
            subject=subject, body=body, idempotency_key=key,
        )

    def _one(self, *, key: str = "single") -> dict:
        return self._bulk(key=key)[0]

    def _unknown(self, *, key: str = "unknown") -> dict:
        queued = self._one(key=key)
        job = self.repo.claim_job()
        self.assertIsNotNone(job)
        self.assertTrue(self.repo.mark_job_delivery_unknown(
            job["id"], job["message_id"], "Проверка не завершена.", job["claim_token"],
        ))
        return queued

    def _incoming(self, message_id: str = "<inbound@example.com>") -> int:
        result = self.repo.import_incoming_messages(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            account_id=self.account_id,
            messages=[IncomingMessage(
                provider_message_id=f"imap:INBOX:1:{message_id}", message_id=message_id,
                in_reply_to=None, references=None, from_email="supplier@example.com",
                to_email="user@example.com", subject="Новое письмо", body_text="Входящее",
                body_html="<p>Входящее</p>", received_at=datetime.now(timezone.utc),
            )],
        )
        self.assertEqual(result["unmatched"], 1)
        return int(self.repo.list_unmatched_incoming(self.workspace_id)[0]["id"])

    def _status(self, message_id: int) -> tuple[str, str]:
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT j.status AS job_status, m.status AS message_status FROM mail_jobs j JOIN mail_messages m ON m.id=j.message_id WHERE m.id=?",
                (message_id,),
            ).fetchone()
        return row["job_status"], row["message_status"]

    def test_01_same_key_same_content_does_not_create_second_batch(self) -> None:
        first = self._bulk(key="batch-1", suppliers=[
            {"name": "One", "email": "one@example.com", "host": "one.example"},
            {"name": "Two", "email": "two@example.com", "host": "two.example"},
        ])
        second = self._bulk(key="batch-1", suppliers=[
            {"name": "One", "email": "one@example.com", "host": "one.example"},
            {"name": "Two", "email": "two@example.com", "host": "two.example"},
        ])
        self.assertEqual(first, second)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_operations").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0], 2)

    def test_01b_bulk_http_without_key_is_400_and_creates_nothing(self) -> None:
        harness = MailEndpointHarness()
        try:
            before = harness.counts()
            for extra in ({}, {"idempotency_key": ""}):
                payload = {
                    "request_id": 1043,
                    "suppliers": [{"name": "No Key", "email": "no-key@example.com", "host": "no-key.example"}],
                    "subject": "Запрос",
                    "body": "Текст",
                    **extra,
                }
                status, response = harness.post("/api/mail/send-bulk", payload, authenticated=True)
                self.assertEqual(status, 400)
                self.assertIn("idempotency key", response["error"])
                self.assertEqual(harness.counts(), before)
        finally:
            harness.close()

    def test_01c_bulk_http_retry_with_same_key_does_not_create_second_batch(self) -> None:
        harness = MailEndpointHarness()
        try:
            payload = {
                "request_id": 1043,
                "suppliers": [{"name": "HTTP", "email": "http-key@example.com", "host": "http-key.example"}],
                "subject": "Запрос",
                "body": "Текст",
                "idempotency_key": "http-retry-key",
            }
            first_status, first = harness.post("/api/mail/send-bulk", payload, authenticated=True)
            second_status, second = harness.post("/api/mail/send-bulk", payload, authenticated=True)
            self.assertEqual((first_status, second_status), (202, 202))
            self.assertEqual(first["queued"], second["queued"])
            self.assertEqual(harness.counts()["operations"], 1)
            self.assertEqual(harness.counts()["messages"], 1)
            self.assertEqual(harness.counts()["jobs"], 1)
        finally:
            harness.close()

    def test_01ca_bulk_http_same_request_email_guard_and_explicit_repeat(self) -> None:
        harness = MailEndpointHarness()
        try:
            base = {
                "request_id": 1043,
                "suppliers": [{"name": "HTTP guard", "email": "http-guard@example.com", "host": "http-guard.example"}],
                "subject": "Запрос",
                "body": "Текст",
            }
            first_status, _ = harness.post(
                "/api/mail/send-bulk", {**base, "idempotency_key": "http-guard-first"}, authenticated=True,
            )
            before_block = harness.counts()
            blocked_status, blocked = harness.post(
                "/api/mail/send-bulk", {**base, "idempotency_key": "http-guard-second"}, authenticated=True,
            )
            self.assertEqual(first_status, 202)
            self.assertEqual(blocked_status, 409)
            self.assertIn("same_request_already_contacted", blocked["preflight"]["blocks"])
            self.assertEqual(harness.counts(), before_block)

            invalid_status, _ = harness.post(
                "/api/mail/send-bulk",
                {**base, "idempotency_key": "http-guard-invalid", "allow_repeat": "true"},
                authenticated=True,
            )
            self.assertEqual(invalid_status, 400)
            self.assertEqual(harness.counts(), before_block)

            repeated_status, repeated = harness.post(
                "/api/mail/send-bulk",
                {**base, "idempotency_key": "http-guard-repeat", "allow_repeat": True},
                authenticated=True,
            )
            self.assertEqual(repeated_status, 202)
            self.assertEqual(len(repeated["queued"]), 1)
            self.assertEqual(harness.counts()["messages"], before_block["messages"] + 1)
        finally:
            harness.close()

    def test_01e_bulk_http_rejects_non_boolean_manual_mode_without_entities(self) -> None:
        harness = MailEndpointHarness()
        try:
            before = harness.counts()
            payload = {
                "request_id": 1043,
                "suppliers": [{"name": "Strict", "email": "strict@example.com", "host": "strict.example"}],
                "subject": "Запрос",
                "body": "Текст",
                "idempotency_key": "strict-mode",
                "manual_stage_approval": "true",
            }
            status, response = harness.post("/api/mail/send-bulk", payload, authenticated=True)
            self.assertEqual(status, 400)
            self.assertIn("логическим", response["error"])
            self.assertEqual(harness.counts(), before)
        finally:
            harness.close()

    def test_01d_preview_exposes_non_frozen_intent_contract(self) -> None:
        harness = MailEndpointHarness()
        try:
            status, response = harness.post(
                "/api/mail/deliverability/preview",
                {
                    "request_id": 1043,
                    "suppliers": [{"name": "Preview", "email": "preview@example.com", "host": "preview.example"}],
                    "subject": "Preview",
                    "body": "Request",
                },
                authenticated=True,
            )
            self.assertEqual(status, 200)
            self.assertEqual(response["preview_contract"]["frozen"], False)
            self.assertTrue(response["preview_contract"]["rerun_if_source_data_changed"])
            self.assertTrue(response["dry_run"])
            self.assertEqual(harness.counts()["operations"], 0)
        finally:
            harness.close()

    def test_01f_bulk_http_accepts_explicit_html_content_contract(self) -> None:
        harness = MailEndpointHarness()
        try:
            status, response = harness.post(
                "/api/mail/send-bulk",
                {
                    "request_id": 1043,
                    "suppliers": [{"name": "HTTP HTML", "email": "http-html@example.com", "host": "http-html.example"}],
                    "subject": "Запрос",
                    "body_text": "HTTP text",
                    "body_html": "<p>HTTP <strong>HTML</strong></p>",
                    "idempotency_key": "http-html-contract",
                },
                authenticated=True,
            )
            self.assertEqual(status, 202)
            self.assertEqual(len(response["queued"]), 1)
            operation = harness.app.repository.get_send_operation(harness.user["workspace_id"], "http-html-contract")
            self.assertIsNotNone(operation)
            assert operation is not None
            target = harness.app.repository.get_send_operation_targets(int(operation["id"]))[0]
            self.assertEqual(target["body_text"], "HTTP HTML")
            self.assertIn("<strong>HTML</strong>", target["body_html"])
        finally:
            harness.close()

    def test_02_same_key_changed_content_is_conflict(self) -> None:
        self._bulk(key="conflict", body="Первый текст")
        with self.assertRaisesRegex(ValueError, "другого содержимого"):
            self._bulk(key="conflict", body="Другой текст")

    def test_02b_same_key_ignores_enrichment_name_change_and_keeps_snapshot(self) -> None:
        suppliers = [{"name": "ООО Ромашка", "email": "snapshot@example.com", "host": "snapshot.example"}]
        first = self._bulk(
            key="snapshot-stability",
            suppliers=suppliers,
            subject="КП для {{supplier_name}}",
            body="Здравствуйте, {{supplier_name}}!",
        )
        with self.repo.connect() as connection:
            connection.execute("UPDATE suppliers SET name=? WHERE email=?", ("Ромашка, ООО", "snapshot@example.com"))
            first_target = connection.execute(
                "SELECT subject, body_text FROM mail_send_operation_targets WHERE normalized_email=?",
                ("snapshot@example.com",),
            ).fetchone()
        second = self._bulk(
            key="snapshot-stability",
            suppliers=[{"name": "Ромашка, ООО", "email": "snapshot@example.com", "host": "snapshot.example"}],
            subject="КП для {{supplier_name}}",
            body="Здравствуйте, {{supplier_name}}!",
        )
        with self.repo.connect() as connection:
            after_target = connection.execute(
                "SELECT subject, body_text FROM mail_send_operation_targets WHERE normalized_email=?",
                ("snapshot@example.com",),
            ).fetchone()
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_operations").fetchone()[0], 1)
        self.assertEqual(first, second)
        self.assertEqual(dict(first_target), dict(after_target))
        self.assertIn("ООО Ромашка", first_target["body_text"])

    def test_03_new_mail_endpoints_require_auth_csrf_and_workspace_ownership(self) -> None:
        harness = MailEndpointHarness()
        try:
            paths = [
                "/api/mail/messages/999999/verify",
                "/api/mail/messages/999999/resend",
                "/api/mail/messages/999999/resolve",
            ]
            for path in paths:
                status, _ = harness.post(path, {}, authenticated=False)
                self.assertEqual(status, 401, path)
                status, _ = harness.post(path, {}, authenticated=True, csrf=False)
                self.assertEqual(status, 403, path)

            foreign_message_id = harness.create_foreign_outbound_message()
            for path in [
                f"/api/mail/messages/{foreign_message_id}/verify",
                f"/api/mail/messages/{foreign_message_id}/resend",
                f"/api/mail/messages/{foreign_message_id}/resolve",
            ]:
                status, response = harness.post(path, {}, authenticated=True)
                self.assertEqual(status, 400, path)
                self.assertNotIn("other@example.com", json.dumps(response, ensure_ascii=False))
        finally:
            harness.close()

    def test_session_renews_on_activity_and_survives_repository_restart(self) -> None:
        harness = MailEndpointHarness()
        try:
            near_expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            with harness.app.repository.connect() as connection:
                connection.execute(
                    "UPDATE sessions SET expires_at=? WHERE token_hash=?",
                    (near_expiry, token_hash(harness.session_token)),
                )
            status, payload, headers = harness.get("/api/auth/me", authenticated=True)
            self.assertEqual(status, 200)
            self.assertTrue(payload["authenticated"])
            self.assertIn("Max-Age=2592000", headers.get("Set-Cookie", ""))
            with harness.app.repository.connect() as connection:
                renewed = connection.execute(
                    "SELECT expires_at FROM sessions WHERE token_hash=?",
                    (token_hash(harness.session_token),),
                ).fetchone()[0]
            self.assertGreater(renewed, near_expiry)

            restarted = MailRepository(harness.app.repository.db_path)
            self.assertIsNotNone(restarted.get_session(harness.session_token))
        finally:
            harness.close()

    def test_expired_session_is_not_revived_by_activity(self) -> None:
        harness = MailEndpointHarness()
        try:
            with harness.app.repository.connect() as connection:
                connection.execute(
                    "UPDATE sessions SET expires_at=? WHERE token_hash=?",
                    ("2000-01-01T00:00:00+00:00", token_hash(harness.session_token)),
                )
            status, payload, headers = harness.get("/api/auth/me", authenticated=True)
            self.assertEqual(status, 200)
            self.assertFalse(payload["authenticated"])
            self.assertNotIn("Set-Cookie", headers)
            self.assertIsNone(harness.app.repository.get_session(harness.session_token))
        finally:
            harness.close()

    def test_03_recipient_permutation_reuses_operation(self) -> None:
        suppliers = [
            {"name": "One", "email": "one@example.com", "host": "one.example"},
            {"name": "Two", "email": "two@example.com", "host": "two.example"},
        ]
        first = self._bulk(key="permutation", suppliers=suppliers)
        second = self._bulk(key="permutation", suppliers=list(reversed(suppliers)))
        self.assertEqual({row["message_id"] for row in first}, {row["message_id"] for row in second})
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_send_operations").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0], 2)

    def test_04_interrupted_assembly_rolls_back_operation_and_is_not_claimable(self) -> None:
        original = self.repo._create_queued_message_connection
        calls = 0

        def interrupted(connection, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("assembly interrupted")
            return original(connection, **kwargs)

        suppliers = [
            {"name": "One", "email": "one@example.com", "host": "one.example"},
            {"name": "Two", "email": "two@example.com", "host": "two.example"},
        ]
        with patch.object(self.repo, "_create_queued_message_connection", side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self._bulk(key="assembling", suppliers=suppliers)
        self.assertIsNone(self.repo.get_send_operation(self.workspace_id, "assembling"))
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_request_email_guards").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0], 0)
        self.assertIsNone(self.repo.claim_job())

    def test_05_retry_after_atomic_rollback_creates_all_targets(self) -> None:
        original = self.repo._create_queued_message_connection
        calls = 0

        def interrupted(connection, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("assembly interrupted")
            return original(connection, **kwargs)

        suppliers = [
            {"name": "One", "email": "one@example.com", "host": "one.example"},
            {"name": "Two", "email": "two@example.com", "host": "two.example"},
        ]
        with patch.object(self.repo, "_create_queued_message_connection", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self._bulk(key="resume", suppliers=suppliers)
        resumed = self._bulk(key="resume", suppliers=suppliers)
        self.assertEqual(len(resumed), 2)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0], 2)

    def test_06_operation_ready_only_after_all_expected_targets_exist(self) -> None:
        self._bulk(key="ready", suppliers=[
            {"name": "One", "email": "one@example.com", "host": "one.example"},
            {"name": "Two", "email": "two@example.com", "host": "two.example"},
        ])
        operation = self.repo.get_send_operation(self.workspace_id, "ready")
        targets = self.repo.get_send_operation_targets(operation["id"])
        self.assertEqual(operation["status"], "ready")
        self.assertEqual(operation["expected_recipient_count"], len(targets))
        self.assertTrue(all(target["message_id"] is not None for target in targets))

    def test_07_sqlite_two_processes_claim_one_job(self) -> None:
        queued = self._one(key="claim-race")
        repos = [MailRepository(self.db_path), MailRepository(self.db_path)]
        barrier = threading.Barrier(2)
        claimed: list[dict | None] = []

        def claim(repo: MailRepository) -> None:
            barrier.wait()
            claimed.append(repo.claim_job())

        threads = [threading.Thread(target=claim, args=(repo,)) for repo in repos]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(item is not None for item in claimed), 1)
        self.assertEqual(claimed[0]["message_id"] if claimed[0] else claimed[1]["message_id"], queued["message_id"])

    @unittest.skipUnless(os.getenv("INTEGRITY_POSTGRES_URL"), "PostgreSQL URL is not configured in this environment")
    def test_07_postgresql_two_processes_claim_one_job(self) -> None:
        self.skipTest("PostgreSQL integration fixture requires a dedicated isolated database and seed harness")

    def test_08_expired_claim_before_gate_returns_to_queue(self) -> None:
        queued = self._one(key="before-gate")
        job = self.repo.claim_job()
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_job_integrity SET lease_expires_at='2000-01-01T00:00:00+00:00', irreversible_at=NULL WHERE job_id=?", (job["id"],))
        recovered = MailRepository(self.db_path)
        self.assertEqual(self._status_with(recovered, queued["message_id"]), ("queued", "queued"))

    def test_09_expired_claim_after_gate_becomes_unknown(self) -> None:
        queued = self._one(key="after-gate")
        job = self.repo.claim_job()
        self.assertTrue(self.repo.enter_irreversible_stage(job["id"], job["claim_token"]))
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_job_integrity SET lease_expires_at='2000-01-01T00:00:00+00:00', irreversible_at='2000-01-01T00:00:00+00:00' WHERE job_id=?", (job["id"],))
        recovered = MailRepository(self.db_path)
        self.assertEqual(self._status_with(recovered, queued["message_id"]), ("delivery_unknown", "delivery_unknown"))

    def test_10_failed_gate_makes_no_provider_call(self) -> None:
        self._one(key="gate-fail")
        job = self.repo.claim_job()
        with patch.object(self.repo, "enter_irreversible_stage", return_value=False):
            with self.assertRaisesRegex(ProviderError, "фиксировать начало"):
                self.service.send_claimed_job(job)
        # The provider may be contacted for reversible preparation, but the
        # durable gate must remain untouched and DATA must not be reached.
        self.assertEqual(self.provider.send_calls, 1)
        self.assertIsNone(self.repo.get_job_integrity(job["id"])["irreversible_at"])

    def test_10a_pre_data_encoding_failure_is_terminal_without_delivery_unknown(self) -> None:
        self.provider.mode = "pre_data"
        queued = self._one(key="pre-data-encoding")
        job = self.repo.claim_job()
        MailQueue(self.repo, self.service, pacing=PacingSettings(min_interval_seconds=0, max_interval_seconds=0))._process(job)
        self.assertEqual(self._status(queued["message_id"]), ("failed", "failed"))
        self.assertEqual(self.provider.sent, [])
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT j.attempts, j.status, ji.irreversible_at FROM mail_jobs j "
                "JOIN mail_job_integrity ji ON ji.job_id=j.id WHERE j.id=?",
                (queued["job_id"],),
            ).fetchone()
        self.assertEqual((row["attempts"], row["status"], row["irreversible_at"]), (0, "failed", None))

    def test_11_success_then_result_db_failure_never_uses_ordinary_retry(self) -> None:
        self._one(key="db-failure")
        job = self.repo.claim_job()
        retry = Mock()
        with patch.object(self.repo, "mark_job_sent", side_effect=RuntimeError("db failed")), patch.object(self.repo, "retry_job", retry):
            MailQueue(self.repo, self.service)._process(job)
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(self.provider.copy_calls, 1)
        retry.assert_not_called()

    def test_12_transport_error_after_transfer_is_unknown_without_retry(self) -> None:
        self.provider.mode = "uncertain"
        self._one(key="transport-unknown")
        job = self.repo.claim_job()
        retry = Mock()
        with patch.object(self.repo, "retry_job", retry):
            MailQueue(self.repo, self.service)._process(job)
        self.assertEqual(self._status(job["message_id"]), ("delivery_unknown", "delivery_unknown"))
        retry.assert_not_called()

    def test_13_explicit_refusal_before_acceptance_uses_ordinary_retry(self) -> None:
        self.provider.mode = "refused"
        self._one(key="explicit-refusal")
        job = self.repo.claim_job()
        MailQueue(self.repo, self.service, max_retries=2)._process(job)
        self.assertEqual(self._status(job["message_id"]), ("queued", "queued"))

    def test_14_status_transition_keeps_job_message_and_supplier_state_atomic(self) -> None:
        queued = self._one(key="atomic")
        job = self.repo.claim_job()
        attempt = self.service.send_claimed_job(job)
        self.assertTrue(self.repo.mark_job_sent(job["id"], job["message_id"], None, attempt.message_id, attempt.sent_at.isoformat(), job["claim_token"]))
        self.assertEqual(self._status(queued["message_id"]), ("sent", "sent"))
        state = self.repo.request_statuses(self.workspace_id, 1043)[0]
        self.assertEqual(state["status"], "sent")

    def test_15_legacy_sending_without_integrity_version_becomes_unknown(self) -> None:
        queued = self._one(key="legacy-sending")
        job = self.repo.claim_job()
        with self.repo.connect() as connection:
            connection.execute("DELETE FROM mail_job_integrity WHERE job_id=?", (job["id"],))
        recovered = MailRepository(self.db_path)
        self.assertEqual(self._status_with(recovered, queued["message_id"]), ("delivery_unknown", "delivery_unknown"))

    def test_16_legacy_queued_without_integrity_version_stays_queued(self) -> None:
        queued = self._one(key="legacy-queued")
        with self.repo.connect() as connection:
            connection.execute("DELETE FROM mail_job_integrity WHERE job_id=(SELECT id FROM mail_jobs WHERE message_id=?)", (queued["message_id"],))
        recovered = MailRepository(self.db_path)
        self.assertEqual(self._status_with(recovered, queued["message_id"]), ("queued", "queued"))

    def test_17_sent_copy_failure_does_not_change_sent_status(self) -> None:
        self.provider.copy_error = True
        queued = self._one(key="copy-failure")
        job = self.repo.claim_job()
        MailQueue(self.repo, self.service)._process(job)
        self.assertEqual(self._status(queued["message_id"]), ("sent", "sent"))

    def test_18_copy_is_attempted_after_result_write_failure(self) -> None:
        self._one(key="copy-after-db-failure")
        job = self.repo.claim_job()
        with patch.object(self.repo, "mark_job_sent", side_effect=RuntimeError("db failed")):
            MailQueue(self.repo, self.service)._process(job)
        self.assertEqual(self.provider.copy_calls, 1)

    def test_19_sync_unmatched_reply_also_saves_sent_copy(self) -> None:
        inbox_id = self._incoming()
        self.service.reply_to_inbox(
            user_id=self.user_id, workspace_id=self.workspace_id, inbox_message_id=inbox_id,
            subject="Re: Новое письмо", body="Ответ",
        )
        self.assertEqual(self.provider.send_calls, 1)
        self.assertEqual(self.provider.copy_calls, 1)

    def test_20_found_verification_promotes_to_sent(self) -> None:
        queued = self._unknown(key="verify-found")
        self.provider.verify_outcome = "found"
        result = self.service.verify_delivery(user_id=self.user_id, workspace_id=self.workspace_id, message_id=queued["message_id"])
        self.assertEqual(result["outcome"], "found")
        self.assertEqual(self._status(queued["message_id"]), ("sent", "sent"))

    def test_21_not_found_or_unavailable_stays_unknown_and_not_queued(self) -> None:
        queued = self._unknown(key="verify-unknown")
        self.provider.verify_outcome = "not_found"
        self.assertEqual(self.service.verify_delivery(user_id=self.user_id, workspace_id=self.workspace_id, message_id=queued["message_id"])["outcome"], "not_found")
        self.provider.verify_outcome = "unavailable"
        self.assertEqual(self.service.verify_delivery(user_id=self.user_id, workspace_id=self.workspace_id, message_id=queued["message_id"])["outcome"], "unavailable")
        self.assertEqual(self._status(queued["message_id"]), ("delivery_unknown", "delivery_unknown"))

    def test_22_guessed_sent_folder_is_unavailable(self) -> None:
        class DummyIMAP:
            def list(self):
                return "OK", [b'(\\HasNoChildren) "/" "Sent"']

        provider = YandexMailProvider("client", "secret")
        folder, is_authoritative = provider._find_sent_folder_details(DummyIMAP())
        self.assertFalse(is_authoritative)
        self.assertIsNotNone(folder)

    def test_23_missing_message_id_is_unavailable_and_not_rewritten(self) -> None:
        queued = self._unknown(key="no-message-id")
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_messages SET message_id=NULL WHERE id=?", (queued["message_id"],))
        result = self.service.verify_delivery(user_id=self.user_id, workspace_id=self.workspace_id, message_id=queued["message_id"])
        self.assertEqual(result["outcome"], "unavailable")
        self.assertEqual(self.provider.verify_calls, 0)

    def test_24_runtime_switch_stops_already_running_queue(self) -> None:
        queued = self._one(key="runtime-queue")
        job = self.repo.claim_job()
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at='now' WHERE id=1")
        MailQueue(self.repo, self.service)._process(job)
        self.assertEqual(self.provider.send_calls, 0)
        self.assertEqual(self._status(queued["message_id"]), ("queued", "queued"))

    def test_25_runtime_switch_stops_sync_unmatched_reply(self) -> None:
        inbox_id = self._incoming("<sync-kill@example.com>")
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at='now' WHERE id=1")
        with self.assertRaisesRegex(ProviderError, "аварийным выключателем"):
            self.service.reply_to_inbox(
                user_id=self.user_id, workspace_id=self.workspace_id, inbox_message_id=inbox_id,
                subject="Re: Новое письмо", body="Ответ",
            )
        self.assertEqual(self.provider.send_calls, 0)

    def test_32_disabled_queue_does_not_spin_and_resumes_without_restart(self) -> None:
        queued = self._one(key="disabled-queue")
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at='now' WHERE id=1")
        queue = MailQueue(
            self.repo,
            self.service,
            pacing=PacingSettings(min_interval_seconds=0, max_interval_seconds=0),
        )
        try:
            queue.start()
            time.sleep(0.25)
            with self.repo.connect() as connection:
                row = connection.execute(
                    "SELECT j.status, j.attempts, ji.irreversible_at FROM mail_jobs j JOIN mail_job_integrity ji ON ji.job_id=j.id WHERE j.id=?",
                    (queued["job_id"],),
                ).fetchone()
            self.assertEqual((row["status"], row["attempts"], row["irreversible_at"]), ("queued", 0, None))
            self.assertEqual(self.provider.send_calls, 0)

            with self.repo.connect() as connection:
                connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=1, updated_at='now' WHERE id=1")
            queue.wake()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self._status(queued["message_id"]) == ("sent", "sent"):
                    break
                time.sleep(0.05)
            self.assertEqual(self._status(queued["message_id"]), ("sent", "sent"))
            self.assertEqual(len(self.provider.sent), 1)
        finally:
            queue.stop()

    def test_33_kill_switch_race_final_guard_blocks_provider_without_attempt_growth(self) -> None:
        queued = self._one(key="kill-race")
        job = self.repo.claim_job()

        def disable_switch() -> None:
            with self.repo.connect() as connection:
                connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at='now' WHERE id=1")

        self.provider.before_irreversible_hook = disable_switch
        MailQueue(self.repo, self.service)._process(job)
        self.assertEqual(self.provider.send_calls, 1)
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self._status(queued["message_id"]), ("queued", "queued"))
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT j.attempts, ji.irreversible_at FROM mail_jobs j JOIN mail_job_integrity ji ON ji.job_id=j.id WHERE j.id=?",
                (queued["job_id"],),
            ).fetchone()
        # The final callback observes the switch immediately before the
        # irreversible stage, so the claim is released without charging an
        # attempt or recording a false irreversible-stage marker.
        self.assertEqual(row["attempts"], 0)
        self.assertIsNone(row["irreversible_at"])

    def test_34_positive_data_response_survives_quit_failure(self) -> None:
        class QuitFailingSMTP:
            def __init__(self) -> None:
                self.data_payload = None

            def mail(self, _sender: str):
                return 250, b"sender accepted"

            def rcpt(self, _recipient: str):
                return 250, b"recipient accepted"

            def data(self, payload: bytes):
                self.data_payload = payload
                return 250, b"message accepted"

            def quit(self):
                raise smtplib.SMTPServerDisconnected("cleanup failed")

        provider = YandexMailProvider("client", "secret")
        smtp = QuitFailingSMTP()
        outgoing = OutgoingMessage(
            from_email="sender@yandex.ru", to_email="recipient@example.com",
            subject="Positive response", body_text="Body", body_html="<p>Body</p>",
            message_id="<positive-data@example.com>",
        )
        with patch.object(provider, "_smtp_connection", return_value=smtp):
            with self.assertLogs("mail.yandex", level="WARNING") as logs:
                result = provider.send_message("access-token", outgoing)
        self.assertEqual(result.message_id, outgoing.message_id)
        self.assertIsNotNone(smtp.data_payload)
        self.assertIn("cleanup failed", "\n".join(logs.output).lower())

    def test_35_disabled_wait_preserves_retry_budget_for_real_transport_attempt(self) -> None:
        queued = self._one(key="retry-budget-after-disabled-wait")
        with self.repo.connect() as connection:
            connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=0, updated_at='now' WHERE id=1")
        self.provider.mode = "refused"
        queue = MailQueue(
            self.repo,
            self.service,
            max_retries=2,
            pacing=PacingSettings(min_interval_seconds=0, max_interval_seconds=0),
        )
        try:
            queue.start()
            time.sleep(0.25)
            with self.repo.connect() as connection:
                row = connection.execute(
                    "SELECT attempts FROM mail_jobs WHERE id=?", (queued["job_id"],)
                ).fetchone()
            self.assertEqual(row["attempts"], 0)

            with self.repo.connect() as connection:
                connection.execute("UPDATE mail_runtime_controls SET outgoing_enabled=1, updated_at='now' WHERE id=1")
            queue.wake()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and self.provider.send_calls < 1:
                time.sleep(0.05)
            self.assertEqual(self.provider.send_calls, 1)
            with self.repo.connect() as connection:
                row = connection.execute(
                    "SELECT status, attempts, next_attempt_at FROM mail_jobs WHERE id=?", (queued["job_id"],)
                ).fetchone()
            self.assertEqual(row["status"], "queued")
            self.assertEqual(row["attempts"], 1)
            self.assertIsNotNone(row["next_attempt_at"])
        finally:
            queue.stop()

    def test_36_queue_start_does_not_block_http_startup_on_recovery(self) -> None:
        self._unknown(key="slow-recovery")
        entered = threading.Event()
        release = threading.Event()

        def blocked_recovery() -> None:
            entered.set()
            release.wait(timeout=2)

        self.service.recover_delivery_unknown = blocked_recovery
        queue = MailQueue(self.repo, self.service)
        started_at = time.monotonic()
        try:
            queue.start()
            self.assertLess(time.monotonic() - started_at, 0.5)
            self.assertTrue(entered.wait(timeout=1))
        finally:
            release.set()
            queue.stop()

    def test_26_manual_resend_creates_new_message_and_keeps_original_unknown(self) -> None:
        original = self._unknown(key="manual-resend")
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE mail_messages SET body_text=?, body_html=? WHERE id=?",
                ("Rich resend", "<p>Rich <strong>resend</strong></p>", original["message_id"]),
            )
        self.provider.verify_outcome = "not_found"
        result = self.service.resend_delivery_unknown(
            user_id=self.user_id, workspace_id=self.workspace_id, message_id=original["message_id"], confirmed=True,
        )
        self.assertTrue(result["resent"])
        self.assertEqual(self._status(original["message_id"]), ("delivery_unknown", "delivery_unknown"))
        with self.repo.connect() as connection:
            rows = connection.execute("SELECT id, message_id FROM mail_messages WHERE request_id=1043 AND direction='outbound' ORDER BY id").fetchall()
            self.assertEqual(len(rows), 2)
            self.assertNotEqual(rows[0]["message_id"], rows[1]["message_id"])
            resent = connection.execute(
                "SELECT body_text, body_html FROM mail_messages WHERE id=?", (rows[1]["id"],)
            ).fetchone()
            self.assertEqual(resent["body_text"], "Rich resend")
            self.assertIn("<strong>resend</strong>", resent["body_html"])
            link = connection.execute("SELECT resend_of_message_id FROM mail_message_integrity WHERE message_id=?", (rows[1]["id"],)).fetchone()
            self.assertEqual(link["resend_of_message_id"], original["message_id"])

    def test_27_manual_resend_is_cancelled_when_recheck_finds_original(self) -> None:
        original = self._unknown(key="manual-found")
        self.provider.verify_outcome = "found"
        result = self.service.resend_delivery_unknown(
            user_id=self.user_id, workspace_id=self.workspace_id, message_id=original["message_id"], confirmed=True,
        )
        self.assertFalse(result["resent"])
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'").fetchone()[0], 1)

    def test_28_manual_resolution_keeps_delivery_unknown_fact(self) -> None:
        queued = self._unknown(key="resolve")
        self.repo.resolve_delivery_unknown(self.workspace_id, self.user_id, queued["message_id"], "Проверено вручную")
        self.assertEqual(self._status(queued["message_id"]), ("delivery_unknown", "delivery_unknown"))
        message = self.repo.get_outbound_message(self.workspace_id, queued["message_id"])
        self.assertTrue(message["delivery_resolved"])
        supplier = next(item for item in self.repo.list_suppliers(self.workspace_id, 1043) if item["email"] == "good@example.com")
        self.assertEqual(supplier["mail_status"], "delivery_unknown")
        self.assertTrue(supplier["delivery_issue_resolved"])

    def test_29_resolution_rolls_back_when_audit_write_fails(self) -> None:
        queued = self._unknown(key="resolve-audit-failure")
        with patch.object(self.repo, "_audit_connection", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                self.repo.resolve_delivery_unknown(self.workspace_id, self.user_id, queued["message_id"])
        with self.assertRaises(DeliveryResolutionRequiredError):
            self.repo.delete_request(self.workspace_id, 1043, self.user_id)

    def test_30_delete_is_blocked_until_resolution_then_allowed(self) -> None:
        queued = self._unknown(key="delete-gate")
        with self.assertRaises(DeliveryResolutionRequiredError):
            self.repo.delete_request(self.workspace_id, 1043, self.user_id)
        self.repo.resolve_delivery_unknown(self.workspace_id, self.user_id, queued["message_id"])
        self.repo.delete_request(self.workspace_id, 1043, self.user_id)
        self.assertIsNone(self.repo.get_request(self.workspace_id, 1043))

    def test_31_resolution_snapshot_survives_request_deletion(self) -> None:
        queued = self._unknown(key="snapshot")
        self.repo.resolve_delivery_unknown(self.workspace_id, self.user_id, queued["message_id"], "Архивная запись")
        self.repo.delete_request(self.workspace_id, 1043, self.user_id)
        with self.repo.connect() as connection:
            row = connection.execute("SELECT delivery_state, recipient_email, comment FROM mail_delivery_resolutions WHERE message_id=?", (queued["message_id"],)).fetchone()
        self.assertEqual(row["delivery_state"], "delivery_unknown")
        self.assertEqual(row["recipient_email"], "good@example.com")
        self.assertEqual(row["comment"], "Архивная запись")

    @staticmethod
    def _status_with(repo: MailRepository, message_id: int) -> tuple[str, str]:
        with repo.connect() as connection:
            row = connection.execute(
                "SELECT j.status AS job_status, m.status AS message_status FROM mail_jobs j JOIN mail_messages m ON m.id=j.message_id WHERE m.id=?",
                (message_id,),
            ).fetchone()
        return row["job_status"], row["message_status"]


if __name__ == "__main__":
    unittest.main()
