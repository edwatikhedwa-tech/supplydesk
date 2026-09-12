from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.repository import MailRepository


class ThreadNoteVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "notes.sqlite3")
        self.user = self.repo.seed_user("notes@example.com", "correct-horse")
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                "INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at) VALUES (?, ?, 'fake', 'notes@example.com', 'connected', ?, ?)",
                (self.user["id"], self.user["workspace_id"], now, now),
            )
            account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) VALUES (?, 'notes-supplier', 'Поставщик заметок', 'supplier@example.com', 'example.com', ?, ?)",
                (self.user["workspace_id"], now, now),
            )
            self.supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, last_message_at, created_at) VALUES (?, ?, 1043, ?, ?, 'Заметки', ?, ?)",
                (self.user["workspace_id"], self.user["id"], self.supplier_id, account_id, now, now),
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_private_and_workspace_notes_are_explicitly_separate(self) -> None:
        workspace_id = self.user["workspace_id"]
        user_id = self.user["id"]
        self.repo.save_thread_note(workspace_id, user_id, 1043, self.supplier_id, "Только для меня")
        self.repo.save_thread_note(workspace_id, user_id, 1043, self.supplier_id, "Общее для команды", "workspace")

        notes = self.repo.get_thread_notes(workspace_id, user_id, 1043, self.supplier_id)
        self.assertEqual(notes["private"]["note"], "Только для меня")
        self.assertEqual(notes["private"]["visibility"], "private")
        self.assertEqual(notes["workspace"]["note"], "Общее для команды")
        self.assertEqual(notes["workspace"]["visibility"], "workspace")
        self.assertIsNotNone(notes["workspace"]["created_at"])

    def test_invalid_visibility_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.save_thread_note(self.user["workspace_id"], self.user["id"], 1043, self.supplier_id, "x", "public")

    def test_workspace_note_identifies_the_last_editor(self) -> None:
        colleague = self.repo.seed_user("notes-colleague@example.com", "correct-horse")
        with self.repo.connect() as connection:
            connection.execute(
                "INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'member')",
                (self.user["workspace_id"], colleague["id"]),
            )
        self.repo.save_thread_note(self.user["workspace_id"], self.user["id"], 1043, self.supplier_id, "Первый текст", "workspace")
        self.repo.save_thread_note(self.user["workspace_id"], colleague["id"], 1043, self.supplier_id, "Уточнённый текст", "workspace")

        note = self.repo.get_thread_notes(self.user["workspace_id"], self.user["id"], 1043, self.supplier_id)["workspace"]
        self.assertEqual(note["note"], "Уточнённый текст")
        self.assertEqual(note["author_name"], colleague["display_name"])
        self.assertIsNotNone(note["created_at"])

    def test_other_workspace_cannot_read_or_save_this_thread_note(self) -> None:
        other = self.repo.seed_user("other-notes@example.com", "correct-horse")
        visible = self.repo.get_thread_notes(other["workspace_id"], other["id"], 1043, self.supplier_id)
        self.assertEqual(visible, {"private": None, "workspace": None})
        with self.assertRaises(ValueError):
            self.repo.save_thread_note(other["workspace_id"], other["id"], 1043, self.supplier_id, "чужая заметка", "workspace")


if __name__ == "__main__":
    unittest.main()
