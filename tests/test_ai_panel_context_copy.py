"""Regression contract for AI-context disclosure in the Messages panel.

The active correspondence is always sent as primary AI context.  It is not
selectable because the checkboxes are only for extra suppliers.  The panel
must say that plainly so an operator never mistakes the missing checkbox for
an omitted current thread.
"""

from __future__ import annotations

import unittest
from pathlib import Path


PANEL_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "frontend-v2"
    / "src"
    / "components"
    / "AiChatPanel.tsx"
)
MESSAGES_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "frontend-v2"
    / "src"
    / "pages"
    / "Messages.tsx"
)


class AiPanelContextCopyTests(unittest.TestCase):
    def test_ai_uses_the_compact_support_style_and_header_actions(self) -> None:
        panel = PANEL_SOURCE.read_text(encoding="utf-8")
        messages = MESSAGES_SOURCE.read_text(encoding="utf-8")

        self.assertIn('role="dialog"', panel)
        self.assertIn('SUPPLYDESK · AI', panel)
        self.assertIn('max-w-[calc(100vw-32px)]', panel)
        self.assertIn('max-h-[calc(100dvh-32px)]', panel)
        self.assertIn('aria-label="Изменить размер ИИ-помощника"', panel)
        self.assertIn('Новый чат', panel)
        self.assertIn('function renderAiAnswer', panel)
        self.assertIn('isMarkdownTableDivider', panel)
        self.assertIn('overflow-x-auto rounded-lg', panel)
        self.assertIn('Сравнить предложения', panel)
        self.assertIn('Подготовить вопросы', panel)
        self.assertIn('NotebookPen', messages)
        self.assertIn('ListTodo', messages)
        self.assertIn('MessageCircleMore', messages)
        self.assertNotIn('BrainCircuit', messages)
        self.assertIn('PageHeader title="Сообщения"', messages)
        self.assertNotIn('flex w-12 shrink-0 flex-col items-center', messages)

    def test_current_thread_is_explicitly_disclosed_as_ai_context(self) -> None:
        source = PANEL_SOURCE.read_text(encoding="utf-8")

        self.assertIn("Текущая переписка включена", source)
        self.assertIn("Выбрать остальных поставщиков", source)

    def test_active_thread_is_the_first_context_id_passed_to_the_chat_panel(self) -> None:
        """The unchecked active row must not be mistaken for omitted context."""
        source = MESSAGES_SOURCE.read_text(encoding="utf-8")

        self.assertIn("const aiContextThreadIds = activeThread", source)
        self.assertIn("? [\n        activeThread.id,", source)
        self.assertIn("threadIds={aiContextThreadIds}", source)


if __name__ == "__main__":
    unittest.main()
