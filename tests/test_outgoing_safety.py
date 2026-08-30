from __future__ import annotations

import http.client
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import supplier_app
from mail.crypto import generate_key
from mail.pacing import PacingSettings
from mail.queue import MailQueue
from mail.repository import MailRepository, iso_now
from mail.runtime import RuntimeSession
from mail.service import MailService
from mail.types import OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet


class SafetyProvider:
    name = "fake-safety"

    def __init__(self) -> None:
        self.send_calls = 0
        self.sent: list[OutgoingMessage] = []

    def get_account(self, access_token: str) -> ProviderAccount:
        return ProviderAccount("owner@example.com")

    def send_message(self, access_token: str, message: OutgoingMessage, *, before_irreversible=None) -> SendResult:
        self.send_calls += 1
        if before_irreversible is not None:
            before_irreversible()
        self.sent.append(message)
        return SendResult(
            message.message_id or "<fake-safety@example.com>",
            "fake-provider-message",
            datetime.now(timezone.utc),
        )

    def save_sent_copy(self, access_token: str, message: OutgoingMessage, result: SendResult) -> None:
        return None


class OutgoingSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {"SUPPLYDESK_ENV": "test", "MAIL_OUTGOING_DISABLED": "0", "DATABASE_URL": ""},
            clear=False,
        )
        self.env_patch.start()
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "safety.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()
        self.env_patch.stop()

    def _repo(self) -> MailRepository:
        return MailRepository(self.db_path)

    def _owner(self, repo: MailRepository) -> dict[str, int | str]:
        return repo.seed_user("owner@example.com", "correct-horse")

    def _service_with_account(self, repo: MailRepository, provider: SafetyProvider) -> tuple[MailService, dict, int]:
        user = self._owner(repo)
        pacing = PacingSettings(min_interval_seconds=0, max_interval_seconds=0)
        service = MailService(
            repo,
            lambda *_args: provider,
            generate_key(),
            pacing_settings=pacing,
            daily_limit=1000,
        )
        account_id = service.save_oauth_tokens(
            user_id=int(user["id"]),
            workspace_id=int(user["workspace_id"]),
            token_set=TokenSet("access", "refresh", 3600),
            email="owner@example.com",
        )
        return service, user, account_id

    def test_clean_database_and_missing_control_are_disabled(self) -> None:
        repo = self._repo()
        with repo.connect() as connection:
            column = connection.execute(
                "SELECT dflt_value FROM pragma_table_info('mail_runtime_controls') WHERE name='outgoing_enabled'"
            ).fetchone()[0]
            stored = connection.execute(
                "SELECT outgoing_enabled FROM mail_runtime_controls WHERE id=1"
            ).fetchone()[0]
        self.assertEqual(str(column).strip("'"), "0")
        self.assertEqual(stored, 0)
        self.assertFalse(repo.outgoing_enabled())

        with repo.connect() as connection:
            connection.execute("DELETE FROM mail_runtime_controls WHERE id=1")
        self.assertFalse(repo.outgoing_enabled())

    def test_false_malformed_and_restart_states_are_disabled(self) -> None:
        repo = self._repo()
        repo.set_outgoing_enabled(False)
        self.assertFalse(repo.outgoing_enabled())
        with repo.connect() as connection:
            connection.execute(
                "UPDATE mail_runtime_controls SET outgoing_enabled=?, updated_at=? WHERE id=1",
                ("corrupt", iso_now()),
            )
        self.assertFalse(repo.outgoing_enabled())

        with repo.connect() as connection:
            connection.execute("DELETE FROM mail_runtime_controls WHERE id=1")
        restarted = MailRepository(self.db_path)
        self.assertFalse(restarted.outgoing_enabled())

    def test_control_database_error_is_disabled(self) -> None:
        repo = self._repo()
        with patch.object(repo, "connect", side_effect=sqlite3.OperationalError("simulated database outage")):
            self.assertFalse(repo.outgoing_enabled())

    def test_missing_account_profile_is_disabled(self) -> None:
        repo = self._repo()
        user = self._owner(repo)
        account_id = repo.save_mail_account(
            user_id=int(user["id"]),
            workspace_id=int(user["workspace_id"]),
            provider="yandex",
            email="owner@example.com",
            access_token_encrypted="encrypted-access",
            refresh_token_encrypted="encrypted-refresh",
            token_expires_at="2099-01-01T00:00:00+00:00",
        )
        with repo.connect() as connection:
            connection.execute("DELETE FROM mail_account_profiles WHERE account_id=?", (account_id,))
        account = repo.get_mail_account(int(user["id"]), int(user["workspace_id"]), "yandex")
        self.assertEqual(account["account_outgoing_enabled"], 0)

    def test_running_runtime_refreshes_explicit_control_without_restart(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            db_path = root / "runtime.sqlite3"
            with patch.dict(
                os.environ,
                {
                    "SUPPLYDESK_ENV": "production",
                    "MAIL_OUTGOING_DISABLED": "0",
                    "MAIL_DB_PATH": str(db_path),
                    "SUPPLYDESK_CANONICAL_DB_PATH": str(db_path),
                },
                clear=False,
            ):
                repo = MailRepository(db_path)
                user = self._owner(repo)
                runtime = RuntimeSession.start(
                    environment="production",
                    db_path=db_path,
                    canonical_db_path=db_path,
                    repository=repo,
                    root=root,
                )
                try:
                    service = MailService(repo, lambda *_args: SafetyProvider(), None, runtime=runtime)
                    self.assertFalse(service.outgoing_enabled())
                    result = service.set_outgoing_enabled(
                        user_id=int(user["id"]),
                        workspace_id=int(user["workspace_id"]),
                        enabled=True,
                        confirmation=True,
                    )
                    self.assertTrue(result["durable_outgoing_enabled"])
                    self.assertTrue(result["effective_outgoing_enabled"])
                    self.assertTrue(service.outgoing_enabled())
                finally:
                    runtime.close()

    def test_owner_endpoint_requires_csrf_confirmation_and_explicit_owner(self) -> None:
        harness = _EndpointHarness(self.db_path)
        try:
            status, _ = harness.post(
                "/api/mail/runtime/outgoing", {"enabled": True, "confirmation": True}, authenticated=False,
            )
            self.assertEqual(status, 401)
            status, _ = harness.post(
                "/api/mail/runtime/outgoing", {"enabled": True, "confirmation": True}, authenticated=True, csrf=False,
            )
            self.assertEqual(status, 403)
            status, _ = harness.post(
                "/api/mail/runtime/outgoing", {"enabled": "true", "confirmation": True}, authenticated=True,
            )
            self.assertEqual(status, 400)
            status, _ = harness.post(
                "/api/mail/runtime/outgoing", {"enabled": True, "confirmation": False}, authenticated=True,
            )
            self.assertEqual(status, 400)

            status, payload = harness.post(
                "/api/mail/runtime/outgoing", {"enabled": True, "confirmation": True}, authenticated=True,
            )
            self.assertEqual(status, 200)
            self.assertTrue(payload["durable_outgoing_enabled"])
            # A test runtime is intentionally not eligible to own live SMTP.
            self.assertFalse(payload["effective_outgoing_enabled"])
        finally:
            harness.close()

    def test_member_cannot_change_outgoing_control(self) -> None:
        harness = _EndpointHarness(self.db_path)
        try:
            with harness.app.repository.connect() as connection:
                connection.execute(
                    "UPDATE workspace_members SET role='member' WHERE user_id=? AND workspace_id=?",
                    (harness.user["id"], harness.user["workspace_id"]),
                )
            status, _ = harness.post(
                "/api/mail/runtime/outgoing", {"enabled": True, "confirmation": True}, authenticated=True,
            )
            self.assertEqual(status, 403)
            self.assertFalse(harness.app.repository.outgoing_enabled())
        finally:
            harness.close()

    def test_importing_vercel_adapter_does_not_start_queue(self) -> None:
        import mail.queue as queue_module

        import_temp = tempfile.TemporaryDirectory()
        import_db = str(Path(import_temp.name) / "import.sqlite3")
        module_name = "_supplydesk_api_index_import_safety_test"
        spec = importlib.util.spec_from_file_location(module_name, Path(__file__).parents[1] / "api" / "index.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        try:
            with patch.dict(
                os.environ,
                {
                    "SUPPLYDESK_ENV": "test",
                    "MAIL_DB_PATH": import_db,
                    "SUPPLYDESK_CANONICAL_DB_PATH": import_db,
                    "APP_USER_EMAIL": "",
                    "APP_USER_PASSWORD": "",
                    "MAIL_TOKEN_ENCRYPTION_KEY": "",
                    "MAIL_OUTGOING_DISABLED": "1",
                    "DATABASE_URL": "",
                },
                clear=False,
            ), patch.object(queue_module.MailQueue, "start") as queue_start:
                spec.loader.exec_module(module)
                queue_start.assert_not_called()
        finally:
            runtime = getattr(getattr(module, "_APP", None), "runtime", None)
            if runtime is not None:
                runtime.close()
            import_temp.cleanup()
            sys.modules.pop(module_name, None)

    def test_eighty_four_queued_jobs_stay_queued_when_outgoing_is_off(self) -> None:
        repo = self._repo()
        provider = SafetyProvider()
        service, user, _account_id = self._service_with_account(repo, provider)
        suppliers = [
            {
                "name": f"Synthetic {index}",
                "email": f"synthetic-{index}@example.com",
                "host": f"synthetic-{index}.example.com",
            }
            for index in range(84)
        ]
        queued = service.queue_bulk(
            user_id=int(user["id"]),
            workspace_id=int(user["workspace_id"]),
            request_id=1043,
            suppliers=suppliers,
            subject="Safety test",
            body="No real delivery",
            idempotency_key="safety-84",
        )
        self.assertEqual(len(queued), 84)
        queue = MailQueue(repo, service, pacing=service.pacing_settings)
        queue.start()
        try:
            time.sleep(0.35)
        finally:
            queue.stop()
        with repo.connect() as connection:
            counts = connection.execute(
                "SELECT status, COUNT(*) AS count FROM mail_jobs GROUP BY status"
            ).fetchall()
            attempts = connection.execute("SELECT COALESCE(SUM(attempts), 0) FROM mail_jobs").fetchone()[0]
        self.assertEqual({row["status"]: row["count"] for row in counts}, {"queued": 84})
        self.assertEqual(attempts, 0)
        self.assertEqual(provider.send_calls, 0)

    def test_explicit_enable_allows_one_fake_provider_delivery(self) -> None:
        repo = self._repo()
        provider = SafetyProvider()
        service, user, _account_id = self._service_with_account(repo, provider)
        # This is a provider-neutral unit harness, not an application runtime.
        # The real configured test runtime remains blocked by RuntimeSession.
        with patch.dict(os.environ, {"SUPPLYDESK_ENV": ""}):
            self.assertFalse(service.outgoing_enabled())
            result = service.set_outgoing_enabled(
                user_id=int(user["id"]),
                workspace_id=int(user["workspace_id"]),
                enabled=True,
                confirmation=True,
            )
            self.assertTrue(result["durable_outgoing_enabled"])
            self.assertTrue(service.outgoing_enabled())
            queued = service.queue_one(
                user_id=int(user["id"]),
                workspace_id=int(user["workspace_id"]),
                request_id=1043,
                supplier={"name": "Explicit", "email": "explicit@example.com", "host": "explicit.example"},
                subject="Safety test",
                body="Fake provider only",
                idempotency_key="safety-explicit",
            )
            queue = MailQueue(repo, service, pacing=service.pacing_settings)
            queue.start()
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and provider.send_calls < 1:
                    time.sleep(0.05)
            finally:
                queue.stop()
        self.assertEqual(provider.send_calls, 1)
        with repo.connect() as connection:
            status = connection.execute(
                "SELECT status FROM mail_jobs WHERE id=?", (queued["job_id"],)
            ).fetchone()[0]
        self.assertEqual(status, "sent")

    def test_configured_test_runtime_without_runtime_authority_stays_off(self) -> None:
        repo = self._repo()
        repo.set_outgoing_enabled(True)
        service = MailService(repo, lambda *_args: SafetyProvider(), None)
        self.assertFalse(service.outgoing_enabled())
        with self.assertRaisesRegex(ProviderError, "runtime"):
            service._assert_outgoing_allowed()


class _EndpointHarness:
    def __init__(self, db_path: Path) -> None:
        self.app = supplier_app.SupplierApp(
            supplier_app.Config(
                host="127.0.0.1",
                port=0,
                base_url="http://127.0.0.1",
                redirect_uri="http://127.0.0.1/oauth/yandex/callback",
                db_path=str(db_path),
                encryption_key=generate_key(),
                app_user_email=None,
                app_user_password=None,
                session_cookie_secure=False,
                queue_concurrency=1,
                max_retries=2,
                daily_limit=1000,
                environment="test",
            )
        )
        self.user = self.app.repository.seed_user("endpoint-owner@example.com", "correct-horse")
        self.session_token, self.csrf_token = self.app.repository.create_session(
            self.user["id"], self.user["workspace_id"],
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), supplier_app.SupplierHandler)
        self.server.app = self.app  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = int(self.server.server_address[1])

    def post(self, path: str, payload: dict, *, authenticated: bool, csrf: bool = True) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Cookie"] = f"session_id={self.session_token}"
            if csrf:
                headers["X-CSRF-Token"] = self.csrf_token
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("POST", path, body=json.dumps(payload), headers=headers)
            response = connection.getresponse()
            return int(response.status), json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.app.runtime.close()
