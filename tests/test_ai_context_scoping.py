"""Proves the AI chat endpoint's server-side context scoping (owner's §11
requirement): whichever thread_ids the caller selects are exactly what
reaches the model, nothing more -- not the whole request, not every
supplier, not a stale/forged id from another workspace or request. This is
the backend half of the "3 of 132 suppliers selected -> AI context has
exactly 3" scenario; frontend "Есть ответ"-only checkbox filtering
(docs/ui/MESSAGES_SCREEN_SPEC.md §7) is a separate, already-covered UX
concern -- this test exercises the actual security/correctness boundary,
which now lives server-side in AiChatService._build_context /
MailRepository.get_thread_owned.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.domain.ai_agent.chat_service import AiChatService
from mail.repository import MailRepository


class _FakeRouterClient:
    """Records exactly what AiChatService sent to the model, without any
    real network call -- RouterAiClient itself talks to a live RouterAI
    catalog endpoint on first use, which tests must never do."""

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def chat(self, model: str, messages: list[dict]) -> tuple[str, float]:
        self.calls.append(messages)
        return "Ответ ассистента.", 0.0


class AiContextScopingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "ai-context.sqlite3")
        self.user = self.repo.seed_user("ai-context@example.com", "correct-horse")
        self.workspace_id = self.user["workspace_id"]
        self.now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        self.service = AiChatService(self.repo, api_key="test-key")
        self.fake_client = _FakeRouterClient()
        self.service._client = self.fake_client  # bypass real RouterAiClient construction entirely

        self.request_id = self.repo.create_request(
            self.workspace_id, name="Печь-камин — глубокий поиск 20", description="",
            positions=[{"name": "Позиция", "quantity": "1"}], sender_name="Buyer", company_name="ООО Тест", user_id=self.user["id"],
        )

        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at)
                   VALUES (?, ?, 'fake', 'buyer@example.com', 'connected', ?, ?)""",
                (self.user["id"], self.workspace_id, self.now, self.now),
            )
            account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

            self.thread_ids: list[int] = []
            self.supplier_names: list[str] = []
            for index in range(132):
                supplier_name = f"Поставщик {index:03d}"
                self.supplier_names.append(supplier_name)
                connection.execute(
                    """INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.workspace_id, f"supplier-{index}.example", supplier_name, f"s{index}@supplier-{index}.example", f"supplier-{index}.example", self.now, self.now),
                )
                supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                connection.execute(
                    """INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, last_message_at, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.workspace_id, self.user["id"], self.request_id, supplier_id, account_id, "Запрос", self.now, self.now),
                )
                thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                self.thread_ids.append(thread_id)
                # Every supplier has a real reply, so the test's assertions
                # are about scoping (who is included), not about response
                # status (that's a separate, frontend-owned filter).
                connection.execute(
                    """INSERT INTO mail_messages(
                           thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id,
                           direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at
                       ) VALUES (?, ?, ?, ?, ?, ?, 'inbound', ?, 'buyer@example.com', 'Re: Запрос', ?, ?, 'sent', ?, ?)""",
                    (
                        thread_id, self.workspace_id, self.user["id"], self.request_id, supplier_id, account_id,
                        f"s{index}@supplier-{index}.example", f"Наша цена {1000 + index} руб., поставщик {supplier_name}.",
                        f"<p>Наша цена {1000 + index} руб., поставщик {supplier_name}.</p>", self.now, self.now,
                    ),
                )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_selecting_3_of_132_suppliers_sends_exactly_those_3_to_the_model(self) -> None:
        selected_indexes = [5, 47, 130]
        selected_thread_ids = [self.thread_ids[i] for i in selected_indexes]
        selected_names = [self.supplier_names[i] for i in selected_indexes]
        excluded_names = [name for i, name in enumerate(self.supplier_names) if i not in selected_indexes]

        result = self.service.send_message(
            self.workspace_id, self.user["id"], "Сравни предложения выбранных поставщиков.",
            request_id=self.request_id, thread_ids=selected_thread_ids,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(len(self.fake_client.calls), 1)
        prompt_sent_to_model = self.fake_client.calls[0][-1]["content"]

        self.assertEqual(prompt_sent_to_model.count("ПОСТАВЩИК:"), 3, "expected exactly 3 supplier blocks in the model prompt")
        for name in selected_names:
            self.assertIn(name, prompt_sent_to_model)
        for name in excluded_names:
            self.assertNotIn(name, prompt_sent_to_model)

        # The audit trail (context_thread_ids) records the same exact set --
        # the owner's explicit ask for backend-side diagnosability.
        messages = self.repo.list_ai_messages(self.workspace_id, self.user["id"], result.conversation_id)
        assert messages is not None
        user_turn = next(m for m in messages if m["role"] == "user")
        self.assertEqual(sorted(user_turn["context_thread_ids"]), sorted(selected_thread_ids))

    def test_thread_id_from_a_different_request_is_silently_dropped_not_trusted(self) -> None:
        other_request_id = self.repo.create_request(
            self.workspace_id, name="Другая заявка", description="",
            positions=[{"name": "Позиция", "quantity": "1"}], sender_name="Buyer", company_name="ООО Тест", user_id=self.user["id"],
        )
        genuine_thread_id = self.thread_ids[0]
        foreign_thread_id = self.thread_ids[1]  # real thread, but belongs to self.request_id, not other_request_id

        result = self.service.send_message(
            self.workspace_id, self.user["id"], "Что написал поставщик?",
            request_id=other_request_id, thread_ids=[genuine_thread_id, foreign_thread_id],
        )
        self.assertEqual(result.status, "success")
        prompt_sent_to_model = self.fake_client.calls[0][-1]["content"]
        # Neither id belongs to other_request_id, so no supplier block at all --
        # not "both", not "the one that happened to match by accident".
        self.assertNotIn("ПОСТАВЩИК:", prompt_sent_to_model)

    def test_workspace_isolation_a_thread_from_another_workspace_is_never_trusted(self) -> None:
        other_user = self.repo.seed_user("ai-context-2@example.com", "correct-horse")
        other_request_id = self.repo.create_request(
            other_user["workspace_id"], name="Чужая заявка", description="",
            positions=[{"name": "Позиция", "quantity": "1"}], sender_name="Buyer", company_name="ООО Чужой", user_id=other_user["id"],
        )
        result = self.service.send_message(
            other_user["workspace_id"], other_user["id"], "Что написал поставщик?",
            request_id=other_request_id, thread_ids=[self.thread_ids[0]],  # belongs to self.workspace_id, not other_user's
        )
        self.assertEqual(result.status, "success")
        prompt_sent_to_model = self.fake_client.calls[0][-1]["content"]
        self.assertNotIn("ПОСТАВЩИК:", prompt_sent_to_model)
        self.assertNotIn(self.supplier_names[0], prompt_sent_to_model)


if __name__ == "__main__":
    unittest.main()
