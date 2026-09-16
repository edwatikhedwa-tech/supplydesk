"""Proves that resolve_effective_send_email (mail/contact_intelligence.py)
is actually consulted when a NEW outbound message is queued -- not just
correct in isolation. Closes the gap the owner flagged: AC-02 ("used in
subsequent requests of this workspace") must be true at the send path, not
only in the data model.

Priority under test: workspace preferred override -> cross-tenant global
preferred contact (DECISION-024) -> the caller-supplied fallback email
(existing, untouched behavior). A hard-bounced candidate must never be used
blindly -- it is skipped in favor of the next tier and the skip is written
to the audit log.

Fixture style follows tests/test_mail_pacing.py (real MailService, a fake
in-process SMTP provider, no real network) and
tests/test_contact_intelligence.py (real MailRepository, raw-SQL fixtures
for suppliers/global_suppliers/global_supplier_links).
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.crypto import generate_key
from mail.pacing import PacingSettings
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import SendResult, TokenSet

UTC = timezone.utc


class _FakeProvider:
    def __init__(self) -> None:
        self.sent: list[object] = []

    def send_message(self, _access_token: str, message, *, before_irreversible=None) -> SendResult:
        if before_irreversible:
            before_irreversible()
        self.sent.append(message)
        return SendResult(message_id=message.message_id or "<resolved@example.test>", provider_message_id="provider:1", sent_at=datetime.now(UTC))

    def save_sent_copy(self, *_args, **_kwargs) -> None:
        return None


class ContactResolutionSendPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "send-resolution.sqlite3")
        self.user = self.repo.seed_user("resolver-owner@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.repo.set_outgoing_enabled(True)
        self.provider = _FakeProvider()
        self.settings = PacingSettings(
            min_interval_seconds=0, max_interval_seconds=0, max_per_hour=1000, max_per_day=1000,
            reservation_lease_seconds=120, cooldown_base_seconds=2, cooldown_max_seconds=8,
            breaker_failure_threshold=3, breaker_window_seconds=60, breaker_open_seconds=30,
            retry_base_seconds=1, retry_max_seconds=8,
        )
        self.service = MailService(
            self.repo, lambda _provider, _credential=None: self.provider, generate_key(),
            daily_limit=1000, pacing_settings=self.settings,
        )
        self.account_id = self.service.save_oauth_tokens(
            user_id=self.user["id"], workspace_id=self.workspace_id,
            token_set=TokenSet("access", "refresh", 3600), email="resolver-owner@example.com",
        )
        self.request_id = self.repo.create_request(
            self.workspace_id, user_id=self.user["id"], name="Send-resolution request",
            description="", positions=[{"name": "Item", "quantity": "1"}],
            sender_name="Buyer", company_name="Company",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _add_supplier(self, *, external_key: str, email: str, inn: str) -> tuple[int, int]:
        """Returns (supplier_id, global_supplier_id). Also creates a
        mail_threads row -- record_contact_result (the "Связаться" action)
        requires an existing thread, exactly like a real needs_followup
        conversation always has one (see tests/test_contact_intelligence.py).
        """
        supplier_id = self.repo.upsert_supplier(
            workspace_id=self.workspace_id, external_key=external_key, name="Поставщик",
            email=email, host=external_key, request_id=self.request_id,
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, last_message_at, created_at)
                   VALUES (?, ?, ?, ?, ?, 'Запрос', ?, ?)""",
                (self.workspace_id, self.user["id"], self.request_id, supplier_id, self.account_id, now, now),
            )
            connection.execute(
                """INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at)
                   VALUES (?, ?, 'Поставщик', ?, ?, ?)""",
                (self.workspace_id, inn, email, now, now),
            )
            global_supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)",
                (supplier_id, global_supplier_id),
            )
        return supplier_id, global_supplier_id

    def _sent_to_email(self) -> str:
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT to_email FROM mail_messages WHERE request_id=? AND direction='outbound' ORDER BY id DESC LIMIT 1",
                (self.request_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        return str(row["to_email"])

    def test_workspace_preferred_email_is_used_for_a_new_send(self) -> None:
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="workspace-pref.example", email="stale@workspace-pref.example", inn="7711110001",
        )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="fresh@workspace-pref.example",
        )
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@workspace-pref.example", "host": "workspace-pref.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k1",
        )
        self.assertEqual(self._sent_to_email(), "fresh@workspace-pref.example")

    def test_global_preferred_used_when_no_workspace_override_exists(self) -> None:
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="global-pref.example", email="stale@global-pref.example", inn="7711110002",
        )
        # Promote a global preferred contact the same way three independent
        # workspaces + a strong signal would (see tests/test_contact_intelligence.py
        # for the full consensus proof) -- here we only need the *effect*
        # (a row with status='preferred') to test that the send path reads it.
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            company = connection.execute(
                "SELECT inn FROM global_suppliers WHERE id=?", (global_supplier_id,),
            ).fetchone()
            connection.execute(
                "INSERT INTO canonical_companies(inn, first_seen_at, updated_at) VALUES (?, ?, ?)",
                (company["inn"], now, now),
            )
            canonical_company_id = int(connection.execute(
                "SELECT id FROM canonical_companies WHERE inn=?", (company["inn"],),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO canonical_company_contacts(canonical_company_id, email, purpose, status, first_seen_at, updated_at)
                   VALUES (?, 'global-preferred@example.com', 'rfq', 'preferred', ?, ?)""",
                (canonical_company_id, now, now),
            )
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@global-pref.example", "host": "global-pref.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k2",
        )
        self.assertEqual(self._sent_to_email(), "global-preferred@example.com")

    def test_workspace_override_outranks_global_preferred(self) -> None:
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="both-exist.example", email="stale@both-exist.example", inn="7711110003",
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            company = connection.execute("SELECT inn FROM global_suppliers WHERE id=?", (global_supplier_id,)).fetchone()
            connection.execute(
                "INSERT INTO canonical_companies(inn, first_seen_at, updated_at) VALUES (?, ?, ?)",
                (company["inn"], now, now),
            )
            canonical_company_id = int(connection.execute("SELECT id FROM canonical_companies WHERE inn=?", (company["inn"],)).fetchone()[0])
            connection.execute(
                """INSERT INTO canonical_company_contacts(canonical_company_id, email, purpose, status, first_seen_at, updated_at)
                   VALUES (?, 'global-preferred@example.com', 'rfq', 'preferred', ?, ?)""",
                (canonical_company_id, now, now),
            )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="workspace-wins@both-exist.example",
        )
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@both-exist.example", "host": "both-exist.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k3",
        )
        self.assertEqual(self._sent_to_email(), "workspace-wins@both-exist.example")

    def test_hard_bounced_workspace_preferred_is_not_used_blindly(self) -> None:
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="bounced.example", email="stale@bounced.example", inn="7711110004",
        )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="bounced-address@bounced.example",
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            company = connection.execute("SELECT inn FROM global_suppliers WHERE id=?", (global_supplier_id,)).fetchone()
            canonical_company_id = int(connection.execute("SELECT id FROM canonical_companies WHERE inn=?", (company["inn"],)).fetchone()[0])
            # A real hard bounce against the workspace-preferred address, with
            # no later positive signal -- "unresolved".
            connection.execute(
                """INSERT INTO canonical_company_contact_signals(
                       canonical_company_id, email, signal_type, strength, workspace_id, source, basis, created_at
                   ) VALUES (?, 'bounced-address@bounced.example', 'hard_bounce', 'weak', ?, 'test', 'bounce', ?)""",
                (canonical_company_id, self.workspace_id, now),
            )
            # A valid, promoted global-preferred alternative exists.
            connection.execute(
                """INSERT INTO canonical_company_contacts(canonical_company_id, email, purpose, status, first_seen_at, updated_at)
                   VALUES (?, 'safe-alternative@bounced.example', 'rfq', 'preferred', ?, ?)""",
                (canonical_company_id, now, now),
            )
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@bounced.example", "host": "bounced.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k4",
        )
        # Never blindly re-used the known-bounced address.
        self.assertEqual(self._sent_to_email(), "safe-alternative@bounced.example")
        # ...and the demotion was written to the audit log, not silently applied.
        with self.repo.connect() as connection:
            audit_row = connection.execute(
                """SELECT details_json FROM audit_events
                   WHERE workspace_id=? AND action='mail.contact_resolution.demoted'
                   ORDER BY id DESC LIMIT 1""",
                (self.workspace_id,),
            ).fetchone()
        self.assertIsNotNone(audit_row)
        self.assertIn("bounced-address@bounced.example", audit_row["details_json"])

    def test_no_alternative_falls_back_to_the_hard_bounced_workspace_override(self) -> None:
        """If the workspace-preferred address bounced hard and there is no
        safer alternative anywhere, the existing fallback (the address the
        caller supplied) is used -- resolution never invents an address and
        never blocks the send outright; it only avoids blindly preferring a
        known-bad one over a better option when one exists."""
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="only-bounced.example", email="fallback@only-bounced.example", inn="7711110005",
        )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="bounced-address@only-bounced.example",
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            company = connection.execute("SELECT inn FROM global_suppliers WHERE id=?", (global_supplier_id,)).fetchone()
            canonical_company_id = int(connection.execute("SELECT id FROM canonical_companies WHERE inn=?", (company["inn"],)).fetchone()[0])
            connection.execute(
                """INSERT INTO canonical_company_contact_signals(
                       canonical_company_id, email, signal_type, strength, workspace_id, source, basis, created_at
                   ) VALUES (?, 'bounced-address@only-bounced.example', 'hard_bounce', 'weak', ?, 'test', 'bounce', ?)""",
                (canonical_company_id, self.workspace_id, now),
            )
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "fallback@only-bounced.example", "host": "only-bounced.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k5",
        )
        self.assertEqual(self._sent_to_email(), "fallback@only-bounced.example")

    def test_a_fresh_recipient_with_no_stored_supplier_id_is_unaffected(self) -> None:
        """Existing behavior for a brand-new campaign target (never stored as
        a supplier row before) must be completely untouched."""
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"name": "Новый", "email": "brand-new@example.com", "host": "example.com", "external_key": "brand-new.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k6",
        )
        self.assertEqual(self._sent_to_email(), "brand-new@example.com")

    def test_another_workspace_never_sees_this_workspaces_override(self) -> None:
        """Same real-world company (same ИНН), two separate workspaces.
        Workspace A sets a preferred-contact override; workspace B's own
        supplier row for the same company must resolve to its OWN fallback,
        not workspace A's override -- a single workspace's confirmation
        never promotes a cross-tenant global preferred contact (AC-05), so
        there is nothing for workspace B to legitimately inherit yet.
        """
        inn = "7711110006"
        supplier_a, _ = self._add_supplier(external_key="shared-company-a.example", email="a-fallback@shared.example", inn=inn)
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_a,
            result="new_email_provided", new_email="workspace-a-only@shared.example",
        )

        other_user = self.repo.seed_user("resolver-other@example.com", "correct-horse")
        other_workspace_id = int(other_user["workspace_id"])
        self.assertNotEqual(other_workspace_id, self.workspace_id)
        self.repo.set_outgoing_enabled(True)
        self.service.save_oauth_tokens(
            user_id=other_user["id"], workspace_id=other_workspace_id,
            token_set=TokenSet("access", "refresh", 3600), email="resolver-other@example.com",
        )
        other_request_id = self.repo.create_request(
            other_workspace_id, user_id=other_user["id"], name="Other workspace request",
            description="", positions=[{"name": "Item", "quantity": "1"}],
            sender_name="Buyer", company_name="Company",
        )
        supplier_b = self.repo.upsert_supplier(
            workspace_id=other_workspace_id, external_key="shared-company-b.example", name="Поставщик",
            email="b-fallback@shared.example", host="shared-company-b.example", request_id=other_request_id,
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at)
                   VALUES (?, ?, 'Поставщик', ?, ?, ?)""",
                (other_workspace_id, inn, "b-fallback@shared.example", now, now),
            )
            global_supplier_id_b = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)",
                (supplier_b, global_supplier_id_b),
            )

        self.service.queue_one(
            user_id=other_user["id"], workspace_id=other_workspace_id, request_id=other_request_id,
            supplier={"id": supplier_b, "name": "Поставщик", "email": "b-fallback@shared.example", "host": "shared-company-b.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="k7",
        )
        with self.repo.connect() as connection:
            row = connection.execute(
                "SELECT to_email FROM mail_messages WHERE request_id=? AND direction='outbound' ORDER BY id DESC LIMIT 1",
                (other_request_id,),
            ).fetchone()
        self.assertEqual(str(row["to_email"]), "b-fallback@shared.example")


if __name__ == "__main__":
    unittest.main()
