"""Regression contracts for the Messages interaction fixes.

These checks deliberately inspect the shipped React source because this
repository does not yet have a browser-component test runner.  Browser QA
remains required before delivery; these assertions make the intended UI
contracts explicit and prevent a later source-level regression.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MESSAGES = ROOT / "frontend-v2" / "src" / "pages" / "Messages.tsx"
AI_PANEL = ROOT / "frontend-v2" / "src" / "components" / "AiChatPanel.tsx"


class MessagesInteractionContractTests(unittest.TestCase):
    def test_request_group_can_collapse_with_any_thread_filter(self) -> None:
        source = MESSAGES.read_text(encoding="utf-8")

        self.assertIn("const isOpen = expanded?.has(g.request_id) ?? false;", source)
        self.assertNotIn("const isOpen = threadFilter !== 'all'", source)
        self.assertIn("aria-expanded={isOpen}", source)

    def test_request_deep_link_reveals_waiting_correspondence(self) -> None:
        source = MESSAGES.read_text(encoding="utf-8")

        self.assertIn("if (requestedRequestId) setThreadFilter('all');", source)
        self.assertIn("g.request_id === Number(requestedRequestId)", source)

    def test_ai_launcher_is_a_chat_symbol_not_a_brain_symbol(self) -> None:
        source = MESSAGES.read_text(encoding="utf-8")

        self.assertIn("MessageCircleMore", source)
        self.assertNotIn("BrainCircuit", source)

    def test_ai_panel_has_russian_action_history_dates_and_resize_handle(self) -> None:
        source = AI_PANEL.read_text(encoding="utf-8")

        self.assertIn(">Новый чат<", source)
        self.assertNotIn(">NEW<", source)
        self.assertIn("formatDateTime(c.updated_at)", source)
        self.assertIn("onPointerDown={startResize}", source)
        self.assertIn('aria-label="Изменить размер ИИ-помощника"', source)


if __name__ == "__main__":
    unittest.main()
