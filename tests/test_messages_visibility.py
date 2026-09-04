from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mail.repository import MailRepository


class MessagesVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "messages.sqlite3")
        self.user = self.repo.seed_user("messages@example.com", "correct-horse")
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(
                       user_id, workspace_id, provider, email, status, created_at, updated_at
                   ) VALUES (?, ?, 'fake', 'messages@example.com', 'connected', ?, ?)""",
                (self.user["id"], self.user["workspace_id"], self._time(0), self._time(0)),
            )
            self.account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _time(self, offset: int) -> str:
        return (self.now + timedelta(seconds=offset)).isoformat()

    def _supplier(self, suffix: str) -> int:
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'example.com', ?, ?)""",
                (
                    self.user["workspace_id"],
                    f"supplier-{suffix}",
                    f"Поставщик {suffix}",
                    f"{suffix}@example.com",
                    self._time(0),
                    self._time(0),
                ),
            )
            return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def _thread(self, suffix: str, status: str, *, offset: int = 0) -> tuple[int, int]:
        supplier_id = self._supplier(suffix)
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_threads(
                       workspace_id, user_id, request_id, supplier_id, mail_account_id,
                       subject, last_message_at, created_at
                   ) VALUES (?, ?, 1043, ?, ?, ?, ?, ?)""",
                (
                    self.user["workspace_id"],
                    self.user["id"],
                    supplier_id,
                    self.account_id,
                    f"Запрос {suffix}",
                    self._time(offset),
                    self._time(0),
                ),
            )
            thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                """INSERT INTO mail_messages(
                       thread_id, workspace_id, user_id, request_id, supplier_id,
                       mail_account_id, from_email, to_email, subject, body_text,
                       body_html, status, direction, created_at, sent_at
                   ) VALUES (?, ?, ?, 1043, ?, ?, 'messages@example.com', ?, ?, 'Текст', '<p>Текст</p>', ?, 'outbound', ?, ?)""",
                (
                    thread_id,
                    self.user["workspace_id"],
                    self.user["id"],
                    supplier_id,
                    self.account_id,
                    f"{suffix}@example.com",
                    f"Запрос {suffix}",
                    status,
                    self._time(offset),
                    self._time(offset) if status == "sent" else None,
                ),
            )
        return thread_id, supplier_id

    def _inbox(self, suffix: str, *, offset: int = 0) -> int:
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_inbox_messages(
                       workspace_id, user_id, mail_account_id, provider_message_id,
                       message_id, from_email, to_email, subject, body_text, body_html,
                       received_at, status, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, 'messages@example.com', ?, 'Входящий текст', '<p>Входящий текст</p>', ?, 'unmatched', ?)""",
                (
                    self.user["workspace_id"],
                    self.user["id"],
                    self.account_id,
                    f"provider-{suffix}",
                    f"<{suffix}@example.com>",
                    f"{suffix}@example.com",
                    f"Входящее {suffix}",
                    self._time(offset),
                    self._time(offset),
                ),
            )
            return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def test_queue_only_thread_is_hidden_from_correspondence_but_present_in_outbox(self) -> None:
        _, supplier_id = self._thread("queued", "queued")

        self.assertFalse(any(item["supplier_id"] == supplier_id for item in self.repo.list_threads(self.user["workspace_id"])))
        outbox = self.repo.list_outbox_threads(self.user["workspace_id"])
        queued = next(item for item in outbox if item["supplier_id"] == supplier_id)
        self.assertEqual(queued["last_outbound_status"], "queued")
        self.assertEqual(queued["pending_outbound_count"], 1)

    def test_only_transmitted_outbound_threads_are_visible(self) -> None:
        _, sent_supplier_id = self._thread("sent", "sent", offset=1)
        _, failed_supplier_id = self._thread("failed", "failed", offset=2)
        _, unknown_supplier_id = self._thread("unknown", "delivery_unknown", offset=3)

        items = {item["supplier_id"]: item for item in self.repo.list_threads(self.user["workspace_id"])}
        self.assertEqual(items[sent_supplier_id]["last_outbound_status"], "sent")
        self.assertEqual(items[sent_supplier_id]["last_message_direction"], "outbound")
        self.assertNotIn(failed_supplier_id, items)
        self.assertEqual(items[unknown_supplier_id]["last_outbound_status"], "delivery_unknown")

        with self.repo.connect() as connection:
            failed_row = connection.execute(
                "SELECT status, sent_at FROM mail_messages WHERE supplier_id=?",
                (failed_supplier_id,),
            ).fetchone()
        self.assertEqual(failed_row["status"], "failed")
        self.assertIsNone(failed_row["sent_at"])

    def test_pre_send_cancelled_attempt_stays_durable_but_not_in_conversation(self) -> None:
        thread_id, supplier_id = self._thread("cancelled-after-sent", "sent", offset=4)
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_messages(
                       thread_id, workspace_id, user_id, request_id, supplier_id,
                       mail_account_id, from_email, to_email, subject, body_text,
                       body_html, status, direction, created_at, sent_at, error
                   ) VALUES (?, ?, ?, 1043, ?, ?, 'messages@example.com', ?, ?, 'Не отправлено', '<p>Не отправлено</p>', 'cancelled', 'outbound', ?, NULL, 'cancelled before transport')""",
                (
                    thread_id,
                    self.user["workspace_id"],
                    self.user["id"],
                    supplier_id,
                    self.account_id,
                    f"cancelled-after-sent@example.com",
                    "Запрос cancelled-after-sent",
                    self._time(5),
                ),
            )
            cancelled_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        items = {item["supplier_id"]: item for item in self.repo.list_threads(self.user["workspace_id"])}
        self.assertEqual(items[supplier_id]["messages_count"], 1)
        messages = self.repo.thread_messages(self.user["workspace_id"], 1043, supplier_id)
        self.assertEqual([message["status"] for message in messages], ["sent"])

        with self.repo.connect() as connection:
            durable = connection.execute(
                "SELECT status FROM mail_messages WHERE id=?",
                (cancelled_id,),
            ).fetchone()
        self.assertEqual(durable["status"], "cancelled")

    def test_inbound_reply_is_unread_until_thread_is_opened(self) -> None:
        thread_id, supplier_id = self._thread("reply", "sent", offset=1)
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_messages(
                       thread_id, workspace_id, user_id, request_id, supplier_id,
                       mail_account_id, from_email, to_email, subject, body_text,
                       body_html, status, direction, created_at, sent_at
                   ) VALUES (?, ?, ?, 1043, ?, ?, ?, 'messages@example.com', ?, 'Ответ', '<p>Ответ</p>', 'received', 'inbound', ?, ?)""",
                (
                    thread_id,
                    self.user["workspace_id"],
                    self.user["id"],
                    supplier_id,
                    self.account_id,
                    f"reply@example.com",
                    "Re: Запрос reply",
                    self._time(3),
                    self._time(3),
                ),
            )
            connection.execute("UPDATE mail_threads SET last_message_at=? WHERE id=?", (self._time(3), thread_id))

        before = next(item for item in self.repo.list_threads(self.user["workspace_id"]) if item["supplier_id"] == supplier_id)
        self.assertEqual(before["unread_count"], 1)
        self.assertEqual(before["last_message_direction"], "inbound")

        self.repo.thread_messages(self.user["workspace_id"], 1043, supplier_id)
        after = next(item for item in self.repo.list_threads(self.user["workspace_id"]) if item["supplier_id"] == supplier_id)
        self.assertEqual(after["unread_count"], 0)

    def test_unmatched_and_manual_linked_inbox_message_keep_unread_state(self) -> None:
        inbox_id = self._inbox("unmatched")
        listed = next(item for item in self.repo.list_unmatched_incoming(self.user["workspace_id"]) if item["id"] == inbox_id)
        preview = next(item for item in self.repo.list_unmatched_incoming_preview(self.user["workspace_id"]) if item["id"] == inbox_id)
        self.assertTrue(listed["unread"])
        self.assertTrue(preview["unread"])

        self.repo.inbox_conversation(self.user["workspace_id"], inbox_id)
        read_item = next(item for item in self.repo.list_unmatched_incoming(self.user["workspace_id"]) if item["id"] == inbox_id)
        self.assertFalse(read_item["unread"])

        linked_id = self._inbox("linked", offset=1)
        self.repo.manually_link_inbox_message(
            self.user["workspace_id"], self.user["id"], linked_id, 1043, confirmed=True,
        )
        linked = next(item for item in self.repo.list_threads(self.user["workspace_id"]) if item["manual_inbox_id"] == linked_id)
        self.assertEqual(linked["unread_count"], 1)
        self.repo.inbox_conversation(self.user["workspace_id"], linked_id)
        linked_read = next(item for item in self.repo.list_threads(self.user["workspace_id"]) if item["manual_inbox_id"] == linked_id)
        self.assertEqual(linked_read["unread_count"], 0)


if __name__ == "__main__":
    unittest.main()
