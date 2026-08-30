import unittest

from supplier_discovery_v2.contacts import ContactCandidate, prioritize_contacts
from supplier_discovery_v2.matching import qualify_candidate
from supplier_discovery_v2.query_planner import load_positions


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.position = load_positions(key="кабель ВВГ нг 3х2,5")[0]

    def test_exact_seller_contact_is_qualified(self):
        html = "<html><title>Кабель ВВГнг 3x2.5 купить</title><body>ООО КабельСнаб. Поставщик, продажа оптом, в наличии. Email: sales@cablesnab.example. Телефон: +7 (999) 123-45-67</body></html>"
        offer = qualify_candidate(self.position, "direct_site", "https://cablesnab.example/product/vvgng", "Кабель ВВГнг 3x2.5 купить", "Поставщик кабеля", html, [])
        self.assertEqual(offer.status, "qualified")
        self.assertEqual(offer.match_class, "exact_match")
        self.assertEqual([contact.value for contact in offer.contacts], ["sales@cablesnab.example", "+79991234567"])

    def test_buyer_request_is_never_qualified(self):
        html = "<html><title>Купим кабель ВВГнг 3x2.5</title><body>Требуется поставщик. Отправьте предложение: buyer@example.com +7 (999) 123-45-67</body></html>"
        offer = qualify_candidate(self.position, "directory", "https://directory.example/buy-request", "Купим кабель ВВГнг 3x2.5", "Требуется поставщик", html, [])
        self.assertEqual(offer.status, "unqualified")
        self.assertEqual(offer.role, "buyer_request")
        self.assertIn("buyer_request", offer.reasons)

    def test_buyer_title_wins_over_seller_footer_markers(self):
        html = "<html><body>Поставщик, продажа, в наличии, цена, опт, доставка, каталог. Телефон +7 (999) 123-45-67</body></html>"
        offer = qualify_candidate(self.position, "flagma", "https://flagma.ru/chelyabinsk/products/123", "Купим кабель ВВГнг 3x2.5", "Требуется поставщик", html, [], "flagma.ru")
        self.assertEqual(offer.role, "buyer_request")
        self.assertEqual(offer.status, "unqualified")

    def test_platform_owned_contact_is_rejected(self):
        html = "<html><title>Кабель ВВГнг 3x2.5 купить</title><body>Поставщик, продажа. Email: support@flagma.ru</body></html>"
        offer = qualify_candidate(self.position, "flagma", "https://flagma.ru/ufa/products/123", "Кабель ВВГнг 3x2.5 купить", "Поставщик", html, [], "flagma.ru")
        self.assertEqual(offer.status, "unqualified")
        self.assertIn("no_public_seller_contact", offer.reasons)
        self.assertFalse(offer.contacts)

    def test_missing_technical_spec_is_not_an_acceptable_match(self):
        html = "<html><body>Магазин, продажа кабеля. sales@cable.example +7 (999) 123-45-67</body></html>"
        offer = qualify_candidate(self.position, "direct_site", "https://cable.example/product", "Кабель 3x2.5 купить", "Кабель в наличии", html, [])
        self.assertEqual(offer.match_class, "near_match")
        self.assertEqual(offer.status, "unqualified")

    def test_contact_duplicates_are_collapsed(self):
        html = "<html><body>Продажа кабеля ВВГнг 3x2.5. sales@cable.example +7 (999) 123-45-67</body></html>"
        offer = qualify_candidate(self.position, "direct_site", "https://cable.example/product", "Кабель ВВГнг 3x2.5 купить", "Поставщик", html + html, [])
        self.assertEqual(len(offer.contacts), 2)

    def test_region_phone_is_preferred_over_other_branch(self):
        contacts = [
            ContactCandidate("phone", "+74162229674", 0.82, "https://supplier.example/contacts", "Благовещенск телефон: 8 (416) 222-96-74 многоканальный Москва г. Москва, ул. Семеновский Вал"),
            ContactCandidate("phone", "+74993400239", 0.82, "https://supplier.example/contacts", "Москва г. Москва, ул. Семеновский Вал телефон: 8 (499) 340-02-39 многоканальный"),
            ContactCandidate("phone", "+78003025006", 0.82, "https://supplier.example/contacts", "8 (800) 302-50-06 бесплатно для регионов"),
        ]
        selected = prioritize_contacts(contacts, "Москва")
        self.assertEqual(selected[0].value, "+74993400239")
        self.assertIn("+78003025006", [contact.value for contact in selected])


if __name__ == "__main__":
    unittest.main()
