"""
Офлайн-проверки извлечения ИНН. Сети не требует.

Главное здесь — контрольная сумма: она превращает «похоже на ИНН»
в «это точно ИНН» без обращения к каким-либо сервисам.

Запуск:  python test_inn.py
"""

from __future__ import annotations

import sys

from backend.domain.supplier_identity.inn_extractor import (
    InnHit, extract_inn_from_html, extract_inn_from_text, inn_kind,
    normalize_inn, score_inn, validate_inn_checksum,
)

failures: list[str] = []


def check(name: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {name}")
    else:
        failures.append(f"{name}: получено {actual!r}, ожидалось {expected!r}")
        print(f"  FAIL {name}: получено {actual!r}, ожидалось {expected!r}")


# Настоящие ИНН крупных компаний — публичные данные из ЕГРЮЛ.
REAL_ORG_INN = "7707083893"   # Сбербанк
REAL_ORG_INN_2 = "7736050003"  # Газпром
REAL_IP_INN = "500100732259"   # 12-значный, физлицо


def test_checksum() -> None:
    print("Контрольная сумма:")
    check("настоящий ИНН юрлица", validate_inn_checksum(REAL_ORG_INN), True)
    check("второй настоящий ИНН", validate_inn_checksum(REAL_ORG_INN_2), True)
    check("настоящий 12-значный", validate_inn_checksum(REAL_IP_INN), True)
    check("одна цифра испорчена", validate_inn_checksum("7707083894"), False)
    check("две цифры переставлены", validate_inn_checksum("7700783893"), False)
    check("круглое число", validate_inn_checksum("1234567890"), False)
    check("все нули не проходят как 10-значный", validate_inn_checksum("0000000001"), False)
    check("9 цифр — не ИНН", validate_inn_checksum("770708389"), False)
    check("11 цифр — не ИНН", validate_inn_checksum("77070838931"), False)
    check("буквы", validate_inn_checksum("77070838ab"), False)
    check("тип юрлица", inn_kind(REAL_ORG_INN), "organization")
    check("тип физлица", inn_kind(REAL_IP_INN), "individual")


def test_normalize() -> None:
    print("Нормализация:")
    check("пробелы убраны", normalize_inn("7707 083 893"), REAL_ORG_INN)
    check("дефисы убраны", normalize_inn("7707-083-893"), REAL_ORG_INN)
    check("тире убрано", normalize_inn("7707—083—893"), REAL_ORG_INN)


def test_labeled() -> None:
    print("Извлечение с подписью:")
    hits = extract_inn_from_text(f"ООО «Кирпич». ИНН {REAL_ORG_INN}, КПП 770701001")
    check("найден один", len(hits), 1)
    check("это он", hits[0].inn, REAL_ORG_INN)
    check("источник — подпись", hits[0].method, "labeled")
    check("контекст сохранён", "ООО" in hits[0].evidence, True)

    hits = extract_inn_from_text(f"ИНН/КПП: {REAL_ORG_INN}/770701001")
    check("формат ИНН/КПП разобран", hits[0].inn if hits else None, REAL_ORG_INN)

    hits = extract_inn_from_text(f"ИНН — {REAL_ORG_INN}")
    check("тире после подписи", hits[0].inn if hits else None, REAL_ORG_INN)

    hits = extract_inn_from_text(f"инн {REAL_ORG_INN}")
    check("нижний регистр", hits[0].inn if hits else None, REAL_ORG_INN)

    hits = extract_inn_from_text(f"ИНН 7707 083 893")
    check("с пробелами внутри", hits[0].inn if hits else None, REAL_ORG_INN)


def test_confusables() -> None:
    """Главный источник ошибок: рядом с ИНН стоят похожие номера."""
    print("Отсев похожих номеров:")
    # ОГРН 13 цифр — по длине не пройдёт.
    hits = extract_inn_from_text("ОГРН 1027700132195")
    check("ОГРН не принят за ИНН", len(hits), 0)

    # Число со сходящейся суммой, но подписанное как расчётный счёт.
    hits = extract_inn_from_text(f"Р/с {REAL_ORG_INN} в банке")
    check("расчётный счёт отброшен по подписи", len(hits), 0)

    hits = extract_inn_from_text(f"ОКПО {REAL_ORG_INN}")
    check("ОКПО отброшен по подписи", len(hits), 0)

    hits = extract_inn_from_text(f"Артикул {REAL_ORG_INN}")
    check("артикул отброшен по подписи", len(hits), 0)

    hits = extract_inn_from_text("Телефон 84957079999, звоните")
    check("телефон не прошёл контрольную сумму", len(hits), 0)

    hits = extract_inn_from_text("Цена 1234567890 рублей")
    check("случайное число не прошло", len(hits), 0)

    # Настоящий случай с сайтов кирпича: «инн» сидит внутри русских слов.
    check("«каминные» не подпись ИНН",
          len(extract_inn_from_text(f"Каминные {REAL_ORG_INN}")), 0)
    check("«длинного» не подпись ИНН",
          len(extract_inn_from_text(f"кирпич длинного {REAL_ORG_INN}")), 0)
    check("«подлинность» не подпись ИНН",
          len(extract_inn_from_text(f"подлинность {REAL_ORG_INN}")), 0)
    check("настоящая подпись по-прежнему работает",
          extract_inn_from_text(f"ИНН {REAL_ORG_INN}")[0].inn, REAL_ORG_INN)


def test_html() -> None:
    print("Разбор страницы:")
    page = f"""<html><body>
      <div class="footer">
        <p>ООО «Кирпичный Двор»</p>
        <p>ИНН {REAL_ORG_INN} / КПП 770701001</p>
        <p>ОГРН 1027700132195</p>
      </div>
      <script>var trackingId = "1234567890";</script>
    </body></html>"""
    hits = extract_inn_from_html(page, "https://zavod.ru/rekvizity/")
    check("найден ровно один ИНН", len(hits), 1)
    check("это он", hits[0].inn, REAL_ORG_INN)
    check("источник записан", hits[0].source_url, "https://zavod.ru/rekvizity/")

    page = f'<html><body><span itemprop="taxID">{REAL_ORG_INN_2}</span></body></html>'
    hits = extract_inn_from_html(page, "https://gaz.ru/")
    check("schema.org taxID разобран", hits[0].inn if hits else None, REAL_ORG_INN_2)
    check("источник — разметка", hits[0].method if hits else None, "jsonld")


def test_scoring() -> None:
    print("Достоверность:")
    hit = InnHit(inn=REAL_ORG_INN, method="labeled", checksum_ok=True)
    hit.dadata_ok = True
    hit.company_name = "ПАО СБЕРБАНК"
    score_inn(hit, on_requisites_page=True)
    check("подпись + сумма + реестр = подтверждён", hit.confidence, "high")
    check("название компании в причине",
          any("СБЕРБАНК" in r for r in hit.reasons), True)

    hit = InnHit(inn=REAL_ORG_INN, method="labeled", checksum_ok=True)
    hit.dadata_ok = False
    score_inn(hit)
    check("нет в реестре — не подтверждаем", hit.confidence, "low")

    hit = InnHit(inn=REAL_ORG_INN, method="labeled", checksum_ok=True)
    score_inn(hit, on_requisites_page=True)
    check("без реестра — вероятен, но не подтверждён", hit.confidence, "medium")

    hit = InnHit(inn=REAL_ORG_INN, method="llm", checksum_ok=True)
    hit.dadata_ok = True
    score_inn(hit, on_requisites_page=True)
    check("модель + реестр = подтверждён", hit.confidence, "high")

    hit = InnHit(inn=REAL_ORG_INN, method="llm", checksum_ok=True)
    score_inn(hit, on_requisites_page=True)
    check("модель без реестра не подтверждается", hit.confidence, "medium")

    hit = InnHit(inn="7707083894", method="labeled", checksum_ok=False)
    score_inn(hit)
    check("без контрольной суммы — ноль", hit.score, 0)
    check("причина названа", "не сошлась" in hit.reasons[0], True)


def main() -> int:
    for test in (test_checksum, test_normalize, test_labeled,
                 test_confusables, test_html, test_scoring):
        test()
    print()
    if failures:
        print(f"ПРОВАЛЕНО проверок: {len(failures)}")
        for f in failures:
            print("  -", f)
        return 1
    print("Все проверки пройдены.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
