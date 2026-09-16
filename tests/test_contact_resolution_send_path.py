"""Proves that resolve_contact_priority (mail/contact_intelligence.py) is
actually consulted when a NEW outbound message is queued -- not just
correct in isolation -- AND that preflight_bulk's campaign preview and the
real send that follows it always agree, because both call the exact same
shared, side-effect-free resolver at the same point in their respective
pipelines (FINDING-037). Closes the gap the owner flagged: AC-02 ("used in
subsequent requests of this workspace") must be true at the send path, not
only in the data model.

Priority under test: workspace preferred override -> cross-tenant global
preferred contact (DECISION-024) -> the caller-supplied fallback email
(existing, untouched behavior). A hard-bounced candidate must never be used
blindly -- it is skipped in favor of the next tier and the skip is written
to the audit log, once, only by the real send (never by the read-only
preview).

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

    def _preflight_eligible_email(self, *, supplier_id: int, email: str, host: str,
                                   workspace_id: int | None = None, user_id: int | None = None,
                                   request_id: int | None = None) -> str:
        """Runs the exact same read-only campaign preview the composer UI
        would show before sending, and returns the one eligible recipient's
        resolved email -- the same field `queue_bulk` will actually send to.
        """
        preview = self.service.preflight_bulk(
            user_id=user_id if user_id is not None else self.user["id"],
            workspace_id=workspace_id if workspace_id is not None else self.workspace_id,
            request_id=request_id if request_id is not None else self.request_id,
            suppliers=[{"id": supplier_id, "name": "Поставщик", "email": email, "host": host}],
            subject="Запрос", body="Текст запроса.",
        )
        eligible = [r for r in preview["recipient_results"] if r["status"] == "eligible"]
        self.assertEqual(len(eligible), 1, msg=f"expected exactly one eligible recipient, got {preview['recipient_results']}")
        preview_targets = {p["to_email"] for p in preview["previews"]}
        self.assertIn(eligible[0]["email"], preview_targets)
        return str(eligible[0]["email"])

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

    def test_workspace_preferred_is_shown_in_preview_and_used_at_send(self) -> None:
        supplier_id, _ = self._add_supplier(
            external_key="preview-ws.example", email="stale@preview-ws.example", inn="7711110007",
        )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="fresh@preview-ws.example",
        )
        previewed_email = self._preflight_eligible_email(
            supplier_id=supplier_id, email="stale@preview-ws.example", host="preview-ws.example",
        )
        self.assertEqual(previewed_email, "fresh@preview-ws.example")
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@preview-ws.example", "host": "preview-ws.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="pv1",
        )
        self.assertEqual(self._sent_to_email(), previewed_email)

    def test_global_preferred_is_shown_in_preview_and_used_at_send(self) -> None:
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="preview-global.example", email="stale@preview-global.example", inn="7711110008",
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
                   VALUES (?, 'global-preview-preferred@example.com', 'rfq', 'preferred', ?, ?)""",
                (canonical_company_id, now, now),
            )
        previewed_email = self._preflight_eligible_email(
            supplier_id=supplier_id, email="stale@preview-global.example", host="preview-global.example",
        )
        self.assertEqual(previewed_email, "global-preview-preferred@example.com")
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@preview-global.example", "host": "preview-global.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="pv2",
        )
        self.assertEqual(self._sent_to_email(), previewed_email)

    def test_hard_bounced_preferred_is_not_shown_as_final_in_preview_when_a_safer_alternative_exists(self) -> None:
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="preview-bounced.example", email="stale@preview-bounced.example", inn="7711110009",
        )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="bounced-preview@preview-bounced.example",
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            company = connection.execute("SELECT inn FROM global_suppliers WHERE id=?", (global_supplier_id,)).fetchone()
            canonical_company_id = int(connection.execute("SELECT id FROM canonical_companies WHERE inn=?", (company["inn"],)).fetchone()[0])
            connection.execute(
                """INSERT INTO canonical_company_contact_signals(
                       canonical_company_id, email, signal_type, strength, workspace_id, source, basis, created_at
                   ) VALUES (?, 'bounced-preview@preview-bounced.example', 'hard_bounce', 'weak', ?, 'test', 'bounce', ?)""",
                (canonical_company_id, self.workspace_id, now),
            )
            connection.execute(
                """INSERT INTO canonical_company_contacts(canonical_company_id, email, purpose, status, first_seen_at, updated_at)
                   VALUES (?, 'safe-preview-alternative@preview-bounced.example', 'rfq', 'preferred', ?, ?)""",
                (canonical_company_id, now, now),
            )
        previewed_email = self._preflight_eligible_email(
            supplier_id=supplier_id, email="stale@preview-bounced.example", host="preview-bounced.example",
        )
        self.assertEqual(previewed_email, "safe-preview-alternative@preview-bounced.example")
        # The read-only preview must never itself write an audit-log demotion
        # entry -- only a real send does that, once, when it commits.
        with self.repo.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS n FROM audit_events WHERE workspace_id=? AND action='mail.contact_resolution.demoted'",
                (self.workspace_id,),
            ).fetchone()["n"]
        self.assertEqual(int(count), 0)
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@preview-bounced.example", "host": "preview-bounced.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="pv3",
        )
        self.assertEqual(self._sent_to_email(), previewed_email)
        with self.repo.connect() as connection:
            count_after_send = connection.execute(
                "SELECT COUNT(*) AS n FROM audit_events WHERE workspace_id=? AND action='mail.contact_resolution.demoted'",
                (self.workspace_id,),
            ).fetchone()["n"]
        self.assertEqual(int(count_after_send), 1)

    def test_preview_and_direct_resolver_call_agree_with_the_actual_send(self) -> None:
        """The literal same-state consistency check: calling the shared
        resolver directly, calling it through preflight_bulk's preview, and
        calling it through an actual queue_one send must all return the
        exact same address while nothing about the underlying data changes
        in between.
        """
        supplier_id, global_supplier_id = self._add_supplier(
            external_key="triple-check.example", email="stale@triple-check.example", inn="7711110011",
        )
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_id,
            result="new_email_provided", new_email="agreed@triple-check.example",
        )
        direct = self.repo.resolve_contact_priority(
            self.workspace_id, supplier_id, fallback_email="stale@triple-check.example",
        )
        self.assertEqual(direct["email"], "agreed@triple-check.example")
        previewed_email = self._preflight_eligible_email(
            supplier_id=supplier_id, email="stale@triple-check.example", host="triple-check.example",
        )
        self.service.queue_one(
            user_id=self.user["id"], workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "name": "Поставщик", "email": "stale@triple-check.example", "host": "triple-check.example"},
            subject="Запрос", body="Текст запроса.", idempotency_key="pv4",
        )
        self.assertEqual(direct["email"], previewed_email)
        self.assertEqual(previewed_email, self._sent_to_email())

    def test_preview_never_leaks_another_workspaces_override_either(self) -> None:
        """Preview-side counterpart to test_another_workspace_never_sees_this_workspaces_override:
        the campaign preview for workspace B's own supplier row must show
        workspace B's own fallback, never workspace A's override, for the
        same real-world company.
        """
        inn = "7711110012"
        supplier_a, _ = self._add_supplier(external_key="preview-shared-a.example", email="a-fallback@preview-shared.example", inn=inn)
        self.repo.record_contact_result(
            workspace_id=self.workspace_id, user_id=self.user["id"],
            request_id=self.request_id, supplier_id=supplier_a,
            result="new_email_provided", new_email="workspace-a-only@preview-shared.example",
        )

        other_user = self.repo.seed_user("resolver-other-preview@example.com", "correct-horse")
        other_workspace_id = int(other_user["workspace_id"])
        self.repo.set_outgoing_enabled(True)
        self.service.save_oauth_tokens(
            user_id=other_user["id"], workspace_id=other_workspace_id,
            token_set=TokenSet("access", "refresh", 3600), email="resolver-other-preview@example.com",
        )
        other_request_id = self.repo.create_request(
            other_workspace_id, user_id=other_user["id"], name="Other workspace preview request",
            description="", positions=[{"name": "Item", "quantity": "1"}],
            sender_name="Buyer", company_name="Company",
        )
        supplier_b = self.repo.upsert_supplier(
            workspace_id=other_workspace_id, external_key="preview-shared-b.example", name="Поставщик",
            email="b-fallback@preview-shared.example", host="preview-shared-b.example", request_id=other_request_id,
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at)
                   VALUES (?, ?, 'Поставщик', ?, ?, ?)""",
                (other_workspace_id, inn, "b-fallback@preview-shared.example", now, now),
            )
            global_supplier_id_b = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)",
                (supplier_b, global_supplier_id_b),
            )

        previewed_email = self._preflight_eligible_email(
            supplier_id=supplier_b, email="b-fallback@preview-shared.example", host="preview-shared-b.example",
            workspace_id=other_workspace_id, user_id=other_user["id"], request_id=other_request_id,
        )
        self.assertEqual(previewed_email, "b-fallback@preview-shared.example")


if __name__ == "__main__":
    unittest.main()
