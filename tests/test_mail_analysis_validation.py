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


if __name__ == "__main__":
    unittest.main()
