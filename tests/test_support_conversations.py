from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class SupportConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "support.sqlite3")
        self.user = self.repo.seed_user("support@example.com", "correct-horse")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_new_ticket_persists_technical_context_and_attachment(self) -> None:
        conversation = self.repo.create_support_conversation(
            self.user["workspace_id"], self.user["id"], text="Не открывается письмо",
            category="bug", current_url="http://localhost/#/requests/1059",
            current_section="requests", browser="TestBrowser/1.0", app_version="test",
            attachment={
                "filename": "screen.png", "mime_type": "image/png",
                "content_base64": base64.b64encode(b"png-data").decode("ascii"),
            },
        )
        self.assertEqual(conversation["status"], "received")
        self.assertEqual(conversation["current_section"], "requests")
        self.assertEqual(conversation["messages"][0]["sender_type"], "user")
        self.assertEqual(conversation["messages"][0]["attachment_url"], f"/api/support/attachments/{conversation['messages'][0]['id']}")
        attachment = self.repo.get_support_attachment(self.user["workspace_id"], self.user["id"], conversation["messages"][0]["id"])
        self.assertEqual(bytes(attachment["attachment_content"]), b"png-data")

    def test_user_message_reopens_a_resolved_conversation(self) -> None:
        conversation = self.repo.create_support_conversation(
            self.user["workspace_id"], self.user["id"], text="Вопрос", category="technical",
        )
        self.repo.add_support_reply(
            self.user["workspace_id"], self.user["id"], conversation["id"], text="Готово", status="resolved",
        )
        reopened = self.repo.add_support_message(
            self.user["workspace_id"], self.user["id"], conversation["id"], text="Проблема повторилась",
        )
        self.assertEqual(reopened["status"], "in_progress")
        self.assertEqual([message["sender_type"] for message in reopened["messages"]], ["user", "support", "user"])

    def test_workspace_owner_can_reply_to_a_member_ticket(self) -> None:
        member = self.repo.seed_user("member-support@example.com", "correct-horse")
        with self.repo.connect() as connection:
            connection.execute(
                "INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'member')",
                (self.user["workspace_id"], member["id"]),
            )
            connection.commit()
        conversation = self.repo.create_support_conversation(
            self.user["workspace_id"], member["id"], text="Нужна помощь", category="technical",
        )
        reply = self.repo.add_support_reply(
            self.user["workspace_id"], self.user["id"], conversation["id"], text="Проверяем", status="waiting_user",
        )
        self.assertEqual(reply["status"], "waiting_user")
        member_view = self.repo.get_support_conversation(self.user["workspace_id"], member["id"], conversation["id"])
        self.assertEqual(member_view["messages"][-1]["sender_type"], "support")

    def test_other_workspace_cannot_read_ticket_or_attachment(self) -> None:
        conversation = self.repo.create_support_conversation(
            self.user["workspace_id"], self.user["id"], text="Приватное", category="bug",
            attachment={
                "filename": "private.txt", "mime_type": "text/plain",
                "content_base64": base64.b64encode(b"secret").decode("ascii"),
            },
        )
        other = self.repo.seed_user("other-support@example.com", "correct-horse")
        self.assertEqual(self.repo.list_support_conversations(other["workspace_id"], other["id"]), [])
        with self.assertRaisesRegex(ValueError, "не найдено"):
            self.repo.get_support_conversation(other["workspace_id"], other["id"], conversation["id"])
        with self.assertRaisesRegex(ValueError, "не найдено"):
            self.repo.get_support_attachment(other["workspace_id"], other["id"], conversation["messages"][0]["id"])

    def test_invalid_attachment_is_rejected_before_storage(self) -> None:
        with self.assertRaisesRegex(ValueError, "Поддерживаются"):
            self.repo.create_support_conversation(
                self.user["workspace_id"], self.user["id"], text="x", category="bug",
                attachment={"filename": "payload.exe", "mime_type": "application/octet-stream", "content_base64": "eA=="},
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
