from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ListPageHeaderPluralizationTests(unittest.TestCase):
    """Regression guard: Requests/Suppliers/Blacklist header counters used to
    read "1 заявок в работе", "1 поставщиков", "1 доменов" -- the same
    ungrammatical genitive-plural-always bug the Dashboard KPI chips had,
    fixed there first with the shared `pluralRu` helper. Owner audit request:
    "оцени весь сайт... найди косяки" surfaced the same bug repeated in three
    more places; this applies the identical fix.
    """

    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_requests_page_declines_the_request_count(self) -> None:
        source = self.read("frontend-v2/src/pages/Requests.tsx")
        self.assertIn("pluralRu(requests.length, 'заявка', 'заявки', 'заявок')", source)

    def test_suppliers_page_declines_the_supplier_count(self) -> None:
        source = self.read("frontend-v2/src/pages/Suppliers.tsx")
        self.assertIn("pluralRu(suppliers.length, 'поставщик', 'поставщика', 'поставщиков')", source)

    def test_blacklist_page_declines_both_supplier_and_domain_counts(self) -> None:
        source = self.read("frontend-v2/src/pages/Blacklist.tsx")
        self.assertIn("pluralRu(suppliers.length, 'поставщик', 'поставщика', 'поставщиков')", source)
        self.assertIn("pluralRu(domains.length, 'домен', 'домена', 'доменов')", source)


if __name__ == "__main__":
    unittest.main()
