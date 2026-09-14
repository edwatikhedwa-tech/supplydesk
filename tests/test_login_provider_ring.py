from __future__ import annotations

import unittest
from pathlib import Path


class LoginProviderRingTests(unittest.TestCase):
    def test_login_keeps_magic_rings_and_equal_provider_choices(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "frontend-v2" / "src" / "pages" / "Login.tsx").read_text(encoding="utf-8")
        self.assertIn("MagicRings", source)
        self.assertIn("id: 'yandex'", source)
        self.assertIn("id: 'google'", source)
        self.assertIn("id: 'mailru'", source)
        self.assertIn("Войти через почту", source)
        self.assertIn("disabled={!provider.enabled}", source)
        self.assertIn("или по email и паролю", source)
        self.assertIn("bg-slate-950/55", source)
        self.assertNotIn("bg-surface p-6 shadow", source)
