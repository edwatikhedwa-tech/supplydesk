from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mail.crypto import generate_key
from mail.pacing import PacingSettings
from mail.repository import MailRepository
from mail.runtime import RuntimeSession
from mail.service import MailService
from mail.types import ProviderError, TokenSet
from scripts.supplier_identity_audit import backup_database


class CanonicalRuntimeTests(unittest.TestCase):
    def test_production_runtime_owns_one_lock_and_manifest_has_no_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            db_path = root / "supplier.sqlite3"
            environment = {
                "SUPPLYDESK_ENV": "production",
                "MAIL_OUTGOING_DISABLED": "1",
                "MAIL_DB_PATH": str(db_path),
                "SUPPLYDESK_CANONICAL_DB_PATH": str(db_path),
            }
            with patch.dict("os.environ", environment, clear=False):
                repo = MailRepository(db_path)
                first = RuntimeSession.start(
                    environment="production", db_path=db_path,
                    canonical_db_path=db_path, repository=repo, root=root,
                )
                second = RuntimeSession.start(
                    environment="production", db_path=db_path,
                    canonical_db_path=db_path, repository=MailRepository(db_path), root=root,
                )
                try:
                    self.assertTrue(first.live_mail_lock_acquired)
                    self.assertFalse(second.live_mail_lock_acquired)
                    self.assertFalse(first.outgoing_allowed)
                    self.assertIn("live-mail runtime lock is not owned", second.transport_block_reason() or "")
                    manifest = json.loads((root / "runtime" / "canonical_manifest.json").read_text(encoding="utf-8"))
                    self.assertEqual(len(manifest["database_sha256"]), 64)
                    self.assertEqual(manifest["manifest_role"], "canonical")
                    self.assertNotIn("access_token", manifest)
                    self.assertNotIn("refresh_token", manifest)
                finally:
                    second.close()
                    first.close()

    def test_noncanonical_runtime_blocks_before_provider(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            db_path = root / "supplier.sqlite3"
            canonical_path = root / "another.sqlite3"
            with patch.dict(
                "os.environ",
                {
                    "SUPPLYDESK_ENV": "production",
                    "MAIL_OUTGOING_DISABLED": "0",
                    "MAIL_DB_PATH": str(db_path),
                    "SUPPLYDESK_CANONICAL_DB_PATH": str(canonical_path),
                },
                clear=False,
            ):
                repo = MailRepository(db_path)
                # Exercise the non-canonical runtime gate after the durable
                # control itself has been explicitly enabled in this fixture.
                repo.set_outgoing_enabled(True)
                runtime = RuntimeSession.start(
                    environment="production", db_path=db_path,
                    canonical_db_path=canonical_path, repository=repo, root=root,
                )
                try:
                    factory = Mock()
                    service = MailService(repo, factory, None, runtime=runtime)
                    with self.assertRaises(ProviderError) as raised:
                        service._assert_outgoing_allowed()
                    self.assertEqual(raised.exception.provider_code, "operational_blocked_noncanonical_runtime")
                    factory.assert_not_called()
                finally:
                    runtime.close()

    def test_noncanonical_runtime_writes_only_its_session_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            canonical_db = root / "canonical.sqlite3"
            temporary_db = root / "Temp" / "copy.sqlite3"
            temporary_db.parent.mkdir()
            environment = {
                "SUPPLYDESK_ENV": "production",
                "MAIL_OUTGOING_DISABLED": "1",
                "MAIL_DB_PATH": str(canonical_db),
                "SUPPLYDESK_CANONICAL_DB_PATH": str(canonical_db),
            }
            with patch.dict("os.environ", environment, clear=False):
                canonical_repo = MailRepository(canonical_db)
                canonical = RuntimeSession.start(
                    environment="production", db_path=canonical_db,
                    canonical_db_path=canonical_db, repository=canonical_repo, root=root,
                )
                try:
                    canonical_manifest = root / "runtime" / "canonical_manifest.json"
                    before = canonical_manifest.read_text(encoding="utf-8")
                    temporary_repo = MailRepository(temporary_db)
                    noncanonical = RuntimeSession.start(
                        environment="production", db_path=temporary_db,
                        canonical_db_path=canonical_db, repository=temporary_repo, root=root,
                    )
                    try:
                        self.assertFalse(noncanonical.canonical_check_passed)
                        self.assertEqual(canonical_manifest.read_text(encoding="utf-8"), before)
                        session_manifest = root / "runtime" / "sessions" / f"{noncanonical.runtime_id}.json"
                        self.assertEqual(json.loads(session_manifest.read_text(encoding="utf-8"))["manifest_role"], "session")
                        self.assertTrue(canonical.authoritative_session_valid())
                    finally:
                        noncanonical.close()
                finally:
                    canonical.close()

    def test_corrupt_canonical_manifest_does_not_revoke_authoritative_session(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            db_path = root / "supplier.sqlite3"
            with patch.dict(
                "os.environ",
                {
                    "SUPPLYDESK_ENV": "production",
                    "MAIL_OUTGOING_DISABLED": "1",
                    "MAIL_DB_PATH": str(db_path),
                    "SUPPLYDESK_CANONICAL_DB_PATH": str(db_path),
                },
                clear=False,
            ):
                repo = MailRepository(db_path)
                runtime = RuntimeSession.start(
                    environment="production", db_path=db_path,
                    canonical_db_path=db_path, repository=repo, root=root,
                )
                try:
                    runtime.canonical_manifest_path.write_text("{broken", encoding="utf-8")
                    self.assertTrue(runtime.authoritative_session_valid())
                    self.assertFalse(runtime.outgoing_allowed)
                finally:
                    runtime.close()

    def test_irreversible_attempt_records_runtime_provenance(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            db_path = root / "supplier.sqlite3"
            with patch.dict(
                "os.environ",
                {
                    "SUPPLYDESK_ENV": "production",
                    "MAIL_OUTGOING_DISABLED": "0",
                    "MAIL_DB_PATH": str(db_path),
                    "SUPPLYDESK_CANONICAL_DB_PATH": str(db_path),
                },
                clear=False,
            ):
                repo = MailRepository(db_path)
                runtime = RuntimeSession.start(
                    environment="production", db_path=db_path,
                    canonical_db_path=db_path, repository=repo, root=root,
                )
                try:
                    user = repo.seed_user("runtime@example.com", "correct-horse")
                    service = MailService(repo, lambda _provider: Mock(), generate_key(), runtime=runtime)
                    account_id = service.save_oauth_tokens(
                        user_id=user["id"], workspace_id=user["workspace_id"],
                        token_set=TokenSet("access", "refresh", 3600), email="runtime@yandex.ru",
                    )
                    request_id = repo.create_request(
                        user["workspace_id"], user_id=user["id"], name="Runtime",
                        description="Runtime", positions=[{"name": "Item", "quantity": "1"}],
                        sender_name="Buyer", company_name="Company",
                    )
                    supplier_id = repo.upsert_supplier(
                        workspace_id=user["workspace_id"], external_key="runtime-supplier",
                        name="Runtime Supplier", email="supplier@example.com", host="example.com",
                        request_id=request_id,
                    )
                    service.queue_one(
                        user_id=user["id"], workspace_id=user["workspace_id"], request_id=request_id,
                        supplier={"id": supplier_id, "name": "Runtime Supplier", "email": "supplier@example.com", "host": "example.com", "external_key": "runtime-supplier"},
                        subject="Runtime", body="Body", idempotency_key="runtime-job",
                        mail_account_id=account_id,
                    )
                    claimed = repo.claim_job(pacing=PacingSettings(min_interval_seconds=0, max_interval_seconds=0, max_per_hour=100, max_per_day=100))
                    self.assertIsNotNone(claimed)
                    assert claimed is not None
                    self.assertTrue(repo.enter_irreversible_stage(
                        claimed["id"], claimed["claim_token"], claimed["pacing_reservation_token"],
                        runtime_provenance=runtime.provenance(),
                    ))
                    with repo.connect() as connection:
                        row = connection.execute(
                            "SELECT runtime_id, db_identity, canonical_check_passed FROM mail_send_attempt_runtime"
                        ).fetchone()
                    self.assertEqual(row["runtime_id"], runtime.runtime_id)
                    self.assertEqual(row["db_identity"], runtime.database_uuid)
                    self.assertEqual(int(row["canonical_check_passed"]), 1)
                finally:
                    runtime.close()

    def test_reconciliation_is_idempotent_and_changes_only_provider_neutral_view(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = MailRepository(Path(directory) / "reconcile.sqlite3")
            user = repo.seed_user("reconcile@example.com", "correct-horse")
            service = MailService(repo, lambda _provider: Mock(), generate_key())
            account_id = service.save_oauth_tokens(
                user_id=user["id"], workspace_id=user["workspace_id"],
                token_set=TokenSet("access", "refresh", 3600), email="reconcile@yandex.ru",
            )
            request_id = repo.create_request(
                user["workspace_id"], user_id=user["id"], name="Reconciliation",
                description="Reconciliation", positions=[{"name": "Item", "quantity": "1"}],
                sender_name="Buyer", company_name="Company",
            )
            supplier_id = repo.upsert_supplier(
                workspace_id=user["workspace_id"], external_key="tmf-shop.ru",
                name="TMF", email="info@tmf-shop.ru", host="tmf-shop.ru", request_id=request_id,
            )
            queued = service.queue_one(
                user_id=user["id"], workspace_id=user["workspace_id"], request_id=request_id,
                supplier={"id": supplier_id, "name": "TMF", "email": "info@tmf-shop.ru", "host": "tmf-shop.ru", "external_key": "tmf-shop.ru"},
                subject="Reconciliation", body="Body", idempotency_key="reconcile-job", mail_account_id=account_id,
            )
            kwargs = {
                "request_id": request_id,
                "supplier_id": supplier_id,
                "normalized_recipient": "info@tmf-shop.ru",
                "provider_type": "mailru",
                "rfc_message_id": "<historical@mail.ru>",
                "accepted_at": "2026-08-30T10:00:00+00:00",
                "evidence_type": "verified_backup_row",
                "evidence_reference": "supplier.20260830T100322488891Z.bak.sqlite3",
                "evidence_sha256": "a" * 64,
                "created_by": "test",
                "operator_reason": "verified historical acceptance",
            }
            first = repo.reconcile_outbound_event(**kwargs)
            second = repo.reconcile_outbound_event(**kwargs)
            summary = repo.campaign_summary(user["workspace_id"], queued["campaign_id"])
            self.assertFalse(first["already_reconciled"])
            self.assertTrue(second["already_reconciled"])
            self.assertEqual(len(repo.list_reconciled_outbound_events(request_id)), 1)
            self.assertEqual(summary["accepted"], 1)
            self.assertEqual(summary["accepted_reconciled"], 1)
            self.assertEqual(summary["accepted_in_campaign"], 0)

    def test_backup_writes_source_identity_and_hash_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "supplier.sqlite3"
            MailRepository(db_path)
            backup_path = backup_database(db_path)
            metadata = json.loads(
                backup_path.with_name(backup_path.name + ".metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["source_path"], str(db_path.resolve()))
            self.assertTrue(metadata["source_database_uuid"])
            self.assertEqual(len(metadata["source_sha256"]), 64)
            self.assertEqual(len(metadata["backup_sha256"]), 64)
            self.assertEqual(metadata["backup_integrity"], "ok")

    def test_canonical_start_closes_dead_runtime_session_records(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            db_path = root / "supplier.sqlite3"
            environment = {
                "SUPPLYDESK_ENV": "production",
                "MAIL_OUTGOING_DISABLED": "1",
                "MAIL_DB_PATH": str(db_path),
                "SUPPLYDESK_CANONICAL_DB_PATH": str(db_path),
            }
            with patch.dict("os.environ", environment, clear=False):
                repo = MailRepository(db_path)
                repo.create_runtime_session(
                    runtime_id="dead-runtime",
                    environment="production",
                    started_at="2026-08-30T10:00:00+00:00",
                    pid=99999999,
                    cwd=str(root),
                    db_path=str(db_path.resolve()),
                    db_identity=repo.get_database_identity()["database_uuid"],
                    git_revision=None,
                    outgoing_allowed=False,
                    canonical_check_passed=True,
                    live_mail_lock_acquired=True,
                )
                runtime = RuntimeSession.start(
                    environment="production", db_path=db_path,
                    canonical_db_path=db_path, repository=repo, root=root,
                )
                try:
                    with repo.connect() as connection:
                        ended_at = connection.execute(
                            "SELECT ended_at FROM mail_runtime_sessions WHERE runtime_id='dead-runtime'"
                        ).fetchone()["ended_at"]
                    self.assertTrue(ended_at)
                finally:
                    runtime.close()


if __name__ == "__main__":
    unittest.main()
