"""EDW-33: attachment parsing, checksum, matching, idempotency and vision admission. No network, no benchmark fixtures:
tiny files are built in memory."""

from __future__ import annotations

import io
import unittest
import zipfile
from types import SimpleNamespace

from mail import attachment_intelligence as A

POSITIONS = [
    {"pid": "P1", "name": "Подшипник шариковый SKF 6205-2RS1", "sku": "6205-2RS1", "brand": "SKF", "qty": 40, "unit": "шт"},
    {"pid": "P2", "name": "Подшипник шариковый 6306-2Z HRB", "sku": "6306-2Z", "brand": "HRB", "qty": 30, "unit": "шт"},
    {"pid": "P3", "name": "Подшипник роликовый NU 2210 E", "sku": "NU 2210 E", "brand": "FAG", "qty": 10, "unit": "шт"},
    {"pid": "P4", "name": "Болт DIN 933 M8x30 кл. 8.8 оцинкованный", "sku": "DIN933-M8x30-88", "brand": "Metiz", "qty": 200, "unit": "шт"},
    {"pid": "P5", "name": "Болт DIN 933 M10x40 кл. 8.8 оцинкованный", "sku": "DIN933-M10x40-88", "brand": "Metiz", "qty": 200, "unit": "шт"},
]


def xlsx(rows: list[list], hidden_cols=()) -> bytes:
    from xml.sax.saxutils import escape
    body = []
    for r, cells in enumerate(rows, 1):
        cs = []
        for c, v in enumerate(cells, 1):
            ref = f"{chr(64 + c)}{r}"
            cs.append(f'<c r="{ref}"><v>{v}</v></c>' if isinstance(v, (int, float)) else f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>')
        body.append(f'<row r="{r}">{"".join(cs)}</row>')
    cols = "".join(f'<col min="{c}" max="{c}" hidden="1"/>' for c in hidden_cols)
    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + (f"<cols>{cols}</cols>" if cols else "")
             + f'<sheetData>{"".join(body)}</sheetData></worksheet>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Цены" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


QUOTE = [["Коммерческое предложение"], [],
         ["№", "Наименование", "Артикул", "Кол-во", "Ед.", "Цена, руб.", "Сумма, руб."],
         [1, "Подшипник SKF 6205-2RS1", "6205-2RS1", 40, "шт", 1850, 74000],
         [2, "Подшипник 6306-2Z HRB", "6306-2Z", 30, "шт", 780.5, 23415],
         ["", "ИТОГО", "", "", "", "", 97415],
         ["Цены указаны без НДС"], ["Срок поставки: 7 рабочих дней"]]


class ParseAndExtractTest(unittest.TestCase):
    def test_xlsx_lines_carry_sheet_and_row_and_terms_are_read(self) -> None:
        r = A.analyze_attachment(xlsx(QUOTE), "kp.xlsx")
        self.assertEqual((r["status"], r["is_quote"], len(r["facts"])), ("ok", True, 2))
        f = r["facts"][0]
        self.assertEqual((f["price"], f["qty"], f["sku"], f["loc"]), (1850.0, 40.0, "6205-2RS1", {"sheet": "Цены", "row": 4}))
        self.assertEqual((r["vat_mode"], r["delivery_days"], r["currency"]), ("excluded", 7, "RUB"))

    def test_total_row_and_document_total_are_never_a_price(self) -> None:
        r = A.analyze_attachment(xlsx(QUOTE), "kp.xlsx")
        self.assertNotIn(97415.0, [f["price"] for f in r["facts"]])
        self.assertNotIn(74000.0, [f["price"] for f in r["facts"]])

    def test_hidden_column_is_not_read(self) -> None:
        rows = [["№", "Наименование", "Артикул", "Кол-во", "Ед.", "Старая цена", "Цена, руб."], [1, "Подшипник 6205-2RS1", "6205-2RS1", 10, "шт", 999, 800]]
        r = A.analyze_attachment(xlsx(rows, hidden_cols=[6]), "kp.xlsx")
        self.assertEqual([f["price"] for f in r["facts"]], [800.0])

    def test_every_fact_has_a_locator(self) -> None:
        r = A.analyze_attachment(xlsx(QUOTE), "kp.xlsx")
        self.assertTrue(all(f["loc"] for f in r["facts"]))

    def test_empty_corrupt_and_unknown_files_go_to_manual_review_without_facts(self) -> None:
        for data, name, reason in ((b"", "a.pdf", "empty_file"), (xlsx(QUOTE)[:200], "a.xlsx", "corrupt_file"), (b"PK\x03\x04junk", "a.docx", "corrupt_file"),
                                   (b"MZ\x90\x00", "a.exe", "unsupported_format")):
            r = A.analyze_attachment(data, name)
            self.assertEqual((r["status"], r["manual_review"], r["facts"], reason in r["reasons"]), ("unreadable", True, [], True), name)

    def test_price_on_request_is_not_a_price(self) -> None:
        rows = [["№", "Наименование", "Кол-во", "Цена, руб."], [1, "Подшипник 6205-2RS1", 10, "по запросу"]]
        f = A.analyze_attachment(xlsx(rows), "k.xlsx")["facts"][0]
        self.assertEqual((f["price"], f["review"]), (None, "price_on_request"))


class ChecksumTest(unittest.TestCase):
    def test_ocr_lookalike_digits_are_repaired_only_when_qty_times_price_equals_total(self) -> None:
        r = A.resolve_row_numbers("з 542,64", "12", "42 511,68", 1, None, 12.0)        # 'з' read instead of '3'
        self.assertEqual((r["state"], r["price"], r["qty"]), ("ok", 3542.64, 12.0))
        bad = A.resolve_row_numbers("з 542,64", "12", "42 000,00", 1, None, 12.0)      # checksum does not hold: no repair is accepted
        self.assertEqual(bad["state"], "mismatch")

    def test_missing_quantity_is_derived_only_from_an_exact_integer(self) -> None:
        self.assertEqual(A.resolve_row_numbers("819,78", "", "24 593,40", 1, 819.78, None)["qty"], 30.0)
        self.assertEqual(A.resolve_row_numbers("3,17", "", "170 850,00", 1, 3.17, None)["state"], "mismatch")   # 53895.9 is not an integer

    def test_price_per_100_is_part_of_the_checksum(self) -> None:
        self.assertEqual(A.resolve_row_numbers("500,00", "200", "1 000,00", 100, 500.0, 200.0)["state"], "ok")


class MatchingTest(unittest.TestCase):
    def match(self, name, sku=None):
        return A.match_position({"name": name, "sku": sku}, POSITIONS)

    def test_same_article_in_any_spelling_is_exact(self) -> None:
        for name in ("Подш. SKF 6205-2RS1", "SKF 6205 2RS1 подшипник", "Подшипник 6205-2RS1"):
            self.assertEqual((self.match(name)["status"], self.match(name)["pid"]), ("exact", "P1"), name)

    def test_an_article_that_extends_the_requested_one_is_an_analog_never_exact(self) -> None:
        m = self.match("Подшипник шариковый ZWZ 6306-2Z", "6306-2Z-ZWZ")
        self.assertEqual((m["status"], m["pid"]), ("analog", "P2"))
        m = self.match("Подшипник роликовый NU 2210 ECP", "NU 2210 ECP")
        self.assertEqual((m["status"], m["pid"]), ("analog", "P3"))

    def test_size_and_standard_decide_between_bolts(self) -> None:
        self.assertEqual(self.match("Болт M10x40 8.8 цинк DIN 933")["pid"], "P5")
        self.assertEqual(self.match("Болт М8x30 DIN933 8.8")["pid"], "P4")            # Cyrillic М and х

    def test_same_size_other_standard_is_an_analog(self) -> None:
        m = self.match("Болт ГОСТ 7798 M8x30 кл. 8.8")
        self.assertEqual((m["status"], m["pid"]), ("analog", "P4"))

    def test_a_line_with_the_standard_but_without_the_size_is_ambiguous(self) -> None:
        m = self.match("Болт DIN 933 кл. 8.8 оцинкованный")
        self.assertEqual((m["status"], sorted(m["candidates"])), ("ambiguous", ["P4", "P5"]))

    def test_an_item_that_was_not_requested_stays_unmatched(self) -> None:
        for name, sku in (("Болт DIN 933 M14x50 кл. 8.8", None), ("Подшипник шариковый 6304-2RS", "6304-2RS"), ("Кирпич силикатный", None)):
            self.assertEqual(self.match(name, sku)["status"], "unmatched", name)

    def test_a_model_number_shared_by_two_positions_is_ambiguous_not_guessed(self) -> None:
        positions = POSITIONS + [{"pid": "P6", "name": "Подшипник шариковый 6205ZZ", "sku": "6205ZZ", "brand": "GPZ", "qty": 5, "unit": "шт"}]
        m = A.match_position({"name": "Подшипник шариковый NSK 6205DDU", "sku": "6205DDU"}, positions)
        self.assertEqual((m["status"], sorted(m["candidates"])), ("ambiguous", ["P1", "P6"]))

    def test_ocr_reads_the_i_of_din_as_l(self) -> None:
        self.assertEqual(self.match("Болт M10x40 8.8 цинк DlN 933")["pid"], "P5")


class Models:
    def __init__(self, data) -> None:
        self.data, self.calls = data, 0

    def call(self, stage, system, user, schema):
        self.calls += 1
        return SimpleNamespace(data=self.data, model="m", input_tokens=10, output_tokens=5, cost_rub=0.001, latency_ms=1, error="")


class IdempotencyAndAdmissionTest(unittest.TestCase):
    def test_same_bytes_are_analysed_once(self) -> None:
        cache, data = A.MemoryCache(), xlsx(QUOTE)
        first = A.analyze_attachment(data, "a.xlsx", cache=cache)
        second = A.analyze_attachment(data, "renamed.xlsx", cache=cache)
        self.assertEqual((first["cache_hit"], second["cache_hit"], second["ai_calls"], second["ocr_pages"]), (False, True, [], 0))
        self.assertEqual(first["facts"], second["facts"])

    def test_a_new_analysis_version_recomputes(self) -> None:
        cache, data = A.MemoryCache(), xlsx(QUOTE)
        A.analyze_attachment(data, "a.xlsx", cache=cache, version="v1")
        self.assertFalse(A.analyze_attachment(data, "a.xlsx", cache=cache, version="v2")["cache_hit"])

    def test_the_same_file_twice_in_one_email_counts_once(self) -> None:
        r = A.analyze_attachment(xlsx(QUOTE), "a.xlsx")
        merged = A.merge_attachments([r, dict(r)], POSITIONS)
        self.assertEqual((merged["unique_documents"], merged["duplicate_attachments"], len(merged["lines"])), (1, 1, 2))

    def test_two_documents_with_different_prices_for_one_position_are_a_conflict(self) -> None:
        a = A.analyze_attachment(xlsx(QUOTE), "a.xlsx")
        rows = [list(r) for r in QUOTE]
        rows[3][5], rows[3][6] = 1900, 76000
        b = A.analyze_attachment(xlsx(rows), "b.xlsx")
        merged = A.merge_attachments([a, b], POSITIONS)
        self.assertEqual([c["pid"] for c in merged["conflicts"]], ["P1"])
        self.assertTrue(merged["manual_review"])
        same = A.merge_attachments([a, A.analyze_attachment(xlsx(QUOTE + [[]]), "c.xlsx")], POSITIONS)
        self.assertEqual((same["conflicts"], sorted(same["confirmed_by_two_sources"])), ([], ["P1", "P2"]))

    def test_a_terms_only_file_donates_delivery_to_the_quote_file(self) -> None:
        quote = A.analyze_attachment(xlsx([row for row in QUOTE if not (row and str(row[0]).startswith("Срок"))]), "q.xlsx")
        terms = A.analyze_attachment(xlsx([["Условия"], ["Срок поставки: 14 календарных дней"]]), "t.xlsx")
        self.assertIsNone(quote["delivery_days"])
        merged = A.merge_attachments([quote, terms], POSITIONS)
        self.assertEqual({ln["delivery_days"] for ln in merged["lines"]}, {14})

    def test_vision_answer_is_admitted_only_with_checksum_and_a_visible_number(self) -> None:
        target = [{"text": "5  Смазка SkF LGMT 2/1  LGMT 2/1  8  шт  2221,58  17 772,64", "loc": {"page": 1, "bbox": [0, 0, 1, 1], "ocr": True}}]
        good = {"items": [{"row_no": 5, "name": "Смазка SKF LGMT 2/1", "sku": "LGMT 2/1", "quantity": 8, "unit": "шт", "price": 2221.58, "total": 17772.64}]}
        wrong_but_consistent = {"items": [{"row_no": 5, "name": "Смазка SKF LGMT 2/1", "sku": "LGMT 2/1", "quantity": 6, "unit": "шт", "price": 294.58, "total": 1767.48}]}
        inconsistent = {"items": [{"row_no": 5, "name": "Смазка SKF LGMT 2/1", "sku": "LGMT 2/1", "quantity": 5, "unit": "шт", "price": 2221.58, "total": 17772.64}]}
        img = SimpleNamespace(convert=lambda mode: SimpleNamespace(width=100, save=lambda buf, fmt, **kw: buf.write(b"x")))
        for data, expected in ((good, 1), (wrong_but_consistent, 0), (inconsistent, 0)):
            facts, left, ledger = A.vision_repair(Models(data), 1, img, target, {"currency": "RUB"})
            self.assertEqual(len(facts), expected, data)
            self.assertEqual(len(ledger), 1)
        self.assertEqual(facts, [])
        facts, _, _ = A.vision_repair(Models(good), 1, img, target, {"currency": "RUB"})
        self.assertEqual((facts[0]["price"], facts[0]["source"], facts[0]["loc"]["page"]), (2221.58, "vision", 1))

    def test_text_model_answer_with_a_number_not_in_the_row_is_dropped(self) -> None:
        rows = [{"text": "3  Гайка M10  400  шт  2,42  968,00", "loc": {"page": 1}, "header": ""}]
        guess = Models({"items": [{"row_id": 0, "name": "Гайка M10", "sku": None, "quantity": 400, "unit": "шт", "price": 2.5}]})
        facts, left, _ = A.ai_read_rows(guess, rows, {"currency": "RUB"})
        self.assertEqual((facts, len(left)), ([], 1))
        right = Models({"items": [{"row_id": 0, "name": "Гайка M10", "sku": None, "quantity": 400, "unit": "шт", "price": 2.42}]})
        self.assertEqual(len(A.ai_read_rows(right, rows, {"currency": "RUB"})[0]), 1)


if __name__ == "__main__":
    unittest.main()
