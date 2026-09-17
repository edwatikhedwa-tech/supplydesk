from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SupplierCardPanelWebsiteLinkTests(unittest.TestCase):
    def test_unresolved_supplier_still_offers_a_link_to_its_own_site(self) -> None:
        # Owner report while reviewing a thread whose supplier has no ИНН yet:
        # "я бы хотел иметь возможность перейти на сайт компании, если даже
        # инн нету" -- the "Найти по ИНН" dead-end used to offer no way out
        # at all before this, even though the thread's site (supplierHost)
        # is known from the moment the thread exists.
        source = (ROOT / "frontend-v2" / "src" / "components" / "SupplierCardPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("supplierHost", source)
        self.assertIn("supplierHost.startsWith('http')", source)
        self.assertIn("target=\"_blank\"", source)

    def test_messages_screen_passes_the_thread_host_through(self) -> None:
        source = (ROOT / "frontend-v2" / "src" / "pages" / "Messages.tsx").read_text(encoding="utf-8")
        self.assertIn("supplierHost={activeThread.supplier_host}", source)


if __name__ == "__main__":
    unittest.main()
