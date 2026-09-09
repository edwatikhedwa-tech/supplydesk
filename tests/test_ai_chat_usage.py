from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mail.repository import MailRepository


class AiChatUsageTests(unittest.TestCase):
    def test_repeated_spend_is_accumulated_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"DATABASE_URL": ""}):
            repository = MailRepository(Path(temp_dir) / "ai-chat.sqlite3")
            user = repository.seed_user("ai-sqlite@example.com", "correct-horse")

            self.assertAlmostEqual(repository.add_ai_chat_spend(user["workspace_id"], user["id"], 0.25), 0.25)
            self.assertAlmostEqual(repository.add_ai_chat_spend(user["workspace_id"], user["id"], 0.75), 1.0)


@unittest.skipUnless(os.getenv("SUPPLYDESK_TEST_DATABASE_URL"), "Disposable PostgreSQL URL is not configured")
class AiChatUsagePostgresTests(unittest.TestCase):
    def test_repeated_spend_is_accumulated_in_postgres(self) -> None:
        database_url = os.environ["SUPPLYDESK_TEST_DATABASE_URL"]
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"DATABASE_URL": database_url}):
            repository = MailRepository(Path(temp_dir) / "unused.sqlite3")
            user = repository.seed_user("ai-postgres@example.com", "correct-horse")

            self.assertAlmostEqual(repository.add_ai_chat_spend(user["workspace_id"], user["id"], 0.25), 0.25)
            self.assertAlmostEqual(repository.add_ai_chat_spend(user["workspace_id"], user["id"], 0.75), 1.0)


if __name__ == "__main__":
    unittest.main()
