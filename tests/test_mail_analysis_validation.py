"""EDW-26: the validator must not let a guess become a fact. Scripted model answers, no API.
Covers: invented SKU, invented price, wrong currency, a quote that is not in the letter, a price that exists only in
the quoted history, a number that is not a price, and two possible requests."""

from __future__ import annotations

import unittest

from mail.message_analysis import normalize_text, validate_extraction

SUBJECT = "Re: Запрос цены"
BODY = ("Добрый день!\nПодшипник SKF 6205-2RS1 — 20 шт., цена 1 850 руб. за шт. с НДС 20%.\nАртикул печи 78500, "
        "ИНН 7707083893, тел. 8 800 555-35-35.\n> Ранее: ориентир 1 200 руб. за шт. подшипник 6206-ZZ\n")
TEXT = normalize_text(SUBJECT, BODY)
QUOTE = "Подшипник SKF 6205-2RS1 — 20 шт., цена 1 850 руб. за шт. с НДС 20%"


def answer(**over):
    item = {"name": "Подшипник SKF 6205-2RS1", "sku": "6205-2RS1", "price": 1850, "currency": "RUB", "quantity": 20,
            "source_quote": QUOTE}
    item.update(over)
    return {"message_type": "quote", "items": [item]}


class GuessNeverBecomesFactTest(unittest.TestCase):
    def issues(self, data) -> list[str]:
        return validate_extraction(data, TEXT)["issues"]

    def test_a_correct_answer_is_accepted(self) -> None:
        verdict = validate_extraction(answer(), TEXT)
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["facts"][0]["data"]["price"], 1850.0)

    def test_invented_sku_is_dropped_but_the_supported_price_stays(self) -> None:
        verdict = validate_extraction(answer(sku="6999-XX"), TEXT)
        self.assertIsNone(verdict["facts"][0]["data"]["sku"])
        self.assertIn("item0:sku_not_in_message", verdict["issues"])
        self.assertFalse(verdict["ok"])                       # an issue was found -> not accepted as clean

    def test_invented_price_is_rejected(self) -> None:
        for price in (1200, 1600, 18500):
            verdict = validate_extraction(answer(price=price), TEXT)
            self.assertEqual((verdict["facts"], verdict["issues"][:1]), ([], ["item0:price_not_in_quote"]), price)

    def test_wrong_currency_is_rejected(self) -> None:
        self.assertEqual(self.issues(answer(currency="USD"))[:1], ["item0:currency_not_in_message"])
        self.assertEqual(self.issues(answer(currency="EUR"))[:1], ["item0:currency_not_in_message"])
        self.assertEqual(self.issues(answer(currency="XXX"))[:1], ["item0:currency_invalid"])

    def test_a_quote_that_is_not_in_the_letter_is_rejected(self) -> None:
        self.assertEqual(self.issues(answer(source_quote="Подшипник SKF 6205-2RS1 по 1 850 руб. со склада в Твери"))[:1],
                         ["item0:source_quote_not_in_message"])

    def test_a_price_that_exists_only_in_quoted_history_is_rejected(self) -> None:
        # the quoted line is removed before the model sees the letter and before validation
        self.assertNotIn("6206", TEXT)
        self.assertEqual(self.issues(answer(sku="6206-ZZ", price=1200, source_quote="ориентир 1 200 руб. за шт. подшипник 6206-ZZ"))[:1],
                         ["item0:source_quote_not_in_message"])

    def test_a_number_that_is_not_a_price_is_rejected_when_no_currency_stands_with_it(self) -> None:
        text = normalize_text(SUBJECT, "Артикул печи 78500, ИНН 7707083893, тел. 8 800 555-35-35. Срок 5 дней.")
        for quote, price in (("Артикул печи 78500", 78500), ("ИНН 7707083893", 7707083893), ("тел. 8 800 555-35-35", 8800)):
            verdict = validate_extraction({"message_type": "quote", "items": [
                {"name": "x", "price": price, "currency": "RUB", "source_quote": quote}]}, text)
            self.assertEqual(verdict["facts"], [], quote)

    def test_a_price_without_any_currency_in_the_letter_is_rejected(self) -> None:
        text = normalize_text("Re", "Подшипник 6205-2RS1: цена 1850.")
        verdict = validate_extraction({"message_type": "quote", "items": [
            {"name": "Подшипник", "sku": "6205-2RS1", "price": 1850, "currency": "RUB", "source_quote": "Подшипник 6205-2RS1: цена 1850"}]}, text)
        self.assertEqual((verdict["facts"], verdict["issues"][:1]), ([], ["item0:currency_not_in_message"]))

    def test_the_price_must_match_the_number_after_thousand_separators(self) -> None:
        for price in (1850, 1850.0, "1850", "1 850", "1850,00"):
            self.assertTrue(validate_extraction(answer(price=price), TEXT)["facts"], price)


    def test_a_price_written_in_the_letter_but_missing_from_the_answer_is_flagged(self) -> None:
        text = normalize_text("Re", "Подшипник 6306-2Z: 780 руб./шт. без НДС, от 50 шт. — 730 руб.")
        one = {"message_type": "quote", "items": [{"name": "Подшипник 6306-2Z", "sku": "6306-2Z", "price": 780, "currency": "RUB",
                                                   "source_quote": "Подшипник 6306-2Z: 780 руб./шт."}]}
        verdict = validate_extraction(one, text)
        self.assertEqual((verdict["ok"], verdict["issues"]), (False, ["price_mentioned_not_extracted"]))
        self.assertEqual(len(verdict["facts"]), 1)                  # the supported fact is kept, the doubt is recorded
        two = {"message_type": "quote", "items": one["items"] + [{"name": "Подшипник 6306-2Z", "sku": "6306-2Z", "price": 730,
                                                                  "currency": "RUB", "source_quote": "от 50 шт. — 730 руб."}]}
        self.assertTrue(validate_extraction(two, text)["ok"])

    def test_the_same_amount_in_different_formats_is_covered(self) -> None:
        text = normalize_text("Re", "Подшипник 6205: 1 420,00 руб./шт.")
        answer_ = {"message_type": "quote", "items": [{"name": "Подшипник", "price": 1420, "currency": "RUB", "source_quote": "1 420,00 руб./шт."}]}
        self.assertTrue(validate_extraction(answer_, text)["ok"])


    def test_a_price_range_is_not_a_price(self) -> None:
        text = normalize_text("Re", "Кирпич облицовочный: 1 200–1 350 руб. за м2, точную цену подтвердим.")
        verdict = validate_extraction({"message_type": "quote", "items": [{"name": "Кирпич", "price": 1200, "currency": "RUB",
                                                                          "source_quote": "1 200–1 350 руб. за м2"}]}, text)
        self.assertEqual((verdict["facts"], verdict["issues"][:1]), ([], ["item0:price_is_range"]))

    def test_an_em_dash_between_the_item_and_its_price_is_not_a_range(self) -> None:
        text = normalize_text("Re", "Rexroth R901025 — 18 400 ₽/шт. Подшипник 6205-2RS1 — 1 780 руб. за шт.")
        for name, price, quote in (("R901025", 18400, "Rexroth R901025 — 18 400 ₽/шт."), ("6205", 1780, "Подшипник 6205-2RS1 — 1 780 руб. за шт.")):
            verdict = validate_extraction({"message_type": "quote", "items": [{"name": name, "price": price, "currency": "RUB", "source_quote": quote}]}, text)
            self.assertTrue(verdict["facts"], quote)
        ranged = normalize_text("Re", "Цена от 1 200 до 1 350 руб. за м2")
        self.assertEqual(validate_extraction({"message_type": "quote", "items": [{"name": "x", "price": 1350, "currency": "RUB", "source_quote": "от 1 200 до 1 350 руб. за м2"}]}, ranged)["facts"], [])

    def test_an_item_without_a_price_is_ignored_not_an_error(self) -> None:
        text = normalize_text("Акция", "Скидка 15% на билеты на форум.")
        verdict = validate_extraction({"message_type": "other", "items": [{"name": "Билет", "price": None, "source_quote": "Скидка 15% на билеты"}]}, text)
        self.assertEqual((verdict["ok"], verdict["facts"], verdict["issues"]), (True, [], []))


if __name__ == "__main__":
    unittest.main()
