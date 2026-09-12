from __future__ import annotations

import unittest
from pathlib import Path


class HelpScreenContractTests(unittest.TestCase):
    def test_help_is_a_secondary_truthful_product_guide(self) -> None:
        root = Path(__file__).resolve().parents[1]
        page = (root / "frontend-v2/src/pages/Help.tsx").read_text(encoding="utf-8")
        app = (root / "frontend-v2/src/App.tsx").read_text(encoding="utf-8")
        sidebar = (root / "frontend-v2/src/components/shell/Sidebar.tsx").read_text(encoding="utf-8")
        support = (root / "frontend-v2/src/components/SupportChat.tsx").read_text(encoding="utf-8")
        self.assertIn('path="help"', app)
        self.assertNotIn("label: 'Помощь'", sidebar)
        self.assertIn('to="/help"', support)
        self.assertIn("Открыть справку по функциям", support)
        self.assertIn('title="Справка"', page)
        self.assertIn("не использует ИИ и не придумывает", page)
        self.assertIn("Пока не могу подтвердить ответ", page)
        self.assertIn("Скопировать вопрос", page)
        self.assertIn("откройте техническую поддержку внизу слева", page)
        self.assertIn("Не удалось скопировать вопрос", page)
        self.assertNotIn("api.", page)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
