from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.repository import MailRepository


class ThreadMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "metadata.sqlite3")
        self.user = self.repo.seed_user("metadata@example.com", "correct-horse")
        self.now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(
                       user_id, workspace_id, provider, email, status, created_at, updated_at
                   ) VALUES (?, ?, 'fake', 'metadata@example.com', 'connected', ?, ?)""",
                (self.user["id"], self.user["workspace_id"], self.now, self.now),
            )
            self.account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                """INSERT INTO suppliers(
                       workspace_id, external_key, name, email, host, created_at, updated_at
                   ) VALUES (?, 'metadata-supplier', 'Поставщик метаданных', 'supplier@example.com', 'example.com', ?, ?)""",
                (self.user["workspace_id"], self.now, self.now),
            )
            self.supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                """INSERT INTO mail_threads(
                       workspace_id, user_id, request_id, supplier_id, mail_account_id,
                       subject, last_message_at, created_at
                   ) VALUES (?, ?, 1043, ?, ?, 'Метаданные', ?, ?)""",
                (
                    self.user["workspace_id"], self.user["id"], self.supplier_id,
                    self.account_id, self.now, self.now,
                ),
            )
            thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                """INSERT INTO mail_messages(
                       thread_id, workspace_id, user_id, request_id, supplier_id,
                       mail_account_id, from_email, to_email, subject, body_text,
                       body_html, status, direction, created_at, sent_at
                   ) VALUES (?, ?, ?, 1043, ?, ?, 'metadata@example.com',
                             'supplier@example.com', 'Метаданные', 'Текст',
                             '<p>Текст</p>', 'sent', 'outbound', ?, ?)""",
                (
                    thread_id, self.user["workspace_id"], self.user["id"],
                    self.supplier_id, self.account_id, self.now, self.now,
                ),
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_metadata_is_durable_and_independent(self) -> None:
        workspace_id = self.user["workspace_id"]
        user_id = self.user["id"]
        self.repo.update_thread_metadata(workspace_id, user_id, 1043, self.supplier_id, important=True)
        self.repo.update_thread_metadata(workspace_id, user_id, 1043, self.supplier_id, priority=2)

        item = next(item for item in self.repo.list_threads(workspace_id, user_id) if item["supplier_id"] == self.supplier_id)
        self.assertTrue(item["is_important"])
        self.assertEqual(item["priority"], 2)

        self.repo.update_thread_metadata(workspace_id, user_id, 1043, self.supplier_id, important=False, priority=None)
        item = next(item for item in self.repo.list_threads(workspace_id, user_id) if item["supplier_id"] == self.supplier_id)
        self.assertFalse(item["is_important"])
        self.assertIsNone(item["priority"])

    def test_invalid_or_cross_scope_metadata_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.update_thread_metadata(
                self.user["workspace_id"], self.user["id"], 1043, self.supplier_id, priority=4,
            )
        with self.assertRaises(ValueError):
            self.repo.update_thread_metadata(
                self.user["workspace_id"], self.user["id"], 999999, self.supplier_id, important=True,
            )


if __name__ == "__main__":
    unittest.main()
