"""
Офлайн-проверки извлечения email. Сети не требует.

Две группы: полнота (находим ли всё, что опубликовано) и точность
(не тащим ли мусор). Обе меряются на одной фикстуре, чтобы правки,
поднимающие одно за счёт другого, сразу были видны.

Запуск:  python test_extractor.py
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from backend.domain.supplier_identity.email_extractor import (
    EmailHit, decode_cfemail, deobfuscate, extract_from_html, merge_hits,
    normalize_email, repair_email_candidate, score_hit, split_mailto_addresses,
    validate_email, is_contact_url,
)
from backend.integrations.search.web_lookup import WebLookup

failures: list[str] = []


def check(name: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {name}")
    else:
        failures.append(f"{name}: получено {actual!r}, ожидалось {expected!r}")
        print(f"  FAIL {name}: получено {actual!r}, ожидалось {expected!r}")


# Каждый адрес опубликован своим способом — проверяем всю лестницу извлечения.
PAGE_ALL_METHODS = """
<html><head>
  <script type="application/ld+json">
  {"@type":"Organization","name":"Кирпич","contactPoint":{"@type":"ContactPoint","email":"jsonld@zavod.ru"}}
  </script>
</head><body>
  <a href="mailto:sales@zavod.ru?subject=Заявка">Написать в отдел продаж</a>
  <span itemprop="email">micro@zavod.ru</span>
  <a href="/cdn-cgi/l/email-protection#3b5a5749555e7b5e435a565b4e52155855">защищено</a>
  <p>Пишите на opt@zavod.ru или zakaz (собака) zavod точка ru</p>
  <div data-email="hidden@zavod.ru">контакт</div>
  <script>var mail = 'script' + '@' + 'zavod.ru';</script>
  <script>window.support = "support@zavod.ru";</script>
</body></html>
"""

# Классические ложные срабатывания, на которых сыпятся наивные парсеры.
PAGE_FALSE_POSITIVES = """
<html><body>
  <img src="logo@2x.png"><img srcset="sprite@3x.svg 3x">
  <p>example@example.com — впишите свой адрес</p>
  <p>Шаблон: name@domain.ru</p>
  <p>Сайт сделан в студии: hello@tilda.cc</p>
  <p>noreply@zavod.ru — не отвечаем на письма сюда</p>
  <span>version@1.2.3</span>
  <span>a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4@tracking.io</span>
  <p>Настоящий адрес: info@zavod.ru</p>
