from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mail.repository import MailRepository, _is_bulk_sender


class BulkSenderHeuristicTests(unittest.TestCase):
    def test_generic_bulk_local_parts_are_flagged(self) -> None:
        for address in (
            "hello@360.yandex.ru",
            "welcome@stormbpmn.com",
            "care@practicum.yandex.ru",
            "content@mann-ivanov-ferber.ru",
            "NEWS@Example.com",
        ):
            with self.subTest(address=address):
                self.assertTrue(_is_bulk_sender(address))

    def test_no_reply_is_never_flagged_because_it_can_carry_real_alerts(self) -> None:
        # A CHECKO_KEY "API balance is low" notice arrives from no-reply@checko.ru --
        # a real operational alert that must stay visible, not just marketing mail.
        self.assertFalse(_is_bulk_sender("no-reply@checko.ru"))
        self.assertFalse(_is_bulk_sender("noreply@some-service.ru"))

    def test_supplier_looking_addresses_are_never_flagged(self) -> None:
        for address in ("info@supplier.ru", "sales@supplier.ru", "ivan@supplier.ru", None, ""):
            with self.subTest(address=address):
                self.assertFalse(_is_bulk_sender(address))


class DashboardBulkSenderFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "dashboard-bulk.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(
                       user_id, workspace_id, provider, email, status, created_at, updated_at
                   ) VALUES (?, ?, 'fake', 'buyer@example.com', 'connected', ?, ?)""",
                (self.user["id"], self.user["workspace_id"], self._time(0), self._time(0)),
            )
            self.account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _time(self, offset: int) -> str:
        return (self.now + timedelta(seconds=offset)).isoformat()

    def _inbox(self, from_email: str, *, offset: int = 0) -> None:
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_inbox_messages(
                       workspace_id, user_id, mail_account_id, provider_message_id,
                       message_id, from_email, to_email, subject, body_text, body_html,
                       received_at, status, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, 'buyer@example.com', ?, 'Текст', '<p>Текст</p>', ?, 'unmatched', ?)""",
                (
                    self.user["workspace_id"],
                    self.user["id"],
                    self.account_id,
                    f"provider-{from_email}-{offset}",
                    f"<{from_email}-{offset}@example.com>",
                    from_email,
                    f"Письмо от {from_email}",
                    self._time(offset),
                    self._time(offset),
                ),
            )

    def test_dashboard_kpi_excludes_bulk_senders_but_counts_real_alerts(self) -> None:
        workspace_id = self.user["workspace_id"]
        self._inbox("no-reply@checko.ru", offset=0)  # real operational alert -- must count
        self._inbox("hello@360.yandex.ru", offset=1)  # bulk -- must not count
        self._inbox("care@practicum.yandex.ru", offset=2)  # bulk -- must not count
        self._inbox("client@some-supplier.ru", offset=3)  # genuine unmatched reply -- must count

        summary = self.repo.dashboard_summary(workspace_id)
        self.assertEqual(summary["kpis"]["unmatched_mail"], 2)

    def test_preview_excludes_bulk_senders_without_starving_real_items(self) -> None:
        workspace_id = self.user["workspace_id"]
        # Three bulk-mail items land most recently, ahead of two real ones --
        # naively taking the first N by recency would show only bulk mail.
        self._inbox("hello@360.yandex.ru", offset=10)
        self._inbox("welcome@stormbpmn.com", offset=11)
        self._inbox("content@mann-ivanov-ferber.ru", offset=12)
        self._inbox("no-reply@checko.ru", offset=8)
        self._inbox("client@some-supplier.ru", offset=9)

        preview = self.repo.list_unmatched_incoming_preview(workspace_id, limit=5)
        senders = {item["from_email"] for item in preview}
        self.assertEqual(senders, {"no-reply@checko.ru", "client@some-supplier.ru"})

    def test_full_unmatched_inbox_list_is_never_filtered(self) -> None:
        # The dashboard-only heuristic must not hide mail from the actual
        # Messages/inbox screen -- only the at-a-glance dashboard surface.
        workspace_id = self.user["workspace_id"]
        self._inbox("hello@360.yandex.ru")
        full = self.repo.list_unmatched_incoming(workspace_id)
        self.assertEqual(len(full), 1)


if __name__ == "__main__":
    unittest.main()
