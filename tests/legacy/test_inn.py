"""
Офлайн-проверки извлечения ИНН. Сети не требует.

Главное здесь — контрольная сумма: она превращает «похоже на ИНН»
в «это точно ИНН» без обращения к каким-либо сервисам.

Converted from the standalone root script test_inn.py into a real
unittest.TestCase (TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903) so it
runs under scripts/run_test_suite.py instead of only by manual invocation.
"""

from __future__ import annotations

import unittest

from backend.domain.supplier_identity.inn_extractor import (
    InnHit, extract_inn_from_html, extract_inn_from_text, inn_kind,
    normalize_inn, score_inn, validate_inn_checksum,
)

# Настоящие ИНН крупных компаний — публичные данные из ЕГРЮЛ.
REAL_ORG_INN = "7707083893"   # Сбербанк
REAL_ORG_INN_2 = "7736050003"  # Газпром
REAL_IP_INN = "500100732259"   # 12-значный, физлицо


class InnExtractorTests(unittest.TestCase):
    def _check(self, name: str, actual, expected) -> None:
        with self.subTest(name):
            self.assertEqual(actual, expected, name)

    def test_checksum(self) -> None:
        self._check("настоящий ИНН юрлица", validate_inn_checksum(REAL_ORG_INN), True)
        self._check("второй настоящий ИНН", validate_inn_checksum(REAL_ORG_INN_2), True)
        self._check("настоящий 12-значный", validate_inn_checksum(REAL_IP_INN), True)
        self._check("одна цифра испорчена", validate_inn_checksum("7707083894"), False)
        self._check("две цифры переставлены", validate_inn_checksum("7700783893"), False)
        self._check("круглое число", validate_inn_checksum("1234567890"), False)
        self._check("все нули не проходят как 10-значный", validate_inn_checksum("0000000001"), False)
        self._check("9 цифр — не ИНН", validate_inn_checksum("770708389"), False)
        self._check("11 цифр — не ИНН", validate_inn_checksum("77070838931"), False)
        self._check("буквы", validate_inn_checksum("77070838ab"), False)
        self._check("тип юрлица", inn_kind(REAL_ORG_INN), "organization")
        self._check("тип физлица", inn_kind(REAL_IP_INN), "individual")

    def test_normalize(self) -> None:
        self._check("пробелы убраны", normalize_inn("7707 083 893"), REAL_ORG_INN)
        self._check("дефисы убраны", normalize_inn("7707-083-893"), REAL_ORG_INN)
        self._check("тире убрано", normalize_inn("7707—083—893"), REAL_ORG_INN)

    def test_labeled(self) -> None:
        hits = extract_inn_from_text(f"ООО «Кирпич». ИНН {REAL_ORG_INN}, КПП 770701001")
        self._check("найден один", len(hits), 1)
        self._check("это он", hits[0].inn, REAL_ORG_INN)
        self._check("источник — подпись", hits[0].method, "labeled")
        self._check("контекст сохранён", "ООО" in hits[0].evidence, True)

        hits = extract_inn_from_text(f"ИНН/КПП: {REAL_ORG_INN}/770701001")
        self._check("формат ИНН/КПП разобран", hits[0].inn if hits else None, REAL_ORG_INN)

        hits = extract_inn_from_text(f"ИНН — {REAL_ORG_INN}")
        self._check("тире после подписи", hits[0].inn if hits else None, REAL_ORG_INN)

        hits = extract_inn_from_text(f"инн {REAL_ORG_INN}")
        self._check("нижний регистр", hits[0].inn if hits else None, REAL_ORG_INN)

        hits = extract_inn_from_text(f"ИНН 7707 083 893")
        self._check("с пробелами внутри", hits[0].inn if hits else None, REAL_ORG_INN)

    def test_confusables(self) -> None:
        """Главный источник ошибок: рядом с ИНН стоят похожие номера."""
        # ОГРН 13 цифр — по длине не пройдёт.
        hits = extract_inn_from_text("ОГРН 1027700132195")
        self._check("ОГРН не принят за ИНН", len(hits), 0)

        # Число со сходящейся суммой, но подписанное как расчётный счёт.
        hits = extract_inn_from_text(f"Р/с {REAL_ORG_INN} в банке")
        self._check("расчётный счёт отброшен по подписи", len(hits), 0)

        hits = extract_inn_from_text(f"ОКПО {REAL_ORG_INN}")
        self._check("ОКПО отброшен по подписи", len(hits), 0)

        hits = extract_inn_from_text(f"Артикул {REAL_ORG_INN}")
        self._check("артикул отброшен по подписи", len(hits), 0)

        hits = extract_inn_from_text("Телефон 84957079999, звоните")
        self._check("телефон не прошёл контрольную сумму", len(hits), 0)

        hits = extract_inn_from_text("Цена 1234567890 рублей")
        self._check("случайное число не прошло", len(hits), 0)

        # Настоящий случай с сайтов кирпича: «инн» сидит внутри русских слов.
        self._check("«каминные» не подпись ИНН",
                     len(extract_inn_from_text(f"Каминные {REAL_ORG_INN}")), 0)
        self._check("«длинного» не подпись ИНН",
                     len(extract_inn_from_text(f"кирпич длинного {REAL_ORG_INN}")), 0)
        self._check("«подлинность» не подпись ИНН",
                     len(extract_inn_from_text(f"подлинность {REAL_ORG_INN}")), 0)
        self._check("настоящая подпись по-прежнему работает",
                     extract_inn_from_text(f"ИНН {REAL_ORG_INN}")[0].inn, REAL_ORG_INN)

    def test_html(self) -> None:
        page = f"""<html><body>
          <div class="footer">
            <p>ООО «Кирпичный Двор»</p>
            <p>ИНН {REAL_ORG_INN} / КПП 770701001</p>
            <p>ОГРН 1027700132195</p>
          </div>
          <script>var trackingId = "1234567890";</script>
        </body></html>"""
        hits = extract_inn_from_html(page, "https://zavod.ru/rekvizity/")
        self._check("найден ровно один ИНН", len(hits), 1)
        self._check("это он", hits[0].inn, REAL_ORG_INN)
        self._check("источник записан", hits[0].source_url, "https://zavod.ru/rekvizity/")

        page = f'<html><body><span itemprop="taxID">{REAL_ORG_INN_2}</span></body></html>'
        hits = extract_inn_from_html(page, "https://gaz.ru/")
        self._check("schema.org taxID разобран", hits[0].inn if hits else None, REAL_ORG_INN_2)
        self._check("источник — разметка", hits[0].method if hits else None, "jsonld")

    def test_scoring(self) -> None:
        hit = InnHit(inn=REAL_ORG_INN, method="labeled", checksum_ok=True)
        hit.dadata_ok = True
        hit.company_name = "ПАО СБЕРБАНК"
        score_inn(hit, on_requisites_page=True)
        self._check("подпись + сумма + реестр = подтверждён", hit.confidence, "high")
        self._check("название компании в причине",
                     any("СБЕРБАНК" in r for r in hit.reasons), True)

        hit = InnHit(inn=REAL_ORG_INN, method="labeled", checksum_ok=True)
        hit.dadata_ok = False
        score_inn(hit)
        self._check("нет в реестре — не подтверждаем", hit.confidence, "low")

        hit = InnHit(inn=REAL_ORG_INN, method="labeled", checksum_ok=True)
        score_inn(hit, on_requisites_page=True)
        self._check("без реестра — вероятен, но не подтверждён", hit.confidence, "medium")

        hit = InnHit(inn=REAL_ORG_INN, method="llm", checksum_ok=True)
        hit.dadata_ok = True
        score_inn(hit, on_requisites_page=True)
        self._check("модель + реестр = подтверждён", hit.confidence, "high")

        hit = InnHit(inn=REAL_ORG_INN, method="llm", checksum_ok=True)
        score_inn(hit, on_requisites_page=True)
        self._check("модель без реестра не подтверждается", hit.confidence, "medium")

        hit = InnHit(inn="7707083894", method="labeled", checksum_ok=False)
        score_inn(hit)
        self._check("без контрольной суммы — ноль", hit.score, 0)
        self._check("причина названа", "не сошлась" in hit.reasons[0], True)


if __name__ == "__main__":
    unittest.main()