</body></html>
"""


def test_validation() -> None:
    print("Валидация (точность):")
    check("картинка @2x.png отбракована",
          bool(validate_email("logo@2x.png")), True)
    check("шаблонный домен отбракован",
          bool(validate_email("info@example.com")), True)
    check("домен CMS отбракован",
          bool(validate_email("hello@tilda.cc")), True)
    check("хеш-трекер отбракован",
          bool(validate_email("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4@tracking.io")), True)
    check("две собаки отбракованы", bool(validate_email("a@b@c.ru")), True)
    check("двойная точка отбракована", bool(validate_email("a..b@zavod.ru")), True)
    check("версия вместо домена отбракована", bool(validate_email("version@1.2.3")), True)
    check("нормальный адрес проходит", validate_email("info@zavod.ru"), None)
    check("адрес с дефисом проходит", validate_email("opt-sales@za-vod.ru"), None)
    check("адрес с плюсом проходит", validate_email("info+zakaz@zavod.ru"), None)


def test_normalize() -> None:
    print("Нормализация:")
    check("хвостовая точка убрана", normalize_email("info@zavod.ru."), "info@zavod.ru")
    check("регистр приведён", normalize_email("Info@Zavod.RU"), "info@zavod.ru")
    check("скобка убрана", normalize_email("(info@zavod.ru)"), "info@zavod.ru")
    check("url-кодирование снято", normalize_email("info%40zavod.ru"), "info@zavod.ru")
    check("полноширинные символы исправлены", normalize_email("info＠zavod。ru"), "info@zavod.ru")
    check("пробелы вокруг собаки убраны", normalize_email("info @ zavod.ru"), "info@zavod.ru")


def test_decoders() -> None:
    print("Декодирование:")
    # Cloudflare: первый байт — ключ XOR.
    plain = "info@zavod.ru"
    key = 0x2b
    encoded = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in plain)
    check("Cloudflare data-cfemail", decode_cfemail(encoded), plain)
    check("битый hex не ломает", decode_cfemail("zzzz"), None)
    check("собака словом", deobfuscate("zakaz", "zavod точка ru"), "zakaz@zavod.ru")
    check("точка в скобках", deobfuscate("info", "za-vod (dot) ru"), "info@za-vod.ru")


def test_extraction_recall() -> None:
    print("Полнота извлечения:")
    hits, _ = extract_from_html(PAGE_ALL_METHODS, "https://zavod.ru/contacts/")
    found = {h.email for h in hits}
    for email in ("sales@zavod.ru", "jsonld@zavod.ru", "micro@zavod.ru",
                  "opt@zavod.ru", "zakaz@zavod.ru", "hidden@zavod.ru",
                  "script@zavod.ru", "support@zavod.ru"):
        check(f"найден {email}", email in found, True)

    by_email = {h.email: h for h in hits}
    check("mailto распознан как mailto", by_email["sales@zavod.ru"].method, "mailto")
    check("subject отрезан от адреса", "?" in by_email["sales@zavod.ru"].email, False)
    check("JSON-LD распознан", by_email["jsonld@zavod.ru"].method, "jsonld")
    check("микроданные распознаны", by_email["micro@zavod.ru"].method, "microdata")
    check("обфускация распознана", by_email["zakaz@zavod.ru"].method, "obfuscated")
    check("склейка в JS распознана", by_email["script@zavod.ru"].method, "script")
    check("есть причина попадания", bool(by_email["opt@zavod.ru"].evidence), True)


def test_json_fields() -> None:
    """Так сайты отдают контакты филиалов и менеджеров — самые ценные адреса."""
    print("Контакты из JSON внутри скриптов:")
    page = r'''<html><body>
      <script>var nav = {"548":{"label":"Чехов","email":"c@zavod.ru"}};</script>
      <script>var d = "{\"position\":\"Менеджер\",\"email\":\"kvi@zavod.ru\"}";</script>
      <script>var cfg = {"emailAddress": "sales@zavod.ru"};</script>
    </body></html>'''
    hits, _ = extract_from_html(page, "https://zavod.ru/")
    by_email = {h.email: h for h in hits}
    check("филиал из JSON найден", "c@zavod.ru" in by_email, True)
    check("экранированный JSON разобран", "kvi@zavod.ru" in by_email, True)
    check("поле emailAddress найдено", "sales@zavod.ru" in by_email, True)
    check("источник — структурное поле", by_email["c@zavod.ru"].method, "jsonfield")
    check("рядом сохранился контекст", "Чехов" in by_email["c@zavod.ru"].evidence, True)

    hit = by_email["c@zavod.ru"]
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru")
    check("структурное поле подтверждается", hit.confidence, "high")


def test_extraction_precision() -> None:
    print("Точность извлечения:")
    hits, rejected = extract_from_html(PAGE_FALSE_POSITIVES, "https://zavod.ru/")
    found = {h.email for h in hits}
    check("настоящий адрес найден", "info@zavod.ru" in found, True)
    for junk in ("logo@2x.png", "example@example.com", "name@domain.ru",
                 "hello@tilda.cc", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4@tracking.io",
                 "version@1.2.3"):
        check(f"мусор отброшен: {junk}", junk in found, False)
    check("отбраковка объяснена", all(r.reason for r in rejected), True)
    check("технический адрес найден, но помечен позже",
          "noreply@zavod.ru" in found, True)


def test_href_text_mismatch() -> None:
    """Реальный случай с kirpich-ko.ru: показан один адрес, ссылка ведёт на другой."""
    print("Расхождение ссылки и видимого адреса:")
    page = '<html><body><a href="mailto:buh@chuzhaya.ru">buh-baza@mail.ru</a></body></html>'
    hits, _ = extract_from_html(page, "https://zavod.ru/contacts/")
    by_email = {h.email: h for h in hits}
    check("адрес из ссылки найден", "buh@chuzhaya.ru" in by_email, True)
    check("показанный адрес тоже найден", "buh-baza@mail.ru" in by_email, True)
    check("расхождение помечено", by_email["buh@chuzhaya.ru"].text_mismatch, True)
    check("показанный адрес не помечен", by_email["buh-baza@mail.ru"].text_mismatch, False)
    check("расхождение объяснено в причине",
          "расходятся" in by_email["buh@chuzhaya.ru"].evidence, True)

    hit = by_email["buh@chuzhaya.ru"]
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru", on_contact_page=True)
    check("адрес из расходящейся ссылки не подтверждается",
          hit.confidence in ("low", "medium"), True)


def test_scoring() -> None:
    print("Достоверность:")
    hit = EmailHit(email="info@zavod.ru", method="mailto")
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru", on_contact_page=True)
    check("mailto + MX + свой домен = подтверждён", hit.confidence, "high")

    hit = EmailHit(email="info@zavod.ru", method="mailto")
    hit.mx_ok = False
    score_hit(hit, site_root="zavod.ru", on_contact_page=True)
    check("без MX не подтверждаем", hit.confidence in ("low", "medium"), True)

    hit = EmailHit(email="ivan@mail.ru", method="text")
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru", on_contact_page=True)
    check("бесплатная почта не подтверждается автоматом", hit.confidence, "medium")

    hit = EmailHit(email="info@drugaya-firma.ru", method="text")
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru")
    check("чужой домен понижен", hit.confidence, "low")

    hit = EmailHit(email="noreply@zavod.ru", method="mailto")
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru", on_contact_page=True)
    check("технический адрес не подтверждается", hit.confidence, "medium")
    check("технический помечен", hit.is_technical, True)

    hit = EmailHit(email="zakaz@zavod.ru", method="obfuscated")
    hit.mx_ok = True
    score_hit(hit, site_root="zavod.ru", on_contact_page=True)
    check("обфусцированный не подтверждается автоматом", hit.confidence, "medium")
    check("ролевой адрес помечен", hit.is_role, True)


def test_merge() -> None:
    print("Склейка по страницам:")
    hits = [
        EmailHit(email="info@zavod.ru", method="text", source_url="https://zavod.ru/"),
        EmailHit(email="info@zavod.ru", method="mailto", source_url="https://zavod.ru/contacts/"),
    ]
    merged = merge_hits(hits)
    check("адрес один", len(merged), 1)
    check("способ повышен до mailto", merged[0].method, "mailto")
    check("счётчик страниц", merged[0].pages_seen, 2)


def test_contact_urls() -> None:
    print("Поиск страницы контактов:")
    check("по пути", is_contact_url("https://zavod.ru/kontakty/"), True)
    check("по тексту ссылки", is_contact_url("https://zavod.ru/page7", "Контакты"), True)
    check("реквизиты", is_contact_url("https://zavod.ru/rekvizity/"), True)
    check("каталог не контакты", is_contact_url("https://zavod.ru/catalog/kirpich/"), False)


def test_repaired_emails() -> None:
    """Проверяем типографическую опечатку из footer dongradus.ru."""
    print("Восстановление опубликованных адресов:")
    check(
        "запятая перед зоной исправляется",
        repair_email_candidate("zakaz@dongradus,ru"),
        "zakaz@dongradus.ru",
    )
    check(
        "mailto с несколькими адресами не ломает домен",
        split_mailto_addresses("zakaz@dongradus,ru;info@dongradus.ru"),
        ["zakaz@dongradus,ru", "info@dongradus.ru"],
    )
    page = """
      <a href="mailto:zakaz@dongradus,ru">zakaz@dongradus,ru</a>
      <span itemprop="email" content="sales@dongradus,ru"></span>
      <script>window.contact = {"email":"office@dongradus,ru"};</script>
      <a href="mailto:info@dongradus.ru">info@dongradus.ru</a>
    """
    hits, _ = extract_from_html(page, "https://donetsk.dongradus.ru/")
    by_email = {hit.email: hit for hit in hits}
    check("битый mailto восстановлен", "zakaz@dongradus.ru" in by_email, True)
    check("JSON/атрибут восстановлен", "sales@dongradus.ru" in by_email, True)
    check("битый JS email восстановлен", "office@dongradus.ru" in by_email, True)
    check("обычный mailto не помечен восстановленным", by_email["info@dongradus.ru"].method, "mailto")
    check(
        "восстановление видно в доказательстве",
        "исправлено" in by_email["zakaz@dongradus.ru"].evidence,
        True,
    )
    repaired = by_email["zakaz@dongradus.ru"]
    repaired.mx_ok = True
    score_hit(repaired, site_root="dongradus.ru", on_contact_page=True)
    check("восстановленный адрес требует проверки", repaired.confidence, "medium")


def test_web_lookup_reuses_extractor() -> None:
    """Регрессия: web fallback не должен иметь отдельную слабую регулярку."""
    print("Web fallback использует общий extractor:")

    class FakeSerp:
        first_page = 0

        @staticmethod
        def search(_query: str, _page: int):
            return SimpleNamespace(docs=[SimpleNamespace(
                url="https://donetsk.dongradus.ru/contacts/",
                title="Контакты",
                snippet="Почта: zakaz@dongradus,ru",
            )])

    finding = WebLookup(FakeSerp(), pages=1, max_queries=1).find_contacts("donetsk.dongradus.ru")
    check("web fallback восстановил email", [h.email for h in finding.emails], ["zakaz@dongradus.ru"])
    check("web fallback сохранил отметку восстановления", finding.emails[0].method, "web_repaired")


def main() -> int:
    for test in (
        test_validation, test_normalize, test_decoders,
        test_extraction_recall, test_json_fields, test_extraction_precision,
        test_href_text_mismatch, test_scoring, test_merge, test_contact_urls,
        test_repaired_emails, test_web_lookup_reuses_extractor,
    ):
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
