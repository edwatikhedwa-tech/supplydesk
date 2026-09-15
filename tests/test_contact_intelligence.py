"""SUP-030: needs_followup + self-updating cross-tenant supplier contacts.

Covers the owner's acceptance criteria (AC-01..AC-09) against a real SQLite
MailRepository -- no mocks for the repository layer itself, following the
same fixture style as tests/test_ai_context_scoping.py and
tests/test_canonical_companies.py.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mail.repository import MailRepository

UTC = timezone.utc


class _Fixture:
    """One workspace with a mail account, ready to attach suppliers/threads to."""

    def __init__(self, repo: MailRepository, email: str) -> None:
        self.repo = repo
        user = repo.seed_user(email, "correct-horse")
        self.user_id = int(user["id"])
        self.workspace_id = int(user["workspace_id"])
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        with repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at)
                   VALUES (?, ?, 'fake', ?, 'connected', ?, ?)""",
                (self.user_id, self.workspace_id, f"buyer-{email}", now, now),
            )
            self.account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def create_request(self, name: str = "Заявка") -> int:
        return self.repo.create_request(
            self.workspace_id, name=name, description="", positions=[{"name": "Позиция", "quantity": "1"}],
            sender_name="Buyer", company_name="ООО Тест", user_id=self.user_id,
        )

    def add_supplier_thread(
        self, request_id: int, *, inn: str, email: str, host: str,
    ) -> tuple[int, int, int]:
        """Creates suppliers + global_suppliers (+link) + mail_threads rows.

        Returns (supplier_id, thread_id, global_supplier_id).
        """
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at)
                   VALUES (?, ?, 'Поставщик', ?, ?, ?, ?)""",
                (self.workspace_id, host, email, host, now, now),
            )
            supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
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
            connection.execute(
                """INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, last_message_at, created_at)
                   VALUES (?, ?, ?, ?, ?, 'Запрос', ?, ?)""",
                (self.workspace_id, self.user_id, request_id, supplier_id, self.account_id, now, now),
            )
            thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        return supplier_id, thread_id, global_supplier_id

    def send_outbound(self, *, request_id: int, supplier_id: int, to_email: str, sent_at: datetime, status: str = "sent") -> None:
        created_at = sent_at.isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_messages(
                       thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id,
                       direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at
                   ) SELECT t.id, ?, ?, ?, ?, ?, 'outbound', 'buyer@example.com', ?, 'Запрос', 'Текст', '', ?, ?, ?
                     FROM mail_threads t WHERE t.workspace_id=? AND t.request_id=? AND t.supplier_id=?""",
                (
                    self.workspace_id, self.user_id, request_id, supplier_id, self.account_id,
                    to_email, status, created_at, created_at,
                    self.workspace_id, request_id, supplier_id,
                ),
            )

    def receive_inbound(self, *, request_id: int, supplier_id: int, from_email: str, subject: str = "Re: Запрос", body_text: str = "Наш ответ.", received_at: datetime | None = None) -> None:
        created_at = (received_at or datetime.now(UTC)).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_messages(
                       thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id,
                       direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at
                   ) SELECT t.id, ?, ?, ?, ?, ?, 'inbound', ?, 'buyer@example.com', ?, ?, '', 'received', ?, NULL
                     FROM mail_threads t WHERE t.workspace_id=? AND t.request_id=? AND t.supplier_id=?""",
                (
                    self.workspace_id, self.user_id, request_id, supplier_id, self.account_id,
                    from_email, subject, body_text, created_at,
                    self.workspace_id, request_id, supplier_id,
                ),
            )


class NeedsFollowupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "followup.sqlite3")
        self.ws = _Fixture(self.repo, "buyer@example.com")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_waiting_thread_under_sla_is_not_needs_followup(self) -> None:
        request_id = self.ws.create_request()
        supplier_id, _thread_id, _gs = self.ws.add_supplier_thread(request_id, inn="7700000001", email="s1@example.com", host="s1.example")
        self.ws.send_outbound(request_id=request_id, supplier_id=supplier_id, to_email="s1@example.com", sent_at=datetime.now(UTC))
        threads = self.repo.list_threads(self.ws.workspace_id, self.ws.user_id)
        thread = next(t for t in threads if t["supplier_id"] == supplier_id)
        self.assertFalse(thread["needs_followup"])
        # AC-01: it must still read as the ordinary transport "waiting" state.
        self.assertEqual(thread["messages_count"], 1)
        self.assertEqual(thread["replies_count"], 0)

    def test_ac01_waiting_thread_past_default_sla_needs_followup_but_stays_waiting(self) -> None:
        request_id = self.ws.create_request()
        supplier_id, _thread_id, _gs = self.ws.add_supplier_thread(request_id, inn="7700000002", email="s2@example.com", host="s2.example")
        sent_at = datetime.now(UTC) - timedelta(days=6)  # comfortably >2 business days ago regardless of weekday
        self.ws.send_outbound(request_id=request_id, supplier_id=supplier_id, to_email="s2@example.com", sent_at=sent_at)
        threads = self.repo.list_threads(self.ws.workspace_id, self.ws.user_id)
        thread = next(t for t in threads if t["supplier_id"] == supplier_id)
        self.assertTrue(thread["needs_followup"])
        self.assertEqual(thread["replies_count"], 0)  # still "Ждём ответа", not a new/replacing status

    def test_answered_thread_never_needs_followup(self) -> None:
        request_id = self.ws.create_request()
        supplier_id, _thread_id, _gs = self.ws.add_supplier_thread(request_id, inn="7700000003", email="s3@example.com", host="s3.example")
        sent_at = datetime.now(UTC) - timedelta(days=10)
        self.ws.send_outbound(request_id=request_id, supplier_id=supplier_id, to_email="s3@example.com", sent_at=sent_at)
        self.ws.receive_inbound(request_id=request_id, supplier_id=supplier_id, from_email="s3@example.com")
        threads = self.repo.list_threads(self.ws.workspace_id, self.ws.user_id)
        thread = next(t for t in threads if t["supplier_id"] == supplier_id)
        self.assertFalse(thread["needs_followup"])

    def test_configurable_per_request_sla(self) -> None:
        request_id = self.ws.create_request()
        supplier_id, _thread_id, _gs = self.ws.add_supplier_thread(request_id, inn="7700000004", email="s4@example.com", host="s4.example")
        sent_at = datetime.now(UTC) - timedelta(days=3)
        self.ws.send_outbound(request_id=request_id, supplier_id=supplier_id, to_email="s4@example.com", sent_at=sent_at)
        # Default (2 business days) would already flag this thread -- widen
        # the SLA for this specific request and confirm it clears again.
        self.repo.set_followup_settings(self.ws.workspace_id, self.ws.user_id, request_id, 10)
        threads = self.repo.list_threads(self.ws.workspace_id, self.ws.user_id)
        thread = next(t for t in threads if t["supplier_id"] == supplier_id)
        self.assertFalse(thread["needs_followup"])
        settings = self.repo.get_followup_settings(self.ws.workspace_id, request_id)
        self.assertEqual(settings["sla_business_days"], 10)
        self.assertFalse(settings["is_default"])

    def test_default_sla_is_2_business_days_when_unset(self) -> None:
        request_id = self.ws.create_request()
        settings = self.repo.get_followup_settings(self.ws.workspace_id, request_id)
        self.assertEqual(settings["sla_business_days"], 2)
        self.assertTrue(settings["is_default"])


class ContactResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "contact-result.sqlite3")
        self.ws = _Fixture(self.repo, "buyer@example.com")
        self.request_id = self.ws.create_request()
        self.supplier_id, self.thread_id, self.global_supplier_id = self.ws.add_supplier_thread(
            self.request_id, inn="7700000010", email="old@example.com", host="old.example",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_ac02_new_email_is_used_immediately_only_in_this_workspace(self) -> None:
        self.repo.record_contact_result(
            workspace_id=self.ws.workspace_id, user_id=self.ws.user_id,
            request_id=self.request_id, supplier_id=self.supplier_id,
            result="new_email_provided", comment="уточнили по телефону", new_email="New@Example.com",
        )
        contacts = self.repo.list_email_contacts_for_global_supplier(self.ws.workspace_id, self.global_supplier_id)
        self.assertIsNotNone(contacts["workspace_override"])
        self.assertEqual(contacts["workspace_override"]["email"], "new@example.com")

    def test_ac03_a_single_workspace_confirmation_never_changes_global_preferred(self) -> None:
        self.repo.record_contact_result(
            workspace_id=self.ws.workspace_id, user_id=self.ws.user_id,
            request_id=self.request_id, supplier_id=self.supplier_id,
            result="new_email_provided", new_email="new@example.com",
        )
        contacts = self.repo.list_email_contacts_for_global_supplier(self.ws.workspace_id, self.global_supplier_id)
        statuses = {c["email"]: c["status"] for c in contacts["global_contacts"]}
        self.assertEqual(statuses.get("new@example.com"), "candidate")
        self.assertNotIn("preferred", statuses.values())

    def test_ac04_three_users_of_one_workspace_count_as_one_independent_confirmation(self) -> None:
        now = datetime.now(UTC).isoformat()
        user_ids = [self.ws.user_id]
        with self.repo.connect() as connection:
            for suffix in ("second", "third"):
                email = f"{suffix}-user@example.com"
                connection.execute(
                    "INSERT INTO users(email, display_name, password_hash, created_at) VALUES (?, ?, 'x', ?)",
                    (email, suffix, now),
                )
                user_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                connection.execute(
                    "INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'member')",
                    (self.ws.workspace_id, user_id),
                )
                user_ids.append(user_id)
        self.assertEqual(len(user_ids), 3)

        for user_id in user_ids:
            self.repo.record_contact_result(
                workspace_id=self.ws.workspace_id, user_id=user_id,
                request_id=self.request_id, supplier_id=self.supplier_id,
                result="contact_confirmed",
            )
        contacts = self.repo.list_email_contacts_for_global_supplier(self.ws.workspace_id, self.global_supplier_id)
        entry = next(c for c in contacts["global_contacts"] if c["email"] == "old@example.com")
        # Three different users of the SAME workspace -> exactly one
        # independent confirmation, never three.
        self.assertEqual(entry["confirming_workspace_count"], 1)

    def test_not_reached_and_call_back_later_do_not_create_signals(self) -> None:
        self.repo.record_contact_result(
            workspace_id=self.ws.workspace_id, user_id=self.ws.user_id,
            request_id=self.request_id, supplier_id=self.supplier_id, result="not_reached",
        )
        self.repo.record_contact_result(
            workspace_id=self.ws.workspace_id, user_id=self.ws.user_id,
            request_id=self.request_id, supplier_id=self.supplier_id, result="call_back_later",
        )
        contacts = self.repo.list_email_contacts_for_global_supplier(self.ws.workspace_id, self.global_supplier_id)
        self.assertEqual(contacts["global_contacts"], [])

    def test_ac07_previous_email_survives_in_workspace_history(self) -> None:
        self.repo.record_contact_result(
            workspace_id=self.ws.workspace_id, user_id=self.ws.user_id,
            request_id=self.request_id, supplier_id=self.supplier_id,
            result="new_email_provided", new_email="first@example.com",
        )
        self.repo.record_contact_result(
            workspace_id=self.ws.workspace_id, user_id=self.ws.user_id,
            request_id=self.request_id, supplier_id=self.supplier_id,
            result="new_email_provided", new_email="second@example.com",
        )
        with self.repo.connect() as connection:
            rows = connection.execute(
                """SELECT email, superseded_at FROM workspace_supplier_contact_overrides
                   WHERE workspace_id=? AND global_supplier_id=? ORDER BY created_at""",
                (self.ws.workspace_id, self.global_supplier_id),
            ).fetchall()
        emails = [dict(r)["email"] for r in rows]
        self.assertEqual(emails, ["first@example.com", "second@example.com"])
        self.assertIsNotNone(dict(rows[0])["superseded_at"])
        self.assertIsNone(dict(rows[1])["superseded_at"])
        contacts = self.repo.list_email_contacts_for_global_supplier(self.ws.workspace_id, self.global_supplier_id)
        self.assertEqual(contacts["workspace_override"]["email"], "second@example.com")


class CrossTenantConsensusTests(unittest.TestCase):
    """AC-05/AC-06/AC-08/AC-09 -- consensus must be counted across truly
    independent workspaces (different SupplyDesk tenants), keyed by ИНН via
    canonical_companies, never by any one workspace's own global_suppliers.id.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "consensus.sqlite3")
        self.inn = "7700000099"
        self.email = "shared@example.com"
        self.workspaces: list[_Fixture] = []
        self.requests: list[int] = []
        self.supplier_ids: list[int] = []
        self.global_supplier_ids: list[int] = []
        for index in range(3):
            ws = _Fixture(self.repo, f"tenant-{index}@example.com")
            request_id = ws.create_request()
            supplier_id, _thread_id, global_supplier_id = ws.add_supplier_thread(
                request_id, inn=self.inn, email=self.email, host=f"shared-{index}.example",
            )
            self.workspaces.append(ws)
            self.requests.append(request_id)
            self.supplier_ids.append(supplier_id)
            self.global_supplier_ids.append(global_supplier_id)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _confirm(self, index: int) -> None:
        ws = self.workspaces[index]
        ws.receive_inbound(request_id=self.requests[index], supplier_id=self.supplier_ids[index], from_email=self.email)
        # Force a sync of that workspace's own signals by reading its own card.
        self.repo.list_email_contacts_for_global_supplier(ws.workspace_id, self.global_supplier_ids[index])

    def _weak_confirm(self, index: int) -> None:
        ws = self.workspaces[index]
        self.repo.record_contact_result(
            workspace_id=ws.workspace_id, user_id=ws.user_id,
            request_id=self.requests[index], supplier_id=self.supplier_ids[index], result="contact_confirmed",
        )

    def test_ac05_three_workspaces_without_strong_signal_do_not_promote(self) -> None:
        for index in range(3):
            self._weak_confirm(index)
        for index in range(3):
            contacts = self.repo.list_email_contacts_for_global_supplier(self.workspaces[index].workspace_id, self.global_supplier_ids[index])
            entry = next(c for c in contacts["global_contacts"] if c["email"] == self.email)
            self.assertEqual(entry["status"], "candidate")
            self.assertEqual(entry["confirming_workspace_count"], 3)
            self.assertFalse(entry["has_strong_signal"])

    def test_ac06_three_workspaces_plus_a_strong_signal_promotes_to_preferred(self) -> None:
        for index in range(2):
            self._weak_confirm(index)
        # The third, independent workspace supplies the strong signal (a real
        # inbound reply) that the other two lacked.
        self._confirm(2)
        contacts = self.repo.list_email_contacts_for_global_supplier(self.workspaces[0].workspace_id, self.global_supplier_ids[0])
        entry = next(c for c in contacts["global_contacts"] if c["email"] == self.email)
        self.assertEqual(entry["status"], "preferred")
        self.assertEqual(entry["confirming_workspace_count"], 3)
        self.assertTrue(entry["has_strong_signal"])
        self.assertIsNotNone(entry["last_verified_at"])

    def test_ac09_explanation_never_exposes_which_workspaces_confirmed(self) -> None:
        for index in range(2):
            self._weak_confirm(index)
        self._confirm(2)
        contacts = self.repo.list_email_contacts_for_global_supplier(self.workspaces[0].workspace_id, self.global_supplier_ids[0])
        entry = next(c for c in contacts["global_contacts"] if c["email"] == self.email)
        # Only a count and a strength flag are exposed -- never an identifier
        # that names or numbers a *specific* contributing workspace.
        allowed_fields = {
            "email", "purpose", "status", "last_verified_at", "first_seen_at",
            "confirming_workspace_count", "has_strong_signal", "hard_bounce_count", "soft_bounce_count",
        }
        self.assertEqual(set(entry.keys()), allowed_fields)
        self.assertIsInstance(entry["confirming_workspace_count"], int)
        self.assertNotIn("workspace_id", entry)
        self.assertNotIn("workspace_ids", entry)
        self.assertNotIn("confirmed_by", entry)

    def test_ac08_hard_bounce_demotes_preferred_but_soft_bounce_does_not(self) -> None:
        for index in range(2):
            self._weak_confirm(index)
        self._confirm(2)
        contacts = self.repo.list_email_contacts_for_global_supplier(self.workspaces[0].workspace_id, self.global_supplier_ids[0])
        entry = next(c for c in contacts["global_contacts"] if c["email"] == self.email)
        self.assertEqual(entry["status"], "preferred")

        # A soft bounce from a 4th, otherwise uninvolved workspace must not
        # touch the preferred status at all.
        soft_ws = _Fixture(self.repo, "soft-bounce@example.com")
        soft_request = soft_ws.create_request()
        soft_supplier_id, _t, soft_gs_id = soft_ws.add_supplier_thread(soft_request, inn=self.inn, email=self.email, host="soft.example")
        soft_ws.receive_inbound(
            request_id=soft_request, supplier_id=soft_supplier_id, from_email="mailer-daemon@soft.example",
            subject="Delivery Status Notification (Delay)",
            body_text=f"<{self.email}>: 450 4.2.1 mailbox full, try again later",
        )
        self.repo.list_email_contacts_for_global_supplier(soft_ws.workspace_id, soft_gs_id)
        contacts = self.repo.list_email_contacts_for_global_supplier(self.workspaces[0].workspace_id, self.global_supplier_ids[0])
        entry = next(c for c in contacts["global_contacts"] if c["email"] == self.email)
        self.assertEqual(entry["status"], "preferred")
        self.assertEqual(entry["soft_bounce_count"], 1)
        self.assertEqual(entry["hard_bounce_count"], 0)

        # A hard bounce, from another independent workspace, reduces trust --
        # demotes the preferred contact but must never delete/deactivate it.
        hard_ws = _Fixture(self.repo, "hard-bounce@example.com")
        hard_request = hard_ws.create_request()
        hard_supplier_id, _t2, hard_gs_id = hard_ws.add_supplier_thread(hard_request, inn=self.inn, email=self.email, host="hard.example")
        hard_ws.receive_inbound(
            request_id=hard_request, supplier_id=hard_supplier_id, from_email="mailer-daemon@hard.example",
            subject="Undeliverable: Запрос",
            body_text=f"<{self.email}>: 550 5.1.1 user unknown",
        )
        self.repo.list_email_contacts_for_global_supplier(hard_ws.workspace_id, hard_gs_id)
        contacts = self.repo.list_email_contacts_for_global_supplier(self.workspaces[0].workspace_id, self.global_supplier_ids[0])
        entry = next(c for c in contacts["global_contacts"] if c["email"] == self.email)
        self.assertEqual(entry["status"], "secondary")
        self.assertEqual(entry["hard_bounce_count"], 1)
        # Never deleted -- the contact row (and its history) is still present.
        self.assertIn(self.email, {c["email"] for c in contacts["global_contacts"]})


if __name__ == "__main__":
    unittest.main()
